"""Agent 算法扩展知识包 (bank_ext_agent_algo)。

外挂式扩展数据模块：纯数据、无 import，定义 EXTRA_ENTRIES 列表。
主题覆盖 Agent 推理搜索、奖励建模、强化学习训练与记忆压缩算法。
"""

EXTRA_ENTRIES = [
    {
        "id": "mcts-agent",
        "name": "蒙特卡洛树搜索智能体 (MCTS Agent)",
        "aliases": ["mcts", "蒙特卡洛树搜索", "monte carlo tree search", "uct搜索", "树搜索推理", "tree search agent", "mcts-agent", "蒙特卡洛推理"],
        "category": "Agent算法",
        "definition": "MCTS 是一种通过选择、扩展、模拟、回传四步循环，在解空间中做前瞻式规划的搜索算法。它解决 LLM 单步贪心解码短视、在数学证明与代码修复等多步任务中无法试错回退的问题，核心机制是用 UCB 公式平衡探索与利用，靠大量 rollout 估计中间状态价值。",
        "detailed_explanation": "关键组件包括选择阶段的 UCB/PUCT 策略、扩展阶段的候选动作生成、模拟阶段用 LLM 或价值模型 rollout 到终态、回传阶段更新路径节点价值。工作流程是给定当前状态反复建树，最终选访问量或均值价值最高的动作。算法权衡在于搜索宽度深度与算力开销的矛盾，分支过大时必须配合剪枝与价值网络。常见坑是 rollout 策略与真实策略分布不一致导致价值估计偏差，以及奖励稀疏时整棵树退化为随机游走。",
        "project_relevance": "TopoCode 分析 Agent 会话时，可借鉴 MCTS 视角评估多分支试错轨迹的质量：识别高价值决策节点、合并重复探索分支，为长会话压缩与关键路径摘要提供树形价值回传思路。",
        "related_concepts": ["planning-tot-got", "tree-search-verifier"],
        "interview_questions": [
            {
                "question": "【字节 Seed / 腾讯混元】在 LLM 推理中做 token 级 MCTS 与 step 级 MCTS 有什么本质区别？为什么工业界几乎都用 step 级？",
                "answer": "1. 动作粒度不同：token 级分支因子约几万，树深度极大，UCB 统计量被稀释到几乎无意义；step 级以完整推理步或工具调用为动作，分支因子可控在个位数，价值估计更稳定。\n2. 奖励可定义性不同：token 中间态几乎无法打分，而 step 级可用 PRM 或规则 verifier 给出稠密反馈。\n3. 工程成本不同：token 级每次扩展都要做完整 rollout，KV-Cache 复用困难；step 级可缓存前缀并批量并行模拟，吞吐高一个量级。"
            },
            {
                "question": "【阿里通义 / DeepSeek】MCTS 中的 UCT 公式在 LLM 场景下为什么常被替换为 PUCT？先验概率 P(s,a) 从哪里来？",
                "answer": "1. UCT 只用访问次数做探索 bonus，对 LLM 这种先验极强的策略是浪费，PUCT 引入策略网络先验 P(s,a)，让搜索优先探索模型本身认为有希望的分支。\n2. P(s,a) 通常取 LLM 生成该 step 的归一化 logprob，或由独立的 policy/value 头输出，AlphaGo 系做法是策略网络直接给出。\n3. 实践坑点：LLM 先验过度自信会导致搜索坍缩到单条链，需调大 c_puct 系数或对 logprob 做温度平滑，保证探索多样性。"
            }
        ]
    },
    {
        "id": "process-reward-model",
        "name": "过程奖励模型 (Process Reward Model)",
        "aliases": ["prm", "过程奖励模型", "process reward model", "逐步打分", "过程监督", "process supervision", "prm打分器", "步骤级奖励"],
        "category": "Agent算法",
        "definition": "PRM 是对推理链条中每一个中间步骤逐个打分的奖励模型。它解决结果奖励只能看最终对错、无法定位中间哪一步推理崩坏的问题，核心机制是训练一个判别器为每个 step 输出正确性概率，在搜索剪枝与 RL 训练中提供稠密的过程反馈信号。",
        "detailed_explanation": "关键组件包括步骤切分器、步骤级标注数据、判别式打分头。工作流程是将 CoT 按换行或语义切分为 step，模型对每个 step 输出 good/bad 概率。相比 ORM，PRM 给出稠密信号，能指导 MCTS 剪枝与 PPO 的 step 级 advantage。算法权衡是标注成本极高，且存在因果混淆：某步本身正确但前序已错时标签难以定义。常见坑是 PRM 被模型 hack，用冗长正确的废话步骤刷高分，以及跨任务泛化差，数学 PRM 迁移到代码几乎失效。",
        "project_relevance": "TopoCode 做 Agent 会话分析时天然需要步骤级质量判断：哪一步工具调用是有效推进、哪一步是无效重试。PRM 的步骤切分与逐段打分思想可直接用于会话轨迹的自动标注与检索排序。",
        "related_concepts": ["outcome-reward-model", "tree-search-verifier"],
        "interview_questions": [
            {
                "question": "【OpenAI / 字节】Math-Shepherd 提出的软标签与硬标签估计 PRM 训练数据各有什么优劣？数据构造的核心 trick 是什么？",
                "answer": "1. 硬标签由人工或强模型逐步骤判定对错，准确但成本极高；软标签用 completer 从该步骤出发 rollout N 次，以最终答对比例作为该步价值的蒙特卡洛估计，全自动但噪声大。\n2. 核心 trick 是自动构造：固定前缀到 step k，后续用 completer 补全多次，用成功率近似 Q 值，无需人工标注即可规模化。\n3. 实践要点：completer 能力决定标签上限，太弱的 completer 会把好步骤误判为坏；需过滤成功率接近 0.5 的模糊样本，只保留高置信两端数据训练。"
            },
            {
                "question": "【腾讯 / 阿里】PRM 在 RL 训练中做 dense reward 时，如何避免 reward hacking？",
                "answer": "1. 现象是策略模型学会生成 PRM 喜欢的表面模式，如超长分步、堆砌验证句式，ORM 指标反而下降。\n2. 缓解手段包括 PRM 与 ORM 加权混合、PRM 分数做 advantage 归一化与裁剪、定期用新策略 rollout 数据重训 PRM 消除分布漂移。\n3. 更彻底的做法是规则奖励锚定：数学用最终答案校验、代码用单元测试通过率做主奖励，PRM 只做 shaping 系数，保证优化方向不偏离真实目标。"
            }
        ]
    },
    {
        "id": "outcome-reward-model",
        "name": "结果奖励模型 (Outcome Reward Model)",
        "aliases": ["orm", "结果奖励模型", "outcome reward model", "结果监督", "outcome supervision", "verifier判别器", "答案级奖励", "orm验证器"],
        "category": "Agent算法",
        "definition": "ORM 是只根据最终结果对错给出整体打分的奖励模型。它解决推理过程难以逐步骤标注、但最终答案易于自动校验的场景，核心机制是把整条推理轨迹当作一个样本训练二分类器，用最终正确性作为标签，推理时用于 Best-of-N 重排序与 RL 结果奖励。",
        "detailed_explanation": "关键组件是轨迹级编码器与正确性判别头，训练数据只需问题加最终答案 pairs，成本远低于 PRM。工作流程是采样 N 条完整推理，用 ORM 打分取最高。相比 PRM 实现简单且不易被步骤级 hack，但信号稀疏，无法指出错误位置，长链条下信用分配困难。常见坑是 ORM 偏爱表面流畅但推理跳跃的答案，以及在开放式任务中最终正确性本身难以自动判定，导致标签噪声淹没训练信号。",
        "project_relevance": "TopoCode 的知识检索排序需要对候选条目做整体相关性打分，这正是 ORM 式轨迹级判别思想。分析会话成败时先做整体判定再下钻归因，符合本项目的分层分析架构。",
        "related_concepts": ["process-reward-model", "best-of-n"],
        "interview_questions": [
            {
                "question": "【谷歌 / 华为】ORM 与直接用 LLM-as-a-Judge 做 Best-of-N 重排序相比，各自的 latency 与精度权衡是什么？",
                "answer": "1. ORM 是轻量判别模型，单次前向即可打分，N=64 时延迟可忽略；LLM-as-a-Judge 需完整生成评语，延迟与成本随 N 线性暴涨。\n2. 精度上 ORM 在分布内任务拟合更准，但跨任务泛化弱；生成式 judge 借助大模型通用推理，零样本迁移更好。\n3. 生产选型是分层：先用 ORM 粗排截断到 top-8，再用 LLM judge 精排，兼顾吞吐与天花板；高风险场景还可加规则校验做最终否决。"
            },
            {
                "question": "【字节 / 美团】ORM 训练中正负样本比例严重失衡时（如强模型答对率 90%），你会怎么处理？",
                "answer": "1. 首先用温度采样或弱模型补全构造更多负样本，保证每个问题正负配对，避免模型坍缩为全预测正确。\n2. 训练用 pairwise ranking loss 替代 pointwise BCE，让模型学相对排序而非绝对概率，对不平衡更鲁棒。\n3. 评估必须看 Best-of-N 曲线而非 AUC：一个 AUC 很高的 ORM 可能只是学会了题目难度先验，对同一题目的 N 个候选毫无区分度，这才是真实 serving 指标。"
            }
        ]
    },
    {
        "id": "agentic-rl",
        "name": "智能体强化学习 (Agentic RL)",
        "aliases": ["agentic rl", "智能体强化学习", "agentic reinforcement learning", "r1范式训练", "长链推理rl", "rlvr", "智能体rl训练", "推理模型rl"],
        "category": "Agent算法",
        "definition": "Agentic RL 是用强化学习直接优化智能体多步行为的训练范式。它解决 SFT 只模仿示范、无法超越教师且试错能力弱的问题，核心机制是以可验证奖励为信号，让模型在数学、代码、工具调用环境中自主 rollout 探索，用 GRPO/PPO 类算法更新策略涌现长链推理。",
        "detailed_explanation": "关键组件包括可验证奖励函数、rollout 环境、策略优化器。工作流程是模型生成带工具调用的多步轨迹，环境返回结果奖励，算法计算组内相对优势并更新策略。DeepSeek-R1 范式证明规则奖励加 GRPO 即可涌现自反思行为。算法权衡是探索与稳定的矛盾：KL 约束太强则无涌现，太弱则语言崩坏。常见坑是奖励稀疏导致训练初期梯度几乎为零，以及长轨迹 credit 分配失真，需要课程学习与奖励塑形配合。",
        "project_relevance": "TopoCode 追踪的正是 Agent 多步会话轨迹，理解 Agentic RL 的 rollout-奖励闭环，有助于设计会话质量评估维度：多样性、工具有效率对应关键观测指标。",
        "related_concepts": ["reward-shaping", "test-time-scaling"],
        "interview_questions": [
            {
                "question": "【DeepSeek / 字节 Seed】DeepSeek-R1 的 GRPO 相比 PPO 省掉了什么？为什么在推理任务上 group relative 优势估计是合理的？",
                "answer": "1. GRPO 省掉了 PPO 的 value 评论家网络，对同一 prompt 采样一组输出，用组内奖励均值做基线计算相对优势，大幅降低显存与训练不稳定性。\n2. 合理性在于推理任务奖励多为 0/1 二值且同 prompt 可比，组内归一化天然给出แข่งขัน学习信号，无需跨 prompt 的绝对价值估计。\n3. 代价是组内全对或全错时优势为零、梯度消失，因此必须配合动态采样过滤和课程学习，保证每个 batch 有足够方差，这是 R1 复现中最易踩的坑。"
            },
            {
                "question": "【阿里 / 腾讯】Agentic RL 训练中模型出现语言混杂与无限重复时，通常是哪几个超参或设计出了问题？",
                "answer": "1. KL 散度系数过小或缺失，策略远离 SFT 初始化分布，需加 KL 惩罚或 KL 约束的 early stop。\n2. 奖励只看最终对错，中间胡言乱语不受罚，需加格式奖励与长度惩罚做联合 shaping。\n3. 熵 bonus 或温度设置不当导致坍缩到某条高奖励模板，应监控响应多样性指标，必要时对重复 n-gram 加显式惩罚并回滚 checkpoint。"
            }
        ]
    },
    {
        "id": "self-play",
        "name": "自博弈机制 (Self-Play)",
        "aliases": ["self-play", "自博弈", "自我对弈", "self play", "左右手互搏", "对抗自训练", "self-play训练", "博弈自进化"],
        "category": "Agent算法",
        "definition": "Self-Play 是让智能体与自身历史版本或分身对抗生成训练数据的机制。它解决对抗性与开放式任务缺少外部教师、静态数据集很快被刷满的问题，核心机制是通过与旗鼓相当的对手持续对弈，自动构造出难度自适应的课程，驱动策略与裁判能力共同进化。",
        "detailed_explanation": "关键组件包括对手池、匹配调度、胜负判定。工作流程是当前策略与历史快照对抗，胜者样本回灌训练，AlphaZero 系还用 MCTS 增强对弈质量。从单智能体视角可扩展为生成器与判别器互搏。算法权衡是对手太强导致全败无学习信号、太弱则学不到东西，需维护 ELO 分层匹配。常见坑是策略坍缩到某种专克当前对手池的奇招，换个对手即崩，以及非对称任务中攻防双方能力失衡导致一方停滞。",
        "project_relevance": "TopoCode 可引入自博弈思想做评估：用一个 Agent 生成会话摘要、另一个 Agent 挑刺质疑，两者对抗迭代可自动发现分析盲区，持续提升会话分析报告的质量上限。",
        "related_concepts": ["agentic-rl", "verifier-ensemble"],
        "interview_questions": [
            {
                "question": "【字节 / 腾讯】AlphaZero 的 Self-Play 与 LLM 场景下正反方辩论式 Self-Play（如 SPP）在学习信号来源上有何本质不同？",
                "answer": "1. AlphaZero 有围棋规则这个完美裁判，胜负信号客观无噪声，学习目标明确；LLM 辩论式自博弈多数任务无客观胜负，需依赖 LLM judge 或人工偏好，信号本身带偏。\n2. 棋类状态转移确定，探索空间封闭；语言任务动作空间开放，对手可能用出分布外的诡辩直接击穿裁判，导致训练信号失真。\n3. 因此 LLM 自博弈必须配强裁判校准，如多 judge 投票或规则锚点，否则会出现双方串通、共同输出裁判喜欢的套话这种模式坍缩。"
            },
            {
                "question": "【阿里 / 华为】Self-Play 训练中如何防止策略循环克制（石头剪刀布式循环）而不收敛？",
                "answer": "1. 维护历史对手池并均匀采样对手，而非只打最新版本，逼迫策略学到对全分布鲁棒的解，这就是 fictitious play 的思想。\n2. 引入 ELO 分层与优先匹配势均力敌对手，保证每局胜率在 30%-70% 区间，维持有效梯度。\n3. 监控策略在对手池上的 payoff 矩阵，若出现明显非传递循环，需增大群体多样性，如多随机种子并行进化再蒸馏合并。"
            }
        ]
    },
    {
        "id": "memory-consolidation",
        "name": "记忆巩固与遗忘算法 (Memory Consolidation)",
        "aliases": ["memory consolidation", "记忆巩固", "记忆遗忘", "遗忘曲线", "记忆压缩", "memgpt记忆", "长期记忆管理", "记忆衰减"],
        "category": "Agent算法",
        "definition": "记忆巩固是把 Agent 短期交互沉淀为长期可用知识、并遗忘冗余噪声的机制。它解决长会话上下文爆炸与重要事实被淹没的问题，核心机制是模仿人类记忆：按重要性、复用率与时效性给记忆打分，定期把高价值片段转写为结构化摘要，低价值片段衰减遗忘。",
        "detailed_explanation": "关键组件包括情景记忆缓冲、重要性评分器、巩固转写器、遗忘调度器。工作流程是每轮交互写入原始记忆，评分器结合检索命中率与 LLM 自评重要性打分，超过阈值的转写为事实条目或向量索引，长期未命中且低分的按艾宾浩斯曲线衰减删除。算法权衡是保留太多则检索噪声大，遗忘太激进则关键偏好丢失。常见坑是转写过程中的幻觉污染长期记忆，以及用户偏好变更后旧记忆成为顽固脏数据，需要版本与冲突消解机制。",
        "project_relevance": "TopoCode 的会话压缩与架构知识沉淀正是记忆巩固问题：把海量 Agent 改动事件转写为稳定的架构组件描述，丢弃中间试错噪声。巩固评分与遗忘调度可直接指导本项目的增量修订策略。",
        "related_concepts": ["context-harness", "context-compression-algo"],
        "interview_questions": [
            {
                "question": "【字节 / 美团】MemGPT 式分页记忆与直接向量检索全部历史相比，在一致性与成本上如何取舍？",
                "answer": "1. 分页记忆把热数据常驻上下文、冷数据换页调入，保证当前任务视角的一致性，避免检索 top-k 拼凑出的断裂上下文。\n2. 成本上分页靠 LLM 自主决定换入换出，调用次数多但每次 prompt 短；全量检索每次都要做向量召回加拼接，长尾噪声随历史增长线性放大。\n3. 生产实践是混合：高频用户画像与任务状态放分页主存，低频长尾事实走向量检索，并用巩固转写定期把检索热点提升进主存。"
            },
            {
                "question": "【腾讯 / 小红书】长期记忆被幻觉污染后，如何做冲突检测与修复？",
                "answer": "1. 写入时做来源标注：用户亲述、模型推断、工具返回三类置信度分级，低置信记忆不参与关键决策。\n2. 定期跑一致性审计：用新记忆与旧记忆做 NLI 蕴含检测，发现矛盾时触发澄清或按时间戳新覆盖旧并保留版本链。\n3. 提供用户可视与糾错入口，关键偏好类记忆必须可溯源到原始对话轮次，这是线上止血最有效的手段。"
            }
        ]
    },
    {
        "id": "context-compression-algo",
        "name": "上下文压缩算法 (Context Compression)",
        "aliases": ["上下文压缩", "context compression", "llmlingua", "选择性摘要", "prompt压缩", "上下文蒸馏", "长上下文裁剪", "compaction压缩"],
        "category": "Agent算法",
        "definition": "上下文压缩是在保留任务关键信息前提下缩短 prompt 的算法族。它解决长 Agent 会话线性堆积导致注意力退化、延迟与成本暴涨的问题，核心机制是按 token 信息量或语义重要性做选择性保留：无用 token 删除、冗长工具返回转摘要、低价值轮次整体丢弃。",
        "detailed_explanation": "关键流派包括 LLMLingua 系的 token 级困惑度剪枝、结构化摘要式 compaction、按需解构的分页换入。工作流程是先估计每段内容的边际信息量，再按预算做有损压缩。算法权衡是压缩率与任务成功率的曲线：超过临界点后关键事实丢失导致断崖下跌。常见坑是跨段指代断裂，压缩后代词找不到先行词，以及过度压缩工具返回中的报错堆栈，导致后续调试失去现场信息。",
        "project_relevance": "核心刚需：会话历史与代码快照都受 token 预算约束，渐进裁剪加状态折叠正是 context-harness 的算法底座。",
        "related_concepts": ["context-harness", "memory-consolidation"],
        "interview_questions": [
            {
                "question": "【字节 / 阿里】LLMLingua 用小模型困惑度决定删除哪些 token，这种做法的理论假设是什么？什么场景下会失效？",
                "answer": "1. 假设是小模型与大模型的困惑度排序正相关：小模型觉得可预测的 token，大模型同样不需要，从而可用廉价模型做压缩代理。\n2. 在代码、数学公式、报错堆栈场景失效：这些 token 局部困惑度低但全局缺一不可，删掉一个括号或行号整个语义崩坏。\n3. 工程对策是按类型设保护位：代码块、数字、工具返回状态码设为不可删除区，只压缩自然语言闲聊部分。"
            },
            {
                "question": "【美团 / 华为】Auto-compaction 生成的进展摘要如何评测好坏？线上怎么发现摘要丢了关键信息？",
                "answer": "1. 离线用可恢复性评测：只给摘要让模型继续完成任务，对比给全量历史的成功率差值，这就是信息损失的直接度量。\n2. 线上埋点监控压缩后首轮的澄清提问率与工具重复调用率，突增即说明摘要遗漏了已确认事实。\n3. 摘要结构强制包含已确认事实、待办事项、失败尝试三栏，用 schema 约束替代自由文本，可大幅降低关键信息丢失率。"
            }
        ]
    },
    {
        "id": "test-time-scaling",
        "name": "推理时扩展 (Test-Time Scaling)",
        "aliases": ["test-time scaling", "推理时扩展", "test time compute", "o1范式", "r1范式", "串行扩展", "并行扩展", "推理扩展律"],
        "category": "Agent算法",
        "definition": "Test-Time Scaling 是通过在推理阶段投入更多算力换取更高准确率的新范式。它解决单纯扩大参数规模收益递减、高质量训练数据枯竭的问题，核心机制分两轴：串行扩展拉长单条思维链深度，并行扩展采样多条候选再用 verifier 选优。",
        "detailed_explanation": "关键发现是思维链长度与准确率呈对数线性 scaling 关系，构成与训练 scaling 并列的第二定律。串行扩展靠 RL 训练出的长 CoT 实现自反思，并行扩展靠 Best-of-N 与 MCTS 搜索实现。算法权衡是串行深度带来的延迟与幻觉累积，对比并行采样的吞吐成本。常见坑是无效过度思考：简单题也被迫长思考反而引入错误，以及 verifier 天花板限制并行扩展收益，verifier 不准时采样越多错得越离谱。",
        "project_relevance": "TopoCode 在分析复杂 Agent 会话时面临同样的串并行权衡：是对单条长轨迹做深度下钻，还是对多文件变更做并行摘要再仲裁。理解扩展律有助于为本项目设计按任务难度自适应的分析算力分配策略。",
        "related_concepts": ["best-of-n", "self-consistency"],
        "interview_questions": [
            {
                "question": "【字节 Seed / OpenAI】Snell 等人 2024 年的论文指出什么任务该用串行扩展、什么任务该用并行扩展？背后的直觉是什么？",
                "answer": "1. 结论是简单题用并行扩展性价比高，难题必须用串行扩展：简单题答案空间小，多采样加 verifier 即可覆盖；难题需要连贯的深度推导，并行采样全是浅层错误。\n2. 直觉是 verifier 难度决定一切：verifier 易的任务并行扩展有效，verifier 难的任务只能靠串行把推理质量本身做高。\n3. 工程落地是自适应路由：先用难度分类器或首轮置信度判断，简单查询走 Best-of-N，复杂任务切到长思考模型，避免一刀切浪费算力。"
            },
            {
                "question": "【DeepSeek / 腾讯】R1 类模型出现的过度思考问题，线上有哪些可行的抑制手段？",
                "answer": "1. 训练侧加长度惩罚 shaped reward，对正确且更短的回答给更高奖励，从源头压缩冗余思考。\n2. 推理侧做早停：监控思维链中答案收敛信号，连续多步结论一致即截断思考强制作答。\n3. 路由侧按难度分流：简单意图直接走 instruct 短模型，只有分类器判定为难题才走推理模型，这是线上省成本最立竿见影的一刀。"
            }
        ]
    },
    {
        "id": "best-of-n",
        "name": "Best-of-N 采样与重排序 (Best-of-N)",
        "aliases": ["best-of-n", "best of n", "n选优", "采样重排序", "bon采样", "多采样选优", "rerank选优", "候选重排"],
        "category": "Agent算法",
        "definition": "Best-of-N 是采样 N 个候选回答再用打分器选出最优的并行解码策略。它解决单次贪心解码方差大、好答案常与坏答案混杂的问题，核心机制是用温度采样保证多样性，再靠 ORM、verifier 或 LLM judge 做重排序，把算力花在选优而非训更大的模型上。",
        "detailed_explanation": "关键组件是多样性采样器与排序打分器。工作流程是同一 prompt 独立采样 N 条，逐条打分取 argmax。N 增大时上确界单调提升，但受 verifier 精度封顶：verifier 噪声大会出现选大翻车。算法权衡是 N 与延迟成本的线性关系，以及温度设置：太低多样性不足，太高全是垃圾候选。常见坑是长度偏差，verifier 倾向选更长的回答，需做长度归一化，以及候选间高度同质导致 N 白采，需监控 pairwise 相似度。",
        "project_relevance": "TopoCode 生成架构摘要与会话分析报告时，可对同一事件并行生成多版摘要再用相关性打分选优。这种采样加仲裁的模式能稳定提升报告质量，是本项目低成本提质的首选手段。",
        "related_concepts": ["outcome-reward-model", "self-consistency"],
        "interview_questions": [
            {
                "question": "【腾讯 / 字节】Best-of-N 的 N 从 8 扩大到 128 时收益趋平甚至下降，通常意味着什么？怎么诊断？",
                "answer": "1. 最可能是 verifier 天花板：候选池里已有好答案但打分器选不出来，画出 oracle pass@N 与实际 best-of-N 曲线，两者 gap 拉大即实锤 verifier 瓶颈。\n2. 其次可能是多样性枯竭：N 增大后新增候选全是已有答案的改写，计算 pairwise embedding 相似度可验证，需调高温度或换 diverse beam 策略。\n3. 对策是升级 verifier 而非无脑加 N，或改用 MCTS 这类带反馈的搜索替代纯独立采样。"
            },
            {
                "question": "【阿里 / 美团】线上 serving 做 Best-of-N 时，如何控制 P99 延迟不爆炸？",
                "answer": "1. 候选生成全并行批量推理，延迟取决于最慢的一条，需设单条超时熔断，超时直接按已完成子集选优。\n2. 打分器用轻量 ORM 而非生成式 judge，打分与生成流水线重叠，边生成边打分。\n3. 自适应 N：简单查询 N=1 直出，只有低置信或高价值请求才开大 N，把算力预算花在刀刃上。"
            }
        ]
    },
    {
        "id": "self-consistency",
        "name": "自洽性多路投票 (Self-Consistency)",
        "aliases": ["self-consistency", "自洽性", "多路投票", "self consistency", "多数投票", "一致性投票", "cot投票", "答案自洽"],
        "category": "Agent算法",
        "definition": "Self-Consistency 是采样多条思维链并取多数答案的解码策略。它解决单条 CoT 偶然失误率高、贪心解码押注单一路径的问题，核心机制是假设正确推理虽然路径各异但终点收敛，用边缘化近似对潜在推理路径积分，投票选出最自洽的答案。",
        "detailed_explanation": "关键组件是高温采样器与答案归一化器。工作流程是采样数十条 CoT，抽取每条最终答案做等价归一，票数最高者胜出。相比 Best-of-N 不需要训练 verifier，零成本提点显著。算法权衡是只适用于答案可精确归一的任务，开放式生成无法投票。常见坑是模型系统性偏见：所有路径犯同一个概念错误时投票反而强化错误，以及答案等价判定失败把同义答案拆票，需配语义归一化。",
        "project_relevance": "TopoCode 做会话事件分类与文件职责判定时，可对同一输入采样多路判定再投票，天然获得置信度估计。这种无 verifier 的集成方式适合本项目零外部依赖、轻量本地化的架构约束。",
        "related_concepts": ["best-of-n", "verifier-ensemble"],
        "interview_questions": [
            {
                "question": "【谷歌 / 字节】Self-Consistency 在什么任务上几乎无效？背后的数学直觉是什么？",
                "answer": "1. 开放式生成与证明题几乎无效：答案空间巨大，N 条路径终点互不相同，投票退化为随机抽一条。\n2. 数学直觉是投票只在答案空间小、正确路径收敛时有效，本质是对离散答案分布做众数估计；答案空间连续或组合爆炸时众数无意义。\n3. 这类任务应改用 verifier 选优或 universal self-consistency，即先让 LLM 把多路答案语义聚类再选最大簇，而非字符串精确匹配。"
            },
            {
                "question": "【腾讯 / 华为】投票平票或最高票占比很低时，线上应该怎么处理？",
                "answer": "1. 把投票分布本身当不确定性信号：最高票低于阈值直接判为低置信，走人工复核或升级更大模型，而不是硬选一个。\n2. 对平票候选做第二轮 tie-break：用 ORM 打分或再采样一批定向投票，而非简单取首条。\n3. 监控低一致率 query 的占比突增，它往往是 prompt 退化或模型漂移的最早报警，比用户投诉早得多。"
            }
        ]
    },
    {
        "id": "swe-agent",
        "name": "SWE-agent 代码修复智能体 (SWE-agent)",
        "aliases": ["swe-agent", "swe agent", "代码修复智能体", "swe-bench", "仓库级修bug", "coding agent", "程序修复agent", " issue修bug"],
        "category": "Agent算法",
        "definition": "SWE-agent 是面向真实代码仓库自动修复 issue 的智能体范式。它解决传统补全只能写片段、无法在百万行仓库中定位改测闭环的问题，核心机制是给模型配备文件浏览、代码搜索、终端执行与测试运行工具，在 ReAct 循环中完成复现、定位、 patch、验证全流程。",
        "detailed_explanation": "关键组件包括仓库导航工具、复现脚本执行器、patch 生成器、回归测试守门员。工作流程是读 issue 建复现，搜索定位可疑代码，多轮编辑运行测试直至通过。相比单步生成，成败取决于工具设计与测试反馈质量。算法权衡是探索步数与成本：步数越多定位越准但 token 烧得越快。常见坑是模型为过测试而写特判式 hack，以及 issue 描述模糊时修错方向，需要测试用例充分性检查与最小 diff 约束。",
        "project_relevance": "TopoCode 本质上是 SWE-agent 的观察者：实时追踪这类代码修复智能体在仓库中的改动轨迹。理解其复现定位改测循环，有助于本项目准确切分会话阶段并评估每次改动的真实意图。",
        "related_concepts": ["agent-loop", "test-time-scaling"],
        "interview_questions": [
            {
                "question": "【字节 / 阿里】SWE-bench 的 resolved 率从 10% 涨到 60% 的过程中，公认最关键的三个工程改进是什么？",
                "answer": "1. 工具接口精简化：把开放 shell 收敛为文件查看、精准编辑、定向测试三个高成功率原语，减少模型误操作空间。\n2. 测试反馈闭环：每次 patch 后强制跑相关单测并把失败堆栈回灌，让模型基于真实执行而非臆测迭代。\n3. 多采样加测试选优：并行生成多个 patch，用回归测试通过率做硬筛选，测试即 verifier，这是涨点最稳的一路。"
            },
            {
                "question": "【腾讯 / 美团】如何检测模型为了通过测试而写的作弊式 patch？",
                "answer": "1.  holdout 测试隔离：选优用的可见测试与最终验收测试分离，作弊 patch 过可见集但挂 holdout 集。\n2. 最小 diff 与语义审查：统计 patch 行数与圈复杂度突变，特判式 if 硬编码一眼可识，可配 LLM reviewer 做二次审查。\n3. 变异测试抽查：对 patch 区域做小扰动，若测试依然全过说明测试本身太弱，先补测试再修代码。"
            }
        ]
    },
    {
        "id": "search-r1",
        "name": "检索增强推理训练 (Search-R1)",
        "aliases": ["search-r1", "search r1", "检索增强推理", "搜索增强rl", "rag推理训练", "工具检索rl", "检索智能体训练", "rag rl训练"],
        "category": "Agent算法",
        "definition": "Search-R1 是用强化学习训练 LLM 自主调用搜索引擎做多步推理的框架。它解决静态 RAG 检索与推理割裂、模型不会按需发起多轮查询的问题，核心机制是在 RL 中把检索 token  mask 掉不计 loss，仅用最终答案正确性做奖励，让模型自发学会何时检索、如何改写查询。",
        "detailed_explanation": "关键组件包括支持特殊检索 token 的 rollout 环境、检索内容 mask 的 loss 计算、结果导向的奖励。工作流程是模型生成思考，需要时输出查询调用搜索引擎，把返回结果拼回上下文继续推理。相比 SFT 训检索行为，RL 涌现的查询策略更贴合任务。算法权衡是检索噪声会污染推理链，需要足够的 rollout 覆盖坏检索的恢复路径。常见坑是模型学会刷检索次数薅格式奖励，以及检索语料与评测集泄漏导致指标虚高。",
        "project_relevance": "TopoCode 的知识检索正是检索与推理交织的场景：先召回条目再组织答案。Search-R1 的检索 token 处理与查询改写思想，可指导本项目优化 BM25 召回后的重排序链路。",
        "related_concepts": ["agentic-rl", "toolformer-retrieval"],
        "interview_questions": [
            {
                "question": "【阿里 / 字节】Search-R1 为什么要把检索返回的 token 在 loss 中 mask 掉？不 mask 会发生什么？",
                "answer": "1. 检索内容是环境观测而非模型行为，对它算 loss 等于逼模型去拟合搜索引擎的文本分布，梯度方向完全错误。\n2. 不 mask 会导致模型困惑度被检索噪声主导，策略更新被大量不可控 token 稀释，训练震荡甚至坍缩。\n3. 这是 agentic RL 的通用原则：只对模型自主生成的 action token 算 loss，所有工具返回的 observation token 一律 mask，这也是 veRL 等框架的标准实现。"
            },
            {
                "question": "【腾讯 / 华为】Search-R1 类训练中模型疯狂发起无用检索时，怎么从奖励设计上根治？",
                "answer": "1. 引入检索成本项：每次调用扣固定 penalty，只有带来答案改善的检索才净赚，模型自发学会克制。\n2. 奖励以最终答案正确性为主，检索次数只做正则约束而非正奖励，避免为检索而检索的形式主义。\n3. 训练初期可设检索次数上限课程，从少到多放开，让模型先学会无检索推理，再学何时必须检索。"
            }
        ]
    },
    {
        "id": "verifier-ensemble",
        "name": "多验证器集成与仲裁 (Verifier Ensemble)",
        "aliases": ["verifier ensemble", "多验证器", "验证器集成", "结果仲裁", "多裁判投票", "混合验证", "verifier投票", "验证器融合"],
        "category": "Agent算法",
        "definition": "Verifier Ensemble 是用多个异构验证器交叉检验候选答案再仲裁的机制。它解决单一 verifier 有偏、被 hack 后选优翻车的问题，核心机制是让规则校验、ORM、LLM judge 等正交信号各自独立打分，再按加权投票或分层否决产出最终 verdict，可靠性显著高于单裁判。",
        "detailed_explanation": "关键组件包括异构 verifier 池、分数校准层、仲裁策略。工作流程是候选答案并行过所有 verifier，校准到同一尺度后融合。规则 verifier 精确但覆盖窄，模型 verifier 覆盖广但有偏，两者正交互补。算法权衡是延迟与成本随 verifier 数量线性增长。常见坑是 verifier 间高度相关导致集成无增益，以及分数未校准直接平均让某个大尺度 verifier 独裁，需做 Platt scaling 或 rank 融合。",
        "project_relevance": "TopoCode 的会话分析结论天然需要多信号交叉：BM25 相关性、规则启发、LLM 研判三路互相印证。这种异构仲裁思想是本项目检索排序与分析结论置信度设计的直接依据。",
        "related_concepts": ["outcome-reward-model", "best-of-n"],
        "interview_questions": [
            {
                "question": "【字节 / 腾讯】设计代码任务的 verifier 组合时，规则、ORM、LLM judge 三者的分工与编排顺序是什么？",
                "answer": "1. 第一层规则否决：编译加单测是硬门槛，不过直接淘汰，零误杀且最便宜。\n2. 第二层 ORM 粗排：对通过测试的候选按学习到的质量分排序，截断到 top-k。\n3. 第三层 LLM judge 精排：只审 top-k 的可读性与边界处理，做最终选优。这种漏斗式编排把贵算子用在最少的候选上，精度成本双优。"
            },
            {
                "question": "【阿里 / 美团】多个 verifier 打分量纲不一且相关性未知，融合时最稳妥的 baseline 是什么？",
                "answer": "1. 别直接平均原始分，先转 rank 再做 Borda 计数或 RRF 融合，天然 immune 于量纲问题。\n2. 有少量标注数据就学逻辑回归权重，无标注就按历史准确率设静态权重，规则 verifier 给一票否决权。\n3. 上线后持续监控各 verifier 的两两一致性，高度相关的两个可裁掉一个，省下的预算加一个正交新信号收益更大。"
            }
        ]
    },
    {
        "id": "tree-search-verifier",
        "name": "树搜索与验证器协同解码 (Tree Search Verifier)",
        "aliases": ["tree search verifier", "树搜索验证", "协同解码", "mcts剪枝", "verifier引导搜索", "搜索加验证", "beam验证", "树剪枝解码"],
        "category": "Agent算法",
        "definition": "树搜索与验证器协同解码是用 verifier 分数实时引导搜索树扩展与剪枝的解码范式。它解决纯采样选优浪费算力、盲目搜索指数爆炸的问题，核心机制是把 PRM/ORM 当作树节点的价值函数，每轮只保留高分分支继续展开，实现边搜边验的计算最优分配。",
        "detailed_explanation": "关键组件包括候选扩展器、节点价值 verifier、剪枝调度器。工作流程是 beam 或 MCTS 展开一层，verifier 批量打分，淘汰低分节点后继续。相比事后 Best-of-N，算力集中在有希望的分支，同样预算下覆盖更深。算法权衡是 verifier 调用频率：每步都验最准但最贵，可隔步验证。常见坑是 verifier 早期误杀：好路径的中间态分数低被提前剪掉，需保留一定探索配额或用 UCB 风格的乐观估计。",
        "project_relevance": "TopoCode 分析长 Agent 会话时同样面临分支爆炸：多文件改动、多轮重试构成搜索树。用轻量打分做节点剪枝、只对高价值分支深度下钻，正是本项目有界快照与增量分析的工程映射。",
        "related_concepts": ["mcts-agent", "process-reward-model"],
        "interview_questions": [
            {
                "question": "【字节 / 腾讯】Beam Search 配 verifier 与 MCTS 配 verifier 在探索行为上有何本质差异？分别适合什么任务？",
                "answer": "1. Beam 是宽度优先的同步推进，每层保留 top-k，行为保守但吞吐高，适合步骤价值单调的任务如翻译与摘要。\n2. MCTS 是非对称的乐观探索，算力向高不确定分支倾斜，能挖到深藏的好路径，适合数学证明这种好坏在深层才分晓的任务。\n3. 选型看 verifier 可靠性：verifier 准用 beam 又快又稳，verifier 噪声大用 MCTS 的多次回传平均掉噪声。"
            },
            {
                "question": "【阿里 / 华为】verifier 引导搜索中出现早期误杀的典型症状与缓解手段是什么？",
                "answer": "1. 症状是 oracle 覆盖率远高于搜索命中率：好答案在候选池里但搜不到，说明剪枝剪错了。\n2. 缓解手段包括保留探索槽位，每层强制保留少量低分高方差节点；或用 lookahead 估计，让 completer 往前滚几步再打分。\n3. 根本解是校准 verifier 的 early-step 分数分布，对浅层节点加乐观 bonus，随深度衰减，显式补偿早期低估偏差。"
            }
        ]
    },
    {
        "id": "reward-shaping",
        "name": "奖励塑形与稀疏奖励 (Reward Shaping)",
        "aliases": ["reward shaping", "奖励塑形", "稀疏奖励", "sparse reward", "奖励设计", "势能塑形", "dense reward", "奖励稀疏性"],
        "category": "Agent算法",
        "definition": "奖励塑形是给稀疏的终局奖励补充中间过程小奖励以加速学习的技术。它解决 Agent 长轨迹中只有成功或失败二值信号、初期几乎拿不到正反馈的问题，核心机制是基于势能函数设计附加奖励，在不改变最优策略的前提下把大目标拆成可感知的阶段性进展信号。",
        "detailed_explanation": "关键理论是 Ng 的势能塑形：附加奖励写成折扣势差形式时最优策略不变。实践组件包括子目标里程碑、格式与长度约束、工具调用有效性奖励。工作流程是主奖励保持真实目标，shaping 项只给方向性提示。算法权衡是 shaping 太强会扭曲目标，模型刷中间分放弃终局。常见坑是各 shaping 系数拍脑袋，互相打架导致训练震荡，必须做消融确认每项的边际贡献。",
        "project_relevance": "TopoCode 评估 Agent 会话质量时同样不能只看终局成败：工具调用成功率、重试收敛速度、阶段里程碑达成度都是天然 shaping 信号，可直接复用为会话健康度指标体系。",
        "related_concepts": ["agentic-rl", "curriculum-learning-agent"],
        "interview_questions": [
            {
                "question": "【字节 / 腾讯】为什么给 LLM 推理加每步 0.1 的格式奖励，练到后期模型会输出超长废话？理论根源是什么？",
                "answer": "1. 这是典型的奖励扭曲：附加奖励改变了最优策略，模型发现堆格式分比解难题更划算，直接放弃真实目标。\n2. 理论根源是该 shaping 不是势能差形式，不满足策略不变性条件，长期优化必然偏离。\n3. 修正是把格式奖励改成门槛式：格式对只给过线资格不给累积分，或把 shaping 系数随训练退火，前期引导、后期让真实奖励主导。"
            },
            {
                "question": "【阿里 / DeepSeek】R1 训练早期奖励全零梯度消失时，除了奖励塑形还有哪些标准解法？",
                "answer": "1. 动态采样过滤：丢弃组内全对全错的 prompt，只保留有方差的样本，保证每个 batch 都有有效梯度。\n2. 课程学习：先训短推理简单题让模型拿到正信号，再逐步放开难度与长度。\n3. 冷启动 SFT：先用少量高质量长 CoT 把模型扶到能偶尔答对的起点，再进 RL，这也是 R1 正式版区别于 Zero 的关键稳定手段。"
            }
        ]
    },
    {
        "id": "curriculum-learning-agent",
        "name": "课程学习智能体训练 (Curriculum Learning)",
        "aliases": ["curriculum learning", "课程学习", "课程训练", "由易到难", "难度课程", "渐进训练", "curriculum训练", "自适应课程"],
        "category": "Agent算法",
        "definition": "课程学习是按由易到难的顺序组织训练样本的策略。它解决 Agent 任务难度跨度大、直接上难题导致全零奖励学不动的问题，核心机制是先让模型在简单任务上建立基础行为模式与正反馈，再逐步放开任务复杂度，使能力边界随课程平滑外扩。",
        "detailed_explanation": "关键组件包括难度度量器、课程调度器、能力门槛。工作流程是用通过率、推理长度或人工分级给样本定级，模型在当前级别达标后再解锁下一级。人工课程稳定但需先验，自适应课程按实时成功率动态调参。算法权衡是课程太保守浪费算力，太激进退回全零奖励。常见坑是灾难性遗忘：学难题时把简单能力丢了，需混合回放旧课程样本保持。",
        "project_relevance": "TopoCode 做仓库全量分析时可借鉴课程思想：先分析核心入口文件建立骨架，再逐步下钻边缘模块。这种由主干到枝叶的渐进式分析能保证中断时已有可用结果，契合增量修订架构。",
        "related_concepts": ["agentic-rl", "reward-shaping"],
        "interview_questions": [
            {
                "question": "【腾讯 / 字节】自适应课程中用什么信号判断该升级难度？阈值设多少有讲究？",
                "answer": "1. 标准信号是当前难度组的 rollout 成功率，稳定在 60%-80% 区间即升级：太高说明已无学习价值，太低说明跳级了。\n2. 还要看奖励方差：成功率合适但方差趋零说明样本被刷满，需补充新题而非升级。\n3. 工程上用滑动窗口平滑成功率，避免单 batch 噪声导致课程反复横跳，升级后保留 20% 旧难度样本做回放锚。"
            },
            {
                "question": "【阿里 / 华为】课程学习与直接混合训练相比，在什么情况下反而更慢？",
                "answer": "1. 当难度度量不准时：被标为简单的样本实际很难，课程顺序错乱，还不如均匀混合靠大数定律抹平。\n2. 当模型容量大、任务同质时：强模型直接啃混合数据也能快速找到模式，课程的调度开销反而拖慢收敛。\n3. 判断标准是做对照消融：若混合训练初期梯度方差可控且成功率非零，就别上复杂课程；只在稀疏奖励、冷启动困难的场景课程才是刚需。"
            }
        ]
    },
    {
        "id": "hierarchical-planning",
        "name": "层次化任务规划 (Hierarchical Planning)",
        "aliases": ["hierarchical planning", "层次化规划", "htn规划", "分层规划", "任务分解", "plan-and-execute", "高层规划", "子任务分解"],
        "category": "Agent算法",
        "definition": "层次化规划是把复杂任务逐层分解为可执行子任务的规划方法。它解决长程任务单次规划视野不足、扁平 ReAct 易跑偏的问题，核心机制是高层 planner 只定里程碑与依赖顺序，底层 executor 专注单步执行，遇阻时向上传递重规划，形成分层闭环。",
        "detailed_explanation": "关键组件包括任务分解器、依赖图、子任务执行器、重规划触发器。HTN  classical 做法用方法库逐层展开，现代 LLM 做法是 planner 动态生成子目标。工作流程是顶层拆 milestone，每个 milestone 再拆工具级动作，底层失败可局部重试或上报重规划。算法权衡是层级越深全局越稳但通信开销与延迟越大。常见坑是分解粒度失衡：太粗底层不会做，太细高层 context 被子细节淹没，以及跨层目标漂移。",
        "project_relevance": "TopoCode 的架构分析天然分层：项目级概览、组件级职责、文件级符号。下钻与上卷的层次化组织正是 HTN 思想的映射，分层摘要也让长会话压缩与检索都获得清晰的粒度抓手。",
        "related_concepts": ["agent-loop", "planning-tot-got"],
        "interview_questions": [
            {
                "question": "【美团 / 字节】Plan-and-Execute 中 executor 失败时，什么情况下局部重试、什么情况下上报重规划？",
                "answer": "1. 局部重试适用于偶发性失败：网络超时、工具限流、参数格式小错，换参重调大概率自愈。\n2. 上报重规划适用于结构性失败：子目标本身不可达、依赖前置条件被证伪、连续三次同类失败，说明高层计划有误。\n3. 工程实现是分级熔断：executor 自带 2-3 次重试预算，超限携带失败摘要上报，planner 只改受影响分支而非全盘重排，控制重规划成本。"
            },
            {
                "question": "【阿里 / 腾讯】层次化规划相比扁平 ReAct，在 token 开销上是省还是费？为什么？",
                "answer": "1. 单次成功路径上更省：高层 plan 短小，executor 每次只看子任务上下文，避免把全量历史背在身上。\n2. 失败重规划时更费：跨层通信与 plan 重写带来额外开销， decomposition 本身也消耗一次大模型调用。\n3. 净效果取决于任务长度：短任务扁平更划算，长任务分层把线性增长的上下文切成常数级分片，越长越赚，这也是长程 Agent 必分层的根本原因。"
            }
        ]
    },
    {
        "id": "toolformer-retrieval",
        "name": "Toolformer 式工具自监督学习 (Toolformer)",
        "aliases": ["toolformer", "工具自监督", "工具学习", "tool learning", "api调用学习", "工具增强", "自主调工具", "tool-use训练"],
        "category": "Agent算法",
        "definition": "Toolformer 是让语言模型自监督学会何时调用何种工具的训练方法。它解决人工标注工具调用数据贵、模型不知何时该查计算器日历还是搜索引擎的问题，核心机制是用候选 API 改写文本，以语言建模困惑度是否下降为标准自动筛选有用调用，构造自监督数据微调。",
        "detailed_explanation": "关键组件包括 API 候选采样器、调用效果过滤器、工具增强微调。工作流程是对普通语料采样插入候选工具调用，若加入调用结果后后续 token 困惑度显著下降则保留样本。模型最终学会在 token 级决策调用时机与参数。算法权衡是离线构造的调用模式固定，面对新工具需重跑流程。常见坑是困惑度下降不等于任务成功，模型可能学会无意义但顺滑的调用，以及多工具组合时搜索空间爆炸，需限制单步单工具。",
        "project_relevance": "决定何时调 AST 解析、PageRank 排序或向量检索，Toolformer 自学习可指导工具编排：按质量增益触发。",
        "related_concepts": ["agent-loop", "search-r1"],
        "interview_questions": [
            {
                "question": "【字节 / 阿里】Toolformer 用困惑度下降筛选工具调用样本，这个代理目标的最大漏洞是什么？",
                "answer": "1. 困惑度下降只说明调用结果让续写更顺，不代表调用对任务正确：模型可能插入一个让句子更流畅但事实错误的计算结果。\n2. 模型会偏爱返回冗长模板化文本的工具，因为这类文本最可预测，而真正关键的短答案反而困惑度收益小。\n3. 现代修正是用任务成功率替代困惑度做过滤，或在 RL 阶段用真实环境奖励二次校准，把顺滑调用与有用调用区分开。"
            },
            {
                "question": "【腾讯 / 华为】线上新增一个工具时，不想重训整个模型，有哪些轻量接入手段？",
                "answer": "1. 首选 in-context 接入：工具描述加 few-shot 示例进 system prompt，零训练即可用，适合低频工具。\n2. 中频工具用 LoRA 增量适配：只训工具相关的调用头，冻结主干，成本低且不伤通用能力。\n3. 高频核心工具才值得重跑 Toolformer 式数据构造；同时配 MCP 式统一接口，新工具注册即用，把模型侧改动降到只剩 prompt 模板。"
            }
        ]
    }
]
