"""Comprehensive Knowledge Graph and Interview Question Bank.

Covers 6 Domains:
1. Agent Application Engineering (Agent Loop, ReAct, Memory, Tools, MCP, Context Harness, Multi-Agent)
2. Agent Algorithm & Reasoning (Planning, Reflection, CoT/ToT/GoT, Self-Refine, Verifiers, Toolformer)
3. Backend & Distributed Systems (Redis, MySQL, Kafka/MQ, High Concurrency, Distributed Lock, Microservices)
4. Frontend & Interactive Architecture (React, Vue, Virtual DOM, State Management, Performance, SSE/WebSocket)
5. Business Algorithms & RecSys (Recall, Ranking, Multi-Task Learning, DIN, MMoE, Feature Engineering)
6. LLM Post-Training & Alignment (SFT, RLHF, DPO, PPO, GRPO, Reward Modeling, LoRA/PEFT, Loss Design)
"""

KNOWLEDGE_ENTRIES = [
    # ==========================================
    # 1. Agent 应用开发 (Agent Application Dev)
    # ==========================================
    {
        "id": "agent-loop",
        "name": "Agent 核心循环 (Agent Loop)",
        "aliases": ["agent-loop", "agent loop", "智能体循环", "感知推理行动", "perceive-reason-act"],
        "category": "Agent应用开发",
        "definition": "Agent 的核心运行时机制，由感知(Perceive) -> 推理(Reason) -> 行动(Act) -> 观察(Observe) 组成周期循环，通过终止条件（任务完成、最大步数、用户干预、异常熔断）完成自治作业。",
        "detailed_explanation": "Agent 与传统线性程序的核心区别在于每一步行动决策均由 LLM 根据当前观察结果动态决定。工程设计上必须具备死循环检测、幂等执行、步骤超时自愈和人机协同(Human-in-the-loop)安全审批控制。",
        "interview_questions": [
            {
                "question": "【腾讯/字节】在 Agent Loop 中如何防止模型陷入同义死循环？生产级有哪些熔断和防御策略？",
                "answer": "1. 机械步数硬限制(Max Iterations)；\n2. 行动哈希指纹去重：比对连续 3 步的 Tool Name + Tool Args 字符串哈希，完全相同时注入 System Prompt 强制提示并换向；\n3. 相似度感知：比对最新 Observation 与上轮相似度；\n4. 预算熔断：设置单次任务 Token 消耗硬阈值与耗时熔断。"
            },
            {
                "question": "【阿里/美团】Agent 编排方案中，何时选择状态机/工作流(Workflow)，何时选择自治 Agent？",
                "answer": "确定性高、合规要求严苛、分支预知的流程用工作流（如订单退款、审批流），由代码掌控确定性；面对开放式需求、输入不确定、需多工具自主决策的探索型场景（如代码重构、全网深度检索、竞品分析）使用自治 Agent。"
            }
        ]
    },
    {
        "id": "react-pattern",
        "name": "ReAct 范式 (Reasoning + Acting)",
        "aliases": ["react", "react范式", "thought-action-observation", "react pattern"],
        "category": "Agent应用开发",
        "definition": "经典的 Agent 协同范式，将思维链推理(Reasoning)与外部工具调用(Action)交替交织，形成 Thought -> Action -> Observation 链条。",
        "detailed_explanation": "ReAct 让大模型在生成动作前先进行阶段性自我解释与反思，显著减轻动作幻觉与盲目试错。结合 Scratchpad 上下文，模型可实时依据环境反馈纠偏。",
        "interview_questions": [
            {
                "question": "【快手/百度】ReAct 范式与 Plan-and-Execute（先规划后执行）各有什么优缺点？如何混合使用？",
                "answer": "ReAct 擅长动态环境和局部自适应，但容易因步步短视导致跑偏（Lost in the Middle）；Plan-and-Execute 全局视野清晰、适合复杂长任务，但在中间步骤失败时自适应差。\n最佳生产实践：采用主从式架构，外层 Planner 制定里程碑子任务，内层 ReAct 执行具体子任务并在遇阻时反馈 Planner 重规划(Re-plan)。"
            }
        ]
    },
    {
        "id": "mcp-protocol",
        "name": "MCP 协议 (Model Context Protocol)",
        "aliases": ["mcp", "mcp协议", "model context protocol", "mcp server", "mcp tool"],
        "category": "Agent应用开发",
        "definition": "由 Anthropic 开源的统一大模型上下文与工具接入开放标准（被称为 AI 时代的 USB-C 接口），基于 JSON-RPC 2.0 协议解耦宿主(Host)与工具服务(Server)。",
        "detailed_explanation": "包含四大能力原语：Resources（只读静态数据）、Tools（模型可调用的外部工具/副作用操作）、Prompts（预定义提示词模板）、Sampling（服务端反向请求宿主 LLM 推理）。传输层支持标准 stdio（本地 IPC）与 Streamable HTTP（远程微服务）。",
        "interview_questions": [
            {
                "question": "【字节/小红书】生产级 MCP Server 如何保证调用的安全隔离与幂等性？",
                "answer": "1. 输入合法性 Schema 校验与防注入：禁止直接拼接 shell 参数；\n2. 幂等性设计：对写操作引入 Request-ID 去重与分布式锁；\n3. 权限与资源隔离：采用独立沙箱或工作目录访问限制，严禁越权访问宿主敏感目录；\n4. 耗时与长连接：设定客户端超时阈值（如 2s/10s），失败快速失败不阻塞主 Agent。"
            },
            {
                "question": "【OpenAI生态】MCP 和标准的 OpenAI Function Calling 有什么本质区别？",
                "answer": "Function Calling 是模型单次的接口契约与输出能力；MCP 是跨模型、跨语言、跨机器的分布式系统协议标准。通过 MCP，一个工具服务可以同时供给 Claude、Kimi、Codex 等各类智能体直接插拔使用，无需重复适配 SDK。"
            }
        ]
    },
    {
        "id": "context-harness",
        "name": "上下文工程与 Harness 架构 (Context Harness)",
        "aliases": ["harness", "context-engineering", "上下文工程", "上下文预算", "prompt cache"],
        "category": "Agent应用开发",
        "definition": "模型决定智能上限，Harness（脚手架工程）决定下限。通过系统边界定义、动态裁剪压缩、Prompt Caching 与渐进式披露管理 Token 上下文生命周期的全套工程体系。",
        "detailed_explanation": "大模型在上下文使用率超过 40% 时会出现明显的注意力退化与幻觉（Lost in the Middle）。Harness 负责划分 L1 核心元数据（常驻）、L2 摘要索引（按需解构）、L3 原始大文本（存储在外部环境或独立沙箱，仅在显式请求时引用）。",
        "interview_questions": [
            {
                "question": "【美团/字节】当 Agent 对话历史即将耗尽上下文窗口时，有哪些生产级上下文压缩与保留策略？",
                "answer": "1. 渐进式滑动窗口裁剪：丢弃中间不重要的工具调用冗长返回，只保留最终状态；\n2. 结构化自动 Compact（状态折叠）：通过独立总结模型生成第一人称的进展报告与已确认事实，替换旧消息；\n3. 外部持久化向量化：将历史冷消息沉淀入向量数据库或日志文件，保留指针引用；\n4. 语义感知修剪：优先清除无关的闲聊与报错重试噪音。"
            }
        ]
    },
    {
        "id": "multi-agent-system",
        "name": "多 Agent 协同系统 (Multi-Agent System)",
        "aliases": ["multi-agent", "多智能体", "orchestrator-subagent", "peer-to-peer"],
        "category": "Agent应用开发",
        "definition": "多个具备独立身份、提示词角色与工具集的 Agent 按照拓扑结构协同解决单一模型无法胜任的复杂超长任务体系。",
        "detailed_explanation": "经典架构分为：1. 主从编排（Orchestrator-Subagent）：编排器调度并发子 Agent（如探索者、编码者、审查者）；2. 对等协作（Peer-to-Peer/SOP）：按流水线依次交接工作成果。核心挑战在于消息通信一致性与防止子智能体并发冲突。",
        "interview_questions": [
            {
                "question": "【阿里/腾讯】在多 Agent 协同编码场景中，如何防止多个 Agent 同时修改同一文件产生代码冲突？",
                "answer": "1. 物理环境隔离：每个子任务 Agent 分配独立的 Git Worktree（工作树）或独立沙箱；\n2. 审查把关合并制（Review-Gated Merge Protocol）：各 Agent 分支独立提交，统一由协调者合并与自动化 Lint/测试验证；\n3. 显式文件写锁（File Lock）：在任务粒度前置声明修改文件清单，互斥锁定。"
            }
        ]
    },

    # ==========================================
    # 2. Agent 算法与推理 (Agent Algorithms & Reasoning)
    # ==========================================
    {
        "id": "reflection-self-refine",
        "name": "自我反思与纠错机制 (Reflection & Self-Refine)",
        "aliases": ["reflection", "self-refine", "reflexion", "自我反思", "反思机制", "critic"],
        "category": "Agent算法",
        "definition": "模型在产生输出或执行工具后，通过批评者模型(Critic)或测试执行器(Verifier)的反馈，进行语义反思并将错误经验存入记忆，在下一轮中主动规避错误的推理增强范式。",
        "detailed_explanation": "以 Reflexion 算法为代表，系统分为 Actor、Evaluator、Self-Reflection。Evaluator 计算标量奖励或测试失败栈，Self-Reflection 生成自然语言反思记忆（例如“之前改动未加锁导致并发死锁，下次必须增加互斥控制”），持久化到 Epistemic Memory 中。",
        "interview_questions": [
            {
                "question": "【微软/商汤】大模型在 Self-Correction（自我纠错）时常常出现“越改越错”或无原则迎合批评，如何从算法上解决？",
                "answer": "1. 依赖外部确定性真值（Ground Truth Verifiers）：如单元测试、编译器报错输出、精确正则规则，而非纯自然语言自言自语；\n2. 双模型对抗：采用能力更强或经过特定 Critic 训练的模型作为审查者；\n3. 历史反思记忆注入：在 Prompt 中明确提供之前的错误失败经验以形成负向约束。"
            }
        ]
    },
    {
        "id": "planning-tot-got",
        "name": "复杂规划与树图搜索 (Planning / ToT / GoT)",
        "aliases": ["planning", "tot", "tree of thoughts", "got", "思维树", "思维图", "路径规划"],
        "category": "Agent算法",
        "definition": "超越线性思维链(CoT)的非线性推理算法，通过树状(Tree-of-Thoughts)或有向无环图(Graph-of-Thoughts)生成并探索多个候选推理分支，结合回溯(Backtracking)与启发式评估寻找最优解路径。",
        "detailed_explanation": "系统在每个中间决策点探索多个候选方案，由价值评估函数（Value Function）或判别器对每个分支打分（DFS/BFS/MCTS 蒙特卡洛树搜索），若遇死胡同则回溯至上一节点重新分支。",
        "interview_questions": [
            {
                "question": "【华为/快手】在工程落地中，ToT（思维树）由于高昂的 Token 和延迟代价难以直接上线，有哪些实用的轻量化替代方案？",
                "answer": "1. Best-of-N 采样 + 确定性打分器(PRM)重新打分过滤；\n2. 束搜索(Beam Search)截断：每层仅保留 Top-2 高分分支，其余剪枝；\n3. 静态决策流与动态分支混合：常规确定性步骤走规则，只在关键策略分叉点启动分支打分。"
            }
        ]
    },

    # ==========================================
    # 3. 后端与分布式高并发 (Backend & Distributed)
    # ==========================================
    {
        "id": "redis-distributed-lock",
        "name": "Redis 分布式锁与 Redisson 机制",
        "aliases": ["redis分布式锁", "redlock", "redisson", "setnx", "看门狗机制"],
        "category": "后端与分布式",
        "definition": "利用 Redis 单线程原子性或 Lua 脚本实现的跨进程互斥控制机制，通常使用 SET resource_name my_random_value NX PX 30000 保证独占与防死锁。",
        "detailed_explanation": "生产级实现核心要点：1. 随机 Val 防止误删他人锁；2. Lua 脚本保证释放锁时的比对+删除原子性；3. Redisson 看门狗(Watchdog)自动续期机制；4. 主从切换锁丢失问题（RedLock 算法争议与 Fencing Token 替代方案）。",
        "interview_questions": [
            {
                "question": "【阿里/美团】如果业务执行时间超过了 Redis 锁的过期时间导致锁提前释放，会出现什么灾难？如何解决？",
                "answer": "1. 灾难：并发线程 B 获取到已超期的同一把锁，破坏互斥性；线程 A 执行完成后可能错误释放线程 B 的锁；\n2. 解决方案：使用 Redisson 客户端的看门狗(Watchdog)机制，后台定时任务每隔 internalLockLeaseTime/3 自动续期；或使用递增的 Fencing Token 让下游数据库根据版本号拒绝过期事务。"
            },
            {
                "question": "【腾讯/拼多多】Redis 主从架构下，主节点加锁后尚未同步给从节点就宕机了，从节点升为主，如何处理锁丢失？",
                "answer": "这是 CAP 原理在 Redis AP 模式下的必然妥协。对一致性要求极其苛刻的场景（如金融账户结账），应改用强一致性 CP 系统（如 ZooKeeper、etcd、Raft 一致性锁）或数据库悲观行锁；一般业务可通过幂等校验和业务状态机（如待支付->处理中->已支付）兜底防重。"
            }
        ]
    },
    {
        "id": "cache-concurrency-consistency",
        "name": "缓存与数据库双写一致性",
        "aliases": ["双写一致性", "缓存穿透", "缓存击穿", "缓存雪崩", "延迟双删", "canal"],
        "category": "后端与分布式",
        "definition": "高并发系统中 Redis 缓存与底层 MySQL 数据库在更新时的数据一致性保障方案，涵盖 Cache-Aside、延迟双删与异步监听 Binlog 机制。",
        "detailed_explanation": "常规推荐使用 Cache Aside 模式：读时先读缓存，没有则读库并回写；写时先更新数据库，再删除缓存。高并发极限下仍可能出现脏读覆盖，生产常用 Canal 订阅 MySQL Binlog 异步投递消息队列保证最终一致性。",
        "interview_questions": [
            {
                "question": "【字节/百度】更新缓存时，为什么推荐“先更新数据库，再删除缓存”，而不是“先删缓存再改库”或“直接更新缓存”？",
                "answer": "1. 直接更新缓存容易因并发写乱序产生脏数据（写请求 A 后发起但先到缓存，写请求 B 先发起后写入覆盖）；\n2. 先删缓存再改库：若读请求恰好在两者中间发生，会将旧库数据回填进缓存，导致长期脏读；\n3. 先更库再删缓存：读线程在刚好读出旧值到回填缓存的微小时间差内，才可能产生不一致，概率极低，再配合过期时间(TTL)即可保证高可用与高一致。"
            }
        ]
    },
    {
        "id": "mq-kafka-reliability",
        "name": "消息队列可靠性与重复消费 (Kafka/RabbitMQ)",
        "aliases": ["kafka", "消息队列", "重复消费", "幂等消费", "消息丢失", "ack机制"],
        "category": "后端与分布式",
        "definition": "分布式异步解耦消息系统的可靠性投递闭环，解决高并发下的削峰填谷、消息防丢（At-least-once）与下游消费幂等处理。",
        "detailed_explanation": "消息全链路防丢：生产端 acks=all + 重试，Broker 端多副本 min.insync.replicas=2 + 刷盘，消费端关闭自动提交 offset，手动确认(Manual Ack)。下游通过业务唯一键（如订单号）构建去重表实现幂等。",
        "interview_questions": [
            {
                "question": "【京东/网易】生产环境下 Kafka 消费者出现重复消费的最常见原因是什么？如何做到绝对幂等？",
                "answer": "1. 常见原因：消费者拉取批量消息后，由于业务耗时过长超过 max.poll.interval.ms，Broker 判定消费者心跳假死触发 Rebalance，导致已处理消息的 Offset 未能提交，新消费者重新消费；\n2. 幂等解决方案：在业务消费端引入唯一业务主键（防重表/Redis setnx 状态位）；把操作设计为幂等操作（如基于状态机的 CAS 更新：where status = 'INIT'）。"
            }
        ]
    },

    # ==========================================
    # 4. 前端与交互架构 (Frontend & Interactive Arch)
    # ==========================================
    {
        "id": "react-virtual-dom-fiber",
        "name": "React Fiber 架构与时间切片 (Time Slicing)",
        "aliases": ["react fiber", "virtual dom", "时间切片", "react协调", "reconciliation"],
        "category": "前端工程",
        "definition": "React 16 引入的基于链表结构的调度与协调(Reconciliation)架构，将不可中断的递归深度遍历重构为可分片、可暂停、可恢复的异步工作单元。",
        "detailed_explanation": "通过将组件树表示为包含 child、sibling、return 指针的 Fiber 双缓存树（current 与 workInProgress），结合浏览器的 requestIdleCallback 或 MessageChannel，在主线程空闲时分批执行 Diff，优先保证高优先级用户交互不掉帧。",
        "interview_questions": [
            {
                "question": "【字节/腾讯前端】为什么有了 Fiber 架构后，Vue 却不需要 Fiber 也能保持高性能？",
                "answer": "React 是粗粒度响应式系统，任何状态变更默认自顶向下重新遍历子树，因此需要 Fiber 时间切片来避免长时间占用主线程；\nVue 基于响应式依赖收集（Object.defineProperty / Proxy），精确追踪组件或模板绑定的变化（组件级更新粒度），天然不需要全局 Diff 分片。"
            }
        ]
    },
    {
        "id": "sse-streaming-rendering",
        "name": "SSE 流式交互与长连接渲染 (Server-Sent Events)",
        "aliases": ["sse", "server-sent events", "流式输出", "打字机效果", "长连接", "event-source"],
        "category": "前端工程",
        "definition": "基于 HTTP 协议的单向长连接推送技术（Content-Type: text/event-stream），常用于 AI Agent 对话场景中的流式 Token 打字机渲染与实时状态广播。",
        "detailed_explanation": "相比 WebSocket 的全双工高协议成本，SSE 基于标准 HTTP/1.1 或 HTTP/2，自带断线重连、事件 ID 追溯(Last-Event-ID)，并且能天然享受浏览器的 HTTP 缓存与安全机制。前端需配合 Fetch API + ReadableStream 进行增量文本解码与渲染节流防卡顿。",
        "interview_questions": [
            {
                "question": "【阿里/字节前端】在大模型生成每秒 50-100 个 Token 的高频打字机场景下，前端如何避免频繁 DOM 重绘导致页面卡顿？",
                "answer": "1. 渲染节流与 RAF 队列：将接收到的 Token 推入缓冲区，使用 requestAnimationFrame 批量按固定帧率（如 60fps）刷新 DOM；\n2. 虚拟滚动(Virtual List)：只渲染视口区域内的文本和气泡卡片，超限节点销毁；\n3. 增量追加而非全量 innerHTML：使用 Node.appendChild 或 innerText 局部赋值，避免触发昂贵的整树重排(Reflow)。"
            }
        ]
    },

    # ==========================================
    # 5. 业务算法与推荐系统 (RecSys & Business Algorithms)
    # ==========================================
    {
        "id": "recsys-recall-multi-channel",
        "name": "推荐系统多路召回与向量检索 (RecSys Recall & Vector Search)",
        "aliases": ["多路召回", "向量召回", "item2vec", "双塔模型", "dssm", "faiss", "hnsw"],
        "category": "业务算法",
        "definition": "推荐系统漏斗模型的第一步，从千万级甚至亿级物料库中快速初筛出千级别高相关候选集的算法框架，包括协同过滤、双塔模型(DSSM)向量召回等通道。",
        "detailed_explanation": "双塔模型将用户侧特征与物品侧特征分别送入 User 塔与 Item 塔，在向量空间计算内积相似度。离线将全量物料向量建立 HNSW/IVF 索引，线上实时通过用户向量执行 ANN 最近邻搜索，实现毫秒级快速候选截断。",
        "interview_questions": [
            {
                "question": "【快手/美团】双塔模型（DSSM）在推荐召回中非常流行，但为什么不能直接用于精排？其本质缺陷是什么？",
                "answer": "双塔结构在最后一层才做内积交互，完全割裂了 User 特征与 Item 特征在底层深层网络中的交叉（如“用户历史买过某个品牌的鞋，对该品牌新衣服有偏好”无法深度交叉）。精排需要更复杂的特征交叉网络（如 DeepFM、DCN、DIN），用更高的计算成本换取极高的预估精度。"
            }
        ]
    },
    {
        "id": "recsys-ranking-mmoe",
        "name": "精排多任务学习与用户兴趣建模 (MMoE & DIN)",
        "aliases": ["mmoe", "多任务学习", "din", "精排模型", "ctr预估", "cvr预估", "多目标融合"],
        "category": "业务算法",
        "definition": "在推荐系统精排阶段同时预估点击率(CTR)、转化率(CVR)、停留时长等多个商业目标的神经网络架构，通过多门控混合专家网络(MMoE)解决负迁移(Negative Transfer)问题。",
        "detailed_explanation": "传统 Shared-Bottom 共享底层特征容易在不同目标间相互冲突产生负迁移。MMoE 为每个目标任务分配专门的 Softmax 门控网络（Gate），根据输入样本动态组合不同的 Expert 子网络；DIN 则引入注意力机制捕获用户多样化历史兴趣与当前目标物品的相关性权重。",
        "interview_questions": [
            {
                "question": "【字节/阿里】在推荐精排的多目标模型中，点击率（CTR）和转化率（CVR）同时建模时常见的“样本选择偏差（SSB）”是什么？ESMM 模型如何破解？",
                "answer": "1. 样本选择偏差：传统 CVR 仅在已点击样本上训练，但线上推理时是在全量未点击曝光物料上打分，训练分布与推理分布不一致；\n2. ESMM 破解思路：引入曝光转化率 CTCVR = CTR * CVR，在全空间样本上分别拟合 CTR 和 CTCVR，通过网络内积相除间接得出无偏的 CVR，消除样本偏差。"
            }
        ]
    },

    # ==========================================
    # 6. 大模型后训练与对齐 (LLM Post-Training & Alignment)
    # ==========================================
    {
        "id": "post-training-sft-lora",
        "name": "监督微调与参数高效微调 (SFT & LoRA)",
        "aliases": ["sft", "lora", "qlora", "监督微调", "peft", "参数高效微调"],
        "category": "后训练与对齐",
        "definition": "在预训练基座模型之上，使用高质量 Prompt-Response 对话指令集进行自回归损失训练以激发遵循能力；LoRA 通过低秩分解矩阵 ΔW = B*A 仅训练 0.1% 参数即可实现全量微调效果。",
        "detailed_explanation": "SFT 的核心不是给模型灌输新知识，而是唤醒知识并对齐输出格式。LoRA 冻结原始权重 W0，引入秩为 r（如 r=8/16/32）的小矩阵，推理时可直接合并回权重(W = W0 + α/r * BA)，实现零额外推理延迟。",
        "interview_questions": [
            {
                "question": "【商汤/腾讯】大模型微调中 LoRA 矩阵的初始化为什么通常是 A 采用高斯分布初始化，而 B 采用全零初始化？",
                "answer": "如果 A 和 B 都随机初始化，在训练开始的第一步 ΔW = B*A 就会产生非零偏差，直接破坏原始预训练权重的行为；让 B 为全零，可以保证在训练起始时刻 ΔW = 0，微调是从原始基座模型无损平滑启动的。"
            }
        ]
    },
    {
        "id": "alignment-rlhf-dpo-grpo",
        "name": "人类偏好对齐算法演进 (RLHF / DPO / GRPO)",
        "aliases": ["dpo", "rlhf", "grpo", "ppo", "偏好对齐", "直接偏好优化", "强化学习对齐"],
        "category": "后训练与对齐",
        "definition": "让大模型价值观与人类偏好对齐的强化学习与直觉优化算法族。从经典的 PPO（Actor-Critic + Reward Model）演进到无需奖励模型的 DPO，再到 DeepSeek 推出的消除 Critic 网络的 GRPO 组相对策略优化。",
        "detailed_explanation": "PPO 训练极不稳定且需维护 4 个模型（Actor/Reference/Critic/Reward），显存开销巨大；DPO 通过数学推导将奖励隐式代入交叉熵损失；GRPO 针对一组候选回答利用均值与方差计算相对优势(Relative Advantage)，极度节省显存并契合长链推理(R1)的冷启动与自进化强化学习。",
        "interview_questions": [
            {
                "question": "【月之暗面/DeepSeek/商汤】DeepSeek-R1 为什么采用 GRPO 替代传统的 PPO 算法？其核心创新点是什么？",
                "answer": "1. 摆脱 Critic 估值模型：传统 PPO 需要与 Actor 同等规模的 Critic 网络预估状态价值以计算 GAE，极其消耗显存；\n2. 组相对优势估计（Group Relative Advantage）：GRPO 对同一 Prompt 采样一组响应（如 G=8 个），直接在组内按得分归一化（(R_i - mean)/std）得到优势值，大幅节省 50% 显存；\n3. 结合规则奖励（Rule-based Reward）：在数学、代码推理中直接使用编译器输出和答案正确性作为强硬奖励，驱动模型涌现自反思自验证能力。"
            },
            {
                "question": "【字节/百度】DPO（直接偏好优化）虽然训练简单无须训练 Reward Model，但在长序列生成或复杂推理场景下有什么局限？",
                "answer": "DPO 容易产生分布漂移，无法像 PPO 那样在线探索生成新轨迹并实时修正；DPO 对噪声标注数据极其敏感，容易出现奖励崩塌（Reward Collapse）导致模型生成冗长但无意义的高似然废话。长链推理通常结合在线强化学习（如 GRPO/PPO）效果显著优于静态离线 DPO。"
            }
        ]
    },

    # ==========================================
    # 7. 计算机网络与系统架构基础 (Network & System Fundamentals)
    # ==========================================
    {
        "id": "http-protocol",
        "name": "HTTP / HTTPS 网络传输协议",
        "aliases": ["http", "https", "http协议", "http/1.1", "http/2", "restful api"],
        "category": "计算机网络与协议",
        "definition": "超文本传输协议（HyperText Transfer Protocol），基于请求-响应模型的无状态应用层网络传输协议，现代 Web 与 RESTful API 的基石。",
        "detailed_explanation": "HTTP/1.1 引入持久连接(Keep-Alive)与分块传输(Chunked Transfer)；HTTP/2 引入多路复用(Multiplexing)与头部压缩(HPACK)彻底解决队头阻塞；HTTPS 在传输层之上引入 TLS/SSL 加密握手保证数据机密性与完整性。",
        "project_relevance": "vibe-learning 使用 Python 标准库 ThreadingHTTPServer 提供单进程零外部依赖的 HTTP API 与静态 Web 资源托管服务。",
        "related_concepts": ["sse", "tcp", "websocket", "restful"],
        "interview_questions": [
            {
                "question": "【阿里/美团】HTTP/1.1 长连接与 HTTP/2 多路复用有什么本质区别？",
                "answer": "HTTP/1.1 的 Keep-Alive 仅复用底层 TCP 连接，但在同一个 TCP 连接上请求依然是串行响应的，存在应用层队头阻塞；HTTP/2 将请求拆分为二进制帧(Frame)，多个请求与响应可在同一 TCP 连接上交错并发传输，真正做到了单连接多路复用。"
            },
            {
                "question": "【腾讯/字节】GET 与 POST 在 HTTP 规范中的核心区别与幂等性要求？",
                "answer": "GET 具有幂等性与只读安全性，用于获取资源，参数在 URL 中，支持浏览器缓存；POST 用于向服务器提交数据或触发副作用，非幂等，数据在 Request Body 中传输。"
            }
        ]
    },
    {
        "id": "sse-eventsource",
        "name": "SSE 实时单向流式推送 (Server-Sent Events)",
        "aliases": ["sse", "server-sent events", "text/event-stream", "eventsource"],
        "category": "计算机网络与协议",
        "definition": "基于标准 HTTP 协议的轻量级服务端到客户端单向实时流式事件推送机制（Content-Type: text/event-stream）。",
        "detailed_explanation": "相比 WebSocket 的全双工高协议成本，SSE 基于标准长连接，浏览器原生提供 EventSource API，自带自动重连、Last-Event-ID 断点追溯机制，且天生穿透各种反向代理防火墙。",
        "project_relevance": "vibe-learning 核心流式传输通道：通过 GET /api/events/stream 实时把新检测到的 Agent 代码改动和架构分析毫秒级推送到前端页面，无需前端 1 秒一轮询。",
        "related_concepts": ["http", "websocket", "polling"],
        "interview_questions": [
            {
                "question": "【字节/快手】为什么 AI 大模型打字机和状态监听几乎全部采用 SSE 而不是 WebSocket？",
                "answer": "1. 业务场景天然是单向传输：用户发一条 Prompt 后，服务端源源不断流式生成 Token，单向 HTTP 即可满足；\n2. 协议极简：标准 HTTP 响应流，无须协议升级(Upgrade)与二进制 Frame 封包解包；\n3. 天然兼容代理与缓存：企业内网 Nginx/网关原生支持 SSE 缓冲禁用(X-Accel-Buffering: no)，连接更健壮。"
            }
        ]
    },
    {
        "id": "websocket-protocol",
        "name": "WebSocket 全双工通信协议",
        "aliases": ["websocket", "ws", "wss", "全双工"],
        "category": "计算机网络与协议",
        "definition": "在单个 TCP 连接上进行全双工(Full-Duplex)通信的协议，通过 HTTP 101 Switching Protocols 握手升级，允许客户端与服务端随时互相主动推送消息。",
        "detailed_explanation": "适用于多人实时协同在线编辑（如协同白板/多人协作文档）、高频交互多人联机网游、毫秒级金融行情推送等需要双向高频互动的极端场景。缺点是需自行实现心跳保活(Ping/Pong)与断线重连。",
        "project_relevance": "作为对比技术与知识点，解析单向广播（SSE）与双向交互（WebSocket）的架构选型权衡。",
        "related_concepts": ["sse", "http", "tcp"],
        "interview_questions": [
            {
                "question": "【腾讯/网易】WebSocket 的连接建立过程是怎样的？如何做心跳保活与防假死？",
                "answer": "客户端发起带有 Connection: Upgrade 和 Upgrade: websocket 头的 HTTP GET 请求；服务端验证 Sec-WebSocket-Key 并返回 101 状态码完成握手。生产级通过客户端与服务端互发 Ping/Pong 帧，连续 N 次心跳超时未收到即主动关闭连接并触发指数退避重连。"
            }
        ]
    },
    {
        "id": "ast-code-inspect",
        "name": "AST 抽象语法树与代码静态分析 (Abstract Syntax Tree)",
        "aliases": ["ast", "抽象语法树", "静态分析", "syntax tree", "parse tree"],
        "category": "编译原理与工程工具",
        "definition": "源代码语法结构的树状对象表示，将纯文本代码转化为节点分明的层次树（如 FunctionDef, ClassDef, Import, Call），是编译器、Linter、Babel 和静态代码分析的基础。",
        "detailed_explanation": "通过词法分析(Tokenize)将字符流转为 Token，再经语法分析(Parse)根据语言文法构建 AST。遍历 AST（Visitor 模式）可在无需执行代码的前提下精确分析函数签名、变量调用、依赖导入关系与代码圈复杂度。",
        "project_relevance": "vibe-learning 的底层分析引擎：使用 Python 标准库 ast 模块在毫秒级内提取代码库中所有顶级类、函数签名、行号、以及调用关系，精准分析出每个文件的具体功能职责。",
        "related_concepts": ["pagerank", "diff"],
        "interview_questions": [
            {
                "question": "【字节/美团前端架构】Babel 或 ESLint 是如何利用 AST 进行代码转换和规则校验的？",
                "answer": "采用 Parse -> Transform -> Generate 三阶段。1. Parse：将代码转为 ESTree 规范的 AST；2. Transform：通过 Visitor 模式递归访问特定节点类型（如 ArrowFunctionExpression），对其子树进行增删改查；3. Generate：将修改后的 AST 重新打印为目标平台代码和 SourceMap。"
            }
        ]
    },
    {
        "id": "pagerank-algorithm",
        "name": "PageRank 图算法与节点重要性排序",
        "aliases": ["pagerank", "pagerank算法", "图排序", "阻尼系数", "拓扑权重"],
        "category": "图算法与数据结构",
        "definition": "Google 经典的网页重要性评估图算法，基于随机游走模型与马尔可夫链，通过“被高质量节点引用的节点更重要”的递归投票原理计算每个节点的稳态权重。",
        "detailed_explanation": "在有向图上迭代更新节点权重：PR(u) = (1 - d)/N + d * Σ(PR(v) / OutDegree(v))，其中 d 为阻尼系数（通常取 0.85，代表用户沿外链继续点击的概率）。通过有限次幂迭代（Power Iteration）直至收敛。",
        "project_relevance": "vibe-learning 对导入图计算PageRank，与去重改动组权重按90:10组合。文件选择同时保护关键角色和目录覆盖；超预算时预留依赖排序名额，并显式报告遗漏，分数代表依赖重要性而非业务核心的绝对判定。",
        "related_concepts": ["ast", "diff"],
        "interview_questions": [
            {
                "question": "【阿里/百度】PageRank 算法中的“悬挂节点（Dangling Node）”和“蜘蛛陷阱（Spider Trap）”是什么？如何解决？",
                "answer": "1. 悬挂节点：出度为 0 的节点，会导致随机游走进入死胡同使总权重随迭代归零；解决：悬挂节点将权重均分给全图所有节点；\n2. 蜘蛛陷阱：若干节点互相指向形成环路且无外部出边，吸收全图权重；解决：引入阻尼系数 d，以 (1-d) 概率随机跳出跳转到任意网页。"
            }
        ]
    },
    {
        "id": "blake2b-hash",
        "name": "BLAKE2b 快速密码学哈希算法",
        "aliases": ["blake2b", "blake2", "哈希算法", "文件指纹", "digest"],
        "category": "信息安全与算法",
        "definition": "基于 ChaCha 核心的高性能密码学哈希函数，速度显著快于 MD5、SHA-1、SHA-256 和 SHA-3，同时具备极高的抗碰撞安全性。",
        "detailed_explanation": "BLAKE2b 专为 64 位平台优化，在现代 CPU 上单核吞吐量超过 1GB/s，常用于大型文件指纹校验、快照增量比对与完整性验证。",
        "project_relevance": "vibe-learning 对项目目录做有界快照时的文件级指纹生成器：使用 blake2b 对文件内容计算 16 字节十六进制指纹，实现毫秒级判断文件是否被 Agent 修改。",
        "related_concepts": ["diff", "git"],
        "interview_questions": [
            {
                "question": "【腾讯/字节】在海量文件指纹比对系统中，为什么 BLAKE2b 正在逐渐取代传统的 MD5 和 SHA-256？",
                "answer": "1. 性能极大提升：BLAKE2b 在 64 位平台上的计算速度接近 MD5 但安全性远超 MD5（MD5 已被证明存在实际碰撞攻击）；\n2. 相比 SHA-256：BLAKE2b 免受长度扩展攻击（Length Extension Attack），且在多核处理与指令集优化下吞吐量高出 2~3 倍。"
            }
        ]
    },
    {
        "id": "jsonl-format",
        "name": "JSONL 格式 (JSON Lines / NDJSON)",
        "aliases": ["jsonl", "json lines", "ndjson", "换行分隔json"],
        "category": "数据工程与文件存储",
        "definition": "每行一个独立且完整的合法 JSON 对象的文本存储格式（换行符分隔），专为大规模日志流式追加、断点读写与分布式处理设计。",
        "detailed_explanation": "传统 JSON 数组在追加数据时必须重新解析整个大文件并闭合括号；JSONL 格式天然支持 O(1) 尾部追加（Append-Only），即使写入被意外中断也不会破坏前序数据行的有效性。",
        "project_relevance": "Claude Code（~/.claude/projects/*/*.jsonl）与 OpenAI Codex（rollout-*.jsonl）的底层会话存储均采用此格式。vibe-learning 的 Session Tailer 模块通过逐行扫描 JSONL 高效监听并提取会话 Round。",
        "related_concepts": ["sse", "ipc"],
        "interview_questions": [
            {
                "question": "【快手/字节】在大数据与大模型训练流中，为什么普遍选用 JSONL/Parquet 而非单个巨大 JSON 文件？",
                "answer": "1. 流式与并发：JSONL 支持无须将全文件加载入内存即可逐行迭代(Stream Read)，多个 Worker 可通过文件 Seek 偏移量轻松实现并行分片读取；\n2. 容错性高：单个巨大 JSON 文件若尾部语法截断则整文件报废，JSONL 仅丢弃最后一行损坏数据，容灾恢复极其简单。"
            }
        ]
    },
    {
        "id": "git-vcs",
        "name": "Git 分布式版本控制系统",
        "aliases": ["git", "git版本控制", "worktree", "commit", "branch"],
        "category": "工程效率与工具",
        "definition": "基于内容寻址文件系统的分布式版本控制体系，通过 Commit（提交对象）、Tree（目录对象）、Blob（文件内容）构成有向无环图(DAG)。",
        "detailed_explanation": "支持完全离线提交、轻量级分支与指针移动。Git Worktree 允许从同一仓库同时检出多个不同分支到独立的本地工作目录，避免频繁切换 stash/checkout。",
        "project_relevance": "vibe-learning 快照模块优先使用 git ls-files --cached --others --exclude-standard 高效提取文件列表，天然继承项目的 .gitignore 规则；同时监听各平台 Agent 对仓库文件的改动。",
        "related_concepts": ["diff", "blake2b"],
        "interview_questions": [
            {
                "question": "【阿里/字节】Git 底层存储模型中 Blob、Tree、Commit 三种对象的关系是怎样的？",
                "answer": "Blob 仅存储文件正文内容（以 SHA-1/SHA-256 哈希命名，不存文件名和权限）；Tree 对象记录当前目录下的文件名、文件模式以及指向相应 Blob 或子 Tree 的指针；Commit 对象包含顶层 Tree 指针、父提交指针(Parent)、作者与提交信息，三者串联构成内容不可篡改的历史 DAG。"
            }
        ]
    },
    {
        "id": "diff-algorithm",
        "name": "Diff 文本差异比对算法 (Myers Diff)",
        "aliases": ["diff", "代码diff", "myers算法", "差异比对", "增删行数"],
        "category": "算法原理",
        "definition": "求解两个序列间最长公共子序列（LCS）或最短编辑脚本（SES）的经典算法，常用于版本控制中计算新增(added)、删除(deleted)和修改(modified)代码行。",
        "detailed_explanation": "Myers 算法将编辑过程建模在二维网格图上的对角线搜索，结合 BFS 贪心搜索时间复杂度达 O((N+M)D)，其中 D 为差异大小。由于大多数代码变动很小（D 极小），该算法在实际工程中极度迅速。",
        "project_relevance": "vibe-learning 快照与事件系统：在检测到文件内容指纹变更后，计算文件级 diff 增删行数，并以此作为 Agent 改动事件的确定性证据 (Evidence)。",
        "related_concepts": ["git", "blake2b"],
        "interview_questions": [
            {
                "question": "【腾讯/美团】如何高效比对两个大文件（数万行代码）的行级变动并生成高可读性的统一差分(Unified Diff)？",
                "answer": "1. 预处理哈希：先将每行文本转换为整型哈希值，把字符比对降维为整数数组比较；\n2. 截断公共头尾：O(N) 快速滤去未改动的首尾大段相同代码；\n3. Myers 算法求解：在收敛后的小差异区间运行 Myers 搜索，最后按行展开为带行号上下文的 unified diff 块。"
            }
        ]
    },
    {
        "id": "threading-concurrency",
        "name": "多线程与并发控制 (Threading & Concurrency)",
        "aliases": ["threading", "多线程", "并发", "gil", "线程池", "lock"],
        "category": "操作系统与并发编程",
        "definition": "操作系统调度的最小执行单元，多个线程共享同一进程的地址空间与资源，适合高并发 I/O 密集型应用。",
        "detailed_explanation": "在 Python 中由于全局解释器锁（GIL）的存在，多线程无法利用多核 CPU 加速纯计算任务，但在网络 I/O、磁盘读写和 HTTP 长连接推送场景中，多线程在遇到 I/O 阻塞时自动释放 GIL，能以极低的内存开销实现高并发吞吐。",
        "project_relevance": "vibe-learning 后端采用 ThreadingHTTPServer 并行处理 HTTP 请求与 SSE 长连接，同时启动独立的后台守护线程 _poll_loop() 周期性扫描项目与监听 Agent 会话。",
        "related_concepts": ["http", "sse", "ipc"],
        "interview_questions": [
            {
                "question": "【阿里/字节】Python 的全局解释器锁（GIL）是什么？既然有了 GIL 为什么多线程操作共享变量仍然需要加线程锁（Lock）？",
                "answer": "GIL 是 CPython 解释器级别的互斥锁，保证同一时刻只有一个线程执行 Python 字节码；但 GIL 只保证单条字节码指令的原子性，无法保证 Python 高级语言操作的原子性（例如 count += 1 包含读、加、写三条字节码，中间会被强制上下文切换产生竞态条件）。因此保护共享业务状态必须显式加锁。"
            }
        ]
    },

    {
        "id": "tcp-protocol",
        "name": "TCP 传输控制协议 (Transmission Control Protocol)",
        "aliases": [
            "tcp",
            "tcp协议",
            "三次握手",
            "四次挥手",
            "可靠传输",
            "滑动窗口",
            "拥塞控制",
            "seq",
            "ack"
        ],
        "category": "计算机网络与协议",
        "definition": "运行在传输层的面向连接、可靠、基于字节流的双向通信协议。通过序列号(Seq)、确认号(Ack)、超时重传和滑动窗口实现无差错无丢失的端到端数据传输。",
        "detailed_explanation": "建立连接采用三次握手（同步初始序号 ISN 并协商 MSS），断开连接采用四次挥手（TIME_WAIT 状态必须维持 2MSL 以确保最终 ACK 到达对端并清除网络残留报文）。核心拥塞控制算法涵盖慢启动、拥塞避免、快重传与快恢复（如 CUBIC, BBR 算法）。",
        "project_relevance": "vibe-learning 的 HTTP 服务与 SSE 流式推送底层均依托 TCP 连接保障数据传输的绝对完整与顺序到达。",
        "related_concepts": [
            "http-protocol",
            "udp-protocol",
            "sse-eventsource",
            "tls-ssl-protocol"
        ],
        "interview_questions": [
            {
                "question": "【阿里/腾讯网络高频】TCP 握手为什么必须是三次，两次或四次行不行？",
                "answer": "1. 两次不行：无法防止历史失效的连接请求突然传到服务器产生错误连接与资源浪费；客户端无法确认服务端是否真正接收到了客户端的 SYN-ACK 确认；\n2. 四次多余：服务端的 SYN 和 ACK 可以在第二次握手中合并发送，三次已是建立可靠全双工双向连接与确认双方收发能力的最小必要次数。"
            },
            {
                "question": "【字节/美团】四次挥手中 TIME_WAIT 状态的作用是什么？过多的 TIME_WAIT 会导致什么问题？如何优化？",
                "answer": "1. 作用：确保客户端发送的最后一个 ACK 报文能够到达服务端（若丢失服务端会重发 FIN）；防止历史已关闭连接的老报文在网络中延迟到达，干扰新建立的连接；\n2. 危害：占用系统大量 Socket 四元组和文件句柄，耗尽端口资源导致无法新建外发连接；\n3. 优化：开启 TCP 连接复用（tcp_tw_reuse）、增加可用端口范围、服务端配置长连接 Keep-Alive 避免客户端主动频繁断开。"
            }
        ]
    },

    {
        "id": "udp-protocol",
        "name": "UDP 用户数据报协议 (User Datagram Protocol)",
        "aliases": [
            "udp",
            "udp协议",
            "无连接",
            "数据报",
            "quic传输"
        ],
        "category": "计算机网络与协议",
        "definition": "传输层无连接、不可靠、面向报文的轻量级传输协议。不保证数据交付顺序，不维持连接状态，具有极低的首部开销（仅 8 字节）和零握手延迟。",
        "detailed_explanation": "适用于对实时性要求极高而容忍少量丢包的场景（DNS 查询、音视频通话、在线竞技游戏）。现代 HTTP/3（QUIC）正是基于 UDP 在应用层重新实现了可靠传输、前向纠错与零 RTT 建连，打破了内核态 TCP 协议栈的演进瓶颈。",
        "project_relevance": "解析单向低开销通信原理，与 TCP/HTTP/SSE 架构做横向对比与技术选型对照。",
        "related_concepts": [
            "tcp-protocol",
            "http3-quic-protocol",
            "dns-resolution"
        ],
        "interview_questions": [
            {
                "question": "【字节/网易】既然 UDP 不可靠，为什么 HTTP/3 和许多现代即时通讯协议选择基于 UDP 改造？",
                "answer": "1. 摆脱 TCP 队头阻塞：TCP 单个包丢失会导致整条连接所有后续数据阻塞在接收缓冲区；UDP 在应用层设计流(Stream)，单流丢包不影响其余流；\n2. 零 RTT 连接迁移：移动端在 WiFi 和蜂窝网络切换时，TCP 必须断开重连，基于 UDP 的 QUIC 采用 Connection ID 无感迁移；\n3. 用户态快速迭代：UDP 在应用层实现控制逻辑，无须升级操作系统内核即可快速部署新算法。"
            }
        ]
    },

    {
        "id": "dns-resolution",
        "name": "DNS 域名解析系统 (Domain Name System)",
        "aliases": [
            "dns",
            "域名解析",
            "递归查询",
            "迭代查询",
            "dns解析",
            "hosts",
            "a记录",
            "cname"
        ],
        "category": "计算机网络与协议",
        "definition": "将人类易记的域名（如 github.com）映射为计算机路由寻址所需的数字 IP 地址（如 140.82.112.3）的分布式分层命名系统。",
        "detailed_explanation": "客户端解析优先查找本地 Hosts 与浏览器/系统 DNS 缓存，未命中则请求本地递归 DNS 服务器，递归服务器依次向根域名服务器(.)、顶级域名服务器(.com)、权威域名服务器发起迭代查询，最终获得 A/AAAA 记录并设置 TTL 缓存。",
        "project_relevance": "vibe-learning 服务默认绑定 127.0.0.1 本地回环地址，避免经由外部网络 DNS 解析和路由，确保本机数据绝对私密不外泄。",
        "related_concepts": [
            "http-protocol",
            "tcp-protocol",
            "udp-protocol"
        ],
        "interview_questions": [
            {
                "question": "【百度/快手】输入 URL 后 DNS 解析的完整流程是怎样的？DNS 劫持是什么？如何防范？",
                "answer": "1. 流程：浏览器缓存 -> 系统 Hosts -> 本地 DNS 递归服务器 -> 根域名服务器 -> 顶级域名服务器 -> 权威服务器 -> 缓存并返回；\n2. DNS 劫持：黑客或中间网关篡改 DNS 响应包，返回伪造的恶意 IP 地址；\n3. 防范：采用 DoH (DNS over HTTPS) 或 DoT (DNS over TLS) 进行加密传输防篡改，部署 HTTPDNS 绕过传统运营商 LocalDNS。"
            }
        ]
    },

    {
        "id": "tls-ssl-protocol",
        "name": "TLS / SSL 传输层安全协议",
        "aliases": [
            "tls",
            "ssl",
            "https证书",
            "数字证书",
            "非对称加密",
            "对称加密",
            "ca证书",
            "tls握手"
        ],
        "category": "计算机网络与协议",
        "definition": "运行在传输层 TCP 之上的安全加密协议族（Transport Layer Security），为上层应用协议提供数据机密性、完整性校验与身份鉴别支持。",
        "detailed_explanation": "结合了非对称加密与对称加密优势：握手阶段通过非对称加密（如 ECDHE 椭圆曲线临时密钥交换）校验数字证书合法性并协商出会话对称主密钥；后续应用数据传输全部采用极速对称加密算法（如 AES-GCM 或 ChaCha20）。",
        "project_relevance": "配置外部模型（如 OpenAI / Claude / Kimi API）时，SDK 均通过 TLS 1.3 建立加密隧道，确保 API Key 与敏感数据不被中间人窃听。",
        "related_concepts": [
            "http-protocol",
            "tcp-protocol",
            "blake2b-hash"
        ],
        "interview_questions": [
            {
                "question": "【腾讯/阿里安全】TLS 1.2 与 TLS 1.3 握手有什么重大改进？ECDHE 相比传统 RSA 握手有什么优势？",
                "answer": "1. 握手速度大幅提升：TLS 1.2 完整握手需要 2-RTT，TLS 1.3 精简到 1-RTT，恢复连接支持 0-RTT；\n2. 安全性更强：废弃了易受攻击的静态 RSA 密钥交换；\n3. 前向安全性（Forward Secrecy）：ECDHE 每次握手动态生成临时密钥对，即便服务端的长期私钥未来泄漏，也无法解密过去已捕获的历史流量。"
            }
        ]
    },

    {
        "id": "http3-quic-protocol",
        "name": "HTTP/3 与 QUIC 传输协议",
        "aliases": [
            "http/3",
            "http3",
            "quic",
            "quic协议",
            "连接迁移",
            "0-rtt"
        ],
        "category": "计算机网络与协议",
        "definition": "第三代超文本传输协议，彻底放弃底层 TCP，基于 UDP 协议自研 QUIC 传输层实现，兼具极速建连与多流防阻塞特性。",
        "detailed_explanation": "从根源上消除了 TCP 协议固有的传输层队头阻塞问题。内置 TLS 1.3 原生加密，首次握手仅需 1-RTT，复用连接支持 0-RTT 极速请求，支持根据 Connection ID 实现跨网络环境的无感连接迁移。",
        "project_relevance": "现代高性能分布式通信的前沿选型基准，与经典 HTTP/1.1 和 HTTP/2 进行全维度架构能力对照。",
        "related_concepts": [
            "http-protocol",
            "udp-protocol",
            "tls-ssl-protocol"
        ],
        "interview_questions": [
            {
                "question": "【字节/快手架构】HTTP/2 已经有了多路复用，为什么还会存在队头阻塞？HTTP/3 是如何解决的？",
                "answer": "1. HTTP/2 的局限：多路复用在应用层实现，但底层依然依赖单条 TCP 连接。一旦网络发生丢包，TCP 必须等待该丢失包重传成功后才能滑动窗口，导致整条连接所有后续流阻塞；\n2. HTTP/3 解决思路：基于 UDP 构建多条互相完全隔离的独立流，单个数据包丢失仅阻塞所属流，其余所有数据流仍可并行满速传输。"
            }
        ]
    },

    {
        "id": "grpc-protocol",
        "name": "gRPC 远程过程调用框架",
        "aliases": [
            "grpc",
            "protobuf",
            "protocol buffers",
            "rpc",
            "远程调用",
            "双向流"
        ],
        "category": "分布式系统与微服务",
        "definition": "由 Google 开源的高性能、跨语言 RPC 框架，基于 HTTP/2 协议传输，使用 Protocol Buffers 作为接口定义语言和底层二进制序列化工具。",
        "detailed_explanation": "相比传统 JSON RESTful API，gRPC 具有极高的网络吞吐效率和极小的数据包体积；天然支持一元调用（Unary RPC）、服务端流、客户端流和双向流通信，广泛应用于微服务内部东西向通信。",
        "project_relevance": "与单进程轻量 HTTP/RESTful 架构对比的高性能微服务工业级 RPC 选型标杆。",
        "related_concepts": [
            "http-protocol",
            "jsonl-format",
            "ipc-mechanism"
        ],
        "interview_questions": [
            {
                "question": "【美团/阿里】为什么微服务内部通信广泛采用 gRPC/RPC 而不是直接用 RESTful HTTP/JSON？",
                "answer": "1. 序列化效率极高：Protobuf 采用 Varint 和 Tag 紧凑二进制编码，体积通常只有 JSON 的 1/3~1/5，CPU 序列化/反序列化耗时仅为 JSON 的数分之一；\n2. 严格的类型契约：.proto 文件作为强类型接口单一事实来源，自动生成各语言 SDK；\n3. 多路复用流式支持：天然继承 HTTP/2 连接复用与长连接双向流通信特性。"
            }
        ]
    },

    {
        "id": "mysql-innodb-bplus-tree",
        "name": "MySQL InnoDB 与 B+ 树索引结构",
        "aliases": [
            "mysql",
            "innodb",
            "b+树",
            "b+ tree",
            "聚集索引",
            "非聚集索引",
            "覆盖索引",
            "最左前缀"
        ],
        "category": "数据库与存储引擎",
        "definition": "MySQL 主流存储引擎 InnoDB 采用的核心索引组织形式。非叶子节点仅存储键值指针，所有真实数据记录均顺序存放在最底层的叶子节点并通过双向链表相连。",
        "detailed_explanation": "B+ 树优势在于高扇出（Fan-out）与极低树高（通常 3-4 层即可支撑千万级行记录，大幅减少磁盘 I/O）；聚集索引直接将整行数据挂在主键叶子节点，二级索引叶子节点只存储主键值（需回表查询，通过覆盖索引可消除回表）。遵循最左匹配原则。",
        "project_relevance": "对比轻量级单文件 SQLite 与嵌入式 JSON 文件持久化的优缺点，剖析大型数据存储的索引寻道成本。",
        "related_concepts": [
            "sqlite-db",
            "acid-transactions",
            "cache-concurrency-consistency"
        ],
        "interview_questions": [
            {
                "question": "【阿里/美团】为什么索引选择 B+ 树而不是 B 树、红黑树或哈希表？",
                "answer": "1. 相比哈希表：哈希只支持等值查询（O(1)），无法支持范围查询和 ORDER BY 排序；\n2. 相比红黑树/二叉树：二叉树树高太深，在硬盘上随机 I/O 次数过多；\n3. 相比 B 树：B+ 树非叶子节点不存数据行，单页能容纳更多键值使得树高更低；叶子节点双向链表连接，范围扫描效率远高于 B 树的中序遍历。"
            }
        ]
    },

    {
        "id": "acid-transactions",
        "name": "数据库事务 ACID 与 MVCC 隔离机制",
        "aliases": [
            "acid",
            "mvcc",
            "事务隔离级别",
            "幻读",
            "不可重复读",
            "read view",
            "undo log"
        ],
        "category": "数据库与存储引擎",
        "definition": "关系型数据库保障可靠操作的核心事务理论（原子性、一致性、隔离性、持久性），以及利用多版本并发控制（MVCC）解决读写并发冲突的实现机制。",
        "detailed_explanation": "MySQL 默认可重复读（Repeatable Read）隔离级别通过 Undo Log 版本链和活跃事务数组（Read View）实现一致性非锁定读（快照读），在不加表锁的前提下通过 Next-Key Lock 算法彻底防御幻读与脏读。",
        "project_relevance": "vibe-learning 的事件文件追加与状态更新虽然基于单机文件锁，但在并发持久化上同样借鉴了 ACID 的原子写入与防数据破坏理念。",
        "related_concepts": [
            "mysql-innodb-bplus-tree",
            "redis-distributed-lock",
            "threading-concurrency"
        ],
        "interview_questions": [
            {
                "question": "【腾讯/美团】InnoDB 是如何通过 MVCC 解决不可重复读问题的？Read View 是如何比对事务版本的？",
                "answer": "Read View 包含 m_ids（活跃未提交事务列表）、min_trx_id（最小活跃事务）、max_trx_id（预分配下一事务 ID）。比对记录的 DB_TRX_ID：\n1. 小于 min_trx_id：已提交事务，当前可见；\n2. 大于 max_trx_id：未来事务，当前不可见；\n3. 介于两者之间：若在 m_ids 中说明尚未提交不可见，顺着 Undo Log 回溯找到第一个可见的历史版本数据并返回。"
            }
        ]
    },

    {
        "id": "cap-base-theorem",
        "name": "分布式 CAP 定理与 BASE 理论",
        "aliases": [
            "cap定理",
            "base理论",
            "最终一致性",
            "分区容错性",
            "分布式一致性"
        ],
        "category": "分布式系统与微服务",
        "definition": "分布式系统设计的黄金定律：一个分布式系统不可能同时满足一致性（Consistency）、可用性（Availability）、分区容错性（Partition Tolerance）。",
        "detailed_explanation": "由于网络分区不可避免，分布式系统必须保证 P，因此只能在 CP（强一致但牺牲可用性，如 ZooKeeper、Raft）与 AP（高可用但牺牲强一致性，如 Eureka）之间权衡。大型系统大多遵循 BASE 理论：基本可用、软状态、最终一致性。",
        "project_relevance": "帮助理解分布式 Agent 协同、状态多节点同步与缓存一致性的底层设计取舍。",
        "related_concepts": [
            "raft-consensus",
            "redis-distributed-lock",
            "cache-concurrency-consistency"
        ],
        "interview_questions": [
            {
                "question": "【阿里/字节架构】注册中心设计中，Nacos 为什么支持 AP 和 CP 模式平滑切换？",
                "answer": "无状态微服务实例采用轻量级 Distro 协议走 AP 模式保证高可用，优先保活业务链路；针对配置中心强一致要求走 Raft 协议保证 CP 模式，杜绝配置漂移。"
            }
        ]
    },

    {
        "id": "raft-consensus",
        "name": "Raft 分布式共识一致性算法",
        "aliases": [
            "raft",
            "共识算法",
            "leader选举",
            "日志复制",
            "脑裂",
            "etcd raft"
        ],
        "category": "分布式系统与微服务",
        "definition": "为了解决传统 Paxos 晦涩难懂而设计的分布式共识算法。将状态机复制分解为三大独立子问题：Leader 选举、Log 复制和安全性。",
        "detailed_explanation": "节点分为 Leader、Follower、Candidate 三种角色。通过心跳超时随机化有效避免选票瓜分，依靠“大多数原则（Quorum）”保证已提交日志绝不丢失，并天然防止脑裂。",
        "project_relevance": "解析现代微服务配置中心（etcd, Consul）与集群管理的状态同步真理基石。",
        "related_concepts": [
            "cap-base-theorem",
            "acid-transactions"
        ],
        "interview_questions": [
            {
                "question": "【字节/美团】Raft 算法如何防止“脑裂”？",
                "answer": "只有获得超过半数（N/2 + 1）节点赞成票的候选人才能成为 Leader；网络分区时少数派分区的 Leader 无法收到多数派日志确认，写操作无法 Commit，网络恢复后主动降级覆盖日志。"
            }
        ]
    },

    {
        "id": "vector-db-ann",
        "name": "向量数据库与近似最近邻检索 (Vector DB & ANN)",
        "aliases": [
            "vector db",
            "向量数据库",
            "ann",
            "近似最近邻",
            "hnsw",
            "milvus",
            "faiss",
            "余弦相似度"
        ],
        "category": "AI算法与检索",
        "definition": "专为存储、管理和高效检索大模型 Embedding 高维向量而设计的数据库系统。通过近似最近邻（ANN）算法在万亿维空间中实现毫秒级 Top-K 语义匹配。",
        "detailed_explanation": "常用检索算法包括分层小世界图（HNSW，基于多层跳表和图跳跃实现对数级搜索复杂度）与倒排文件量化（IVF-PQ）。结合元数据标量过滤，解决非结构化数据到高维语义空间的查询诉求。",
        "project_relevance": "vibe-learning 的 RAG 知识检索模块底层技术基石：通过向量相似度计算秒级召回相关联的技术考点与八股原题。",
        "related_concepts": [
            "rag-pattern",
            "embedding-vector",
            "recsys-recall-multi-channel"
        ],
        "interview_questions": [
            {
                "question": "【商汤/阿里AI】HNSW 算法为什么能在海量高维向量检索中大幅领先传统 KD-Tree？",
                "answer": "KD-Tree 在维度大于 10 时性能退化为线性全表扫描，HNSW 将跳表思想迁移到图上，高层大步跳跃快速定位候选簇，底层局部贪婪收敛，检索时间复杂度维持在稳定的 O(log N)。"
            }
        ]
    },

    {
        "id": "embedding-vector",
        "name": "Embedding 语义嵌入向量",
        "aliases": [
            "embedding",
            "语义向量",
            "稠密向量",
            "向量嵌入",
            "text-embedding",
            "向量空间"
        ],
        "category": "AI算法与检索",
        "definition": "将文本、代码等离散高维稀疏符号映射到连续、低维（如 768 / 1536 维）实数稠密向量空间的数学表征技术。",
        "detailed_explanation": "在 Embedding 空间中，向量方向与距离直接表征语义相关度。语义相近的内容在向量空间中夹角极小（余弦相似度接近 1）。广泛应用于语义搜索、推荐系统与 RAG 检索。",
        "project_relevance": "在 RAG 知识图谱检索与单文件全景分析中，将代码上下文与面试知识库转化为向量进行相关度计算与考点命中。",
        "related_concepts": [
            "vector-db-ann",
            "rag-pattern",
            "recsys-recall-multi-channel"
        ],
        "interview_questions": [
            {
                "question": "【月之暗面/商汤】余弦相似度与欧氏距离在衡量 Embedding 相似度时有什么联系？",
                "answer": "如果将向量进行 L2 范数归一化，欧氏距离与余弦相似度呈现严格的反向单调线性对应关系，工程上常借此将余弦运算转化为极速的矩阵内积点积运算。"
            }
        ]
    },

    {
        "id": "cot-reasoning",
        "name": "思维链推理机制 (Chain-of-Thought / CoT)",
        "aliases": [
            "cot",
            "思维链",
            "chain of thought",
            "step by step",
            "一步一步思考",
            "零样本思维链"
        ],
        "category": "Agent算法",
        "definition": "大语言模型的一种关键提示与推理增强技术。通过引导模型在输出最终答案前显式生成中间推理步骤，显著提升复杂逻辑与代码编写的准确率。",
        "detailed_explanation": "在预训练规模超过涌现门槛后，CoT 能有效将长链决策在自回归生成中转化为多个短程条件概率计算，缓解直接生成答案导致的幻觉与逻辑短路。现代推理模型（如 o1, R1）已将 CoT 深度内化为长链自反思强化学习行为。",
        "project_relevance": "vibe-learning 的 Agent 分析提示词要求模型在给出结论前分步显式拆解：改了哪里 -> 意味着什么 -> Agent 意图解构 -> 知识点提取。",
        "related_concepts": [
            "planning-tot-got",
            "reflection-self-refine",
            "react-pattern"
        ],
        "interview_questions": [
            {
                "question": "【DeepSeek/字节AI】为什么简单的“Let'''s think step by step”能大幅提升模型推理能力？",
                "answer": "自回归生成的每一个中间推理 Token 都会进入 KV Cache，后续生成可以直接将注意力集中于这些前序推导事实，本质上将复杂问题分解为了多次多步增量计算。"
            }
        ]
    },

    {
        "id": "transformer-architecture",
        "name": "Transformer 神经网络架构与自注意力机制",
        "aliases": [
            "transformer",
            "self-attention",
            "自注意力",
            "多头注意力",
            "qkv",
            "位置编码",
            "ffn"
        ],
        "category": "AI算法与检索",
        "definition": "彻底颠覆自然语言处理与大模型的深度学习基础架构。全面采用基于 Query、Key、Value 的缩放点积自注意力机制实现全局并行计算。",
        "detailed_explanation": "核心组成包括：Multi-Head Attention（多子空间捕获长程依赖）、RoPE 旋转位置编码、Feed-Forward Network、RMSNorm 层归一化与残差连接。现代大模型无一例外均基于 Transformer 架构演进。",
        "project_relevance": "所有接入的底层分析大模型（Kimi / OpenAI / DeepSeek）的物理计算基础与架构源泉。",
        "related_concepts": [
            "kv-cache-acceleration",
            "cot-reasoning",
            "post-training-sft-lora"
        ],
        "interview_questions": [
            {
                "question": "【商汤/腾讯】Self-Attention 计算中为什么要除以根号 d_k？",
                "answer": "防止向量维度很大时点积绝对值过大导致 Softmax 进入饱和区引发梯度消失，除以 sqrt(d_k) 将方差稳定缩放回 1。"
            }
        ]
    },

    {
        "id": "kv-cache-acceleration",
        "name": "KV Cache 显存加速机制",
        "aliases": [
            "kv cache",
            "键值缓存",
            "自回归解码",
            "prefill",
            "decoding",
            "显存瓶颈"
        ],
        "category": "AI算法与检索",
        "definition": "大语言模型自回归逐词生成中的关键优化技术。通过缓存前序所有已生成 Token 的 Key 和 Value 矩阵，避免在每生成新词时重复计算历史序列的全量注意力。",
        "detailed_explanation": "生成过程拆分为 Prefill（预填充，并行计算并写入 KV Cache）和 Decoding（利用缓存以 O(1) 仅计算新词 Q）。代价是线性吞噬大量 GPU 显存，推动了 PagedAttention、MQA 与 GQA 诞生。",
        "project_relevance": "解释长会话流式响应时显存占用激增的本质原因，也是长文本 Agent 上下文工程需要进行压缩修剪的底层物理瓶颈所在。",
        "related_concepts": [
            "transformer-architecture",
            "context-harness",
            "token-budget"
        ],
        "interview_questions": [
            {
                "question": "【字节/DeepSeek】PagedAttention 是如何解决传统 KV Cache 显存碎片问题的？",
                "answer": "借鉴操作系统虚拟内存分页思想，将 KV Cache 切分为固定大小的物理 Block，通过页表将逻辑连续序列映射到离散物理显存上，实现零显存浪费。"
            }
        ]
    },

    {
        "id": "llm-sampling-hyperparameters",
        "name": "大模型采样超参数 (Temperature & Top-p)",
        "aliases": [
            "temperature",
            "top-p",
            "采样参数",
            "核采样",
            "top-k",
            "随机性控制",
            "logits"
        ],
        "category": "AI算法与检索",
        "definition": "大模型在输出层将未归一化的原始 Logits 转化为下一个 Token 概率分布时的随机性与确定性控制策略。",
        "detailed_explanation": "Temperature 调整分布平滑度：越小确定性越高，越大多样性越强。Top-p 核采样仅从累计概率达到阈值 p 的候选集合中采样，截断低概率长尾词。",
        "project_relevance": "vibe-learning 的 Agent 分析任务需要稳定的 JSON 契约输出，因此分析请求默认将 Temperature 设定为 0.1~0.2，防止格式漂移。",
        "related_concepts": [
            "cot-reasoning",
            "prompt-engineering",
            "token-budget"
        ],
        "interview_questions": [
            {
                "question": "【美团/字节AI】在要求生成结构化 JSON 的 Agent 场景下，采样参数如何设置？",
                "answer": "设为 0.1~0.2 兼顾确定性与适度语义平滑，避免 T 过高引发 JSON 语法崩溃，也避免纯贪婪采样引发长文本重复字符死循环。"
            }
        ]
    },

    {
        "id": "js-event-loop",
        "name": "JavaScript 事件循环与异步并发 (Event Loop)",
        "aliases": [
            "event loop",
            "事件循环",
            "宏任务",
            "微任务",
            "macrotask",
            "microtask",
            "promise",
            "call stack"
        ],
        "category": "前端工程",
        "definition": "浏览器与 Node.js 运行时的单线程非阻塞异步调度模型。通过调用栈、微任务队列与宏任务队列的协调，实现异步 I/O 与 UI 平滑渲染。",
        "detailed_explanation": "执行主线程同步代码 -> 清空调用栈 -> 依序清空当前所有微任务（Promise.then, queueMicrotask）-> 检查执行浏览器 UI 渲染 -> 从宏任务队列取出下一个任务执行，周而复始。",
        "project_relevance": "vibe-learning 前端在处理高频 SSE 事件流推送和 SVG 图谱重绘时，严格利用微任务节流与 requestAnimationFrame 避免主线程卡顿。",
        "related_concepts": [
            "web-worker-concurrency",
            "sse-streaming-rendering",
            "react-virtual-dom-fiber"
        ],
        "interview_questions": [
            {
                "question": "【字节/腾讯前端】微任务和宏任务的执行优先级规律？",
                "answer": "每执行完一个宏任务，浏览器会立即一次性清空此时排队的所有微任务，全部清空后才允许尝试渲染并执行下一个宏任务。"
            }
        ]
    },

    {
        "id": "web-worker-concurrency",
        "name": "Web Worker 浏览器多线程计算",
        "aliases": [
            "web worker",
            "浏览器多线程",
            "postmessage",
            "离线计算",
            "worker线程"
        ],
        "category": "前端工程",
        "definition": "HTML5 提供的在浏览器后台运行独立 JavaScript 线程的能力，允许执行耗时的高 CPU 计算任务而不抢占主线程 UI 渲染。",
        "detailed_explanation": "Worker 线程与主线程通过 postMessage 通信，无法直接访问 DOM、window 和 document，确保了主线程 DOM 操作的线程安全。",
        "project_relevance": "前端架构设计对比：超大型代码仓库进行客户端 PageRank 权重计算时，可置入 Web Worker 避免界面滚屏拖拽卡顿。",
        "related_concepts": [
            "js-event-loop",
            "threading-concurrency",
            "svg-vs-canvas"
        ],
        "interview_questions": [
            {
                "question": "【阿里前端】Web Worker 传输大数据时如何避免内存拷贝？",
                "answer": "使用 Transferable Objects（可转移对象，如 ArrayBuffer），直接零拷贝移交内存地址所有权。"
            }
        ]
    },

    {
        "id": "svg-vs-canvas",
        "name": "SVG 与 Canvas 现代前端图形渲染架构",
        "aliases": [
            "svg",
            "canvas",
            "矢量图",
            "位图渲染",
            "图形渲染",
            "svg渲染"
        ],
        "category": "前端工程",
        "definition": "Web 前端两大核心绘图渲染体系：SVG（基于 XML 标签的保留模式矢量图形，每个形状都是独立 DOM 节点）；Canvas（基于像素网格的立即模式位图画布）。",
        "detailed_explanation": "SVG 矢量无限放大不失真、支持 CSS 样式与原生事件监听；Canvas 像素渲染极快适合百万级密集渲染。工业级常采用混合架构。",
        "project_relevance": "vibe-learning 的拓扑网图与分层组件卡全面选用 SVG 与现代 CSS 结合：利用矢量无损缩放特性与原生事件交互，精准实现节点 hover 联动高亮和点击全景分析。",
        "related_concepts": [
            "web-worker-concurrency",
            "react-virtual-dom-fiber"
        ],
        "interview_questions": [
            {
                "question": "【腾讯/字节可视化】SVG 和 Canvas 应该如何做技术选型？",
                "answer": "节点多、事件少选 Canvas；节点结构丰富、需要复杂样式、独立事件和高清缩放选 SVG；海量背景节点用 Canvas、顶层交互节点用 SVG 混合架构最佳。"
            }
        ]
    },

    {
        "id": "ipc-mechanism",
        "name": "IPC 进程间通信机制 (Inter-Process Communication)",
        "aliases": [
            "ipc",
            "进程间通信",
            "管道",
            "pipe",
            "unix socket",
            "共享内存",
            "信号量"
        ],
        "category": "操作系统与并发编程",
        "definition": "操作系统提供给不同进程之间进行数据交换、协同同步的一系列系统调用接口（包括匿名/命名管道、Unix Domain Socket、共享内存等）。",
        "detailed_explanation": "共享内存是速度最快的 IPC 机制（零拷贝，需配合信号量/互斥锁）；Unix Domain Socket 免去 TCP/IP 协议栈封包解包，本机吞吐极高；管道常用于父子进程单向字节流传输。",
        "project_relevance": "vibe-learning 监听各 Coding Agent 会话时，Claude Code 的 Hook 脚本与本地服务之间、以及与操作系统终端管道之间的数据交换正是典型进程间通信应用。",
        "related_concepts": [
            "threading-concurrency",
            "cwd-process-context",
            "grpc-protocol"
        ],
        "interview_questions": [
            {
                "question": "【阿里系统级】为什么共享内存速度最快？如何保证安全？",
                "answer": "直接将同一块物理内存映射到不同进程虚拟地址空间，读写零系统调用和零内存拷贝；必须配合信号量或进程互斥锁防脏写竞态。"
            }
        ]
    },

    {
        "id": "cwd-process-context",
        "name": "CWD 当前工作目录与进程上下文 (Current Working Directory)",
        "aliases": [
            "cwd",
            "当前工作目录",
            "工作目录",
            "pwd",
            "进程上下文",
            "相对路径解析"
        ],
        "category": "操作系统与并发编程",
        "definition": "操作系统为每个运行中的进程在内核 PCB 中维护的核心属性，指示该进程在解析相对文件路径时的根起始点。",
        "detailed_explanation": "子进程默认继承父进程的 CWD。在多 Agent 协同和自动化脚手架中，CWD 是判定 Agent 当前身处哪个项目目录、改动文件落入哪个物理工程的唯一证据。",
        "project_relevance": "vibe-learning 的核心归因算法（tailer.attribute）：严格根据各平台 Agent 会话中的 cwd 属性比对已登记的项目列表，实现会话轮次的绝对唯一目录归因。",
        "related_concepts": [
            "git-vcs",
            "ipc-mechanism"
        ],
        "interview_questions": [
            {
                "question": "【字节基础架构】在多线程程序中调用 chdir() 会有什么后果？",
                "answer": "CWD 是进程级全局属性，所有线程共享；一个线程调用 chdir() 会瞬间导致其他线程解析相对路径错位引发读写越权灾难，多线程并发禁止调用全局 chdir()。"
            }
        ]
    },

    {
        "id": "prompt-engineering",
        "name": "提示词工程与结构化约束 (Prompt Engineering)",
        "aliases": [
            "prompt",
            "提示词工程",
            "system prompt",
            "少样本提示",
            "few-shot",
            "结构化输出",
            "json schema"
        ],
        "category": "Agent应用开发",
        "definition": "通过精细设计输入提示文本结构、角色设定、上下文注入与输出 Schema 约束，最大化激发大模型推理潜力并获得稳定确定性输出的系统性方法论。",
        "detailed_explanation": "生产级 Prompt 工程依赖防注入、防越狱、思维链路约束与 JSON/XML 标签闭合校验。通过前置约束（如“严格只返回一个 JSON 对象”），将非结构化智能安全锚定在结构化工程管道中。",
        "project_relevance": "vibe-learning 的 agent/prompts.py 精心打造了对话解构与系统架构抽象提示词，强制模型输出固定版本 Schema，是系统高质量分析图谱的基石。",
        "related_concepts": [
            "cot-reasoning",
            "context-harness",
            "token-budget"
        ],
        "interview_questions": [
            {
                "question": "【阿里AI】如何确保大模型严格只输出合法 JSON？",
                "answer": "启用结构化输出接口（response_format: json_object）、提示词尾部强力引导、后处理鲁棒正则剥离与 JSON.parse 失败自动重试机制。"
            }
        ]
    },

    {
        "id": "token-budget",
        "name": "Token 概念与上下文预算控制 (Token & Context Budget)",
        "aliases": [
            "token",
            "分词",
            "tokenizer",
            "bpe",
            "上下文预算",
            "token预算",
            "上下文窗口"
        ],
        "category": "AI算法与检索",
        "definition": "大语言模型进行文本处理、注意力计算与计费的最小原子分词单位。一个 Token 通常对应约 0.75 个英文单词或 0.5~1 个中文字符。",
        "detailed_explanation": "主流分词器采用 BPE 字节对编码。上下文窗口受模型自身架构和注意力退化曲线制约，Agent 循环中必须实时计算与管理 Token 预算，对长文本进行动态截断与折叠。",
        "project_relevance": "vibe-learning 快照与分析引擎执行严格的预算管理：单文件上限 512KB、总文本上限 64MB，会话截断保护，确保送入模型的 Token 不会超出窗口预算。",
        "related_concepts": [
            "kv-cache-acceleration",
            "context-harness",
            "prompt-engineering"
        ],
        "interview_questions": [
            {
                "question": "【字节/DeepSeek】BPE 分词算法如何杜绝未登录词（OOV）？",
                "answer": "BPE 基础词表包含全部 256 个底层字节，任何生僻词都可以被拆解为底层字节进行编码，实现 100% 字符覆盖。"
            }
        ]
    },

    {
        "id": "sqlite-db",
        "name": "SQLite 嵌入式轻量关系数据库",
        "aliases": [
            "sqlite",
            "sqlite3",
            "嵌入式数据库",
            "单文件数据库",
            "wal模式"
        ],
        "category": "数据库与存储引擎",
        "definition": "零配置、无服务器进程、单文件存储的自给自足式嵌入式 ACID 关系数据库引擎。",
        "detailed_explanation": "采用 B-tree 组织表数据与索引，直接内嵌在宿主进程内存中运行，免除网络 IPC 开销。启用 WAL（Write-Ahead Logging）预写日志模式后支持读写并发互不阻塞。",
        "project_relevance": "单进程本地桌面与分析工具的最佳伴侣，与 vibe-learning 的单机文件存储架构高度契合。",
        "related_concepts": [
            "mysql-innodb-bplus-tree",
            "acid-transactions"
        ],
        "interview_questions": [
            {
                "question": "【腾讯】SQLite 的 WAL（Write-Ahead Logging）模式相比传统回滚日志（Rollback Journal）有什么性能优势？",
                "answer": "WAL 模式下写操作追加写入独立的 WAL 文件，读操作直接读取原数据库或 WAL 对应版本，实现了读不阻塞写、写不阻塞读的并发提升。"
            }
        ]
    },

    {
        "id": "cors-cross-origin",
        "name": "CORS 跨域资源共享与预检请求 (Cross-Origin Resource Sharing)",
        "aliases": [
            "cors",
            "跨域",
            "同源策略",
            "options请求",
            "预检请求",
            "access-control-allow-origin"
        ],
        "category": "计算机网络与协议",
        "definition": "浏览器同源策略（协议、域名、端口必须完全相同）下的安全跨域访问规范。通过 HTTP 响应头授权受信任的外部源访问自身资源。",
        "detailed_explanation": "简单请求直接携带 Origin 发送；非简单请求（如携带自定义 Header 或 Content-Type 为 application/json）会先自动触发 OPTIONS 预检请求（Preflight Request），服务器返回 Access-Control-Allow-Origin 等头通过后才允许正式请求通信。",
        "project_relevance": "vibe-learning 允许通过本地浏览器任何端口或外部客户端访问本机的 HTTP/SSE API，需保证跨域头的健壮支持。",
        "related_concepts": [
            "http-protocol",
            "restful-architecture"
        ],
        "interview_questions": [
            {
                "question": "【美团前端】什么是非简单请求？OPTIONS 预检请求为什么会产生？如何减少 OPTIONS 请求次数？",
                "answer": "使用非 GET/POST/HEAD 方法或携带自定义 Header 即为非简单请求；浏览器为确保服务端支持并保护数据安全自动发起预检；服务端设置 Access-Control-Max-Age 缓存预检结果可有效减少请求次数。"
            }
        ]
    },

    {
        "id": "restful-architecture",
        "name": "RESTful API 架构风格与幂等性设计",
        "aliases": [
            "restful",
            "rest架构",
            "幂等性",
            "http动词",
            "无状态api"
        ],
        "category": "计算机网络与协议",
        "definition": "表现层状态转移（Representational State Transfer），一种基于标准 HTTP 协议动词（GET, POST, PUT, DELETE, PATCH）的资源定位与操作架构风格。",
        "detailed_explanation": "核心设计原则：资源具有统一 URI 标识；无状态（Stateless，服务端不保存客户端上下文会话）；动词语义明确（GET 读安全幂等，PUT 全量更新幂等，DELETE 幂等，POST 非幂等）；通过标准状态码（200, 201, 400, 404, 500）表达结果。",
        "project_relevance": "vibe-learning 的全部 API 遵循 RESTful 规范：GET /api/map 获取图谱、GET /api/file_analysis 获取文件分析、POST /api/config 提交配置变更。",
        "related_concepts": [
            "http-protocol",
            "grpc-protocol",
            "cors-cross-origin"
        ],
        "interview_questions": [
            {
                "question": "【阿里/字节】高并发接口设计中，如何保证 POST 接口的绝对幂等性？",
                "answer": "客户端先请求生成全局唯一 Token/RequestId，在发起 POST 请求时携带该 Token；服务端利用 Redis 的 SETNX 或数据库唯一索引进行校验拦截，已处理则直接返回历史结果。"
            }
        ]
    },

    {
        "id": "monorepo-architecture",
        "name": "Monorepo 单体多包仓库工程架构",
        "aliases": [
            "monorepo",
            "多包仓库",
            "pnpm workspace",
            "turbo",
            "lerna",
            "单体仓库"
        ],
        "category": "工程效率与工具",
        "definition": "将多个独立发布的模块、应用、微服务或跨平台 SDK 存放在同一个版本控制仓库中进行统一构建、版本联动与依赖共享的软件工程架构模式。",
        "detailed_explanation": "相比多仓库（Polyrepo），Monorepo 具有原子化跨包重构、零发包本地依赖调试、依赖统一去重（通过 pnpm workspace 硬链接）优势；配合 Turborepo / Nx 进行基于变更图（Dependency Graph）的增量缓存构建。",
        "project_relevance": "vibe-learning 在扫描大型项目时需识别 Monorepo 多包结构，分别提取不同包的清单文件并识别依赖流向。",
        "related_concepts": [
            "git-vcs",
            "cicd-pipeline",
            "ast-code-inspect"
        ],
        "interview_questions": [
            {
                "question": "【字节/美团前端工程化】Monorepo 随着代码量急剧膨胀，构建变慢与 Git 拉取卡顿如何解决？",
                "answer": "引入基于任务依赖图的增量构建缓存（Remote Cache，相同源码与依赖直接命中缓存秒级跳过）；Git 采用稀疏检出（Sparse Checkout）与浅克隆（Shallow Clone）仅拉取当前开发子包。"
            }
        ]
    },

    {
        "id": "cicd-pipeline",
        "name": "CI/CD 持续集成与持续部署流水线",
        "aliases": [
            "ci/cd",
            "持续集成",
            "持续部署",
            "github actions",
            "自动化流水线",
            "测试门禁"
        ],
        "category": "工程效率与工具",
        "definition": "现代软件交付的自动化基石：持续集成（代码提交后自动触发 Lint 检查、单元测试与构建）；持续部署（通过自动化门禁后无缝发布至预发或生产环境）。",
        "detailed_explanation": "以 GitHub Actions、GitLab CI 为代表，基于事件驱动触发（Push, Pull Request）。核心门禁包括代码风格检查（Lint）、单元测试与分支覆盖率（Code Coverage）、静态代码安全扫描（SAST）与构建打包制品产出。",
        "project_relevance": "确保代码与分析系统的健壮性，防止任何无感知回归破坏系统稳定性。",
        "related_concepts": [
            "git-vcs",
            "docker-container",
            "monorepo-architecture"
        ],
        "interview_questions": [
            {
                "question": "【腾讯DevOps】如何对大型项目的 CI 流水线从 30 分钟优化到 3 分钟？",
                "answer": "1. 依赖与构建产物分层缓存（如 actions/cache）；\n2. 任务矩阵并发执行（Matrix Parallelism，测试用例分片并发跑）；\n3. 基于 Git Diff 的增量测试（仅测试改动模块及其下游直接依赖包）；\n4. 使用更高效工具链（如 esbuild / swc 替代传统打包器）。"
            }
        ]
    },

    {
        "id": "docker-container",
        "name": "Docker 容器化与 Linux 命名空间隔离",
        "aliases": [
            "docker",
            "容器化",
            "namespace",
            "cgroups",
            "unionfs",
            "镜像分层",
            "沙箱"
        ],
        "category": "工程效率与工具",
        "definition": "基于 Linux 内核隔离特性的轻量级操作系统级虚拟化技术。将应用程序及其所有运行时依赖打包为一个轻量、可移植的独立容器镜像。",
        "detailed_explanation": "三大底层基石：1. Linux Namespaces（实现 pid、mount、net、ipc、uts 等视图隔离）；2. Control Groups (Cgroups，限制 CPU、内存、I/O 资源配额)；3. UnionFS（联合文件系统，如 OverlayFS，实现镜像只读层共享与读写层轻量追加）。",
        "project_relevance": "为 Agent 提供安全可控的隔离执行环境（Sandbox），防止智能体产生破坏宿主机系统的风险操作。",
        "related_concepts": [
            "ipc-mechanism",
            "cicd-pipeline"
        ],
        "interview_questions": [
            {
                "question": "【阿里/美团云原生】Docker 容器和传统虚拟机（VM）有什么本质区别？",
                "answer": "虚拟机基于 Hypervisor 虚拟化物理硬件并运行完整的独立客户操作系统（Guest OS），启动慢、资源开销数 GB；Docker 容器直接共享宿主机操作系统内核，仅通过 Namespaces 和 Cgroups 进行进程级别的视图隔离与资源限额，秒级启动、近乎原生性能。"
            }
        ]
    },

    {
        "id": "polling-long-polling",
        "name": "轮询与长轮询调度机制 (Polling & Long Polling)",
        "aliases": [
            "polling",
            "轮询",
            "长轮询",
            "long polling",
            "短轮询",
            "定时拉取"
        ],
        "category": "计算机网络与协议",
        "definition": "客户端定期向服务端主动发起请求以检测状态更新的通信模式。短轮询固定时间间隔反复请求；长轮询服务端在无新数据时保持连接挂起，直到有更新或超时才返回。",
        "detailed_explanation": "短轮询实现最简单，但高频请求会带来巨大网络握手开销与服务端空转压力；长轮询显著降低空请求，但长期占用服务端线程/连接。现代实时流式广播普遍推荐采用单向长连接 SSE 替代轮询。",
        "project_relevance": "vibe-learning 的双重保障设计：前端默认优先通过 SSE 实时监听事件推送，同时配合 45 秒温和轮询兜底，既保证极速响应又杜绝断网漏事件。",
        "related_concepts": [
            "sse-eventsource",
            "websocket-protocol",
            "http-protocol"
        ],
        "interview_questions": [
            {
                "question": "【快手前端】短轮询、长轮询、SSE 与 WebSocket 的核心演进与选型逻辑？",
                "answer": "短轮询适合低频低实时状态查询；长轮询是老旧浏览器不支持 HTML5 时的妥协；SSE 是标准 HTTP 单向事件流，极适合 AI 打字机和状态广播；WebSocket 是全双工双向交互，适合在线协同文档与实时联机游戏。"
            }
        ]
    }
]

