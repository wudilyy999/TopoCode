# vibe-learning

<p align="center">
  <strong>Let agents build. Understand what they build. Learn as you go.</strong><br>
  A local, read-only project understanding and learning companion for Claude Code, Codex, and more.
</p>

vibe-learning turns local coding-agent sessions and file changes into a live project map, a readable change timeline, and optional model-generated explanations. It is an independent observer: it does not run agents or manage their work.

## Why vibe-learning?

Coding agents can change many files before a human has time to reconstruct the story. vibe-learning keeps evidence and explanation together:

- **Project map**: layered architecture, file tree, imports, technologies, entry points, and file roles.
- **Change timeline**: which agent changed which files, in which round, and when.
- **Meaning, not transcript noise**: concise descriptions of what a completed round changed and why it matters.
- **On-demand file guide**: inspect entry points, symbols, responsibilities, and selected local code blocks.
- **Ask about selected text**: select a word or passage and ask without depending on a predefined keyword list.

## Demo

Your coding agent builds the project. vibe-learning helps you understand what it is building—and learn from the changes.

### Architecture and change timeline

See the project structure beside the agent's change narrative. Follow modified file paths from a completed round into the architecture and file guide, keeping implementation details and their broader meaning connected.

![vibe-learning architecture beside the agent change timeline](docs/images/architecture-timeline.png)

### File guide: responsibilities, entry points, and functions

Explore a file's module membership, responsibilities, capabilities, and function definitions. The beginner guide suggests where to start; on-demand Agent analysis adds context, while expandable local code blocks let you inspect the implementation.

![File guide with module role, capabilities, and function explanations](docs/images/file-guide.png)

### Learn in context: interview questions and modification history

Retrieve relevant interview-style questions and expandable answers alongside the file's recorded agent modifications. Connect concepts to the code you are reading, rather than studying an unrelated list of terms.

![Contextual interview questions and historical agent modifications](docs/images/knowledge-history.png)

These are development screenshots supplied from a real vibe-learning session. Historical model text, counts, and timings illustrate that session, not current release guarantees. Questions shown as “大厂真题” in the interface should be treated as curated practice unless an original source is supplied. The displayed local model label is an example configuration, not a required provider.

## From changes to understanding

### Explore a connected architecture

A compact, layered blueprint places entry modules above, the core in the center, collaborators alongside it, and infrastructure below. Arrows distinguish code imports from model-inferred dependencies. Open a module to inspect responsibilities and files, or switch to the expandable file tree and follow imports in both directions. Full regeneration and incremental revision keep the map connected to project evolution; coverage information makes input limits visible.

### Know where to start

The beginner guide highlights entry-point candidates and suggests a reading order. File details connect responsibilities, symbols, and local function code blocks with historical modifications, recorded motivations, and technical impact. Explore how a file works and how it evolved in the same view.

### Learn through interview questions

The built-in knowledge base brings together technical concepts, English aliases, interview-style questions, and expandable answer explanations. Lightweight retrieval matches relevant knowledge and questions to the file you are exploring, covering frontend, backend, fundamentals, agent development, and algorithms. Curated practice questions are distinguished from attributed interview questions, with reference links for further reading.

### Select, ask, and reuse

Select a word or passage in explanation text, up to 2,000 characters. A compact question button appears beside the selection; the full panel opens only after a click. Code blocks and input controls retain their normal interaction.

- **Context-aware answers** separate general meaning from the concept's role in this project.
- **Local answers first**: exact matches reuse saved answers; similar selections can suggest previous general explanations, showing the original selection for comparison.
- **Cross-project reuse** shares general knowledge while keeping project-specific interpretations separate.
- **Independent question branches** copy the original analysis context without changing its parent. Compatible providers may reuse that prompt prefix; usage statistics are the evidence of a cache hit.
- **Ask again** to generate a fresh explanation when a saved answer is unsuitable.

### Observe without waiting for analysis

Monitoring, dialogue analysis, and architecture revision use separate bounded workers. Initial observation selects the project's latest five completed rounds. Subsequent new rounds remain eligible continuously, including delayed completion updates. Choose a positive number of recent rounds and use “Add to analysis” to include more captured history; saved eligibility survives restarts and queue saturation. Evidence/model fingerprints prevent duplicate work. Session memory compresses older context within a token budget. The interface supports Chinese and English.

## Quick start

Requirements: Python 3.9+ and a local project directory. No third-party Python packages are required.

```bash
git clone https://github.com/wudilyy999/vibe-learning.git
cd vibe-learning
python3 server.py --project /path/to/your/project --port 8765
```

Open <http://127.0.0.1:8765>. Use the sniffing center to select additional directories when an agent's working directory is a broad parent folder.

## How it works

```text
Claude Code / Codex session logs
              |
              v
     read-only tailing and round parsing
              |
              v
 project-bound file evidence + idempotent events
              |
       +------+------+
       |             |
       v             v
 live map/timeline   optional model analysis
       |             |
       +------+------+
              v
       architecture and knowledge views
```

File evidence is collected first. Analysis runs asynchronously, so a slow or unavailable model does not stop monitoring. The UI shows evidence immediately and updates the same event when analysis finishes.

## Supported agents

