# vibe-learning 框架设计规范

> 本文档是 vibe-learning 的权威架构规范。任何 AI 或开发者在本仓库改动代码前必须先读本文件。
> 与代码冲突时以代码为准，但改动使本文档过时的一方必须同步更新本文档。

## 1. 定位与硬边界

vibe-learning 是**独立外挂式 Agent 项目实时分析系统**：只读监听本机各 Coding Agent
（Claude Code / Codex / Kimi Code 等）在被观察项目目录里的会话与文件改动，
实时生成项目图谱、会话时间线与知识解构。

硬性边界（不可违反）：

1. **只读观察**：永不写被观察项目目录，永不写任何 agent 家目录；自身状态只落在 `~/.vibe-learning/`。
2. **本地回环**：HTTP 服务只绑 `127.0.0.1`，不鉴权，不暴露局域网。
3. **脱敏出域**：送给分析模型的只有脱敏摘要与文件元数据（路径/行数/语言），
   绝不输出源码正文与 diff；key/token/secret/password/Authorization/Bearer 赋值一律替换为 `[credential omitted]`。
4. **零重依赖**：后端只用 Python 标准库（ThreadingHTTPServer），前端是单页 `web/index.html`，不引入框架。
5. **不做编排**：不做 goal/todo/调度/quota/执行 agent/管理 agent 生命周期。这是纯观察者。
6. **发布隔离**：默认模型列表为空，首次运行使用evidence_only；凭据保存在用户数据目录。会话JSONL、日志、运行缓存与本地配置不进入发布仓库。

## 2. 模块地图

| 模块 | 职责 |
|---|---|
| `server.py` | HTTP 入口：REST API、SSE 推送、Claude Hook 接收；监听、会话分析、架构修订分别由独立后台 worker 承担 |
| `snapshot/` | 项目快照与 diff：`scanner.py`(git ls-files 优先/目录遍历降级，512KB·64MB·8000 文件上限)、`languages.py`(后缀→语言/技术栈)、`redact.py`(密钥脱敏)、`ast_inspect.py`/`symbols.py`(符号提取)、`file_analysis.py`(单文件确定性解析) |
| `platforms/` | 各 agent 平台适配器：`base.py` 定义统一接口，`claude.py`/`codex.py`/`kimi.py` 已实现，`stubs.py` 占位其余平台 |
| `session_tail/tailer.py` | 会话轮询 tailer：读会话 JSONL → 按轮次(round)切分 → 生成 change event → 归因到登记目录 |
| `agent/` | 分析智能体：`analyzer.py`(ProjectAnalysisAgent)、`prompts.py`(全部结构化提示词)、`memory.py`(会话记忆+用户画像记忆，含 token 预算自动压缩) |
| `knowledge/` | 知识体系：`bank.py`(核心词库)、`bank_ext_*.py`(领域扩展包)、`rag.py`(BM25+n-gram 轻量检索)、`architecture.py`(架构知识持久化) |
| `model_client/client.py` | 模型调用门面：仅在配置 OpenAI-compatible 模型时生效，失败一律降级 evidence_only |
| `graph/` | `builder.py`(确定性图谱构建：repository/agent/session/turn/file/technology/knowledge 节点)、`rank.py`(文件重要性排序) |
| `config/store.py` | 全部持久化：配置、事件(带文件锁追加+upsert)、架构知识、用户记忆、轮询偏移 |
| `discovery/` | 嗅探引擎：仅返回配置discovery_scope内的会话项目候选；前台通过/api/folders浏览目录，也可粘贴绝对路径。未配置时限已追踪目录。扫描共享agent日志时cwd仅是启动位置；成功改动文件优先定位边界内最近项目标记目录，父目录会话中的子项目独立候选。候选带modified_file/cwd_only依据和文件样例；同轮多个具体项目不自动混归。项目根探测不越选定边界。POST /api/projects/discovery-scope保存范围并使缓存失效，已有追踪保持不变。 |
| `hooks/claude-hook.mjs` | Claude Code observe-only hook，2s 超时自杀，失败永不阻塞 agent |
| `web/index.html` | 单页前端：分层架构蓝图/文件树与双向依赖、新手文件导读、会话时间线、技术词典弹窗(嵌套跳转+问 Agent)、中英双语 |

## 3. 数据流

