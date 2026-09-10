"""Agent 应用开发扩展知识包：工具调用、记忆观测、评测安全、多智能体协议与前沿形态。

纯数据模块，无任何 import。由宿主按需加载并合并进主知识库。
"""

EXTRA_ENTRIES = [
    {
        "id": "function-calling",
        "name": "Function Calling 机制 (Function Calling)",
        "aliases": ["function calling", "function-calling", "函数调用", "工具调用", "function call", "tool calling", "函数签名调用", "fc机制", "openai function calling"],
        "category": "Agent应用开发",
        "definition": "Function Calling是大模型把自然语言意图映射为结构化函数调用的机制：模型按JSON Schema声明的参数规范输出函数名与实参，由宿主程序真实执行再把结果回填上下文。它解决了LLM只能动嘴不能动手的问题，是Tool Use的前身，也是ReAct循环落地的工程契约核心。",
        "detailed_explanation": "关键组件有四块：工具声明层（name、description、parameters三元组）、解码约束层（把输出限制在合法函数签名空间）、宿主执行器（鉴权、超时、重试、幂等）、结果回填层（tool result作为新Observation）。典型流程是模型输出tool_call、宿主执行、结果拼回消息继续生成。工程权衡在于Schema粒度：描述越细命中率越高但越耗token；并行调用提速却放大副作用风险。常见坑有幻觉参数名、枚举外取值、数字类型漂移，必须在执行前做Schema二次校验。",
        "project_relevance": "vibe-learning监听会话tool_use块还原调用参数与耗时，SSE推送工具事件，图谱关联工具与文件定位高频风险。",
        "related_concepts": ["tool-use-engineering", "structured-output", "mcp-protocol", "react-pattern"],
        "interview_questions": [
            {
                "question": "【字节】Function Calling线上出现大量参数幻觉（如编造不存在的枚举值），你会从Schema设计和执行链路上怎么根治？",
                "answer": "1. 收紧Schema表达：把开放string改为enum加description示例，必填与格式（正则、范围）前移到声明层，让非法输出在解码阶段就低概率出现。\n2. 执行前二次校验：宿主侧用JSON Schema validator硬校验，失败不进执行器而是把错误信息回填给模型自纠，最多重试两次后转人工或降级。\n3. 语义层兜底：对关键枚举参数加同义词归一化与模糊匹配，匹配失败返回候选列表让模型重选，而不是直接报错中断整条轨迹。"
            },
            {
                "question": "【阿里】模型需要一次调用多个相互依赖的工具（如先查库存再下单），串行与并行调用如何取舍？依赖关系怎么表达？",
                "answer": "1. 有数据依赖的调用必须串行：后一次的参数来自前一次的Observation，并行会因参数缺失必然失败；无依赖的批量查询才适合parallel_tool_calls提速。\n2. 依赖表达靠提示约束而非模型自觉：在system prompt声明依赖顺序规则，或由Planner先产出DAG再逐层执行，把编排权收回到代码侧。\n3. 副作用操作禁用并行：下单、扣款类写操作即使参数齐全也要串行加幂等键，防止重试放大造成资损。"
            }
        ]
    },
    {
        "id": "tool-use-engineering",
        "name": "Agent 工具工程 (Tool Use Engineering)",
        "aliases": ["tool use", "tool-use", "工具使用", "工具工程", "tool schema", "工具设计", "tool calling", "工具封装", "tool definition"],
        "category": "Agent应用开发",
        "definition": "Agent工具工程是把外部能力封装成模型可理解、可调用、可治理的工具集合的实践：每个工具用自然语言描述加JSON Schema定义用途与参数，配鉴权、超时、幂等与可观测性。它解决的是工具多了模型选不对、调用不稳、副作用不可控三大问题，是Function Calling之上的系统工程。",
        "detailed_explanation": "核心组件包括工具注册表（统一命名、版本、owner）、Schema设计（动词命名、参数正交、示例驱动）、执行运行时（沙箱隔离、并发配额、熔断降级）、反馈通道（结构化错误信息供模型自纠）。工作流程是检索候选工具、装配最小工具集进上下文、模型决策调用、执行回填。工程权衡在于工具粒度：大工具省步数但参数复杂易错，小工具精准但轨迹变长；工具数量超过阈值必须做检索预选。常见坑是描述含糊导致误选、副作用工具缺确认、错误信息过于技术化模型看不懂。",
        "project_relevance": "vibe-learning是外挂式工具观测系统：监听Agent工具调用序列，快照校验副作用真实落盘，图谱沉淀高频工具治理证据。",
        "related_concepts": ["function-calling", "mcp-protocol", "agent-skills", "hooks-lifecycle"],
        "interview_questions": [
            {
                "question": "【腾讯】工具库膨胀到上百个时，一次全量塞进上下文既贵又让模型选错，生产级怎么做工具检索与动态装配？",
                "answer": "1. 分层暴露：按任务类型只装配相关分组（如代码任务只给文件与执行工具），用路由分类器或规则先做粗筛，把候选集压到10个以内。\n2. 检索式预选：把工具描述做embedding索引，用用户意图向量检索Top-K，类似RAG思路，兼顾召回与精度。\n3. 兜底机制：模型可主动请求展开更多工具（声明式缺工具时返回工具目录），避免预选漏召回导致任务卡死。"
            },
            {
                "question": "【美团】写操作工具（如删文件、发券）被模型误调造成线上事故，从工具设计上如何系统性防范？",
                "answer": "1. 读写分级：工具元信息标注风险等级，高危工具默认不暴露，仅在Planner明确需要时动态授权，遵循最小权限。\n2. 双层确认：Schema层面要求高危参数显式声明（如confirm=true），运行时拦截走HITL审批，未审批拒绝执行并回填原因。\n3. 可逆设计：删除改软删、发券先冻结后生效，配套幂等键与审计日志，把误调损失从不可逆变为可回滚。"
            }
        ]
    },
    {
        "id": "agent-memory-system",
        "name": "Agent 记忆系统 (Agent Memory System)",
        "aliases": ["agent memory", "agent记忆", "记忆系统", "长期记忆", "短期记忆", "情景记忆", "memory system", "记忆分层", "mem0"],
        "category": "Agent应用开发",
        "definition": "Agent记忆系统是让智能体跨越单次上下文窗口记住信息的基础设施：短期记忆即当前会话上下文窗口，长期记忆是跨会话持久化的事实与偏好，情景记忆存储历史轨迹的经验教训。它解决长任务遗忘用户约束、重复踩坑、无法沉淀经验的问题，是长程Agent从能用到好用的分水岭。",
        "detailed_explanation": "典型分三层：工作记忆（当前prompt内的对话与scratchpad，容量受窗口限制）、情景记忆（历史任务轨迹摘要与反思结论，检索复用）、语义记忆（用户画像、项目事实、领域知识的结构化沉淀）。写入路径靠后台异步摘要压缩避免阻塞主循环，读取路径靠向量加关键词混合检索按需注入。工程权衡是记忆越多幻觉与污染风险越大，需设可信度与过期机制。常见坑是把原始长文无脑存入导致检索噪声、记忆冲突无仲裁、多用户记忆串扰。",
        "project_relevance": "vibe-learning的会话监听天然是记忆素材采集器：把Agent会话轨迹沉淀为可检索的经验事件，项目快照提供记忆落盘的真实性校验，知识图谱则是长期记忆的一种图式组织形态，三者共同构成记忆可观测底座。",
        "related_concepts": ["scratchpad-context", "agentic-rag", "context-harness", "agent-observability"],
        "interview_questions": [
            {
                "question": "【字节】长期记忆写入脏数据（如模型把临时假设记成事实）导致后续任务持续跑偏，如何设计记忆治理机制？",
                "answer": "1. 分级可信度：记忆条目带来源标注（用户明示、工具验证、模型推测），推测类记忆默认低权重，仅在多次复现后升级。\n2. 写入校验：关键事实记忆写入前用工具二次验证（如查代码确认），通不过则只记为待验证假设不参与检索。\n3. 冲突仲裁与过期：新旧记忆冲突时保留时间戳与证据链并提示用户仲裁；时效性记忆设TTL，过期自动降权或归档。"
            },
            {
                "question": "【阿里】上下文窗口越来越大，为什么还需要专门的记忆系统？窗口与记忆的边界怎么划分？",
                "answer": "1. 成本与延迟：全量历史塞窗口token费用线性增长且注意力稀释，记忆检索只注入相关片段，性价比高一个数量级。\n2. 跨会话连续性：窗口随会话结束即焚毁，用户偏好与项目事实必须靠持久化记忆跨会话传递。\n3. 划分原则：窗口放当前任务的即时状态与最近N轮，记忆放可复用的稳定知识；按复用频率决定沉淀什么，一次性细节不进记忆。"
            }
        ]
    },
    {
        "id": "agent-observability",
        "name": "Agent 可观测性 (Agent Observability)",
        "aliases": ["agent observability", "可观测性", "链路追踪", "tracing", "opentelemetry", "otel", "agent tracing", "llm observability", "轨迹追踪"],
        "category": "Agent应用开发",
        "definition": "Agent可观测性是用追踪、指标、日志三件套还原智能体每一步决策与调用链路的能力：每个LLM调用、工具执行、检索动作都记为span并串成trace。它解决Agent黑盒难调试、坏一次不知哪一步坏、成本与延迟无账可查的问题，是Agent从demo走向生产运维的门票。",
        "detailed_explanation": "关键组件是追踪（trace串起Thought、Action、Observation全链）、指标（步数、token、延迟、工具成功率聚合）、日志与录制（完整prompt与回填结果留档复盘）。基于OpenTelemetry语义约定，各span带trace_id父子关联，可跨LLM网关与工具服务透传。工程权衡是全量录制成本高昂，需采样加敏感字段脱敏。常见坑是只记token账不记决策因果、异步工具调用链断裂、把用户隐私原文写进span明文。",
        "project_relevance": "vibe-learning是外挂可观测性实现：监听对应日志采集，快照提供外部证据链，SSE推送实时trace流，图谱聚合成架构视图。",
        "related_concepts": ["agent-evaluation", "agent-loop", "hooks-lifecycle", "polling-long-polling"],
        "interview_questions": [
            {
                "question": "【腾讯】线上Agent任务失败率突增，如何靠trace体系在分钟级定位是模型、工具还是提示词的问题？",
                "answer": "1. 先看聚合指标分层：LLM延迟与报错率、工具成功率、平均步数三条曲线，单层突变直接缩小嫌疑域，避免逐条翻日志。\n2. 下钻失败trace的错误span：工具超时看执行器，参数校验失败看Schema与提示词，模型胡言乱语且步数打满看终止条件。\n3. 对比基线diff：拉出同任务历史成功trace做步骤对齐，首个分叉span即根因起点，这是轨迹级调试最有效的一招。"
            },
            {
                "question": "【字节】全量记录每次LLM的完整prompt成本极高且有隐私风险，生产级trace采样与脱敏怎么做？",
                "answer": "1. 分级采样：错误trace全采、成功trace按比例采样、高价值任务打标必采，用tail-based采样在trace结束时按结果决定去留。\n2. 字段级脱敏：API Key、用户隐私进span前按正则与NER打码，只保留脱敏后的结构，原始prompt加密存低频冷存储。\n3. 成本隔离：trace写入异步队列不阻塞主循环，存储设TTL分层，热数据查最近七天，冷数据只留聚合指标。"
            }
        ]
    },
    {
        "id": "agent-evaluation",
        "name": "Agent 评测体系 (Agent Evaluation)",
        "aliases": ["agent eval", "agent评测", "swe-bench", "gaia", "轨迹评估", "agent benchmark", "评测体系", "trajectory eval", "llm评测"],
        "category": "Agent应用开发",
        "definition": "Agent评测体系是用基准与指标度量智能体真实任务能力的方法集合：SWE-bench考仓库级代码修复，GAIA考开放世界工具协同，轨迹级评估看中间步骤质量而非只看结果。它解决唯结果论掩盖作弊与低效、离线分数与线上体感脱节的问题，是Agent迭代的方向盘。",
        "detailed_explanation": "三层结构：任务基准（SWE-bench用真实GitHub issue加单测判定，GAIA用需浏览检索的多步问答）、过程评估（步数效率、工具成功率、是否走捷径作弊）、线上回放（影子流量对比）。SWE-bench Verified经人工清洗去 flaky 用例，GAIA分级难度考通用助手能力。工程权衡是自动化判定便宜但易被hack，人工与LLM-as-judge贵且有偏。常见坑是测试集泄漏进训练、Agent记住答案而非学会方法、只报通过率不报成本延迟。",
        "project_relevance": "vibe-learning沉淀的真实会话轨迹正是评测语料金矿：监听记录失败现场供复盘，快照diff可作为任务完成度的客观判定信号，SSE回放能力支撑评测过程可视化，知识图谱沉淀高频失败模式反哺评测集建设。",
        "related_concepts": ["agent-observability", "agentic-rag", "sandbox-execution", "planning-tot-got"],
        "interview_questions": [
            {
                "question": "【阿里】Agent在SWE-bench上分数很高，线上修bug却频繁翻车，离线评测与线上效果脱节的根因一般在哪？怎么弥合？",
                "answer": "1. 基准分布偏差：SWE-bench是 curated 的知名仓库issue，与线上私有仓库的构建复杂度、测试完备度差异大，需建自有仓库的内评集。\n2. 判定口径差异：离线只看单测通过，线上还要看改动面、回归风险与可读性，应引入diff规模与回归测试通过率做联合指标。\n3. 闭环回放：把线上失败case脱敏沉淀为回归评测集，每次发版先跑内评集，用vibe-learning这类轨迹记录做失败归因再补数据。"
            },
            {
                "question": "【腾讯】只看最终任务成败会漏掉Agent走捷径（如硬编码答案绕过测试），轨迹级评估要查哪些信号？",
                "answer": "1. 过程合规信号：是否调用了必要的验证工具（如跑单测、复现脚本），跳过验证直接提交的一律判疑。\n2. 效率信号：步数与token远超同任务分位数说明瞎试，改动文件数异常大说明霰弹枪式修改。\n3. 作弊模式检测：diff中出现针对测试断言的特判、注释掉测试、放宽断言等模式直接判负，必要时用LLM-as-judge做步骤级复审。"
            }
        ]
    },
    {
        "id": "guardrails",
        "name": "安全护栏 (Guardrails)",
        "aliases": ["guardrails", "安全护栏", "护栏", "输出约束", "内容审核", "content moderation", "安全围栏", "合规护栏", "rails"],
        "category": "Agent应用开发",
        "definition": "Guardrails是包在模型输入输出与工具调用链路上的策略 enforcement 层：输入侧拦截注入与敏感请求，输出侧审核有害内容与格式合规，动作侧按风险分级放行或拦截。它解决模型能力越强破坏力越大、单靠提示词约束不可靠的问题，是Agent上线的合规底线。",
        "detailed_explanation": "三道闸：输入护栏（意图分类、注入检测、PII识别）、输出护栏（毒性分类器、正则规则、Schema校验）、动作护栏（工具风险分级、高危操作审批）。实现上分确定性规则（快、准、零幻觉）与模型裁判（覆盖长尾语义）两层串联。工程权衡是误杀与漏放的跷跷板，金融医疗等场景宁可误杀。常见坑是只防输出不防工具链、护栏本身被提示词绕过、多语言下分类器水土不服。",
        "project_relevance": "vibe-learning以外挂视角补强护栏审计：会话监听记录每次护栏触发的上下文，快照验证被拦截的工具是否真的没落盘，SSE实时告警高危拦截事件，知识图谱统计哪类任务触发护栏最多以指导策略调优。",
        "related_concepts": ["prompt-injection-defense", "human-in-the-loop", "structured-output", "sandbox-execution"],
        "interview_questions": [
            {
                "question": "【字节】业务要求护栏误杀率低于千分之五，同时高危漏放零容忍，这对矛盾指标在工程上怎么同时达成？",
                "answer": "1. 分级处置代替二值拦截：高置信有害直接拒，低置信走改写降级（去毒改写后放行）或加免责放行，只有命中红线才硬拦截，用灰度带消化误杀。\n2. 规则与模型串联：确定性规则守红线保证零漏放，模型裁判处理灰区保证体验，两层阈值独立调参互不拖累。\n3. 闭环运营：误杀申诉样本回流做难例挖掘，每周复盘调阈值，用线上真实分布而非测试集指导参数。"
            },
            {
                "question": "【蚂蚁】Agent场景下用户诱导模型调用退款工具套利，纯文本内容审核拦不住，护栏体系要怎么补？",
                "answer": "1. 意图加动作双审：文本过审不代表可执行，工具调用前再做一次带业务上下文的策略判定（用户身份、金额、历史行为）。\n2. 业务规则引擎兜底：金额阈值、频次限制、黑名单等确定性规则放在护栏最内环，不依赖模型判断。\n3. 组合攻击检测：单步看都合规、多步拼成套利链的，需基于轨迹做序列级风控，这正是Agent护栏区别于单轮审核的核心增量。"
            }
        ]
    },
    {
        "id": "structured-output",
        "name": "结构化输出 (Structured Output)",
        "aliases": ["structured output", "结构化输出", "json mode", "json模式", "schema约束", "constrained decoding", "约束解码", "grammar约束", "json schema输出"],
        "category": "Agent应用开发",
        "definition": "结构化输出是强制模型输出符合预定Schema的JSON等格式的技术：轻量做法是提示词加JSON Mode，硬核做法是约束解码在logits层屏蔽非法token。它解决模型输出格式漂移、下游解析靠正则脆弱不堪的问题，是Agent与工程系统对接的接口契约。",
        "detailed_explanation": "两条路线：JSON Mode靠后训练让模型自觉输出合法JSON，便宜但无硬保证；约束解码（grammar-based sampling）在解码时按Schema自动机过滤词表，非法token概率直接置零，保证100%合规但增加推理开销。工程上常组合：约束解码保格式、宿主校验保语义。权衡是Schema越复杂解码越慢，超大枚举会显著拖慢首token。常见坑是Schema与提示词描述打架、嵌套过深模型填错层级、流式输出时半截JSON被下游提前消费。",
        "project_relevance": "vibe-learning解析会话JSONL依赖稳定Schema抽取调用记录，对外事件流与图谱接口同样严格约束防渲染白屏。",
        "related_concepts": ["function-calling", "guardrails", "tool-use-engineering", "jsonl-format"],
        "interview_questions": [
            {
                "question": "【腾讯】JSON Mode和约束解码（constrained decoding）各有什么代价？生产API选型时怎么定？",
                "answer": "1. 可靠性差异：JSON Mode是软约束，复杂嵌套下仍有百分之几的非法率，下游必须try-parse；约束解码是硬保证，合法率100%，适合直写数据库的场景。\n2. 成本差异：约束解码需维护语法自动机并逐token过滤，大Schema下延迟上升10%到30%，简单场景用JSON Mode加重试更划算。\n3. 选型原则：写库、调参、计费等强一致场景用约束解码，展示类、摘要类容忍重试的用JSON Mode，本质是拿延迟换确定性。"
            },
            {
                "question": "【阿里】约束解码保证了格式合法，但模型往合法字段里填幻觉内容怎么办？",
                "answer": "1. 分层设防：格式层靠解码保证，语义层靠后校验，枚举值白名单、数值范围、外键存在性逐项查，这是两类不同问题不能混为一谈。\n2. 校验反馈闭环：语义校验失败把结构化错误（如 porta 不在候选列表）回填给模型，比纯文本报错纠正率高得多。\n3. 高风险字段走工具验证：如下单金额、用户ID必须调业务接口核验存在性，不相信模型的一切断言。"
            }
        ]
    },
    {
        "id": "sandbox-execution",
        "name": "代码沙箱 (Sandbox Execution)",
        "aliases": ["sandbox", "沙箱", "沙盒", "代码沙箱", "隔离执行", "code execution", "沙箱执行", "gvisor", "firecracker"],
        "category": "Agent应用开发",
        "definition": "代码沙箱是让Agent生成的代码在隔离环境中安全试错的执行底座：通过容器、微虚拟机或syscall过滤限制文件、网络与资源访问，跑挂了只影响沙箱不伤宿主。它解决Agent必须动手验证、但直接在本机执行等同于交出root权限的矛盾，是代码智能体的安全基座。",
        "detailed_explanation": "隔离分三级：进程级（seccomp、namespace，轻但隔离弱）、容器级（Docker、gVisor，用户态内核拦截syscall，平衡之选）、微VM级（Firecracker，毫秒级启动接近硬件隔离）。配套资源配额（CPU、内存、磁盘、超时）、网络策略（默认断网或白名单代理）、产物回收（只回传stdout与指定文件）。工程权衡是隔离强度与启动速度、镜像体积的三角。常见坑是沙箱内缺依赖导致误判代码错误、超时一刀切杀掉长编译、挂载目录越权逃逸。",
        "project_relevance": "vibe-learning以外挂只读方式观测Agent：不侵入进程、只监听会话与快照，既拿执行证据又不扩大攻击面，与沙箱思想同源互补。",
        "related_concepts": ["human-in-the-loop", "guardrails", "agent-evaluation", "docker-container"],
        "interview_questions": [
            {
                "question": "【字节】Agent一天执行上万次代码，Firecracker、Docker、gVisor三种隔离方案怎么选？核心权衡是什么？",
                "answer": "1. 看威胁模型：执行不可信网民代码选Firecracker硬隔离，执行自家模型生成的代码gVisor或加固Docker足够，隔离强度与性能成反比。\n2. 看冷启动：Firecracker快照恢复可压到百毫秒内支撑高频，Docker镜像复用层缓存适合依赖重的场景，选型先压测p99启动延迟。\n3. 看运维成本：微VM需自建快照与网络 plumbing，团队小优先用gVisor这类 Seccurity 与易用性折中的方案，别为极致隔离拖垮迭代速度。"
            },
            {
                "question": "【阿里】沙箱默认断网导致 pip install 装不上依赖，任务大量失败，网络策略与依赖供给怎么设计？",
                "answer": "1. 默认断网加显式放行：只允许访问内部 PyPI 镜像与白名单域名，外部直连一律代理审计，既不断粮也不裸奔。\n2. 依赖预装分层：基础镜像预装高频依赖，长尾依赖走按需构建的缓存层，命中缓存秒起、未命中才走受限网络安装。\n3. 失败归因区分：沙箱返回的错误要区分环境缺依赖与代码真bug，前者自动触发依赖补装重试，不计入模型纠错步数。"
            }
        ]
    },
    {
        "id": "human-in-the-loop",
        "name": "人机协同审批 (Human-in-the-Loop)",
        "aliases": ["hitl", "human-in-the-loop", "人机协同", "人工审批", "人工确认", "审批机制", "human approval", "人在回路", "confirm机制"],
        "category": "Agent应用开发",
        "definition": "HITL是在Agent自主链路中按风险插入人工决策点的机制：低风险步骤自动放行，高风险动作暂停并携带完整上下文等待人批准、驳回或改参后放行。它解决全自主不可信、全人工没效率的两难，是高风险Agent上线的标准安全带。",
        "detailed_explanation": "核心是三件套：风险分级器（按工具类型、参数金额、影响面定级）、中断挂起机制（checkpoint冻结轨迹状态，人批后可恢复）、上下文打包（给审批人看 diff、影响面、回滚预案而非原始prompt）。流程上支持批准、驳回、改参放行、升级转交四种处置。工程权衡是审批粒度：太细把人淹没在弹窗里导致乱点通过，太粗漏掉关键风险。常见坑是审批上下文不足人只能盲批、超时无默认策略、审批记录缺审计链。",
        "project_relevance": "vibe-learning事件流是审批台弹药：会话还原决策链，快照diff展示影响面，图谱提示历史风险，一次推送即审计上下文。",
        "related_concepts": ["guardrails", "sandbox-execution", "tool-use-engineering", "agent-observability"],
        "interview_questions": [
            {
                "question": "【美团】审批弹窗太多导致业务人员麻木乱点通过，这种审批疲劳在机制设计上怎么破？",
                "answer": "1. 分级减量：低风险自动放行加事后审计，只把真正高危的动作推给人，用通过率数据持续把误判为高危的规则降级。\n2. 批量与策略审批：同类重复动作支持一次批一类、常用安全组合沉淀为预授权策略，把人从重复劳动摘出来。\n3. 提升单次审批质量：弹窗必须给diff、影响面、回滚按钮三件套，盲批率与拦截事故数一起考核，乱点可追溯到人。"
            },
            {
                "question": "【字节】审批人长时间不响应，Agent任务是无限挂起、自动放行还是自动驳回？超时策略怎么定？",
                "answer": "1. 默认拒绝最安全：高危动作超时按驳回处理并记录，绝不能超时自动放行，否则攻击者用拖延战术即可绕过。\n2. 分级超时：读操作超时可降级自动放行，写操作超时驳回并checkpoint保留现场，人回来后可一键恢复继续。\n3. 升级转交：超时先转交备审批人再驳回，配合企微钉钉多通道触达，用SLA（如15分钟）而非无限等待约束全链路。"
            }
        ]
    },
    {
        "id": "a2a-protocol",
        "name": "A2A 协议 (Agent-to-Agent Protocol)",
        "aliases": ["a2a", "agent-to-agent", "a2a协议", "智能体互操作", "agent card", "agent互联", "多智能体协议", "a2a protocol", "agent通信协议"],
        "category": "Agent应用开发",
        "definition": "A2A是Google于2025年4月发布并捐给Linux基金会的智能体互操作协议：Agent用标准Agent Card声明能力，经HTTP加JSON-RPC互发消息委托任务。它解决各家Agent语言不通、能力发现靠硬编码的问题，与MCP构成调用加协作的互补双协议。",
        "detailed_explanation": "核心机制有三：Agent Card（well-known地址上的JSON能力描述，含技能、端点、鉴权方式）、消息与任务模型（Message含多Part内容块，Task跟踪异步长任务状态）、安全传输（TLS加认证token，Agent可代表用户跨组织协作）。与MCP分工明确：MCP管Agent到工具，A2A管Agent到Agent。工程权衡是标准化带来互操作但增加协议适配与版本治理成本。常见坑是Card描述夸大导致任务错配、跨组织鉴权链过长、长任务状态同步不一致。",
        "project_relevance": "vibe-learning多平台监听适配A2A协作：把分散各家的会话事件与快照diff拼成跨Agent证据链，SSE统一推送，图谱沉淀协作拓扑。",
        "related_concepts": ["mcp-protocol", "multi-agent-system", "guardrails", "agent-observability"],
        "interview_questions": [
            {
                "question": "【腾讯】A2A和MCP经常被混为一谈，两者的定位边界到底在哪？一个多Agent协作系统里它们怎么配合？",
                "answer": "1. 方向不同：MCP是纵向的Agent到工具（我如何使用这个服务），A2A是横向的Agent到Agent（我如何找到并委托另一个智能体），一个管能力调用一个管协作组网。\n2. 配合方式：编排器通过A2A发现专职Agent并把子任务委派出去，每个专职Agent内部再通过MCP调用自己的工具链，两层协议各司其职。\n3. 选型检验：只需要接工具就别上A2A，只有出现跨团队、跨厂商的Agent协作时才引入，避免为协议而协议。"
            },
            {
                "question": "【阿里】生产环境接入外部A2A Agent时，能力描述造假与跨组织鉴权是两大风险，分别怎么防？",
                "answer": "1. 防Card造假：接入前跑标准探针任务集实测能力，线上持续统计其任务成功率，低于宣称即降权；关键任务双Agent交叉验证。\n2. 跨组织鉴权：用短期委托token限定任务范围与有效期，遵循最小权限，敏感数据先脱敏再跨组织流转。\n3. 熔断隔离：外部Agent跑在受限沙箱通道，异常行为（超频调用、越权参数）直接切断并审计全量消息，可随时摘除不影响主链路。"
            }
        ]
    },
    {
        "id": "agent-skills",
        "name": "Agent Skills 能力包 (Agent Skills)",
        "aliases": ["agent skills", "skills", "能力包", "技能包", "技能封装", "插件化", "skill.md", "能力插件", "agent插件"],
        "category": "Agent应用开发",
        "definition": "Agent Skills是把某类专职能力打包成可插拔目录的封装规范：一个skill含说明文档、脚本工具与资源文件，Agent按需加载而非常驻上下文。它解决提示词无限膨胀、能力复用靠复制粘贴的问题，让沉淀下来的专家经验变成可分发、可版本化的能力资产。",
        "detailed_explanation": "标准结构是元信息（名称、版本、触发条件描述）加内容体（操作手册SOP、可用脚本、示例）。运行时靠触发描述做路由：意图匹配才加载，正文渐进展开避免一次吞完。工作流是发现、加载、执行、反馈沉淀四步。工程权衡是skill粒度：太粗加载浪费token，太细路由失败率高。常见坑是触发描述写得像广告导致误触发、skill内脚本与声明行为不一致、版本升级破坏存量任务。",
        "project_relevance": "vibe-learning观测的高频优质行为是skill原材料：监听挖掘操作套路，快照验证真实有效，图谱关联适用目录反哺技能库。",
        "related_concepts": ["tool-use-engineering", "mcp-protocol", "prompt-engineering", "agent-memory-system"],
        "interview_questions": [
            {
                "question": "【字节】Skills和Tools在概念与工程实现上到底是什么关系？什么时候该沉淀skill而不是新造tool？",
                "answer": "1. 抽象层级不同：tool是原子动作（删文件、调接口），skill是带SOP的作战包（如何做一次线上排障），skill内部可编排多个tool。\n2. 沉淀标准：重复三次以上的人工经验、跨任务可复用的流程先做skill；需要新副作用能力、确定性计算才做tool，别把流程知识硬塞进代码。\n3. 演进关系：高频skill中稳定且需提速的部分下沉为tool，tool组合出的新套路上升为skill，两层之间持续流动。"
            },
            {
                "question": "【小红书】skill库膨胀到几百个后触发混乱、互相打架，路由与治理机制怎么设计？",
                "answer": "1. 路由分层：先按领域粗分类过滤，再在类内用触发描述相似度精排，Top1置信度不足就向用户澄清而不硬选。\n2. 冲突声明：skill元信息声明互斥与前置关系，加载前检查冲突集，冲突时按优先级与用户显式选择仲裁。\n3. 用后评价：记录每次skill加载后的任务成败，长期低胜率的skill自动降权下架，用数据而非人工评审治理规模。"
            }
        ]
    },
    {
        "id": "hooks-lifecycle",
        "name": "Hook 生命周期 (Hooks Lifecycle)",
        "aliases": ["hooks", "hook", "钩子", "生命周期钩子", "工具拦截", "tool hook", "pretooluse", "posttooluse", "钩子机制"],
        "category": "Agent应用开发",
        "definition": "Hook是挂在Agent生命周期关键节点上的拦截回调：工具调用前、调用后、会话启停、 compaction 前后都可注入自定义逻辑。它解决想加审计、改写、拦截却不想 fork 主循环的矛盾，是外挂式增强Agent的标准插槽，也是本项目会话监听的思想同源。",
        "detailed_explanation": "典型钩子点包括 PreToolUse（审批改写参数）、PostToolUse（记录结果、触发快照）、SessionStart/End（初始化与收尾）、PreCompact（记忆沉淀）。钩子分阻塞式（可否决本次调用）与旁路式（只观测不干预）。工程权衡是钩子越多主链路延迟与故障点越多，关键路径钩子必须设超时快速失败。常见坑是钩子抛异常拖垮主循环、多个钩子顺序隐含依赖、旁路钩子偷偷变成强依赖。",
        "project_relevance": "vibe-learning是外挂Hook思想实现：监听如PostToolUse旁路钩子，快照如文件变更钩子，SSE如事件分发钩子，可对接官方钩子点。",
        "related_concepts": ["tool-use-engineering", "agent-observability", "guardrails", "agent-loop"],
        "interview_questions": [
            {
                "question": "【字节】PreToolUse钩子里做同步审批导致Agent整体卡顿，钩子链路的性能与可靠性怎么保障？",
                "answer": "1. 分级超时：旁路观测型钩子超时直接跳过，阻塞审批型钩子超时按默认拒绝并挂起，任何钩子都不允许无限阻塞主循环。\n2. 异步化：日志、快照、指标上报全部走队列异步，钩子函数只做入队动作，把重活搬到后台消费。\n3. 故障隔离：钩子异常被捕获隔离并告警，主流程继续或按策略降级，单个钩子挂掉不能级联拖垮整个Agent。"
            },
            {
                "question": "【腾讯】多个团队的钩子（安全、审计、计费）挂在同一个PreToolUse点上顺序打架，怎么治理执行顺序与冲突？",
                "answer": "1. 显式优先级：安全否决类最高、改写类居中、观测类最低，优先级声明在注册表而非代码隐含顺序，新人一眼看懂。\n2. 短路语义：任一否决型钩子拒绝即短路，后续钩子不再执行并返回统一拒绝原因，避免改写与否决互相覆盖。\n3. 冲突测试：钩子注册时跑组合测试矩阵，改写同一参数的钩子强制声明归属，CI拦截未声明的冲突组合。"
            }
        ]
    },
    {
        "id": "deep-research-agent",
        "name": "Deep Research 智能体 (Deep Research Agent)",
        "aliases": ["deep research", "深度研究", "深度检索", "研究报告", "research agent", "调研智能体", "deepresearch", "研报智能体", "agentic search"],
        "category": "Agent应用开发",
        "definition": "Deep Research是面向开放调研的长程智能体形态：给定模糊课题后自主规划检索大纲、多轮搜索浏览交叉验证、最终产出带引用的长篇报告。它解决传统搜索只给碎片链接、人工 synthesis 耗时数小时的问题，把检索从找答案升级为做研究。",
        "detailed_explanation": "核心组件是规划器（拆解子问题与检索大纲）、浏览器工具链（搜索、翻页、PDF解析）、证据管理（引用溯源、冲突标注）、报告生成器（大纲到长文）。流程是规划、并行检索、证据聚合、澄清追问、成稿。工程权衡是广度与成本的矛盾：检索轮次越多覆盖越全但token与时间爆炸，需用信息增益决定何时收敛。常见坑是引用幻觉（编造来源）、只搜英文或只搜中文的语料偏斜、报告臃肿无结论。",
        "project_relevance": "vibe-learning知识库建设与Deep Research同源：研报式检索沉淀条目，监听记录研究轨迹，快照验证引用证据，SSE推送长任务进度。",
        "related_concepts": ["agentic-rag", "planner-executor", "computer-use-agent", "agent-evaluation"],
        "interview_questions": [
            {
                "question": "【腾讯】Deep Research产出的报告引用了不存在的论文链接，这种引用幻觉在链路上怎么系统性治理？",
                "answer": "1. 引用强绑定：每条引用必须携带检索返回的原文URL与摘录片段，生成时只允许引用证据库中的条目，库外引用视为非法直接拦截。\n2. 链接可达校验：成稿前用爬虫回查所有引用链接的HTTP状态与标题匹配度，404或标题不符自动标红打回重写。\n3. 抽样人工审：高风险领域报告走专家抽审，幻觉案例回流为负例，持续统计引用真实率作为核心质量指标。"
            },
            {
                "question": "【字节】开放调研任务动不动跑几十分钟烧掉大量token，如何设计收敛机制控制成本又不伤质量？",
                "answer": "1. 信息增益停机：每轮估算新增独立事实数，连续两轮增益低于阈值即收敛，把预算花在刀刃上。\n2. 分级检索：先用摘要与snippet低成本扫广度，只对关键争议点展开全文精读，避免全文抓取无差别烧钱。\n3. 用户中途干预：检索大纲先给用户确认，方向跑偏早期纠正比重跑十轮再返工便宜一个数量级。"
            }
        ]
    },
    {
        "id": "computer-use-agent",
        "name": "Computer Use 智能体 (Computer Use Agent)",
        "aliases": ["computer use", "cua", "gui智能体", "图形界面操作", "桌面操作", "uiautomation", "gui agent", "屏幕操作", "osworld"],
        "category": "Agent应用开发",
        "definition": "Computer Use是直接操作图形界面的智能体形态：看屏幕截图定位按钮输入框，用点击拖拽敲键盘完成跨应用任务。它解决大量老旧系统无API、RPA靠固定坐标一改版就崩的问题，让Agent像人一样用电脑，是自动化最后的通用入口。",
        "detailed_explanation": "技术栈分三层：感知（截图加无障碍树a11y tree做元素 grounding，纯视觉与树结构融合定位）、规划（把任务拆成点击序列，异常弹窗分支处理）、执行（OS级键鼠注入、操作前后截图diff验效）。工程权衡是速度与可靠：每步截图验证最稳但慢，无验证连击最快但一步错步步错。常见坑是分辨率缩放导致坐标漂移、动态加载元素误点、验证码与支付等红线环节无人值守。",
        "project_relevance": "vibe-learning聚焦代码会话观测，与Computer Use互补：快照diff校验GUI操作生效，SSE推送长任务进度，图谱沉淀界面操作知识。",
        "related_concepts": ["deep-research-agent", "sandbox-execution", "human-in-the-loop", "agent-observability"],
        "interview_questions": [
            {
                "question": "【阿里】纯截图视觉定位在分辨率变化和高DPI下坐标漂移严重，生产级GUI元素 grounding 怎么做才稳？",
                "answer": "1. 语义定位优先：能用无障碍树、DOM、控件ID就不用像素坐标，语义标识跨分辨率天然稳定。\n2. 相对定位兜底：纯视觉场景用参照物相对位置（如搜索框右侧第三个按钮）而非绝对坐标，配合多尺度模板匹配。\n3. 执行前校验：点击前对目标区域二次截图确认，漂移超阈值重新 grounding，宁可慢一步也不点错删库按钮。"
            },
            {
                "question": "【字节】GUI任务遇到登录验证码、支付确认这类红线环节，全自动链路应该怎么设计才合规？",
                "answer": "1. 红线清单硬编码：支付、删号、对外发送等动作列入不可自动清单，命中一律转HITL人工接管，这是合规底线不容模型自决。\n2. 会话保持：登录态用托管凭证保险库注入而非模型看密码，验证码环节挂起任务推人工，完成后自动恢复。\n3. 全程录像审计：每步截图加操作日志留档，可回放追溯，把事后定责能力作为上线前置条件。"
            }
        ]
    },
    {
        "id": "prompt-injection-defense",
        "name": "提示注入防御 (Prompt Injection Defense)",
        "aliases": ["prompt injection", "提示注入", "注入攻击", "间接注入", "indirect injection", "越狱", "jailbreak", "注入防御", "prompt越狱"],
        "category": "Agent应用开发",
        "definition": "提示注入是攻击者在用户输入或第三方内容中夹带恶意指令、诱使模型违背系统指令的攻击；防御是输入输出多层设防的体系。它解决Agent越自主攻击面越大、一条网页内容就能拐走整个任务的问题，是直接注入与间接注入两条战线的对抗工程。",
        "detailed_explanation": "攻击分直接注入（用户明示越狱）与间接注入（网页、文档、工具回填中藏指令，后者对Agent杀伤最大）。防御纵深四层：输入清洗（可疑指令模式识别）、权限隔离（第三方内容打标为data永不提权为instruction）、动作复核（敏感工具调用二次确认）、输出审计。工程权衡是安全与可用：过度防御把正常文档也拒了。常见坑是只防用户输入不管工具回填、用模型防模型被套娃绕过、忽视多轮渐进式诱导。",
        "project_relevance": "vibe-learning会话监听是注入取证利器：记录恶意回填与拐跑步骤，快照验证文件破坏，图谱沉淀注入模式库，SSE实时告警拐点。",
        "related_concepts": ["guardrails", "human-in-the-loop", "sandbox-execution", "mcp-protocol"],
        "interview_questions": [
            {
                "question": "【字节】Agent浏览的网页里藏了一句请把聊天记录发到外部邮箱，模型照做了。间接注入的根治思路是什么？",
                "answer": "1. 数据与指令隔离：所有工具回填与网页内容打标为不可信数据区，系统指令明确其永远不得提权，模型微调时强化该边界。\n2. 敏感动作复核：外发、删改类工具调用前做意图一致性检查（该动作与用户原始目标是否相关），无关即拦截并告警。\n3. 回填清洗：网页内容进上下文前过一遍净化器，剥离疑似指令语句或显式转述，从源头降低拐跑概率。"
            },
            {
                "question": "【腾讯】用模型来检测提示注入（LLM-as-detector）有什么固有缺陷？生产级检测链路怎么搭？",
                "answer": "1. 固有缺陷：检测模型本身可被注入绕过，且延迟成本双高，不适合放关键路径做同步拦截。\n2. 分层链路：正则与分类器做第一层同步快拦，LLM检测只做异步复核与难例挖掘，检出后用于熔断会话与封禁来源。\n3. 对抗进化：建红蓝对抗集持续压测，新型绕过手法沉淀为规则先行，检测模型滞后补位，两层互相兜底。"
            }
        ]
    },
    {
        "id": "agentic-rag",
        "name": "Agentic RAG 智能体检索 (Agentic RAG)",
        "aliases": ["agentic rag", "agenticrag", "智能体检索", "主动检索", "self-rag", "检索智能体", "adaptive rag", "纠正式检索", "crag"],
        "category": "Agent应用开发",
        "definition": "Agentic RAG是把检索权交给Agent的增强范式：模型自主判断何时检索、用什么query、检索质量不行就换词重查、证据够了才作答。它解决传统RAG一次检索定生死、复杂问题单query召回不全的问题，把检索从管道变成带反馈的决策循环。",
        "detailed_explanation": "核心机制是检索决策（按需触发而非每问必检）、query改写（子问题拆分、多视角复述）、证据评估（Self-RAG式打分决定用、弃或重查）、纠正循环（CRAG对低质结果做网络回退）。工程权衡是检索轮次与延迟成本，需设最大轮次与早停。常见坑是检索死循环反复换词查同一批文档、证据冲突时模型和稀泥、引用与正文脱钩无法溯源。",
        "project_relevance": "vibe-learning知识检索可用Agentic RAG：关键词失手改写再查，快照与会话事件构成混合语料，SSE返回检索进度，图谱支持多跳关联。",
        "related_concepts": ["embedding-vector", "vector-db-ann", "agent-memory-system", "deep-research-agent"],
        "interview_questions": [
            {
                "question": "【阿里】传统RAG切到Agentic RAG后延迟涨了三倍，哪些场景值得付这个代价？成本怎么控？",
                "answer": "1. 值得的场景：多跳问答、证据冲突需交叉验证、query模糊需澄清的任务；简单事实问答用传统单次检索足够，别为时髦付费。\n2. 意图分流：分类器先判问题复杂度，简单走直检快通道，复杂才进Agent循环，大部分流量仍是低成本。\n3. 硬性封顶：最大检索轮次、token预算双熔断，超时按已有最佳证据作答并声明置信度，不让长尾拖垮p99。"
            },
            {
                "question": "【字节】多轮检索返回的证据互相矛盾（如两篇文档给相反结论），Agent应该如何裁决而不是和稀泥？",
                "answer": "1. 证据评级：按来源权威性、时效性、一次/二次文献分级，高权威新证据优先采信，低质证据降权而非等权平均。\n2. 冲突显式化：回答中并列双方观点并标注来源与时间，把裁决困难诚实暴露给用户而非编造调和结论。\n3. 主动追查：对关键冲突追加定向检索找第三方佐证，仍无定论则降置信度并建议人工核验，诚实比正确更重要。"
            }
        ]
    },
    {
        "id": "planner-executor",
        "name": "Planner-Executor 架构 (Planner-Executor)",
        "aliases": ["planner-executor", "planner", "executor", "主从架构", "规划执行", "plan-and-execute", "计划执行", "orchestrator-worker", "分层规划"],
        "category": "Agent应用开发",
        "definition": "Planner-Executor是主从式Agent架构：Planner负责全局拆解里程碑与依赖，Executor认领子任务用ReAct具体执行，遇阻反馈给Planner重规划。它解决单Agent长任务顾头不顾尾、纯ReAct短视跑偏的问题，是复杂任务稳定性的经典答案。",
        "detailed_explanation": "三角色分工：Planner产DAG式计划并定验收标准，Executor逐子任务执行并上报证据，Controller做重规划仲裁。通信靠结构化任务包（目标、输入、验收条件）而非自由文本。工程权衡是规划粒度：太粗Executor自由发挥易跑偏，太细Planner成瓶颈。常见坑是计划一次定死不重规划、子任务验收走过场、Executor上下文拿不到全局目标导致局部最优。",
        "project_relevance": "vibe-learning事件模型映射该架构：监听区分规划与执行span，快照diff作子任务验收证据，SSE按里程碑推送，图谱展示任务分解树。",
        "related_concepts": ["react-pattern", "agent-loop", "multi-agent-system", "scratchpad-context"],
        "interview_questions": [
            {
                "question": "【美团】Executor在第三步失败了，是重试本步、换Executor重做，还是上报Planner全局重规划？决策逻辑是什么？",
                "answer": "1. 先看失败类型：偶发超时类错误本地重试加退避即可，参数理解错换个Executor或补上下文重做，只有前置假设被证伪才升级重规划。\n2. 看依赖 blast radius：失败步是叶子节点就地处理，是枢纽节点（后续多步依赖其输出）必须上报Planner评估整条链。\n3. 设升级预算：单子任务重试超两次自动升级，避免Executor闷头瞎试烧光token，这是工程上最实在的一条线。"
            },
            {
                "question": "【字节】Planner一次产出完整长计划 vs 边做边规划，下一步计划何时生成？两种策略的取舍？",
                "answer": "1. 静态全规划适合流程稳定、依赖清晰的任务，一次生成全局可审，缺点是中途环境一变整盘作废。\n2. 动态滚动规划适合开放探索任务，每完成一里程碑用新观察生成下一步，适应强但全局感弱、易局部最优。\n3. 生产折中：粗粒度静态骨架（里程碑可审计）加细粒度动态展开（每步按需规划），骨架变更才触发重规划通知人。"
            }
        ]
    },
    {
        "id": "scratchpad-context",
        "name": "Scratchpad 草稿板 (Scratchpad)",
        "aliases": ["scratchpad", "草稿板", "草稿纸", "中间状态", "working memory", "工作记忆", "thought记录", "推理草稿", "cot草稿"],
        "category": "Agent应用开发",
        "definition": "Scratchpad是Agent在上下文中维护的显式工作区：每步的思考、尝试、观察结论以半结构化形式暂存，供后续步骤回看纠偏。它解决长链推理中间结论稍纵即逝、错了不知哪步错的问题，是ReAct能自我纠正的记忆载体。",
        "detailed_explanation": "组织形式有追加式日志（Thought、Action、Observation三元组顺序沉淀）与状态板式（TODO清单、已知事实、待验证假设分区维护）两种。写入靠模型自觉或模板约束，读取靠全文回看或摘要压缩。工程权衡是详略：记太细窗口爆炸，记太粗纠偏无据。常见坑是草稿与最终答案矛盾、错误结论沉淀后被后续步骤当事实引用、 compaction 时草稿被一刀切丢掉关键中间态。",
        "project_relevance": "vibe-learning会话监听在外部重建scratchpad：拼出可回放决策链；长会话摘要与SSE步骤流同样面临草稿压缩取舍。",
        "related_concepts": ["react-pattern", "agent-memory-system", "context-harness", "token-budget"],
        "interview_questions": [
            {
                "question": "【腾讯】长任务跑到几十步后scratchpad撑爆窗口，直接截断丢掉早期思考会怎样？工程上怎么压缩不断链？",
                "answer": "1. 截断的危害：早期踩坑教训丢失导致重复犯错，任务目标漂移无人察觉，压缩必须保目标、保结论、保教训三件套。\n2. 分区摘要：事实区与教训区做有损摘要保留，原始Thought日志归档冷存，压缩后附索引需要时可回查。\n3. 里程碑 checkpoint：每完成一里程碑固化一次状态快照，压缩只 summarize 快照之间的增量，证据链永不断裂。"
            },
            {
                "question": "【阿里】模型在scratchpad里写下的错误中间结论被后续步骤当成事实引用，越错越远，怎么掐断这种污染传播？",
                "answer": "1. 置信度标注：推测性结论与工具验证过的事实分开记，引用低置信结论做关键决策前必须先验证，这是制度性防火墙。\n2. 结论复核点：里程碑处强制用工具重验核心假设，不是一路信任到底，用外部证据定期校准草稿。\n3. 显式勘误机制：发现错误时不只改后续步骤，还要回写勘误条覆盖旧结论，避免残留旧文本继续被注意力attend到。"
            }
        ]
    }
]
