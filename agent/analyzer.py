"""Project Analysis Agent implementation.
Executes semantic analysis over agent interactions, code changes, and architectural abstractions.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from agent.memory import SessionMemory, UserMemory
from agent.prompts import (
    ARCH_SCHEMA_VERSION,
    ARCH_UPDATE_SCHEMA_VERSION,
    DIALOGUE_SCHEMA_VERSION,
    FILE_ANALYSIS_SCHEMA_VERSION,
    build_architecture_prompt,
    build_architecture_update_prompt,
    build_dialogue_agent_prompt,
    build_file_deep_analysis_prompt,
    build_knowledge_qa_prompt,
)

# Standard agent client headers to prevent upstream proxy/WAF blocks (e.g. 502 on Python-urllib)
DEFAULT_HEADERS = {
    "User-Agent": "vibe-learning/1.0 (Macintosh; Apple Silicon)",
    "Accept": "application/json, */*",
    "Content-Type": "application/json",
}


def _clean_json_markdown(raw_text: str) -> str:
    """Strip markdown code block fences if the LLM wrapped JSON in ```json ... ```."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class ProjectAnalysisAgent:
    """Autonomous agent that analyzes developer-agent conversations and repository changes."""

    def __init__(self, model_cfg: Optional[Dict[str, Any]] = None):
        self.model_cfg = model_cfg or {}
        self.branch_messages = []
        # Ensure loopback isn't intercepted by system proxies like Clash on 7890
        os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

    def is_configured(self) -> bool:
        return bool(self.model_cfg and self.model_cfg.get("base_url") and self.model_cfg.get("model"))

    def _build_request(self, endpoint: str, body: Dict[str, Any], timeout: int = 30) -> Tuple[urllib.request.Request, int]:
        base_url = (self.model_cfg.get("base_url") or "").rstrip("/")
        if not base_url.endswith("/v1") and not "/chat/completions" in base_url:
            # Tolerant appending
            url = base_url + "/chat/completions"
        elif base_url.endswith("/v1"):
            url = base_url + "/chat/completions"
        else:
            url = base_url

        from snapshot.redact import redact
        body['messages'] = [{**message, 'content': redact(message['content'])} for message in body['messages']]
        data = json.dumps(body).encode("utf-8")
        headers = dict(DEFAULT_HEADERS)
        import hashlib
        headers['x-opencode-session'] = 'vibe-learning-' + hashlib.blake2b(
            json.dumps(body['messages'][:1], ensure_ascii=False, sort_keys=True).encode(),
            digest_size=20,
        ).hexdigest()
        api_key = self.model_cfg.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, data=data, headers=headers)
        return req, timeout

    def diagnose_connection(self) -> Dict[str, Any]:
        """Test model connectivity with rich diagnostics."""
        if not self.is_configured():
            return {"ok": False, "error": "模型未配置 (需要 base_url 和 model 名称)"}

        start_t = time.time()
        test_payload = {
            "model": self.model_cfg.get("model"),
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10,
        }
        try:
            req, timeout = self._build_request("/chat/completions", test_payload, timeout=10)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                latency_ms = int((time.time() - start_t) * 1000)
                reply = ""
                if "choices" in data and data["choices"]:
                    reply = data["choices"][0]["message"].get("content", "")
                return {
                    "ok": True,
                    "latency_ms": latency_ms,
                    "model": self.model_cfg.get("model"),
                    "sample_reply": reply[:100],
                    "message": f"连接成功！延迟 {latency_ms}ms"
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message") or str(err_json)
            except Exception:
                msg = err_body[:200]
            if e.code == 401:
                detail = "API Key 认证失败 (401 Unauthorized)"
            elif e.code == 404:
                detail = f"接口地址未找到 (404 Not Found): {req.full_url}"
            elif e.code == 502:
                detail = f"上游网关错误 (502 Bad Gateway): {msg or '上游代理拒绝或访问受限'}"
            else:
                detail = f"HTTP {e.code}: {msg or e.reason}"
            return {"ok": False, "status_code": e.code, "error": detail}
        except Exception as e:
            return {"ok": False, "error": f"网络连接失败: {type(e).__name__} - {str(e)[:200]}"}

    def analyze_dialogue_turn(
        self,
        event: Dict[str, Any],
        history_events: List[Dict[str, Any]],
        project_root: str = "",
        lang: str = "zh"
    ) -> bool:
        """Explain change meaning using bounded history."""
        if not self.is_configured():
            event["analysis_status"] = "evidence_only"
            return False

        memory = SessionMemory(session_id=event.get("session_id", ""), project=project_root)
        memory.update_from_history(history_events)
        if project_root:
            profile = UserMemory(project_root)
            if profile.user_level in ("novice", "practitioner", "expert"):
                memory.inferred_user_level = profile.user_level

        # Summarize files
        file_lines = []
        valid_paths = set()
        for f in event.get("files", []):
            p = f.get("path")
            if p:
                valid_paths.add(p)
                langs = ",".join(f.get("languages", [])) or "Other"
                file_lines.append(f"{p} ({langs}, +{f.get('additions', 0)}/-{f.get('deletions', 0)})")
        changed_files_summary = "\n".join(file_lines)

        history_context = memory.build_context_summary(max_turns=8, token_budget=2400)
        req_text = (event.get("request_text") or "").strip()
        res_text = (event.get("result_text") or "").strip()

        prompt = build_dialogue_agent_prompt(
            current_request=req_text,
            current_result=res_text,
            changed_files_summary=changed_files_summary,
            history_context=history_context,
            inferred_user_level=memory.inferred_user_level,
            lang=lang
        )

        body = {
            "model": self.model_cfg.get("model"),
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            req, timeout = self._build_request("/chat/completions", body, timeout=30)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                raw_resp = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw_resp)
                content = data["choices"][0]["message"]["content"]
                self.branch_messages = body['messages'] + [{'role': 'assistant', 'content': content}]
                clean_json = _clean_json_markdown(content)
                parsed = json.loads(clean_json)

            validated = self._validate_dialogue_result(parsed, valid_paths)
            if not validated:
                event["analysis_status"] = "evidence_only"
                event["dialogue_error"] = "Agent response failed schema validation"
                return False

            event["dialogue"] = validated
            event["analysis_status"] = "analysis_done"
            # Update memory
            memory.add_turn(event, update_profile=True)
            if project_root:
                UserMemory(project_root).record(event)
            return True

        except Exception as exc:
            event["analysis_status"] = "evidence_only"
            event["dialogue_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            return False

    def _validate_dialogue_result(self, data: Any, valid_paths: set) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        ver = data.get("schema_version")
        if ver not in (DIALOGUE_SCHEMA_VERSION, "dialogue.v3", "dialogue.v2", "dialogue.v1"):
            return None
        meaning = data.get("technical_meaning") or data.get("summary")
        if not isinstance(meaning, str) or not meaning.strip():
            return None
        if ver == DIALOGUE_SCHEMA_VERSION and not isinstance(data.get("technical_meaning"), str):
            return None

        change_summary = data.get("change_summary", "")
        if not isinstance(change_summary, str):
            return None

        act = data.get("dialogue_act")
        if act not in ("implement", "fix", "explain", "explore", "configure", "review", "chatter", "other"):
            act = "other"

        return {
            "schema_version": DIALOGUE_SCHEMA_VERSION,
            "dialogue_act": act,
            "involves_change": bool(valid_paths),
            "change_summary": change_summary.strip()[:400],
            "technical_meaning": meaning.strip()[:600],
        }

    def abstract_architecture(
        self,
        project_root: str,
        ranked_files: List[str],
        dir_summary: str,
        readme_text: str = "",
        repo_line: str = "",
        total_files: int = 0,
        lang: str = "zh"
    ) -> Optional[Dict[str, Any]]:
        """Full architecture synthesis: overview + onboarding + layered components."""
        if not self.is_configured():
            return None

        valid_paths = set(ranked_files)
        tree_text = "\n".join(ranked_files)
        prompt = build_architecture_prompt(tree_text, dir_summary,
                                           readme_text[:4000], repo_line, total_files, lang=lang)

        body = {
            "model": self.model_cfg.get("model"),
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            req, timeout = self._build_request("/chat/completions", body, timeout=60)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                raw_resp = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw_resp)
                content = data["choices"][0]["message"]["content"]
                self.branch_messages = body['messages'] + [{'role': 'assistant', 'content': content}]
                clean_json = _clean_json_markdown(content)
                parsed = json.loads(clean_json)

            if not isinstance(parsed, dict) or parsed.get("schema_version") != ARCH_SCHEMA_VERSION:
                return None

            overview_raw = parsed.get("overview") or {}
            overview = {
                "one_liner": str(overview_raw.get("one_liner", "")).strip()[:80],
                "purpose": str(overview_raw.get("purpose", "")).strip()[:180],
                "architecture_style": str(overview_raw.get("architecture_style", "")).strip()[:60],
            }
            onboarding = [str(s).strip()[:70] for s in (parsed.get("onboarding") or [])
                          if str(s).strip()][:5]

            layer_titles = {
                "presentation": "Presentation Layer" if lang == "en" else "应用与接入层",
                "agent": "Agent & Core Logic Layer" if lang == "en" else "智能体与核心逻辑层",
                "pipeline": "Pipeline & Stream Layer" if lang == "en" else "会话感知与流处理层",
                "infrastructure": "Infrastructure & Snapshot Layer" if lang == "en" else "基础快照与数据层",
            }
            components = []
            for comp in parsed.get("components", []) or []:
                if not isinstance(comp, dict):
                    continue
                name = str(comp.get("name", "")).strip()[:40]
                c_files = [f for f in (comp.get("files", []) or []) if f in valid_paths]
                if not name or not c_files:
                    continue
                layer = str(comp.get("layer", "")).strip()
                if layer not in layer_titles:
                    first_file = c_files[0].lower()
                    if "web" in first_file or "server" in first_file or "hook" in first_file:
                        layer = "presentation"
                    elif "agent" in first_file or "prompt" in first_file or "graph" in first_file:
                        layer = "agent"
                    elif "platform" in first_file or "tailer" in first_file or "session" in first_file:
                        layer = "pipeline"
                    else:
                        layer = "infrastructure"
                dirs = [d for d in (comp.get("dirs") or [])
                        if isinstance(d, str) and d and d != "/" and d.endswith("/")][:6]
                role_pairs = []
                for fr in (comp.get("file_roles") or []):
                    if not isinstance(fr, dict) or len(role_pairs) >= 20:
                        continue
                    fr_path = str(fr.get("path", "")).strip()
                    fr_role = str(fr.get("role", "")).strip()[:40]
                    if fr_path in valid_paths and fr_role:
                        role_pairs.append((fr_path, fr_role))
                components.append({
                    "name": name,
                    "layer": layer,
                    "layer_title": str(comp.get("layer_title", "")).strip()[:30] or layer_titles[layer],
                    "summary": str(comp.get("summary", "")).strip()[:100],
                    "responsibilities": [str(r).strip()[:40] for r in (comp.get("responsibilities") or [])
                                         if str(r).strip()][:4],
                    "key_features": [str(f).strip()[:40] for f in (comp.get("key_features") or [])
                                     if str(f).strip()][:6],
                    "entry_files": [f for f in (comp.get("entry_files") or []) if f in valid_paths][:5],
                    "dirs": dirs,
                    "files": c_files[:30],
                    "file_roles": dict(role_pairs),
                    "depends_on": [d for d in (str(x).strip()[:40] for x in (comp.get("depends_on") or [])) if d][:6],
                    "revision": 0,
                })
                if len(components) >= 10:
                    break

            if not components:
                return None

            return {
                "schema_version": ARCH_SCHEMA_VERSION,
                "status": "analysis",
                "overview": overview,
                "onboarding": onboarding,
                "components": components,
            }
        except Exception:
            return None

    def update_architecture(
        self,
        comp_summary: str,
        changed_files: str,
        analysis_text: str,
        lang: str = "zh"
    ) -> Optional[Dict[str, Any]]:
        """Incremental revision patch over the stored architecture knowledge."""
        if not self.is_configured():
            return None
        prompt = build_architecture_update_prompt(comp_summary, changed_files, analysis_text, lang=lang)
        body = {
            "model": self.model_cfg.get("model"),
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            req, timeout = self._build_request("/chat/completions", body, timeout=60)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                raw_resp = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw_resp)
                content = data["choices"][0]["message"]["content"]
                self.branch_messages = body['messages'] + [{'role': 'assistant', 'content': content}]
                clean_json = _clean_json_markdown(content)
                parsed = json.loads(clean_json)

            if not isinstance(parsed, dict) or parsed.get("schema_version") != ARCH_UPDATE_SCHEMA_VERSION:
                return None
            return parsed
        except Exception:
            return None

    def answer_knowledge_question(
        self,
        entry: Dict[str, Any],
        related_entries: List[Dict[str, Any]],
        question: str,
        lang: str = "zh"
    ) -> Optional[str]:
        """Grounded free-form Q&A over one knowledge entry; returns plain text."""
        if not self.is_configured():
            return None
        prompt = build_knowledge_qa_prompt(entry, related_entries, question, lang=lang)
        body = {
            "model": self.model_cfg.get("model"),
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            req, timeout = self._build_request("/chat/completions", body, timeout=45)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                raw_resp = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw_resp)
                content = data["choices"][0]["message"]["content"]
                self.branch_messages = body['messages'] + [{'role': 'assistant', 'content': content}]
            return content.strip() or None
        except Exception:
            return None

    def deep_analyze_file(
        self,
        file_meta: str,
        symbols_text: str,
        imports_text: str,
        history_text: str,
        code_preview: str,
        lang: str = "zh"
    ) -> Optional[Dict[str, Any]]:
        """On-demand thorough explanation of one source file."""
        if not self.is_configured():
            return None
        prompt = build_file_deep_analysis_prompt(file_meta, symbols_text,
                                                 imports_text, history_text, code_preview, lang=lang)
        body = {
            "model": self.model_cfg.get("model"),
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            req, timeout = self._build_request("/chat/completions", body, timeout=60)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                raw_resp = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw_resp)
                content = data["choices"][0]["message"]["content"]
                self.branch_messages = body['messages'] + [{'role': 'assistant', 'content': content}]
                clean_json = _clean_json_markdown(content)
                parsed = json.loads(clean_json)

            if not isinstance(parsed, dict) or parsed.get("schema_version") != FILE_ANALYSIS_SCHEMA_VERSION:
                return None
            return {
                "schema_version": FILE_ANALYSIS_SCHEMA_VERSION,
                "purpose": str(parsed.get("purpose", "")).strip()[:150],
                "responsibilities": [str(r).strip()[:40] for r in (parsed.get("responsibilities") or [])
                                     if str(r).strip()][:4],
                "key_mechanisms": [{"name": str(m.get("name", "")).strip()[:40],
                                    "explain": str(m.get("explain", "")).strip()[:80]}
                                   for m in (parsed.get("key_mechanisms") or [])
                                   if isinstance(m, dict) and str(m.get("name", "")).strip()][:12],
                'reading_steps': [{'symbol': str(s.get('symbol', ''))[:120], 'explain': str(s.get('explain', ''))[:300]}
                                  for s in (parsed.get('reading_steps') or []) if isinstance(s, dict)][:12],
                "collaboration": str(parsed.get("collaboration", "")).strip()[:150],
                "change_impact": str(parsed.get("change_impact", "")).strip()[:120],
            }
        except Exception:
            return None