```
agent 会话 JSONL ──轮询(tailer, ~20s)──▶ round 切分与目录归因
        │
        ├─ 进行中 → collecting，只收集证据
        └─ 已结束 → store.append_event() 先落 evidence_only
                              │
                              ├─ SSE /api/events/stream 立即推送证据
                              └─ 有界会话分析队列（首次5轮、持续增量、手动N轮、证据去重）
                                      │
                                      └─ ProjectAnalysisAgent.analyze_dialogue_turn()
                                              │ 失败/未配置 → evidence_only
                                              └─ 完成后按同一 event_id upsert 并再次推送
                                                      │
                                                      └─ 独立架构修订队列 → knowledge.revision.revise()
Claude hook ──POST /hooks/claude──▶ 只保存观察证据，完整轮次分析由会话日志提供
```

## 4. 核心 Schema

### 4.1 change event（`events-<slug>.jsonl` 每行一个）

```json
{
  "event_id": "稳定逻辑轮次 id(agent_id+session_id+turn_id 派生)",
  "occurred_at": "ISO 时间",
  "agent_id": "claude-code|codex|kimi-code|...",
  "agent_label": "展示名",
  "session_id": "...", "turn_id": "...", "status": "...",
  "evidence_summary": "脱敏后的轮次摘要",
  "request_text": "截断的用户诉求", "result_text": "截断的 agent 回应",
  "files": [{"path": "仓库相对路径", "status": "added|deleted|modified",
             "additions": 0, "deletions": 0, "languages": [], "technologies": []}],
  "source": "poll|hook",
  "is_completed": false,
  "analysis_status": "collecting|evidence_only|analysis_done",
  "dialogue": {"schema_version": "dialogue.v4", "technical_meaning": "改动意义",
               "involves_change": true, "dialogue_act": "other"}
}
```

适配器用显式结束信号或下一次用户提问标记is_completed；EOF保持执行中，Claude的tool_result归属原轮。
Codex使用用户消息偏移作为稳定turn_id，Kimi使用prompt时间；写工具调用先挂起，成功结果确认文件证据。
进行中只保存collecting，完成轮次先保存evidence_only，再由独立有界队列调用模型；首次采集选择项目最近5个完成轮次，后续新增轮次与进行中轮次补全持续分析，已分析轮次按证据指纹与模型标识去重。
analysis-scope-<slug>.json持久化已见event_id与分析资格，重启/队列满保持待分析范围。POST /api/backfill接受正整数recent_rounds，在已捕获历史中选择项目最近N轮加入分析，返回queued而非完成数；轮数与单次上下文预算独立。
upsert比较request/result/files/status/is_completed/cwd的实际变化；同数文件路径替换、短最终回复、结束状态及迟到证据均触发更新。轮询与回补共用采集锁，模型调用不持有采集锁。
图谱缓存键包含事件内容摘要，同轮更新会立即使缓存失效。历史记录通过回补按新适配器重读修正。
事件归因对成功文件路径逐个选择最具体登记项目；文件命中多个不同项目则丢弃，cwd/会话关联只用于无文件证据的轮次。
build_event过滤不属于目标项目的文件，避免父目录cwd把子项目改动写入父项目事件；旧错误历史不静默迁移。

会话模型使用 `dialogue.v4`，同次调用生成 `schema_version / change_summary / technical_meaning`，
change_summary以1-3句描述具体修改（最多400字），technical_meaning解释影响（最多600字）。
后端校验并附加物理证据标记，兼容历史缺少change_summary的结果；额外知识字段从新分析结果中丢弃。
前台常驻显示修改描述、全部完整改动路径和含义；路径点击打开文件导读，长路径自动换行。
历史缺少描述时显示捕获文件数和待分析状态，执行中隐藏旧描述。原文/回复为折叠证据。历史事件中的知识字段保留存储，
会话卡片统一隐藏该板块；会话内部仍以session_id分组、去重和取消追踪，但前台标题取首句用户提问的72字预览，首轮occurred_at的本地化时间紧邻标题显示，不展示session编号。架构词典、文件导读和全局知识库继续独立使用。
画像、意图、独立总结、深度归因不进入新会话输出。UserMemory 保留已有画像、阅读水平与历史接触概念；
此链路不调用独立画像模型。

架构和会话均通过 `model_client` 创建同一个 `ProjectAnalysisAgent` 类，共用当前 active 模型；
各自的 prompt 和 JSON 契约分开。监听、会话分析、架构增量修订使用独立 worker 和有界队列，模型慢时监听仍继续采集；分析完成后以同一 event_id 回写并推送更新。
布局由前端确定性代码负责，模型提供结构化内容。架构输出有版本/路径/数量检查，尚无严格 JSON Schema
约束解码、输出修复重试或跨模型质量保证；开发规范文件也未作为运行时模型提示自动读取。