from knowledge.bank_ext import EXTRA_ENTRIES  # noqa: E402

KNOWLEDGE_ENTRIES = KNOWLEDGE_ENTRIES + EXTRA_ENTRIES

import re
import unicodedata


def normalize_term(term):
    return re.sub(r'[\s_\-]+', ' ', unicodedata.normalize('NFKC', str(term)).strip().lower())


ID_INDEX = {k['id']: k for k in KNOWLEDGE_ENTRIES}
assert len(ID_INDEX) == len(KNOWLEDGE_ENTRIES), 'Duplicate knowledge IDs'
KEYWORD_MAP = {}
for entry in KNOWLEDGE_ENTRIES:
    names = re.split(r'[()（）]', entry['name'])
    aliases = [*entry.get('aliases', []), entry['name'], entry['id'], *names]
    entry['aliases'] = list(dict.fromkeys(a.strip() for a in aliases if len(a.strip()) >= 2))
    for alias in entry['aliases']:
        KEYWORD_MAP[normalize_term(alias)] = entry['id']
    for question in entry.get('interview_questions', []):
        if not question.get('source_url'):
            question['question'] = re.sub(r'^【[^】]+】', '', question['question'])
            question.setdefault('kind', 'curated')

KEYWORD_MAP.update({'react': 'react-library', 'react pattern': 'react-pattern',
                    'sse': 'sse-eventsource', 'rag': 'rag-pipeline',
                    'lora': 'lora-adapter', 'sft': 'sft-training', 'dpo': 'dpo-training'})
