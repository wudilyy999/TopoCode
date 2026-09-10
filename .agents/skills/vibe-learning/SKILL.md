---
name: vibe-learning
description: vibe-learning 仓库的框架设计规范速查与架构处理守则。当在 vibe-learning 仓库内开发、修改架构、新增平台适配器/知识词条/分析能力，或需要理解事件流、图谱构建、memory 压缩机制时使用。确保换了 AI 也能正确处理架构信息。
---

在 vibe-learning 仓库工作时，先读 `docs/ARCHITECTURE.md`（权威规范）与仓库根 `AGENTS.md`。本 skill 是防跑偏速查层。

## 一句话架构

只读监听本机 Coding Agent 会话 JSONL（轮询 tailer + Claude hook）→ 按轮次切分生成 change event → 按 cwd 归因到登记项目目录 → 文件锁持久化（upsert 幂等）→ 可选模型分析（dialogue.v2）→ SSE/轮询推给单页前端渲染图谱与时间线。

## 处理架构信息时的铁律

1. **纯观察者**：不写被观察项目、不写 agent 家目录、状态只落 `~/.vibe-learning/`、只绑 127.0.0.1。
2. **零重依赖**：后端只用 Python 标准库；前端只有 `web/index.html`。禁止引入框架。
3. **脱敏出域**：模型只拿到脱敏摘要+文件元数据；绝不输出源码正文、diff、凭据。
4. **优雅降级**：模型未配置或调用失败 → `analysis_status = evidence_only`，照常展示，绝不抛异常穿透。
5. **物理证据优先**：`event.files` 非空 ⇒ `involves_change=True`，模型说"没改"也要用文件清单覆盖。
6. **轮次幂等**：event_id 由逻辑轮次 `(agent_id, session_id, turn_id)` 派生；轮次早期抓取的不完整事件，必须被后续更完整的抓取经 `store.event_needs_update` 原地 upsert，不得因"id 已存在"丢弃真实改动。

## 各改动的正确落点

| 你要做什么 | 落点 |
|---|---|
| 新分析能力/提示词 | `agent/prompts.py`（带 schema_version）→ `agent/analyzer.py`（校验）→ `model_client/client.py`（门面）→ `server.py`（路由） |
| 新知识词条/题库 | 对应领域 `knowledge/bank_ext_<domain>.py`，聚合在 `knowledge/bank_ext.py`，禁止直接改 `bank.py` 主体列表 |
| 新 agent 平台 | 实现 `platforms/base.py` 接口 + 在 `session_tail/tailer.py` 注册；伪路径过滤放适配器层 |
| 历史上下文拼接 | 必须走 `SessionMemory.build_context_summary(token_budget=...)`（自动阶梯压缩，见 `agent/memory.py`） |
| 前端交互/文案 | `web/index.html`；中英双语文案都加进 `I18N` 字典 |

## 关键存储（~/.vibe-learning/）

`config.json`（项目/模型/忽略名单）、`events-<slug>.jsonl`（事件流）、
`knowledge/arch-<slug>.json`（架构知识 architecture.v2）、`memory/user-<slug>.json`（用户画像，UI 不展示）、`offsets.json`（轮询偏移）。

## 验证

改完必须：`python3 -c "import server"` 通过；涉及词库改动跑 `knowledge/bank.py` 的导入断言；涉及前端的改动在浏览器实际打开 `http://127.0.0.1:8765` 确认。