### 4.2 架构知识（`knowledge/arch-<slug>.json`，schema `architecture.v2`）

`overview{one_liner,purpose,architecture_style}` + `onboarding[≤5]` +
`components[≤10]{name,layer,layer_title,summary,responsibilities,key_features,entry_files,dirs,files,file_roles,depends_on,revision}`。
layer 枚举：`presentation | agent | pipeline | infrastructure`。
全量生成走 `abstract_architecture`，增量修订走 `update_architecture`（只重写受影响组件）。
所有架构写操作经 `knowledge/revision.py:revise`，按真实项目路径共享非阻塞锁，覆盖读→模型→存储全过程。
冲突返回HTTP409；后台轮询遇忙保留待修订状态，下轮继续。持久化使用唯一临时文件再原子替换。
`incorporated_events{event_id:blake2b证据指纹}`记录已纳入版本，pending基于全部已完成轮次，
每次增量合并最多20轮文件改动与摘要，后续轮询继续。无新证据返回unchanged；迟到证据重新变为pending。
旧档案缺少指纹时保留组件并分批重核历史事件，历史revision计数不再作为跳过依据。
全量生成只登记请求开始时的完成事件版本，期间新事件仍待后续处理。
`GET /api/map`返回实时 `architecture_job{busy,pending}`；前端ARCH_JOBS按项目维护请求中状态，
全量与增量按钮共用禁用条件，重绘与项目切换保留状态，执行中轮次隐藏旧分析结论。

文件选择统一由 `snapshot/selection.py:select_files` 实现：manifest、入口、注册/配置三类交替选取，
每类按目录轮转，浅层目录优先、同深度按依赖分数与路径打破平局。
仅当总文件超预算时，关键候选阶段最多使用60%名额，目录覆盖阶段最多增加20%，
剩余按90%导入PageRank + 10%改动组权重补齐；某阶段不足的名额归入最后补齐阶段。
各阶段实际占用通过coverage.stage_counts记录。预算内输入全部保留；单类候选无法耗尽全部名额。
导入边去重，共改动组去重且每组均分权重，避免反复同组修改和大轮次成对边爆炸。
Python用AST提取普通/相对导入，JS/TS保留路径扩展名并解析tsx/jsx等入口；动态注册仍依赖文件角色保底。
快照先枚举候选路径再选8000个读取内容；架构模型最多600个路径，均在选择前保底而非末尾直接截断。
预算内保护的核心候选与目录覆盖计数通过 `structure.analysis_selection / snapshot_selection` 返回并展示。
超过预算的核心候选记录数量与20个路径样例，提示词说明覆盖缺口；角色判断为启发式，不代表业务核心识别保证。

### 4.2.1 分层蓝图展示契约（`graph/builder.py:_build_blueprint` → `web/index.html`）

- 蓝图载荷：`layers[4]{id,name,subtitle,color,components[]}` + `ordered_names[]`。
  每个组件携带 `depends_on[]`（未知目标与自引用已过滤）与 `dep_sources{name→[code|model]}`
  （`code` = 文件 import 推断，`model` = 架构知识判断；`depends_on` 字段本身保持不变）。
- 布局：`bpArrangeModules` 使用 12 列网格，presentation 入口在顶部；agent 中连接度最高
  的模块居中（名称打破平局），其余运行模块分布两侧，剩余模块和 infrastructure 在底部并排。
  缺少 agent 时从运行模块选择中心；孤立模块正常展示。布局为确定性展示选择，关系来自依赖证据。
- 视觉：中性石墨工作台与深色项目画布，蓝色主操作，子系统与功能块通过层级底色和细边框区分，
  核心模块使用蓝灰底；分层色标保留。标题使用真实项目目录名与语言标签，720px最小图宽，窄面板局部横向滚动。
  系统无衬线/苹方字体，代码路径保留等宽；正文14px，桌面左右分栏，900px以下上下排列。
  文件导读与选文问答使用右侧抽屉；嗅探中心整体可滚动并保留候选列表高度；键盘焦点可见，尊重减少动态效果设置。
- 内容：模块标题下展示摘要，功能块优先key_features，其次responsibilities/summary，总览最多六项。
  图下常驻新手导读区，展示入口候选/模型推荐入口及原有阅读建议，点击入口打开文件导读。
  选中模块后下方限高详情展示完整职责、能力、依赖与全部文件作用，文件点击打开既有分析抽屉。