SUPPLEMENT_ALIASES = {
    'acid-transactions': ['transaction', 'transactions', 'atomicity', 'consistency', 'isolation', 'durability', '事务'],
    'local-cache': ['cache', 'caching', '缓存', 'cache eviction', 'lru', 'lfu'],
    'tool-use-engineering': ['registry', 'tool registry', '注册表', 'toolkit', '工具集'],
    'rag-pipeline': ['retrieval', 'retriever', '检索', 'rag-pattern'],
    'structured-output': ['schema', 'json schema', 'schema validation', '结构校验', 'validation'],
    'agent-memory-system': ['memory', 'working memory', 'episodic memory', 'semantic memory'],
    'agent-loop': ['agent', 'agents', '智能体', 'agent runtime'],
    'planner-executor': ['planner', 'executor', '规划器', '执行器'],
    'multi-agent-system': ['orchestration', 'orchestrator', '编排', '协调器'],
    'threading-concurrency': ['thread', 'threads', 'concurrency', 'parallelism', '线程', '并行'],
    'prompt-engineering': ['prompt', 'system prompt', 'user prompt', '提示词'],
    'embedding-vector': ['embedding', 'embeddings', 'vector', 'vectors', '向量'],
    'model-quantization': ['quantization', 'int8', 'int4', '量化'],
    'jvm-gc': ['garbage collection', 'gc', '垃圾回收'],
    'polling-long-polling': ['polling', 'poll', '轮询'],
    'restful-architecture': ['rest', 'restful', 'api', 'endpoint', '端点'],
    'git-vcs': ['repository', 'repo', '仓库', '版本库'],
    'ast-code-inspect': ['parser', 'parse', '解析器', 'syntax', '语法'],
    'rate-limiter': ['rate limit', 'rate limiting', '限流'],
    'circuit-breaker': ['fallback', 'retry', 'retries', '重试', '降级'],
    'docker-container': ['container', 'containers', '容器'],
    'token-budget': ['token', 'tokens', 'context window', '上下文窗口'],
}
for identifier, aliases in SUPPLEMENT_ALIASES.items():
    ID_INDEX[identifier]['aliases'] = list(dict.fromkeys(ID_INDEX[identifier]['aliases'] + aliases))
    for alias in aliases:
        KEYWORD_MAP[normalize_term(alias)] = identifier
