EXTRA_ENTRIES = [
    {
        "id": "jvm-gc",
        "name": "JVM 内存模型与 GC 调优 (JVM GC Tuning)",
        "aliases": ["jvm", "jvm gc", "垃圾回收", "g1", "zgc", "内存模型", "gc调优", "分代收集"],
        "category": "后端与分布式",
        "definition": "JVM堆内存分为年轻代与老年代，年轻代又含Eden与两块Survivor区，方法区存放类元数据。对象优先在Eden分配，熬过多次Minor GC后晋升老年代。垃圾回收以可达性分析为根基，G1做分区混合回收，ZGC主打亚毫秒停顿，调优本质是在吞吐量与停顿时间之间取舍。",
        "detailed_explanation": "关键组件包括Eden、Survivor、Old区、Remembered Set与SATB快照。G1把堆切分为Region，按收益优先级混合回收；ZGC用染色指针加读屏障实现并发标记与转移。权衡是吞吐优先选Parallel、大堆低延迟选G1、超大堆苛刻停顿选ZGC。常见坑是堆过大单次停顿爆炸、元空间泄漏误判堆问题、过度调低暂停目标引发吞吐雪崩。",
        "project_relevance": "本项目用Python标准库HTTP服务承载多路SSE长连接，后台轮询线程常驻内存做会话扫描。借鉴JVM分代思想，可把热点会话快照与冷归档数据分层存放，避免长连接堆积引发内存膨胀与扫描停顿。",
        "related_concepts": ["threading-concurrency", "thread-pool", "local-cache"],
        "interview_questions": [
            {
                "question": "【阿里/字节】G1和ZGC的核心原理有什么区别？各自适合什么业务场景？",
                "answer": "1. G1是分区式分代回收，把堆切成Region并跟踪每个Region的垃圾收益，混合回收时优先收收益最高的Region，停顿可控但仍有STW；\n2. ZGC用染色指针+读屏障+LdSTB，实现几乎全并发的标记与转移，停顿稳定在毫秒内，与堆大小基本无关；\n3. 选型：普通微服务与中等堆用G1兼顾吞吐；超大堆、延迟敏感如交易链路、推荐排序用ZGC，代价是更高的CPU开销与内存预留。"
            },
            {
                "question": "【美团/拼多多】线上频繁Full GC导致接口毛刺，你的排查与调优链路是什么？",
                "answer": "1. 先看GC日志确认是老年代满、元空间满还是显式System.gc，配合jstat看各代增速与晋升速率；\n2. dump堆分析大对象与泄漏点，常见元凶是缓存无上限、ThreadLocal未清理、大集合常驻老年代；\n3. 动作：收紧缓存上限加过期、修复泄漏、调整新生代比例与晋升阈值，必要时从CMS迁G1并设定合理的暂停目标，灰度验证停顿与吞吐曲线。"
            }
        ]
    },
    {
        "id": "thread-pool",
        "name": "线程池原理与参数化配置 (Thread Pool)",
        "aliases": ["线程池", "threadpool", "thread pool", "executor", "核心线程数", "最大线程数", "阻塞队列", "拒绝策略"],
        "category": "后端与分布式",
        "definition": "线程池通过复用固定或弹性的一组工作线程，避免频繁创建销毁线程的开销，并用有界阻塞队列削峰。核心参数包括核心线程数、最大线程数、存活时间、队列容量与拒绝策略。任务提交后先占核心线程，满了进队列，队列满了才扩容到最大线程，再满则触发拒绝策略保护系统。",
        "detailed_explanation": "关键组件是Worker集合、阻塞队列、线程工厂与拒绝处理器。工作流程为提交、核心线程承接、入队缓冲、扩容、拒绝五段式。IO密集型配2倍CPU核数以上，CPU密集型配核数加一。工程权衡在于队列无界会导致OOM，有界加拒绝策略才能快速失败。常见坑是用Executors默认无界队列、IO任务塞满公用池拖垮核心链路、拒绝策略直接丢弃重要任务而不告警。",
        "project_relevance": "本项目用标准库HTTP服务多线程处理请求，后台还有轮询扫描线程与SSE推送。若把快照扫描、文件解析、SSE广播混用同一线程资源，慢任务会饿死实时推送，借鉴线程池隔离思想应对其做读写分离与队列限流。",
        "related_concepts": ["threading-concurrency", "nio-epoll", "rate-limiter"],
        "interview_questions": [
            {
                "question": "【字节/阿里】线程池的七大参数与执行流程是什么？CPU密集和IO密集任务分别怎么配？",
                "answer": "1. 流程：提交任务先看核心线程是否满，不满直接建线程；满了进阻塞队列；队列满则扩容到最大线程；仍满走拒绝策略；\n2. CPU密集配核数加一，减少上下文切换；IO密集配2倍核数甚至更多，因为线程大量时间在等IO；\n3. 混合业务必须多池隔离，核心链路单独小池加有界队列，离线任务另起池，避免慢任务挤占在线容量。"
            },
            {
                "question": "【美团/腾讯】为什么禁用Executors默认工厂？线上线程池打满了怎么定位和治理？",
                "answer": "1. Executors的newFixedThreadPool用无界LinkedBlockingQueue，堆积任务可把堆打爆OOM；CachedThreadPool最大线程近乎无限，来突发流量会建线程打爆CPU；\n2. 定位：看队列堆积量、活跃线程数、拒绝次数三指标，dump线程栈找阻塞在哪个下游IO；\n3. 治理：换ThreadPoolExecutor显式配有界队列与CallerRunsPolicy或自定义告警拒绝策略，慢依赖加超时熔断，核心池与非核心池物理隔离。"
            }
        ]
    },
    {
        "id": "nio-epoll",
        "name": "NIO多路复用与 Reactor 模型 (NIO/epoll)",
        "aliases": ["nio", "epoll", "io多路复用", "reactor", "select", "poll", "非阻塞io", "多路复用"],
        "category": "后端与分布式",
        "definition": "NIO用一个线程监听多个连接的就绪事件，连接有数据可读、可写时才被唤醒处理，终结了一连接一线程的扩展瓶颈。Linux下epoll用红黑树存连接、就绪链表返回事件，时间复杂度接近常数。Reactor模型把监听、分发、业务处理分层，单Reactor适合小并发，主从多Reactor支撑高并发网关。",
        "detailed_explanation": "关键组件是Selector、Channel、事件分发器与业务处理器。流程为注册兴趣事件、epoll_wait阻塞等待、返回就绪fd集合、逐个分发读写。相对select轮询全量fd，epoll只返回就绪集合且用mmap共享内存，万级连接依然稳定。权衡是单Reactor业务耗时会卡死事件循环，必须把耗时逻辑丢线程池。常见坑是空轮询bug打满CPU、读半包未处理粘包拆包、惊群效应下多进程同时被唤醒。",
        "project_relevance": "本项目基于Python标准库HTTP服务，每个SSE长连接长期占用服务线程。理解epoll与Reactor有助于评估何时从多线程迁往事件驱动，避免长连接耗尽线程池。",
        "related_concepts": ["threading-concurrency", "netty-framework", "sse-eventsource"],
        "interview_questions": [
            {
                "question": "【腾讯/字节】select、poll、epoll的本质区别是什么？为什么高并发必选epoll？",
                "answer": "1. select和poll每次调用都要把全量fd从用户态拷到内核态并线性扫描，连接数上万后扫描与拷贝开销爆炸，且select有1024上限；\n2. epoll用红黑树常驻内核存fd，用就绪链表只返回有事件的fd，并用mmap减少拷贝，复杂度与就绪数相关而非总数；\n3. 所以C10K以上场景必选epoll，配合边缘触发与非阻塞读写，一根线程可扛数万空闲长连接。"
            },
            {
                "question": "【阿里/美团】Reactor的单线程、多线程、主从多线程三种形态怎么选？Netty如何落地？",
                "answer": "1. 单Reactor单线程适合连接少、业务轻的场景，代码简单但业务一耗时就卡死所有连接；\n2. 单Reactor多线程把业务丢线程池，适合业务偏重但连接数中等的服务；\n3. 主从Reactor用Boss组只管accept、Worker组管读写，Netty默认即此形态，网关与IM等十万级长连接服务必选，Boss数配1到2，Worker配2倍核数。"
            }
        ]
    },
    {
        "id": "netty-framework",
        "name": "Netty 高性能网络框架 (Netty)",
        "aliases": ["netty", "网络框架", "bytebuf", "channel", "pipeline", "eventloop", "零拷贝", "reactor框架"],
        "category": "后端与分布式",
        "definition": "Netty是基于Java NIO封装的异步事件驱动网络框架，用主从Reactor线程模型处理连接接入与读写。核心抽象是Channel、EventLoop、Pipeline责任链与ByteBuf内存池，屏蔽了epoll、粘包拆包、断线重连等细节，是Dubbo、ES、RocketMQ的通信底座。",
        "detailed_explanation": "关键组件是BossGroup、WorkerGroup、ChannelPipeline与ByteBuf池化内存。数据经解码、业务、编码三段流水线，ByteBuf用引用计数加对象池复用堆外内存，文件发送用零拷贝。Handler里绝不能写阻塞调用，否则卡死整个EventLoop。常见坑是ByteBuf忘记release致堆外泄漏、pipeline顺序写反、共享Handler带可变状态并发错乱。",
        "project_relevance": "本项目SSE推送与快照广播本质是长连接事件分发，与Netty的Pipeline同构。借鉴其编解码与业务分离原则，可把耗时文件解析移出请求线程，保证心跳线程不被卡住。",
        "related_concepts": ["nio-epoll", "rpc-framework", "tcp-protocol"],
        "interview_questions": [
            {
                "question": "【字节/阿里】Netty为什么快？从线程模型、内存、零拷贝三个角度剖析。",
                "answer": "1. 线程模型：主从Reactor加无锁串行化执行，同Channel事件永远绑同一线程，避免锁竞争与上下文切换；\n2. 内存：ByteBuf池化复用堆外内存，引用计数精准释放，大流量下GC压力远小于每次new byte数组；\n3. 零拷贝：文件发送用FileRegion调sendfile，数据不经过用户态；接收用CompositeByteBuf组合多段内存而不做字节拷贝。"
            },
            {
                "question": "【腾讯/美团】Netty中耗时业务写在Handler里有什么后果？ByteBuf泄漏如何排查？",
                "answer": "1. Handler跑在EventLoop上，里面调阻塞DB或 sleep 会卡死该线程绑定的全部上千连接，正确做法是丢到业务线程池或用UnorderedMemoryAwareExecutor隔离；\n2. ByteBuf泄漏多因忘记release或异常分支未释放，开ResourceLeakDetector为PARANOID级跑压测，看泄漏报告的创建堆栈定位；\n3. 规范是入站谁最后用谁释放，出站由框架接管，共享Handler必须无状态或加锁隔离。"
            }
        ]
    },
    {
        "id": "sharding",
        "name": "分库分表与 Sharding 路由策略 (Database Sharding)",
        "aliases": ["分库分表", "sharding", "分片", "shardingsphere", "mycat", "水平拆分", "垂直拆分", "路由策略"],
        "category": "数据库与存储引擎",
        "definition": "当单表数据量破千万或单库写吞吐见顶时，把数据按某字段规则打散到多个库表。垂直拆分按业务解耦大表，水平拆分按哈希或范围切分行。路由层根据分片键算出目标库表，聚合查询需跨片归并。分片键一旦选错，跨片事务与全局排序会成为长期噩梦。",
        "detailed_explanation": "关键组件是分片键、路由算法、全局主键生成器与跨片归并器。哈希取模简单但扩容要迁几乎全量数据，一致性哈希加虚拟节点可降低迁移量，范围分片利于区间查询但易热点。工作流程为解析SQL、算路由、改写下发、多片执行、内存归并。权衡是分片越多写入越分散，但跨片join与分页越痛苦。常见坑是无分片键查询引发全片广播、分页跨片排序错乱、扩容期间双写不一致。",
        "project_relevance": "本项目把多Agent会话事件追加写入本地JSONL文件，单项目会话膨胀后扫描与查询变慢。借鉴分片思想，可按项目目录或时间窗口切分事件文件，避免单个巨型文件拖慢后台轮询线程的全量扫描。",
        "related_concepts": ["mysql-innodb-bplus-tree", "consistent-hashing", "snowflake-id"],
        "interview_questions": [
            {
                "question": "【阿里/字节】分库分表后，原来的join、分页、全局唯一ID分别怎么解决？",
                "answer": "1. join：能冗余就做宽表冗余，实时性要求低走离线同步，强一致小表可在各片全量同步一份广播表；\n2. 分页：跨片order by加limit需每片取足量再全局归并，深翻页改用游标或禁止跳页；\n3. 全局ID：禁用自增，改用Snowflake或号段模式，保证趋势递增且全局唯一，避免主键冲突。"
            },
            {
                "question": "【美团/拼多多】哈希取模分片扩容为什么痛苦？如何设计平滑扩容方案？",
                "answer": "1. 取模分片中节点数变化会导致几乎所有key重映射，迁移量巨大且期间路由错乱；\n2. 一致性哈希只迁移相邻区间数据，配合虚拟节点更均衡；\n3. 生产常用双写迁移：新片预热、线上双写新老片、离线校验对账、灰度切读、停写老片下线，全程可回滚，扩容窗口选低峰并限流迁移任务。"
            }
        ]
    },
    {
        "id": "idempotency",
        "name": "幂等性设计与防重机制 (Idempotency)",
        "aliases": ["幂等", "idempotency", "防重", "去重表", "token机制", "requestid", "唯一索引", "at-least-once"],
        "category": "后端与分布式",
        "definition": "幂等指同一操作重复执行多次与执行一次效果相同，是应对网络重试与消息重复投递的必备设计。落地手段有前端防抖加请求唯一号、服务端Token先发后销、数据库唯一约束兜底、状态机限定流转。查询与删除天然幂等，最危险的是创建订单与扣款类非幂等写操作。",
        "detailed_explanation": "关键组件是全局请求号、去重表或Redis指纹、状态机。流程为客户端生成唯一号并携带、服务端用SETNX抢占、业务用唯一索引二次兜底、成功后缓存结果供重复查询直接返回。Token机制防表单重复提交，状态机用where条件限定只能从待支付走向已支付。权衡是强幂等带来额外一次存储写入，高并发下用布隆加Redis扛住。常见坑是先执行业务后写去重表导致崩溃窗口、先删Token后执行业务导致并发穿透。",
        "project_relevance": "本项目后台轮询线程周期性扫描会话文件，SSE断线重连会重推事件，前端45秒兜底轮询也可能重复拉取。若事件落库与图谱更新不做请求级去重，同一会话轮次会被重复计数，必须给事件加全局序号做幂等消费。",
        "related_concepts": ["mq-kafka-reliability", "restful-architecture", "distributed-transaction"],
        "interview_questions": [
            {
                "question": "【阿里/美团】下单接口用户连点两次、网关超时重试、MQ重复投递，三种重复分别怎么防？",
                "answer": "1. 连点：前端按钮置灰加防抖，后端要求先领一次性Token，消费后立即删除，无Token直接拒绝；\n2. 网关重试：接口要求携带客户端生成的RequestId，服务端SETNX抢占并缓存执行结果，重试直接返回旧结果；\n3. MQ重复：消费端按业务唯一键查去重表，已处理则ack跳过，写操作走状态机CAS，只有处于待处理态才允许推进。"
            },
            {
                "question": "【字节/拼多多】Token机制和数据库唯一索引两道防线各自解决什么？顺序写反会怎样？",
                "answer": "1. Token挡住绝大多数重复提交，成本低但扛不住绕过前端的直接刷接口；唯一索引是最后一道强约束，靠存储层原子性兜底；\n2. 必须先抢Token再执行业务，先执行业务后记去重会在崩溃瞬间留下已执行未标记的窗口，重试即资损；\n3. 高并发下Token用Redis Lua保证查销原子，DB层唯一键冲突直接转查询旧结果返回，不抛错给用户。"
            }
        ]
    },
    {
        "id": "rate-limiter",
        "name": "限流算法与网关防护 (Rate Limiter)",
        "aliases": ["限流", "rate limiter", "令牌桶", "漏桶", "滑动窗口", "sentinel限流", "qps", "削峰"],
        "category": "后端与分布式",
        "definition": "限流是在流量超过系统承载前主动丢弃或排队部分请求，保住核心链路不被打垮。令牌桶按固定速率发令牌允许突发，漏桶按恒定速率放行整形流量，滑动窗口把计数精度细化到小格子防边界突刺。单机用内存计数器，分布式必须用Redis加Lua保证原子扣减。",
        "detailed_explanation": "关键组件是计数器、时间窗口、令牌发生器与拒绝策略。固定窗口在边界两秒各打满会形成双倍毛刺，滑动窗口用多格滚动消除该问题。令牌桶允许攒令牌应对秒杀突发，漏桶强制匀速适合保护慢下游。分布式下用Redis的ZSET记时间戳或Lua扣令牌。权衡是限流阈值设高等于没限，设低误伤正常用户，需按接口分级。常见坑是网关与应用双层重复限流、突发预热未做令牌预热、拒绝后无限重试形成放大。",
        "project_relevance": "本项目HTTP服务同时承载图谱查询、文件分析与SSE订阅，若某个Agent会话疯狂写事件或前端高频轮询，会挤占服务线程。借鉴限流思想，可对扫描接口与SSE订阅数做令牌桶保护，优先保住实时推送链路。",
        "related_concepts": ["circuit-breaker", "thread-pool", "polling-long-polling"],
        "interview_questions": [
            {
                "question": "【阿里/字节】令牌桶、漏桶、滑动窗口三者如何选型？秒杀场景用哪个？",
                "answer": "1. 允许突发用令牌桶，桶里攒的令牌可一次性应对秒杀前几秒洪峰，适合前端抢购入口；\n2. 必须匀速保护慢下游用漏桶，出水速率恒定，突发直接排队或丢弃，适合DB与第三方支付回调；\n3. 追求计数精确防边界毛刺用滑动窗口日志或多格计数，成本是内存更高，网关层常用滑动窗口做通用API限流。"
            },
            {
                "question": "【美团/腾讯】分布式限流用Redis怎么实现才原子？超大QPS下Redis本身成为瓶颈怎么办？",
                "answer": "1. 用Lua脚本把取时间、清过期、计数加一、比阈值四步打包原子执行，或用令牌桶脚本原子扣令牌，避免先get后incr的竞态；\n2. Redis瓶颈时分两层：接入层先做单机滑动窗口粗限，拦截掉大部分垃圾流量，只有通过的请求才调Redis做精准全局限；\n3. 极端场景按用户ID哈希分片到多个Redis实例，限额按片均摊，接受轻微误差换取横向扩展。"
            }
        ]
    },
    {
        "id": "circuit-breaker",
        "name": "熔断降级与 Sentinel 防护 (Circuit Breaker)",
        "aliases": ["熔断", "circuit breaker", "降级", "hystrix", "sentinel", "舱壁隔离", "超时控制", "快速失败"],
        "category": "分布式系统与微服务",
        "definition": "熔断是在下游故障时主动切断调用、快速失败，防止线程被拖死并连锁雪崩。断路器有闭合、断开、半开三态：错误率超阈值跳断开，直接拒绝请求；冷却后放少量试探流量，成功则闭合。降级是熔断后的B计划，返回缓存、默认值或简化页面，保证核心可用。",
        "detailed_explanation": "关键组件是滑动统计窗口、错误率判定器、半开试探器与降级 fallback。Sentinel按资源统计RT与异常比，Hystrix按线程池隔离。流程为调用、统计、超阈值熔断、 fallback、定时半开探测。配合舱壁隔离把核心与非核心线程池分开，超时设置必须小于上游。常见坑是熔断阈值拍脑袋导致正常抖动也熔断、fallback又调同一故障依赖形成二次雪崩、半开试探量过大直接把刚恢复的下游打挂。",
        "project_relevance": "本项目SSE长连接依赖文件扫描与模型分析链路，一旦分析管线卡死，请求线程会被全部占满。借鉴熔断思想，分析接口超时应快速失败返回缓存图谱，SSE推送降级为轮询快照，避免单点拖垮整个HTTP服务。",
        "related_concepts": ["rate-limiter", "thread-pool", "grpc-protocol"],
        "interview_questions": [
            {
                "question": "【阿里/字节】熔断、降级、限流三者的分工是什么？断路器三态如何流转？",
                "answer": "1. 限流管入口流量，超量直接拒；熔断管出口依赖，故障时切断调用；降级是故障后的兜底返回，三者常叠加使用；\n2. 闭合态正常统计，错误率或慢调用超阈值跳断开态，请求直接走fallback；\n3. 断开持续冷却时间后进半开，只放少量试探，成功则闭合恢复，失败则重新断开，避免惊群打垮刚恢复的下游。"
            },
            {
                "question": "【美团/拼多多】Hystrix线程池隔离和Sentinel信号量隔离怎么选？fallback有哪些深坑？",
                "answer": "1. 线程池隔离最彻底，故障不影响主线程但有切换开销，适合重依赖核心链路；信号量隔离零切换适合轻量高频调用，Sentinel默认推荐；\n2. fallback禁止再调任何远程依赖，只能读本地缓存或返回静态兜底，否则二次雪崩；\n3. 兜底数据必须打标告知前端为降级态，避免用户基于过期数据做资金决策，恢复后主动刷新。"
            }
        ]
    },
    {
        "id": "consistent-hashing",
        "name": "一致性哈希与虚拟节点 (Consistent Hashing)",
        "aliases": ["一致性哈希", "consistent hashing", "虚拟节点", "哈希环", "数据分片", "负载均衡", "ketama", "顺时针"],
        "category": "分布式系统与微服务",
        "definition": "一致性哈希把节点和数据同时映射到一个首尾相接的哈希环上，数据顺时针归属第一个遇到的节点。增减节点时只迁移环上相邻区间的数据，迁移量从取模方案的全量降到平均1除以N。引入虚拟节点让每个物理节点对应多个环上位置，解决节点少时的数据倾斜。",
        "detailed_explanation": "关键组件是哈希函数、哈希环、有序映射表与虚拟节点副本。查找时对key哈希后在TreeMap找后继节点，OlogN。虚拟节点数越多分布越均匀，但元数据与心跳成本越高，常用150到200副本。权衡是它只保证最少迁移，不保证绝对均衡，热点key仍需本地缓存。常见坑是节点异构却分同样虚拟节点导致小机器被压垮、哈希函数分布差形成聚集、节点宕机后压力全压到顺时针邻居形成连锁。",
        "project_relevance": "本项目若把会话事件按项目目录哈希分散到多个分片文件或缓存分区，新增归档分区时一致性哈希可只迁移相邻项目数据。虚拟节点思想也可用于把SSE订阅均衡到多个推送分组，避免单分组过热。",
        "related_concepts": ["sharding", "cap-base-theorem", "redis-distributed-lock"],
        "interview_questions": [
            {
                "question": "【字节/阿里】普通取模和一致性哈希在扩容时差多少？虚拟节点解决了什么？",
                "answer": "1. 取模扩容节点数变化几乎全量key重映射，迁移成本是O全量；一致性哈希只迁移新增节点顺时针前驱区间的数据，约1除以N；\n2. 节点很少时区间大小随机，虚拟节点让每个物理节点占多个位置，大数定律拉平分布；\n3. 宕机时其数据顺移到邻居，虚拟节点打散后压力分散到多台而非单台，避免单点过载。"
            },
            {
                "question": "【腾讯/美团】一致性哈希做不到的事有哪些？热点key和异构节点怎么治理？",
                "answer": "1. 做不到绝对均衡与热点打散，爆款key永远落同一节点，需在接入层加本地缓存或热点自动分裂；\n2. 异构节点按机器权重分配不同数量虚拟节点，小机器少分；\n3. 生产需配套数据迁移限流与校验，迁移期间双读做一致性对账，防止新节点未预热就承接全量流量。"
            }
        ]
    },
    {
        "id": "snowflake-id",
        "name": "分布式 ID 生成方案 (Snowflake/Leaf)",
        "aliases": ["snowflake", "分布式id", "leaf", "uuid", "号段模式", "全局唯一id", "趋势递增", "时钟回拨"],
        "category": "分布式系统与微服务",
        "definition": "分布式ID要求全局唯一、趋势递增、高并发低延迟。Twitter Snowflake把64位切为时间戳、机器号、序列号三段，单机每毫秒可发4096个。美团Leaf有号段与Snowflake双模式，号段预批量取号抗时钟回拨。UUID无序且过长，只适合不排序的随机场景。",
        "detailed_explanation": "关键是时间戳回拨处理、机器号分配、序列号并发。Snowflake强依赖时钟，回拨会导致重复或停发，需引入回拨等待或借用高位。Leaf号段模式一次从DB取一段号缓存在内存，发完再取，DB压力极小但趋势递增粒度粗。权衡是强递增利于B加树索引但暴露业务量，随机ID安全却导致页分裂。常见坑是机器号靠人工配置重复、多机房时钟不同步、序列号用锁导致每毫秒吞吐上不去。",
        "project_relevance": "本项目多Agent会话事件由轮询线程与Hook脚本并发追加，若用时间戳加随机数做ID易碰撞。借鉴Snowflake按时间加机器加序列思路，可分配趋势递增序号，支撑SSE续传去重。",
        "related_concepts": ["sharding", "mysql-innodb-bplus-tree", "idempotency"],
        "interview_questions": [
            {
                "question": "【美团/字节】Snowflake、Leaf号段、UUID三者怎么选？时钟回拨问题怎么解？",
                "answer": "1. 要排序且高并发选Snowflake，毫秒内序列号自增，趋势递增对B加树最友好；\n2. 时钟敏感业务选Leaf号段，ID来自DB批量预发，不依赖机器时钟，回拨也无影响；\n3. 回拨治理：小步回拨等待时钟追上，大步回拨拉黑该机器号并告警，跨机房部署NTP加监控，绝不允许回拨时继续发号。"
            },
            {
                "question": "【阿里/拼多多】为什么分布式ID要趋势递增？随机ID对MySQL索引有什么伤害？",
                "answer": "1. InnoDB按主键聚簇存储，趋势递增ID永远追加到B加树最右页，页分裂极少，写入是顺序IO；\n2. UUID随机导致每次插入都要在树中间定位并频繁页分裂，碎片与随机IO暴涨，写入吞吐腰斩；\n3. 若必须用随机ID，改用有序UUID或把主键与排序键分离，主键随机、另建时间索引供范围查询。"
            }
        ]
    },
    {
        "id": "distributed-transaction",
        "name": "分布式事务最终一致性 (2PC/TCC/Saga)",
        "aliases": ["分布式事务", "2pc", "tcc", "saga", "seata", "本地消息表", "最终一致性", "柔性事务"],
        "category": "分布式系统与微服务",
        "definition": "跨库跨服务的写操作无法靠单机事务保证原子，必须用柔性事务换取可用性。2PC强一致但协调者单点且锁持有久，已被淘汰。生产主流是TCC的预留确认取消、Saga的正向加补偿、本地消息表与MQ事务消息，核心都是先保证最终一致，再用对账兜底。",
        "detailed_explanation": "关键组件是事务协调器、分支事务、补偿动作与幂等防重。TCC要求每个服务提供Try预留、Confirm确认、Cancel释放三接口，对业务侵入大但一致性最强。Saga把长事务拆成多步，失败按逆序补偿，适合长链路。本地消息表把业务与消息落同一库事务，靠轮询投递。权衡是补偿必须幂等且可重试，隔离性只能做到最终。常见坑是Try成功Confirm失败无重试、补偿逻辑又调外部导致二次失败、空回滚与悬挂未处理。",
        "project_relevance": "本项目事件写入文件、图谱更新内存、SSE推送前端三步跨介质，崩溃时必然出现写了文件没推图谱的不一致。借鉴本地消息表思想，可把事件先落盘为待投递状态，由轮询线程可靠投递并打标，从而实现最终一致。",
        "related_concepts": ["acid-transactions", "mq-kafka-reliability", "idempotency"],
        "interview_questions": [
            {
                "question": "【阿里/字节】TCC、Saga、本地消息表、MQ事务消息分别适合什么场景？",
                "answer": "1. 资金账户强一致选TCC，预留冻结资金，确认扣减，侵入大但无中间脏读；\n2. 长链路如旅行下单选Saga，每步正向推进，失败逆序补偿；\n3. 单体拆分过渡期用本地消息表，业务与消息同库事务，轮询投递最易落地；\n4. 全异步链路用RocketMQ事务消息，半消息加回查保证最终投递，下游幂等消费。"
            },
            {
                "question": "【美团/腾讯】TCC的空回滚、悬挂、幂等三大坑分别是什么？怎么防？",
                "answer": "1. 空回滚：Try超时但实际没执行，Cancel先到，需记录Try空转标记，空回滚直接成功返回；\n2. 悬挂：Cancel先到后Try迟到又预留资源，需用事务ID判重，Try发现已回滚则拒绝预留；\n3. 幂等：Confirm与Cancel都会被重试，分支记录表按事务ID加状态机去重，已终态直接返回历史结果。"
            }
        ]
    },
    {
        "id": "elasticsearch",
        "name": "Elasticsearch 倒排索引与打分 (Elasticsearch)",
        "aliases": ["elasticsearch", "es", "倒排索引", "lucene", "分词器", "bm25", "相关性打分", "全文检索"],
        "category": "数据库与存储引擎",
        "definition": "ES是基于Lucene的分布式全文检索引擎，核心是倒排索引：词项映射到含该词的文档链表。写入经分词、内存缓冲、段合并形成不可变段，删除只是打标。查询按BM25算词频、逆文档频率与长度归一，相关性高的文档排前，天然适合代码、日志、会话的模糊检索。",
        "detailed_explanation": "关键组件是分词器、倒排表、段、translog与分片副本。写入先记translog再进内存缓冲，定时刷段，段不可变靠后台合并。BM25在TFIDF基础上压制词频饱和并做长度归一，长文档不吃亏。权衡是分片多写入并行但聚合要跨片归并，副本多读吞吐高但写入放大。常见坑是深分页用from加size拖垮协调节点、聚合基数爆炸打爆内存、ik分词与查询分词不一致导致搜不到。",
        "project_relevance": "本项目要在海量Agent会话轮次与文件快照中按关键词定位架构讨论，靠轮询线程逐文件grep迟早变慢。借鉴倒排思想，可对会话文本建内存倒排或接入ES，把架构问答检索从全量扫描降为词项求交。",
        "related_concepts": ["sqlite-db", "vector-db-ann", "polling-long-polling"],
        "interview_questions": [
            {
                "question": "【字节/阿里】ES倒排索引长什么样？写入和删除文档到底发生了什么？",
                "answer": "1. 倒排由词典加倒排表组成，词典存分词后的词项，倒排表存含该词的文档ID、词频与位置，查词即取链表求交；\n2. 写入先进内存缓冲并记translog防丢，定时生成不可变段并可被搜索，段后台合并优化；\n3. 删除只在新段打删除标记，查询时过滤，段合并时才物理剔除，所以ES是近实时而非强实时。"
            },
            {
                "question": "【美团/腾讯】ES深分页为什么慢？TB级日志场景怎么优化查询与写入？",
                "answer": "1. from加size要每片取足量再全局排序归并，页越深堆内存与网络越大，改用search_after游标或scroll快照；\n2. 日志按天建索引加ILM冷热分离，热节点SSD扛写入，冷节点大盘存历史；\n3. 写入批量bulk、关不必要分词、合理分片数，聚合高基数字段用composite分页，(keyword)精确字段与text全文分开建模。"
            }
        ]
    },
    {
        "id": "local-cache",
        "name": "本地缓存与多级缓存架构 (Caffeine)",
        "aliases": ["本地缓存", "caffeine", "guava cache", "多级缓存", "堆外缓存", "w-tiny-lfu", "进程内缓存", "缓存分层"],
        "category": "后端与分布式",
        "definition": "本地缓存是进程堆内的KV存储，Caffeine用W-TinyLFU近似统计访问频率，命中率接近理论最优且读写接近无锁，延迟是纳秒级。标准架构是本地热缓存扛高频读、Redis扛跨机共享、DB兜底，更新用失效加版本号防止脏读。本地缓存容量小，存的是计算贵、变化慢的热点。",
        "detailed_explanation": "关键组件是窗口队列、主缓存区、频率草图与过期器。W-TinyLFU用小样本判断新key是否值得接纳，防突发冷key冲掉热点。流程为读先查本地、未中查Redis回填、再未中查库三级穿透。权衡是多机本地缓存天然不一致，需用MQ广播失效或短TTL妥协。常见坑是缓存对象可变被业务篡改、大value频繁 YoungGC、无上限缓存把堆撑爆、缓存雪崩时多机同时回源打挂DB。",
        "project_relevance": "本项目图谱查询与文件分析结果被前端反复拉取，每次重跑解析浪费CPU。借鉴多级缓存，把图谱快照放进程内字典缓存，SSE只推版本号，命中即返缓存，扫描线程负责失效。",
        "related_concepts": ["cache-concurrency-consistency", "redis-distributed-lock", "threading-concurrency"],
        "interview_questions": [
            {
                "question": "【字节/美团】Caffeine为什么比Guava Cache命中率高？W-TinyLFU在解决什么问题？",
                "answer": "1. Guava用简单LRU，突发扫描式冷key会一次性冲掉全部热点，命中率雪崩；\n2. W-TinyLFU用频率草图统计历史热度，新key要先跟受害者比热度，赢了才准入住，天生抗扫描污染；\n3. 实现上读写大量用无锁缓冲批量摊销，并发吞吐远高于Guava的锁分段，所以高并发读多写少场景无脑选Caffeine。"
            },
            {
                "question": "【阿里/拼多多】多级缓存如何保证一致性？本地缓存更新是推失效还是等过期？",
                "answer": "1. 强一致场景走更新DB删Redis再广播本地失效，用Canal或MQ推失效消息，各机收到清本地条目；\n2. 允许秒级延迟用短TTL妥协，本地过期时间设秒级，Redis设分钟级， simplicity换一致；\n3. 大忌是先清缓存再更库，中间读会回填脏数据，必须先更库再删缓存，配版本号防止删旧盖新。"
            }
        ]
    },
    {
        "id": "delay-queue",
        "name": "延迟队列实现方案对比 (Delay Queue)",
        "aliases": ["延迟队列", "delay queue", "delayqueue", "时间轮", "ttl+死信", "rocketmq延时", "订单超时", "定时任务"],
        "category": "后端与分布式",
        "definition": "延迟队列让消息在指定时间后才被消费，典型场景是订单三十分钟未支付自动取消。实现有JDK DelayQueue堆顶精确唤醒、Redis过期监听、时间轮分槽推进、RocketMQ固定延时等级、数据库轮询扫表五派。单机量小用内存，分布式海量必须用消息中间件或时间轮集群。",
        "detailed_explanation": "关键是到期判定、触发精度、持久化与伸缩。DelayQueue基于最小堆，take时堆顶未到期则等待，到期精度毫秒级但宕机全丢。Redis键过期回调不可靠且集群下丢事件，生产多用ZSET按到期时间排序加轮询搬运。Netty时间轮把一圈切多格，指针每格推进，O1插入适合海量定时。权衡是精度越高轮询越密，持久化越强写入越重。常见坑是DB扫表无索引全表扫、过期回调当可靠投递、时间轮格子太粗错过精度。",
        "project_relevance": "本项目后台轮询线程以固定45秒间隔兜底扫描，本质是粗粒度延迟任务。若要支持会话超时归档、SSE断线后延迟重推、快照定时失效，用时间轮或延迟队列替代固定sleep轮询，可把空转开销与触发精度同时做好。",
        "related_concepts": ["mq-kafka-reliability", "polling-long-polling", "thread-pool"],
        "interview_questions": [
            {
                "question": "【阿里/美团】订单30分钟未支付自动取消，五种延迟方案怎么选？",
                "answer": "1. 量小单机用DelayQueue或ScheduledThreadPool，简单但宕机丢任务；\n2. 通用量用RocketMQ延时消息，固定等级选最接近档，持久化且可重试；\n3. 任意精度海量用时间轮加持久化表，到期搬运到MQ，精度与吞吐兼得；\n4. 反模式是Redis键过期回调做核心链路，丢事件无告警，资损难追查。"
            },
            {
                "question": "【字节/腾讯】时间轮的原理是什么？Kafka的层级时间轮好在哪里？",
                "answer": "1. 时间轮把时间切成环形格子，任务按到期差值挂到对应格链表，指针每tick走一格触发整格，插入删除都是O1；\n2. 单层轮圈数大时空转多，Kafka用多层轮，高层一格对应低层一圈，远期任务先挂高层，临近再下沉；\n3. 对比ZSET轮询，时间轮无中心锁竞争，几十万定时任务依然稳定，是IM心跳与RPC超时的标准解。"
            }
        ]
    },
    {
        "id": "mysql-index-optimization",
        "name": "MySQL 索引优化与执行计划 (EXPLAIN)",
        "aliases": ["索引优化", "explain", "执行计划", "最左前缀", "覆盖索引", "回表", "慢查询", "索引失效"],
        "category": "数据库与存储引擎",
        "definition": "索引优化是用EXPLAIN看懂优化器如何执行SQL，再用最左前缀、覆盖索引、合理join顺序消除慢查询。type从const、ref、range一路劣化到ALL全表扫，Extra出现Using filesort和temporary即需治理。本质是让查询走窄索引顺序读，少回表、少排序、少临时表。",
        "detailed_explanation": "关键是看type、key、rows、Extra四列。最左前缀要求联合索引从左连续匹配，跳过中间列后段全失效。覆盖索引让查询列全在索引里，无需回表主键聚簇。join永远小表驱动大表，大表连接列必须有索引。权衡是索引加速读但拖慢写并占空间，单表超五个索引必审。常见坑是在索引列做函数运算、隐式类型转换、like前导百分号、or两边一侧无索引，都会让索引瞬间失效。",
        "project_relevance": "本项目虽用文件与SQLite承载会话数据，但按项目、时间、会话ID的多维查询同样面临全量扫描问题。借鉴覆盖索引与最左前缀思想，可为事件文件建项目加时间的复合检索键，避免轮询线程每次都全文件grep。",
        "related_concepts": ["mysql-innodb-bplus-tree", "sqlite-db", "acid-transactions"],
        "interview_questions": [
            {
                "question": "【阿里/字节】联合索引(a,b,c)，where b=1、where a=1 and c=3、where a>1 and b=2分别走不走索引？",
                "answer": "1. 只查b完全不走，因为跳过最左列a，优化器只能全表扫；\n2. a加c只有a段生效，c因中间断档失效，type最多ref而非高效的复合命中；\n3. a范围加b等值，a的范围让后段b失效，改写为等值或把范围列放最后才能全命中，生产建索引必须把等值列前置。"
            },
            {
                "question": "【美团/拼多多】线上慢查询飙高，从EXPLAIN到治理的完整链路是什么？",
                "answer": "1. 开慢日志抓rows_examined远大于rows_sent的SQL，对着EXPLAIN看type是否为ALL、key是否为NULL、Extra有无filesort；\n2. 治理按顺序：加覆盖索引消回表、改写函数与隐式转换、拆大分页为游标、join补连接列索引；\n3. 上线前用影子库压测验证rows十倍下降，发布后盯慢日志回落曲线，索引数与写入延迟同步监控防过度建索引。"
            }
        ]
    },
    {
        "id": "redis-data-structures",
        "name": "Redis 底层数据结构 (SDS/跳表/压缩表)",
        "aliases": ["redis数据结构", "sds", "跳表", "skiplist", "ziplist", "listpack", "quicklist", "dict"],
        "category": "数据库与存储引擎",
        "definition": "Redis为每种数据类型配了最省内存又最快的底层编码。字符串用SDS预分配加惰性释放实现O1追加，有序集合用跳表加字典实现范围与单点双优，小集合用listpack紧凑连存省内存，大了自动转跳表或哈希表。对象头里的编码字段让同一命令在不同数据规模下自动切换最优实现。",
        "detailed_explanation": "关键组件是SDS、dict渐进式rehash、跳表多层索引、listpack紧凑编码。SDS存长度与空闲数，取长O1且二进制安全。dict用两表渐进搬迁避免扩容卡顿。跳表期望OlogN，范围查询沿链表顺序走，zset再配dict让单点也是O1。listpack把小对象压成连续字节，超阈值自动转哈希表或跳表。常见坑是大value内存爆炸、rehash期间内存短暂翻倍。",
        "project_relevance": "本项目用内存字典维护会话索引与SSE订阅表，相当于手写简易Redis。若订阅表用无序大字典存海量事件ID，范围拉取只能全扫；借鉴跳表加字典双索引，可让会话事件既支持单点去重又支持区间续传。",
        "related_concepts": ["redis-distributed-lock", "cache-concurrency-consistency", "local-cache"],
        "interview_questions": [
            {
                "question": "【字节/阿里】为什么zset用跳表而不用红黑树或B加树？SDS相对C字符串好在哪？",
                "answer": "1. 跳表实现简单且天然有序，区间查询直接沿底层链表顺序走，红黑树范围要中序遍历更绕，并发下跳表分层更新锁粒度更小；\n2. SDS存长度取长O1，C字符串要扫到零终止符是ON；SDS预分配与惰性释放让追加均摊O1，C字符串每次realloc全拷；\n3. SDS二进制安全可存任意字节，C字符串遇零截断，Redis存图片与协议包全靠这点。"
            },
            {
                "question": "【腾讯/美团】ziplist、listpack、quicklist的演进关系是什么？大key有什么危害？",
                "answer": "1. ziplist连存省内存但更新要连锁 realloc，listpack为每个元素加长度编码终结连锁更新，quicklist再把listpack分页组装成双链表，兼得压缩与分片；\n2. 小hash与小zset默认listpack，超阈值自动转哈希表或跳表，内存与速度自动 trade；\n3. 大key单value数MB会导致单线程长时间搬运，阻塞所有请求，必须拆分为hash分片并用scan渐进遍历。"
            }
        ]
    },
    {
        "id": "rpc-framework",
        "name": "RPC 框架原理与序列化协议 (RPC)",
        "aliases": ["rpc", "远程调用", "dubbo", "thrift", "protobuf", "序列化", "服务发现", "负载均衡"],
        "category": "分布式系统与微服务",
        "definition": "RPC让调用远程服务像调本地函数，框架包办寻址、序列化、传输、超时重试全套脏活。调用方按接口生成动态代理，消费端从注册中心拉地址做负载均衡，参数经protobuf等协议压成字节流走TCP，服务端解码后反射执行再原路返回。本质是用约定与代码生成消灭手写HTTP拼装。",
        "detailed_explanation": "关键组件是注册中心、动态代理、序列化器、负载均衡与容错。protobuf用字段编号加变长编码，包比JSON小几倍且跨语言。Dubbo默认用Netty长连接复用，避免短连接三次握手。超时重试必须配幂等，非幂等写默认不重试。权衡是二进制快但不可读，JSON易调但臃肿。常见坑是超时设太长拖垮调用方线程池、重试风暴打挂刚恢复的下游、接口不兼容升级导致序列化炸裂。",
        "project_relevance": "本项目Hook脚本与本地HTTP服务之间、分析管线各阶段之间多为松散JSON调用。若抽取高频事件上报为类RPC契约并固定版本，可减少字段漂移解析失败，超时重试策略也直接复用。",
        "related_concepts": ["grpc-protocol", "netty-framework", "service-mesh"],
        "interview_questions": [
            {
                "question": "【阿里/字节】一次Dubbo调用从代理到返回的完整链路是什么？注册中心挂了还能调用吗？",
                "answer": "1. 消费端按接口生成代理，调用时按负载均衡选地址，参数protobuf序列化后经Netty长连接发出，服务端解码反射执行业务再回写；\n2. 注册中心只负责启动拉地址与变更推送，调用走直连，挂了后已有地址照常用，新扩容节点找不到而已；\n3. 所以注册中心是AP设计，允许短暂不一致，消费端本地缓存地址表兜底。"
            },
            {
                "question": "【美团/腾讯】protobuf为什么比JSON小而快？RPC重试有哪些资深坑？",
                "answer": "1. protobuf字段用编号不用名字，数值用varint变长编码，小数只占一字节，JSON每个字段都要写全名加引号，体积差数倍且解析要扫字符串；\n2. 重试只敢用于幂等读，非幂等写重试即资损，必须配重试次数加幂等号；\n3. 超时要小于上游，失败快退避重试，熔断打开后直接短路，避免重试风暴把半活的下游彻底打死。"
            }
        ]
    },
    {
        "id": "service-mesh",
        "name": "Service Mesh 服务网格与 Sidecar (Istio)",
        "aliases": ["service mesh", "服务网格", "sidecar", "istio", "envoy", "linkerd", "数据平面", "控制平面"],
        "category": "分布式系统与微服务",
        "definition": "服务网格把熔断、限流、观测、mTLS这些通信能力从业务进程抽出来，下沉到每个Pod旁的Sidecar代理。业务只管调本地端口，流量劫持到Envoy后再做路由与策略，控制平面统一下发规则。好处是多语言一视同仁，坏处是多一跳延迟与运维复杂度，小规模用它纯属负优化。",
        "detailed_explanation": "关键是数据平面Envoy与控制平面Istiod。Envoy做服务发现、负载均衡、熔断与遥测上报，Istiod下发路由与证书。mTLS由Sidecar自动握手，业务零改造即得加密。金丝雀按权重切流，出问题秒回滚。权衡是每跳加毫秒级延迟，边车资源占用可观， latencies敏感链路需调优。常见坑是iptables劫持把健康检查也绕进去、重试与超时在边车和业务双层叠加、控制平面挂了后规则无法更新靠缓存续命。",
        "project_relevance": "本项目多Agent平台脚本直连本地HTTP服务，鉴权限流日志散落各处。借鉴边车思想收敛到入口统一中间层，脚本只调本地回环，治理能力可独立升级而不碰业务。",
        "related_concepts": ["rpc-framework", "grpc-protocol", "circuit-breaker"],
        "interview_questions": [
            {
                "question": "【阿里/字节】Service Mesh相对Spring Cloud和Dubbo解决了什么？什么规模不该上？",
                "answer": "1. 解决多语言治理不统一，Java的熔断限流Go和Python也要重写一遍，网格下沉后各语言只调本地端口；\n2. 升级治理能力不用全量发版业务，控制平面统一下发；\n3. 服务少于几十个、 invoked链短、团队无专职运维时别上，多一跳延迟加边车资源与排障复杂度，收益盖不住成本。"
            },
            {
                "question": "【腾讯/美团】Sidecar的mTLS和灰度是怎么落地的？多一跳延迟怎么优化？",
                "answer": "1. 控制平面给每对Sidecar签发短期证书，握手与轮换全自动，业务无感即得双向认证与加密；\n2. 灰度在Envoy按权重或Header切流，金丝雀先百分之一验证再放大，出错一键回滚规则；\n3. 延迟靠本地回环零拷贝、长连接复用、按需开启过滤器链，极端链路可对核心服务开直通旁路，网格只做观测不做拦截。"
            }
        ]
    },
    {
        "id": "mysql-mvcc",
        "name": "MVCC 多版本并发控制与 ReadView (MVCC)",
        "aliases": ["mvcc", "多版本并发", "readview", "undolog", "快照读", "当前读", "可重复读", "rr隔离"],
        "category": "数据库与存储引擎",
        "definition": "MVCC让读写互不阻塞，写时保留旧版本在Undo链，读时按ReadView挑对自己可见的版本。普通select走快照读不加锁，update走当前读加锁。可重复读下事务第一次读建快照，之后同样查询永远看到同一版本，彻底消灭不可重复读，同时并发远高于全程加锁。",
        "detailed_explanation": "关键是隐藏列DB_TRX_ID、Undo版本链、ReadView三件套。ReadView记活跃事务数组与高低水位，小于低水位已提交可见，大于高水位未来不可见，中间看是否在活跃数组。RR只在首次读建视图所以可重复，RC每次读都新建所以看到最新已提交。当前读加间隙锁防幻读，快照读不管新插入。常见坑是长事务拖住Undo导致膨胀、RC下用快照语义做资金判断、误以为RR完全无幻读而漏掉当前读场景。",
        "project_relevance": "本项目文件锁做互斥、轮询线程做快照读取，天然是读写并发模型。借鉴MVCC快照读思想，SSE推送可读不可变的历史快照版本，后台扫描生成新版本后原子切换引用，读推送全程无锁，消灭长扫描阻塞实时查询的毛刺。",
        "related_concepts": ["acid-transactions", "mysql-innodb-bplus-tree", "threading-concurrency"],
        "interview_questions": [
            {
                "question": "【腾讯/阿里】RR和RC的ReadView生成时机有何不同？这如何决定两者现象差异？",
                "answer": "1. RR在事务第一次快照读时建ReadView并复用到结束，所以同样SQL永远看到同一版本，不可重复读消失；\n2. RC每次快照读都新建视图，总能看到最新已提交，同一事务两次读可看到别人新提交，允许不可重复读；\n3. 两者写都走当前读加锁，RR再用间隙锁防幻读，RC无间隙锁，选型看业务要可重复还是要最新。"
            },
            {
                "question": "【字节/美团】长事务为什么会搞垮MVCC？线上如何发现和治理？",
                "answer": "1. 长事务的ReadView低水位卡住，期间所有旧版本都不能 purge，Undo链越拖越长，快照读要回溯几十版，查询越来越慢；\n2. 发现靠查活跃事务时长与Undo段大小，慢查询里突现回溯深的读；\n3. 治理是拆大事务、禁事务里调远程、只读事务及时提交，定时巡检杀掉超阈值空闲事务。"
            }
        ]
    },
    {
        "id": "bloom-filter",
        "name": "布隆过滤器与缓存穿透治理 (Bloom Filter)",
        "aliases": ["布隆过滤器", "bloom filter", "bloomfilter", "缓存穿透", "误判率", "位数组", "哈希函数", "布谷鸟过滤器"],
        "category": "数据库与存储引擎",
        "definition": "布隆过滤器用位数组加多个哈希函数判断元素是否在集合里，说不在就一定不在，说在则有小概率误判。它以百分之一左右误判率换取极小内存，千万级key只需几十MB。标准用法是查缓存与DB前先过一遍布隆，不存在直接返回，彻底挡住恶意随机key打穿DB的穿透攻击。",
        "detailed_explanation": "关键是位数组长度、哈希个数与误判公式的搭配，哈希太少冲突多，太多打满快。新增只置位不支持删除，删了会误伤，要删除换布谷鸟过滤器。需在数据变更时同步重建或增量加位，配空值缓存做双保险。权衡是内存越小误判越高，规模预估错一个量级误判直接起飞。常见坑是规模翻倍后不重建、哈希函数相关导致误判远超理论、用布隆挡库存扣减这类必须精确的场景。",
        "project_relevance": "本项目按关键词检索会话与文件时，随机杂词会触发全量文件扫描，相当于缓存穿透。若对已知会话ID与文件路径建内存布隆，非法查询在入口即被拦截，轮询线程与磁盘扫描不再被垃圾流量拖垮，SSE正常推送不受影响。",
        "related_concepts": ["cache-concurrency-consistency", "redis-distributed-lock", "local-cache"],
        "interview_questions": [
            {
                "question": "【阿里/字节】缓存穿透、击穿、雪崩三者区别是什么？布隆过滤器治哪一个？",
                "answer": "1. 穿透是查根本不存在的key，缓存与DB双双 miss，恶意随机key可打挂DB，布隆在入口直接拦截治的就是它；\n2. 击穿是单个热点过期瞬间高并发回源，用互斥锁加逻辑过期治；\n3. 雪崩是大批key同时过期，用过期打散加多级缓存治，三者药方完全不同不能混用。"
            },
            {
                "question": "【美团/拼多多】布隆过滤器为什么有误判无漏判？规模翻倍后怎么办？",
                "answer": "1. 多个哈希置位，查询时全为一才判存在，冲突会让没加过的key恰好全中，所以误判有，漏判无，加过的key位一定全一；\n2. 位数组按预期key数与目标误判率预分配，规模翻倍误判指数上升，只能按新规模重建；\n3. 在线重建用双布隆滚动，新表预热完成后原子切换，切换窗口配空值缓存兜底，删需求多则直接上布谷鸟过滤器。"
            }
        ]
    }
]