| Agent | Session logs | File evidence | Notes |
|---|---:|---:|---|
| Claude Code | Yes | Yes | JSONL polling; optional observe-only hook |
| Codex | Yes | Yes | Desktop and CLI rollout formats are normalized |
| Kimi Code | Adapter | Adapter | Depends on the local session source |
| Qoder, Cursor, Qwen, Copilot, Pi, WorkBuddy, Grok, Augment, DeepSeek Harness | Extension stubs | Planned per adapter | Common adapter interface is available |

## Privacy and safety

- Binds only to `127.0.0.1`; it is not a network service.
- Never writes to the observed project or agent home directories.
- Stores its own state under `~/.vibe-learning/` or `VIBE_LEARNING_DATA`.
- Sends only redacted summaries and file metadata to an optional model. Source text and diffs are not sent.
- Redacts credential-like assignments such as `key`, `token`, `secret`, `password`, `Authorization`, and `Bearer`.
- Local file-code inspection is on demand, bounded, and redacted; it is not part of events or model input.

Review the privacy boundary before enabling an external OpenAI-compatible endpoint.

## Optional model analysis

Without a model, events remain `evidence_only`. To enable explanations, configure an independent OpenAI-compatible provider in the web UI or configuration API with a base URL, API key, and model name. The model can provide:

- a short change summary;
- technical meaning;
- knowledge points;
- relationships between files and concepts.

Invalid or failed model responses degrade to evidence-only data. Model analysis is clearly distinguished from deterministic evidence.

## Repository layout

- `server.py`: standard-library HTTP server, REST API, SSE, and worker queues.
- `snapshot/`: bounded snapshots, language detection, redaction, symbols, file guides, and file selection.
- `platforms/`: agent adapters, including Claude Code and Codex.
- `session_tail/`: polling, round parsing, project attribution, and event creation.
- `agent/`: prompts, analysis, session memory, and token-budget compression.
- `knowledge/`: architecture persistence, terminology, interview questions, retrieval, and selected-text explanations.
- `graph/`: deterministic project graph and file navigation.
- `web/index.html`: single-page map, timeline, file tree, and knowledge views.
- `hooks/claude-hook.mjs`: optional Claude Code observe-only hook.
- `docs/ARCHITECTURE.md`: authoritative architecture and data contracts.

## Data and boundaries

vibe-learning does not implement goals, todos, quotas, scheduling, agent execution, or lifecycle management. It is a pure observer.

Local state includes configuration, event streams, architecture records, offsets, user memory, and selected-text explanation caches. Event storage uses append/upsert semantics for concurrent workers. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the complete contract.

## Current limitations

- Agent log formats vary by client version; Claude Code and Codex are the primary validated adapters.
- A session `cwd` is only a starting location. File evidence locates the most specific tracked project, which matters when an agent works in a child directory from a broad parent workspace.
- Architecture layout is deterministic; model output supplies structured content and relationships.
- An external model is optional and requires a compatible endpoint.

## Roadmap

**Direction: a dedicated agent for continuous project understanding and learning—not another general-purpose agent orchestrator.** The foundations exist today; the items below are planned work, not shipped capabilities or delivery commitments.

### 1. Continuous, evidence-backed project understanding

**Today:** architecture synthesis, incremental revisions, dependency views, file guides, and change history.

- [ ] Give modules stable IDs independent of their display names.
- [ ] Attach file/import/event evidence to architecture claims; distinguish observed facts, model inferences, and items awaiting verification.
- [ ] Explain how each meaningful change updates the project's responsibilities, module boundaries, and relationships.
- [ ] Compare candidate architecture versions before accepting major reorganizations; check core-file coverage and preserve prior versions for rollback.

### 2. Learning through the project you are building

**Today:** beginner guides, selected-text questions, general/project-specific explanations, reusable local answers, and a contextual knowledge and interview-question bank.

- [ ] Build reading routes around real behaviors: entry point → request handling → processing → visible result, with navigable function references.
- [ ] Turn actual implementations and changes into project-specific exercises, separating code-backed answers from open-ended design questions.
- [ ] Collect lightweight learning feedback: understood, explain more simply, show an example, or check understanding with a question.
- [ ] Use explicit feedback to adapt explanations; distinguish material viewed, self-reported understanding, and practice results.

### 3. Future: change-evidence review

**Today:** user requests, agent responses, and captured file changes provide the underlying records. Automated claim-to-evidence review is planned.

- [ ] Connect user goals and agent completion claims to observed implementation changes and validation records.
- [ ] Show supported claims and evidence gaps, using “verification not observed” rather than treating missing records as proof of failure.
- [ ] Investigate missing evidence within the read-only boundary and link findings back to the project map and timeline.

The intended progression is stable identity and evidence → architecture evolution → guided learning and practice → change-evidence review. Throughout, vibe-learning remains an independent, local observer: it does not execute coding agents or take over their task lifecycle.

## Development

```bash
python3 -c "import server"
python3 -m py_compile server.py platforms/*.py snapshot/*.py session_tail/*.py
```

Keep changes aligned with `AGENTS.md` and `docs/ARCHITECTURE.md`. The project intentionally uses Python's standard library and a single HTML frontend.

## License

Add the repository license before publishing.
