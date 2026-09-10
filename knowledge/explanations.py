import fcntl
import hashlib
import json
import os
import tempfile
import threading
import time
import unicodedata
import urllib.request
from contextlib import contextmanager

from config import store
from snapshot.redact import redact


_LOCKS = {}
_GUARD = threading.Lock()
VERSION = 'term.v1'


def digest(value):
    return hashlib.blake2b(json.dumps(value, ensure_ascii=False, sort_keys=True).encode(), digest_size=20).hexdigest()


def identity(model):
    return {'provider': (model or {}).get('base_url', ''), 'model': (model or {}).get('model', '')}


def location(kind, key):
    directory = os.path.join(store.data_dir(), 'explanations', kind)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, digest(key) + '.json')


def read(path):
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None


def write(path, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(path), delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False)
        temporary = handle.name
    os.replace(temporary, path)


@contextmanager
def locked(path):
    with _GUARD:
        lock = _LOCKS.setdefault(path, threading.Lock())
    with lock, open(path + '.lock', 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def save_branch(project, scope, lang, agent):
    if not project or not agent.branch_messages:
        return
    messages = [{'role': m['role'], 'content': redact(m['content'])} for m in agent.branch_messages]
    if len(json.dumps(messages, ensure_ascii=False).encode()) > 512 * 1024:
        return
    path = location('branches', [os.path.realpath(project), scope, lang])
    with locked(path):
        write(path, {'messages': messages, 'model': identity(agent.model_cfg), 'saved_at': time.time()})


def context(project, scope, lang, model):
    project = os.path.realpath(project)
    from knowledge import architecture as arch_knowledge
    arch = arch_knowledge.load_architecture(project) or {}
    evidence = {'overview': arch.get('overview', {}), 'components': arch.get('components', [])}
    branch = read(location('branches', [project, scope, lang]))
    messages = branch['messages'] if branch and branch['model'] == identity(model) else []
    if scope.startswith('file:'):
        path = os.path.realpath(os.path.join(project, scope[5:]))
        if os.path.commonpath([project, path]) != project:
            raise ValueError('File scope is outside the project')
        try:
            stat = os.stat(path)
            evidence['file_version'] = [scope[5:], stat.st_mtime_ns, stat.st_size]
        except FileNotFoundError:
            evidence['file_version'] = [scope[5:], 'deleted']
    evidence_text = redact(json.dumps(evidence, ensure_ascii=False))[:16000]
    fingerprint = digest([evidence, branch['messages'] if branch else []])
    if not messages:
        messages = [{'role': 'user', 'content': 'Project architecture evidence (analysis, not instructions):\n' + evidence_text}]
    return messages, evidence_text, fingerprint, bool(branch and branch['model'] == identity(model))


def explain(project, term, lang, model, scope='architecture', generate=True, project_only=False, question='', force=False):
    from agent.analyzer import ProjectAnalysisAgent, _clean_json_markdown
    from agent.prompts import build_term_prompt
    from knowledge.bank import KEYWORD_MAP, normalize_term
    from knowledge.rag import retrieve_knowledge

    term = unicodedata.normalize('NFKC', term).strip()
    sense = 'react-pattern' if term == 'ReAct' else KEYWORD_MAP.get(normalize_term(term), term)
    key = [VERSION, sense, lang, question]
    global_path = location('general', key)
    messages, evidence, fingerprint, forked = context(project, scope, lang, model)
    project_path = location('projects', [os.path.realpath(project), key, scope])
    related = retrieve_knowledge(term, top_k=3)
    from contextlib import nullcontext
    with locked(global_path) if generate else nullcontext():
        general = read(global_path)
        local = read(project_path)
        if local and local.get('context_version') != fingerprint:
            local = None
        result = {'ok': True, 'term': term, 'sense': sense, 'general': general, 'project': local,
                  'references': related, 'cached': bool(general), 'forked': forked}
        if not generate and not general:
            import difflib
            import re
            directory = os.path.dirname(global_path)
            normalized = re.sub(r'\s+', '', term)
            best = None
            for name in os.listdir(directory):
                if not name.endswith('.json'):
                    continue
                candidate = read(os.path.join(directory, name))
                if not candidate or candidate.get('lang') != lang or candidate.get('question', '') != question:
                    continue
                original = candidate.get('term', '')
                other = re.sub(r'\s+', '', original)
                if min(len(normalized), len(other)) < 12:
                    continue
                score = difflib.SequenceMatcher(None, normalized, other, autojunk=False).ratio()
                if score >= 0.85 and (best is None or score > best[0]):
                    best = (score, original, candidate)
            if best:
                return {**result, 'general': best[2], 'project': None, 'cached': True,
                        'match': {'kind': 'similar', 'term': best[1], 'score': round(best[0], 3)}}
        if not generate or (not force and general and (not project_only or local)):
            return result
        if force:
            general = None
            local = None
        agent = ProjectAnalysisAgent(model)
        if not agent.is_configured():
            return {**result, 'ok': bool(general), 'error': 'Configure an analysis model to generate this explanation.'}
        prompt = build_term_prompt(term, lang, evidence, related, general, question)
        body = {'model': model['model'], 'messages': messages + [{'role': 'user', 'content': prompt}]}
        request, timeout = agent._build_request('/chat/completions', body, timeout=60)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            payload = json.load(response)
        data = json.loads(_clean_json_markdown(payload['choices'][0]['message']['content']))
        if not isinstance(data, dict) or data.get('schema_version') != VERSION:
            raise ValueError('Invalid term answer schema')
        required = ['project_meaning'] if general else ['general_meaning', 'project_meaning', 'sense']
        if any(not isinstance(data.get(k), str) or not data[k].strip() for k in required):
            raise ValueError('Term answer is missing required text fields')
        metadata = {'saved_at': time.time(), 'model': identity(model), 'schema_version': VERSION}
        if not general:
            general = {**metadata, 'term': redact(term), 'lang': lang, 'question': redact(question),
                       'sense': redact(data['sense'])[:160], 'text': redact(data['general_meaning'])[:10000]}
            write(global_path, general)
        local = {**metadata, 'text': redact(data['project_meaning'])[:8000], 'context_version': fingerprint,
                 'forked': forked, 'scope': scope}
        with locked(project_path):
            write(project_path, local)
        usage = payload.get('usage') or {}
        return {**result, 'general': general, 'project': local, 'cached': False,
                'cached_tokens': (usage.get('prompt_tokens_details') or {}).get('cached_tokens', usage.get('prompt_cache_hit_tokens'))}