for entry in KNOWLEDGE_ENTRIES:
    related = []
    for ref in entry.get('related_concepts', []):
        identifier = ref if ref in ID_INDEX else KEYWORD_MAP.get(normalize_term(ref))
        if identifier and identifier != entry['id'] and identifier not in related:
            related.append(identifier)
    entry['related_concepts'] = related
KEYWORD_PATTERNS = []
for term in sorted(KEYWORD_MAP, key=lambda t: (-len(t), t)):
    expression = re.escape(term).replace(r'\ ', r'[\s_\-]+')
    prefix = r'(?<![a-z0-9])' if re.match(r'[a-z0-9]', term) else ''
    suffix = r'(?![a-z0-9])' if re.search(r'[a-z0-9]$', term) else ''
    KEYWORD_PATTERNS.append((re.compile(prefix+expression+suffix, re.I), KEYWORD_MAP[term]))


def get_all_knowledge_entries():
    return KNOWLEDGE_ENTRIES


def get_knowledge_by_id(entry_id):
    return ID_INDEX.get(entry_id)


def match_knowledge_ids(text):
    found = []
    if re.search(r'\bReAct\b', str(text)):
        found.append('react-pattern')
    for pattern, identifier in KEYWORD_PATTERNS:
        if pattern.search(str(text)) and identifier not in found:
            found.append(identifier)
    return found


def find_knowledge_by_term(term):
    if not term:
        return None
    if str(term).strip() == 'ReAct':
        return ID_INDEX['react-pattern']
    cleaned = normalize_term(term)
    entry_id = KEYWORD_MAP.get(cleaned)
    if entry_id:
        return ID_INDEX[entry_id]
    matches = match_knowledge_ids(term)
    return ID_INDEX[matches[0]] if matches else None


def get_frontend_dict():
    return {'entries': ID_INDEX, 'keywords': [
        {'term': term, 'id': KEYWORD_MAP[term], 'category': ID_INDEX[KEYWORD_MAP[term]]['category']}
        for term in sorted(KEYWORD_MAP, key=lambda t: (-len(t), t)) if len(term) >= 2
    ]}