- 连线：SVG 模块→依赖有向边（`A → B` 表示 A 依赖 B），代码导入实线、模型判断虚线。
  端点连接模块边框，`bpRoute` 在模块外边距形成的正交网格上求最短通路，避开模块内部；
  连接线支持同排、跨排、循环依赖，使用 SVG marker 箭头。功能块之间仅展示包含关系。
- 重绘：ResizeObserver 监听画布（含 splitter/折叠），rAF 合并重绘并清理旧边；
  滚动不重绘（相对坐标不变）。
- 交互：悬停/聚焦/选中同时高亮直接依赖与被依赖方（图例标明方向）；
  选中为项目键内存 Map（`BP_SEL`），渲染周期内稳定、不落浏览器存储；
  词典关键词点击与文件链接不触发选中；关键词高亮与中英 I18N 保留
  （标题、计数、操作与边提示走 `bp_*` I18N；模型生成的模块内容沿用其分析语言）。
- 顶栏：`header` 允许换行、子项最小宽收敛，窄屏时右上控制组不被裁剪。

### 4.2.2 文件树与新手导读

右侧仅保留架构图、文件树，旧拓扑/活动图及缩放监听器已删除。`graph/navigation.py`提供
`file_tree{files[{path,language,component,role,role_source,entry,symbols}],imports,coverage}`，
使用全部有界快照路径，不受top=60限制。TREE_OPEN按项目保存展开路径，仅渲染展开分支；
搜索匹配路径/职责/符号，保留父目录，双向依赖按钮定位对应文件。entry区分analysis与candidate。
`snapshot/guide.py`提取Python启动块、限定类方法名、起止行与静态调用引用；其他语言使用候选符号。
`/api/file_analysis`返回reading_guide，原始正文preview不返回。文件抽屉函数条目通过独立
`GET /api/file_code?project=&file=&start=&end=`按需展开带行号的本地脱敏代码，snapshot/source.py校验
登记项目内真实路径、敏感文件、512KB文本上限与2000行范围；源码仅用于本地展示，不进入模型/事件/memory。
Python使用AST完整区域，其他语言无end_line时明确标注定义附近最多40行预览。文件抽屉解释启动/初始化与代码区域，
模型按需补充reading_steps（最多12个、限定输入符号），明确输入输出和阅读顺序；静态引用不当作执行顺序。
文件深度分析仅传脱敏元数据、符号文档、调用引用和历史摘要，缓存按project/path/lang和文件mtime/size校验。
完整文件导读后端内存缓存32项、5秒，目标mtime_ns/size变化即失效。前端导读与代码块按URL隔离缓存64项、10秒，同URL在途请求合并，失败不缓存；命中不闪加载，旧文件响应不覆盖新文件。缓存不写磁盘，其他文件依赖/架构/历史变化依靠短有效期更新（两层有效期可能叠加至约15秒）。

### 4.3 知识词条（`knowledge/bank.py` + `bank_ext_*.py`）

`{id(kebab-case 全局唯一), name, aliases[≥5], category, definition, detailed_explanation,
project_relevance?, related_concepts[id...], interview_questions[{question,answer,kind,reference}×2]}`。
新增词条一律放进对应领域的 `bank_ext_<domain>.py`，由 `knowledge/bank_ext.py` 聚合，
基础术语及跨领域面试考点放在 `bank_ext_fundamentals.py`。
`bank.py` 合并后构建 `ID_INDEX`/`KEYWORD_MAP`，id冲突以导入期断言拦截。
前后端共用NFKC、大小写、空格/下划线/连字符规范化词表；长词与完整边界优先，
保留C++、Node.js等标点术语，React指前端框架、精确大小写ReAct指Agent范式。
关联概念归一为真实词条id，弹窗支持嵌套跳转与返回。
本地检索使用BM25（预计算词频）加别名/精确命中加权，召回词条解释和问答。
新增问答标记为 `kind=curated` 并附GitHub主题参考链接；整理题与有出处的公司真题区分展示，
旧题缺少来源时去除公司冠名。当前词库为242词条、2277个规范化关键词、434道问答。
基础扩展包通过ENTRY_REFERENCES为协议/实现词条指定原始规范链接，通过RELATED维护逐词条关联，
覆盖请求取消、Python网关、依赖图算法、列表排序与梯度裁剪等细分概念。

## 5. 存储布局（`~/.vibe-learning/`）

```
config.json                 登记项目列表、模型供应商列表、active_model_id、忽略名单
events-<slug>.jsonl         每项目事件流（append + upsert，文件锁并发安全）
components-<slug>.json      旧版组件存储（兼容）
knowledge/arch-<slug>.json  架构知识（architecture.v2）
memory/user-<slug>.json     用户画像记忆（user.memory.v1，后台维护，UI 不展示）
offsets.json                各会话文件轮询偏移
```

`<slug>` = 项目绝对路径的稳定哈希（`store._slug`）；`VIBE_LEARNING_DATA` 可覆盖数据目录。
会话分析存于事件的 `dialogue`（早期版本为 `analysis`），架构全量/增量结果保存为当前架构档案。
文件深度模型分析仅缓存于 `model_client.client._FILE_DEEP_CACHE` 与前端内存，服务重启后需重新分析；
术语弹窗及后续提问统一走`POST /api/knowledge/explain`，返回general/project/references/cached/forked及可用的cached_tokens。
`explanations/general/`存term.v1通用释义（规范化精确别名/未知原词、语言、问题隔离），
`explanations/projects/`存项目作用（真实项目、scope、上下文指纹），`explanations/branches/`存原分析messages。
分支每项目/类型/语言保存最新一份，单份512KB上限；独立问题复制父messages再追加问题，同供应商和模型才复用。
旧分析无messages时使用架构摘要，明确forked=false；供应商提示缓存取决于服务端，以usage统计为证据。
统一请求入口以脱敏首条message的blake2b派生x-opencode-session，原分析与选文分支使用稳定路由标识，满足OpenCode Go上游的会话头要求。
通用缓存跨项目读取；项目解释只展示当前有效版本，跨项目按需生成。未配置模型仍读取已有缓存和参考资料。
写入使用文件锁、进程锁与唯一临时文件原子替换，同词并发生成去重，错误不写入成功缓存。
cache_only读取原子文件而不等待生成锁。问答面板保留单个可选问题输入与生成按钮、通用/项目答案和折叠参考；检索和生成各有状态提示、15/90秒前端超时与失败重试。
词库保留为RAG参考；说明文本取消自动分词/下划线，鼠标选中最多2000字仅显示紧凑提问浮钮，
点击浮钮才打开大弹窗并以cache_only查询；浮钮随点击外部、滚动或Esc消失，定位限制在视口内。
精确缓存优先，未命中时同语言/问题、至少12字的选文以去空白字符序列相似度≥85%召回最佳记录，
标注原选文及相似度，仅显示通用答案。此为文本近似而非语义等价，用户点击重新提问才force生成当前选文答案。
新缓存保存term/lang/question用于近似检索，旧缓存仍能精确命中。弹窗内仍支持选文与返回。
路径、代码块及输入控件不被词点击劫持；源码不进入分支或模型，模型正文以转义文本展示。
旧`/api/knowledge/ask`接口兼容保留，新弹窗使用持久化解释接口。SessionMemory 是按事件历史重建的工作内存。

## 6. Memory 与 token 预算

- `SessionMemory`（单次分析内存态）：活跃轮次上限 `MAX_LIVE_TURNS=40`，
  超出后最老轮次折叠为一行摘要进 `compacted_digests`（上限 30 行）。
- `build_context_summary(token_budget=2400)`：近轮次全文渲染、老轮次降级一行摘要，
  按 `(keep, chars)` 阶梯 `(8,800)→(6,400)→(4,300)→(2,200)→(1,150)` 逐级收缩，
  用 `estimate_tokens`（中文字符≈1 token，其余≈1/3.5 字符）校验到预算内。
- 压缩全程确定性执行，不调用模型，不产生额外延迟。
- `UserMemory`（持久画像）：`levels_timeline` 保留近 50 条、`sessions` 近 20 个。

## 7. 扩展点

### 新增平台适配器
实现 `platforms/base.py` 的接口（resolveScope / discoverSourceRoots /
discoverSessions / readSession / normalizeEvent），在 `tailer` 的平台注册表登记。
解析注意：轮次未完成时文件列表可能为空，后续轮询必须靠 `store.event_needs_update`
触发 upsert；Bash/正则文本里的伪路径（如 `->`、`/i`）必须在适配器层过滤。

### 新增分析能力
在 `agent/prompts.py` 加带 `schema_version` 的提示词，在 `analyzer.py` 加方法并做
schema 校验，在 `model_client/client.py` 加门面，最后在 `server.py` 接路由。
任何模型失败必须降级为 evidence_only/错误 JSON，绝不抛穿请求线程。

## 8. 物理证据优先原则

只要 event.files 非空，`involves_change` 强制为 True；模型若输出"无改动"类文本，
以实际文件清单覆盖。轮次事件以逻辑轮次 id 幂等，后到的更完整证据原地更新先入的不完整事件。
