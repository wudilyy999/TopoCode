EXTRA_ENTRIES = [
    {
        "id": "react-hooks",
        "name": "React Hooks 原理与闭包陷阱 (React Hooks)",
        "aliases": ["react hooks", "hooks", "useeffect", "usestate", "usememo", "usecallback", "闭包陷阱", "stale closure", "自定义hook"],
        "category": "前端工程",
        "definition": "React Hooks 是 React 16.8 引入的函数组件能力模型，不写 class 也能使用状态、副作用与上下文，useState 管状态、useEffect 管副作用、useMemo 与 useCallback 管缓存，本质是与 Fiber 节点绑定的按序存储的链表记忆单元。",
        "detailed_explanation": "Hooks 状态以链表形式挂载在对应 Fiber 节点的 memoizedState 上，渲染时严格按调用顺序依次取出，因此禁止在条件与循环中调用。函数组件每次渲染都是全新闭包，Effect 回调捕获的是当次渲染的 props 与 state，依赖数组过期即产生闭包陷阱，表现为定时器与事件回调永远读到旧值。工程解法是函数式 setState、useRef 保存最新值、useCallback 稳定引用，并用 exhaustive-deps 补齐依赖，缺依赖是最高频故障源。",
        "project_relevance": "本项目词典弹窗与拖拽分栏面板用 useState 与 useEffect 订阅 SSE 事件流并控制显隐，若 Effect 闭包捕获过期图谱快照会导致高亮错乱，必须用 ref 兜底最新状态。",
        "related_concepts": ["react-virtual-dom-fiber", "js-event-loop", "sse-streaming-rendering"],
        "interview_questions": [
            {
                "question": "【字节跳动】解释 React Hooks 的闭包陷阱：为什么 setInterval 回调里读到的 state 永远是旧值？给出三种以上修复手段并比较取舍。",
                "answer": "1. 成因：函数组件每次渲染都是独立闭包，setInterval 回调捕获的是挂载那次渲染的 state 快照，后续重渲染不会更新已注册的回调；\n2. 函数式更新 setState(prev => ...) 适用于只依赖旧值递推的场景，但读不到其他变量最新值；\n3. useRef 镜像最新值并在渲染时同步，是读取多变量最新快照最通用的解法，代价是 ref 变更不触发渲染；\n4. 把回调逻辑移入 useEffect 并声明完整依赖，状态变化时销毁重建定时器，最符合数据流但频繁重建有性能开销。"
            },
            {
                "question": "【腾讯/阿里】为什么 Hooks 不能写在条件语句里？useState 懒初始化与 useMemo 缓存失效的边界条件有哪些？",
                "answer": "1. Hooks 状态按调用顺序以链表挂在 Fiber 的 memoizedState 上，条件调用会错位，后续所有 Hook 读到别人的状态；\n2. useState 初始值只在挂载执行一次，传 props 做初始值后 props 再变不会同步，需用受控的 key 重置或 useEffect 回填；\n3. useMemo 只保证语义缓存不保证不重算，React 可在内存紧张时丢弃缓存，绝不能把 useMemo 当作只执行一次的语义锁；\n4. useCallback 依赖变化即产生新引用，错误依赖导致子组件 memo 形同虚设，工程上用 exhaustive-deps 兜底。"
            }
        ]
    },
    {
        "id": "react-reconciliation",
        "name": "React Diff 与调和算法 (Reconciliation)",
        "aliases": ["reconciliation", "调和算法", "react diff", "diff算法", "fiber调和", "key的作用", "双缓存", "fiber树", "协调过程"],
        "category": "前端工程",
        "definition": "Reconciliation 是 React 把新的虚拟 DOM 树与旧树对比、计算出最小 DOM 变更集合并提交渲染的调和过程，基于分层对比、同类型复用、key 定位列表三条启发式规则，把指数级树对比降为线性复杂度，是声明式 UI 高性能的根基。",
        "detailed_explanation": "调和分 render 与 commit 两阶段：render 阶段可中断地遍历 Fiber 树打 EffectTag，commit 阶段同步执行 DOM 变更。列表 Diff 采用双指针与 key 映射：无 key 时按下标复用导致错位复用状态，有 key 时通过 map 快速定位移动节点。双缓存机制让 workInProgress 树在后台构建完成后再整体切换 current 树，保证 commit 原子性。下标做 key 与 render 写副作用是两大常见坑。",
        "project_relevance": "本项目单页 SVG 架构图节点频繁增删，高亮联动依赖 key 稳定复用节点，用数组下标做 key 会导致 hover 状态错位，必须用文件路径做稳定 key。",
        "related_concepts": ["react-virtual-dom-fiber", "diff-algorithm", "js-event-loop"],
        "interview_questions": [
            {
                "question": "【字节/快手】React 列表为什么必须写 key？用数组下标做 key 在哪些场景会出线上事故？",
                "answer": "1. key 是调和阶段识别节点身份的唯一依据，有 key 才能通过 map 定位移动而不是销毁重建；\n2. 下标做 key 在头部插入、排序、过滤时导致 DOM 节点与组件状态错位复用，典型事故是输入框内容串行、勾选状态错乱；\n3. 静态不变列表可用下标，任何可增删排序的列表必须用业务唯一 id；\n4. 随机数做 key 更糟，每次渲染全部销毁重建，性能与状态双崩。"
            },
            {
                "question": "【阿里/美团】Fiber 架构下调和过程如何做到可中断？render 阶段与 commit 阶段在副作用处理上有何本质区别？",
                "answer": "1. Fiber 把整棵树拆成可恢复的工作单元，render 阶段边遍历边记录 EffectTag，浏览器有空闲才继续，高优先级更新可打断丢弃重来；\n2. render 阶段必须是纯函数，写 DOM、发请求等副作用会被重复执行或丢弃；\n3. commit 阶段同步不可中断，一次性执行 placement、update、deletion，保证用户看到的 DOM 是原子一致的；\n4. 双缓存 current 与 workInProgress 整体切换是原子提交的前提，也是并发特性的物理基础。"
            }
        ]
    },
    {
        "id": "browser-rendering-pipeline",
        "name": "浏览器渲染流水线 (Rendering Pipeline)",
        "aliases": ["渲染流水线", "重排", "重绘", "reflow", "repaint", "合成层", "compositing", "关键渲染路径", "layout paint composite"],
        "category": "前端工程",
        "definition": "浏览器把 HTML、CSS 与 JS 转化为屏幕像素的流水线：解析构建 DOM 与 CSSOM、合并为渲染树、布局计算几何、绘制生成图层位图、合成上屏。重排触发布局重算代价最高，重绘只重画像素，合成层变换可跳过前两步直接由 GPU 合成。",
        "detailed_explanation": "关键优化围绕三条线：减少重排范围如用 transform 与 opacity 替代 top 与 left，把动画限制在合成层由 GPU 处理；读写分离避免强制同步布局，连续读取 offsetHeight 会逼浏览器提前 flush 队列；合理分层对 will-change 与 translateZ 提升为合成层，但层过多会爆显存。工程权衡是合成层加速动画流畅度与内存占用的矛盾，长列表无节制提升层反而引发卡顿，性能面板的 layer borders 是定位层爆炸的常用手段。",
        "project_relevance": "本项目 SVG 架构图节点 hover 联动高亮与拖拽分栏面板尺寸变化都走渲染流水线，高频样式变更必须收敛到 transform 与 opacity，避免整图重排掉帧。",
        "related_concepts": ["svg-vs-canvas", "js-event-loop", "request-animation-frame"],
        "interview_questions": [
            {
                "question": "【腾讯/字节】重排、重绘、合成三者的触发条件与代价差异？为什么 transform 动画比 left 动画流畅一个数量级？",
                "answer": "1. 重排改几何触发布局整链重算，重绘只重画受影响图层像素，合成只做图层位移缩放由 GPU 执行；\n2. left 动画每帧触发重排加全链绘制，主线程被布局计算占满；\n3. transform 动画元素被提升为独立合成层，主线程只提交矩阵参数，逐帧合成在合成线程与 GPU 完成；\n4. 代价排序是重排远大于重绘远大于合成，动画优化本质是把工作从主线程搬到合成线程。"
            },
            {
                "question": "【美团/阿里】什么是强制同步布局？在长列表场景中如何系统性避免布局抖动？",
                "answer": "1. JS 写入样式后立即读取几何属性，浏览器被迫提前清空渲染队列同步计算布局，打断批量优化；\n2. 循环里交替读写是最典型写法，每轮都触发一次同步布局，复杂度从线性退化为平方级；\n3. 解法是读写分离：先批量读缓存几何值，再批量写，配合 requestAnimationFrame 把写操作收敛到帧起点；\n4. 对海量节点再叠加虚拟列表，只让可视区节点进入流水线，从根上削减布局计算量。"
            }
        ]
    },
    {
        "id": "browser-cache",
        "name": "浏览器缓存策略 (Browser Cache)",
        "aliases": ["浏览器缓存", "强缓存", "协商缓存", "cache-control", "etag", "last-modified", "memory cache", "disk cache", "304协商"],
        "category": "前端工程",
        "definition": "浏览器为减少重复网络传输的分层缓存体系：强缓存命中直接读本地不发请求，由 Cache-Control 与 Expires 控制有效期；过期后走协商缓存，带 ETag 或 Last-Modified 向服务器确认，内容未变返回 304 复用本地副本，两层配合决定资源新鲜度。",
        "detailed_explanation": "查找顺序是 memory cache、disk cache、Service Worker、网络请求，内存缓存随标签页关闭消失。强缓存优先级为 Cache-Control 大于 Expires，no-store 禁一切缓存，no-cache 看似不缓存实则每次都要协商。协商缓存 ETag 精确到内容哈希，Last-Modified 精确到秒且文件语义下易误判，现代静态资源用 contenthash 文件名加一年强缓存、HTML 用 no-cache 协商兜底。HTML 误配强缓存会导致版本卡死。",
        "project_relevance": "本项目单页应用静态资源与架构图快照都依赖缓存分层，入口 HTML 必须协商缓存而带哈希的 JS 与 CSS 可长期强缓存，否则用户会卡在旧版界面收不到 SSE 新事件格式。",
        "related_concepts": ["http-protocol", "cdn-edge", "pwa-service-worker"],
        "interview_questions": [
            {
                "question": "【阿里/字节】强缓存与协商缓存的完整判定流程？no-cache 和 no-store 到底有什么区别？",
                "answer": "1. 先看强缓存：Cache-Control 的 max-age 未过期直接读本地，过期才进入协商；\n2. no-store 是任何环节都不存，no-cache 是可以存但每次使用前必须向服务器协商确认；\n3. 协商时优先 ETag 配 If-None-Match，内容哈希一致返回 304，不一致返回 200 全量；\n4. 落到 Last-Modified 只有秒级精度，一秒内多次发布会误判，这也是 ETag 更可靠的原因。"
            },
            {
                "question": "【腾讯/美团】线上发版后用户反馈一直看到旧页面，如何从缓存链路定位？你的静态资源缓存方案怎么设计？",
                "answer": "1. 先确认是 HTML 被强缓存还是 JS 文件名无哈希被复用，看响应头 Cache-Control 与 200 from disk 还是 304；\n2. 方案是 HTML 用 no-cache 协商、JS 与 CSS 文件名带 contenthash 并配一年强缓存，入口永远最新、静态资源靠文件名天然隔离；\n3. CDN 层同步设置回源策略，发版后主动刷新入口边缘节点；\n4. 兜底在 HTML 内嵌版本号，发现版本落后弹层提示用户硬刷新。"
            }
        ]
    },
    {
        "id": "css-architecture",
        "name": "CSS 架构方法论 (CSS Architecture)",
        "aliases": ["bem", "tailwind", "原子化css", "css modules", "css in js", "utility-first", "样式隔离", "命名规范", "oocss方法论"],
        "category": "前端工程",
        "definition": "管理大型项目样式规模、隔离与作用域的工程方法论集合：BEM 用块元素修饰符命名约束全局命名，CSS Modules 与 Scoped 在构建层做类名哈希隔离，原子化 CSS 如 Tailwind 把样式拆成不可再分的工具类组合，目标都是消灭全局污染与特异性战争。",
        "detailed_explanation": "核心矛盾是复用与隔离：全局 CSS 心智负担低但选择器冲突随规模指数增长，BEM 靠命名纪律解决但依赖人的自觉；CSS Modules 把隔离自动化，类名哈希后天然作用域化，是组件化项目性价比之选；原子化 CSS 把复用粒度压到单个属性，HTML 体积换 CSS 体积并获得近乎零增长的样式文件，代价是模板充斥工具类。工程权衡看团队规模：小团队用 BEM 足够，中大型组件库优先 Modules，原子化适合高频视觉迭代但需配套做类名提取防止首屏膨胀。",
        "project_relevance": "本项目单页 SVG 架构图节点样式、拖拽分栏面板与词典弹窗三套视觉体系共存，必须用作用域隔离防止全局选择器污染 SVG 节点高亮态，原子化工具类可收敛高频布局样式。",
        "related_concepts": ["svg-vs-canvas", "bundler-vite-webpack", "ssr-hydration"],
        "interview_questions": [
            {
                "question": "【字节/阿里】BEM、CSS Modules、Tailwind 原子化三者分别解决什么问题？新项目你如何选型？",
                "answer": "1. BEM 用命名约定解决全局命名冲突，零构建成本但靠纪律，规模一大仍会腐化；\n2. CSS Modules 在构建层哈希隔离，组件化项目默认选项，兼顾书写习惯与隔离；\n3. Tailwind 把复用压到属性级，样式文件体积收敛，适合视觉高频迭代的业务，但模板可读性下降；\n4. 我的选型是组件库用 Modules 保隔离，业务层叠加原子化处理高频布局，BEM 只做跨团队约定的命名前缀。"
            },
            {
                "question": "【腾讯/美团】线上出现样式污染：第三方组件库样式覆盖了业务样式，如何定位与根治？特异性战争怎么打？",
                "answer": "1. 用开发者工具看被覆盖规则的选择器来源与特异性权重，确认是库样式后到还是权重更高；\n2. 根治是隔离而非加 important：业务样式收进 Modules 或 Shadow DOM，第三方库用前缀与层叠层 scope 圈定；\n3. 用 CSS Cascade Layers 把库样式沉到低优先级层，业务层天然胜出，无需拼特异性；\n4. 长期靠视觉回归截图对比卡住污染，靠人盯样式迟早漏网。"
            }
        ]
    },
    {
        "id": "bundler-vite-webpack",
        "name": "构建工具演进 (Bundler Evolution)",
        "aliases": ["webpack", "vite", "esbuild", "rollup", "hmr热更新", "tree-shaking", "分包策略", "code splitting", "构建优化"],
        "category": "前端工程",
        "definition": "把源码样式资源打包为浏览器可运行产物的工具链演进史：Webpack 以 loader 加 plugin 的 bundler 范式统一一切资源，esbuild 用 Go 重写获得百倍构建速度，Vite 开发期原生 ESM 按需加载、生产用 Rollup 打包，核心矛盾是构建速度与产物优化的平衡。",
        "detailed_explanation": "Webpack 的慢来自 JS 单线程全量打包与复杂插件链，冷启动随模块数增长；Vite 开发期跳过打包直接托管 ESM，浏览器请求哪个模块才由 esbuild 即时转译，秒级启动。生产优化三板斧是分包、摇树与压缩：路由级动态 import 做代码分割，sideEffects 标记配合 ESM 静态结构做 tree-shaking，esbuild 做压缩混淆。常见坑是把 node_modules 整包打进主 chunk 导致首屏兆级体积，动态 import 变量表达式会导致全量引入。",
        "project_relevance": "本项目单页前端依赖打包体积决定首屏可交互时间，SVG 图谱库与词典弹窗大依赖必须路由懒加载分包，否则用户打开页面长时间白屏还收不到首批 SSE 推送。",
        "related_concepts": ["monorepo-architecture", "cicd-pipeline", "sourcemap-debug"],
        "interview_questions": [
            {
                "question": "【字节/阿里】Vite 为什么比 Webpack 冷启动快一个数量级？生产构建为什么又切回 Rollup？",
                "answer": "1. Webpack 开发期要全量打包整个依赖图再启动服务，Vite 直接托管原生 ESM，浏览器请求到哪个模块才即时转译；\n2. 转译用 Go 写的 esbuild，比 JS 系 loader 快百倍，且依赖预构建后缓存；\n3. 生产包走 Rollup 是因为其 ESM 打包与 tree-shaking 更成熟，产物更小且生态插件稳定；\n4. 本质是开发要速度用按需转译，生产要体积用全量优化，两阶段目标不同所以双引擎。"
            },
            {
                "question": "【美团/腾讯】首屏 JS 体积从 3MB 优化到 500KB，你的排查与分包手段有哪些？",
                "answer": "1. 先用 bundle-analyzer 可视化各包体积占比，定位被整包引入的大库如 lodash、moment；\n2. 路由级动态 import 做代码分割，非首屏页面与弹窗大依赖全部懒加载；\n3. 大库按需引入与替换轻量实现，moment 换 dayjs，lodash 用单函数引入；\n4. 第三方稳定依赖抽成 vendor chunk 配长期缓存，业务代码变更不影响其哈希，二次访问直接读缓存。"
            }
        ]
    },
    {
        "id": "micro-frontend",
        "name": "微前端架构 (Micro Frontend)",
        "aliases": ["微前端", "qiankun", "module federation", "single-spa", "乾坤框架", "沙箱隔离", "子应用", "基座应用", "微应用"],
        "category": "前端工程",
        "definition": "把大型前端按业务垂直拆分为可独立开发、部署与运行的子应用，再由基座统一编排加载的架构风格，主流有 qiankun 的运行时加载与 Module Federation 的构建时共享，解决巨石应用协作冲突与发布耦合，代价是运行时隔离与通信复杂度。",
        "detailed_explanation": "核心三件套是加载、隔离与通信：qiankun 用 import-html-entry 拉取子应用 HTML 并执行脚本，JS 沙箱用 Proxy 代理 window 防止全局变量串扰，样式用 scoped css 或 Shadow DOM 隔离；Module Federation 在构建层声明共享依赖，运行时复用同一份 react 避免多实例。工程权衡是独立部署的自由换来三倍调试成本，样式串扰、路由冲突、依赖版本分裂是三大线上坑，子应用崩溃必须被基座错误边界捕获否则整站白屏。",
        "project_relevance": "本项目当前是单页集中式前端，微前端是其规模化演进的备选对照：词典弹窗与架构图谱若未来拆给独立团队交付，可借鉴沙箱隔离思路防止双方全局样式互相污染。",
        "related_concepts": ["monorepo-architecture", "cors-cross-origin", "docker-container"],
        "interview_questions": [
            {
                "question": "【阿里/字节】qiankun 的 JS 沙箱与样式隔离原理是什么？子应用之间全局变量串扰如何解决？",
                "answer": "1. JS 沙箱用 Proxy 为每个子应用创建代理 window，读写先落到代理对象，卸载时丢弃快照恢复现场；\n2. 多实例共存用代理沙箱隔离，快照沙箱只适合单实例串行；\n3. 样式隔离靠 scoped css 给子应用根节点加前缀限定，或上 Shadow DOM 硬隔离；\n4. 通信走基座下发的 props 与全局事件总线，禁止子应用直写对方 window 变量，契约化才能可维护。"
            },
            {
                "question": "【美团/腾讯】什么规模才值得上微前端？Module Federation 与 qiankun 如何选型？",
                "answer": "1. 多团队并行、多技术栈、需独立发布回滚时才值得，三人小团队上微前端是纯负收益；\n2. 同技术栈、需共享依赖减体积选 Module Federation，构建层复用 react 等大依赖；\n3. 异构技术栈、老项目渐进迁移选 qiankun，运行时加载与框架无关；\n4. 都要配套基座错误边界、子应用独立监控与版本灰度，否则一个子应用崩溃拖垮整站。"
            }
        ]
    },
    {
        "id": "web-components",
        "name": "Web Components 标准与影子 DOM (Web Components)",
        "aliases": ["web components", "shadow dom", "custom elements", "template标签", "slot插槽", "样式封装", "自定义元素", "html templates", "影子dom"],
        "category": "前端工程",
        "definition": "浏览器原生支持的组件化标准三件套：Custom Elements 定义新标签，Shadow DOM 提供样式与 DOM 结构硬隔离的影子树，template 加 slot 实现内容分发。不依赖任何框架即可构建跨技术栈复用的真正封装组件，是微前端样式隔离的底层备选。",
        "detailed_explanation": "Shadow DOM 把节点挂在影子根下，外部选择器穿透不进去，内部样式也泄漏不出来，这是与 CSS Modules 的本质区别：一个是运行时硬隔离，一个是构建时命名隔离。slot 机制允许使用者向组件预留插槽注入内容，兼顾封装与定制。工程短板是影子内外的主题定制困难、表单关联与无障碍支持弱、SSR 水合复杂，主流框架生态也未完全对齐，因此多用于设计系统原子组件跨栈复用，而非整站开发范式。",
        "project_relevance": "本项目词典弹窗是天然的 Web Components 候选：用 Shadow DOM 封装后弹窗样式与宿主页面彻底隔离，第三方页面嵌入词典浮层时不会出现样式串扰。",
        "related_concepts": ["svg-vs-canvas", "micro-frontend", "css-architecture"],
        "interview_questions": [
            {
                "question": "【字节/阿里】Shadow DOM 与 CSS Modules 的隔离本质有何不同？什么场景必须用 Shadow DOM？",
                "answer": "1. CSS Modules 是构建时类名哈希，运行时仍在同一 document，全局通配选择器与 important 照样能穿透；\n2. Shadow DOM 是运行时影子树隔离，外部选择器物理上选不到内部节点，是真正的硬隔离；\n3. 第三方嵌入场景如广告、客服挂件、跨站点组件必须用 Shadow DOM，否则宿主样式必然污染；\n4. 代价是主题定制要走 CSS 变量穿透，全局换肤体系需要提前设计变量契约。"
            },
            {
                "question": "【腾讯/美团】为什么 Web Components 十年了仍未取代框架组件？它的工程短板有哪些？",
                "answer": "1. 缺状态管理与数据流方案，复杂交互仍要手写大量胶水代码，生产力不如框架；\n2. 影子 DOM 内表单元素与外层 form 的关联、无障碍语义传递都有坑；\n3. SSR 与水合支持长期滞后，SEO 与首屏敏感业务不敢用；\n4. 现实定位是设计系统原子组件跨技术栈复用，整站仍由框架主导，两者是互补而非替代。"
            }
        ]
    },
    {
        "id": "virtual-list",
        "name": "虚拟列表与海量数据渲染 (Virtual List)",
        "aliases": ["虚拟列表", "virtual list", "虚拟滚动", "windowing技术", "react-window", "长列表优化", "可视区渲染", "无限滚动", "大数据渲染"],
        "category": "前端工程",
        "definition": "虚拟列表是只渲染可视区及上下缓冲区的行节点，滚动时复用 DOM 并平移内容的长列表优化技术，用一个占位撑起总高度营造全量渲染的假象，把万级节点的 DOM 数量压到几十个，是前端海量数据不卡顿的标配方案。",
        "detailed_explanation": "核心是三处计算：按行高乘以总数算出占位总高度，按 scrollTop 除以行高算出起始下标，按可视区行数加缓冲算出渲染窗口。不定高场景需逐行实测缓存高度并回填修正，是实现复杂度的主要来源。工程配套包括滚动节流收敛到 rAF、图片懒加载、骨架屏，复用节点时必须用稳定 key 防止状态错位。权衡是内存与首屏换滚动计算量，行内有复杂受控组件时复用带来的状态同步坑会显著增加。",
        "project_relevance": "本项目架构图谱节点与词典检索结果在超大仓库下可达万级条目，全量渲染 SVG 节点会直接卡死主线程，虚拟列表只渲染可视区是保持拖拽与缩放流畅的前提。",
        "related_concepts": ["browser-rendering-pipeline", "request-animation-frame", "js-event-loop"],
        "interview_questions": [
            {
                "question": "【字节/快手】万级数据长列表直接渲染为什么卡？虚拟列表的核心计算是哪三步？",
                "answer": "1. 卡在 DOM 节点数爆炸：每个节点都是布局绘制与事件的对象，万级节点光是首次布局就数百毫秒，滚动更每帧重排；\n2. 第一步按行高乘总数撑出占位总高度，让滚动条表现得像全量渲染；\n3. 第二步按 scrollTop 算起始下标，第三步按可视区加缓冲算渲染窗口，只挂载这几十个节点；\n4. 滚动时复用节点平移内容，DOM 数量恒定，复杂度从 O(n) 降到 O(可视数)。"
            },
            {
                "question": "【阿里/腾讯】不定高虚拟列表的难点在哪？滚动过快出现白屏如何优化？",
                "answer": "1. 难点是行高未知导致起始位置算不准，需先按预估高度渲染、实测后回填高度缓存并修正总高度，会引发滚动条抖动；\n2. 白屏是因为滚动事件密度超过渲染能力，新窗口内容来不及挂载；\n3. 优化是滚动回调收敛到 rAF 每帧最多算一次，加大上下缓冲区预渲染，图片与重型组件懒加载；\n4. 极速滚动时降级先渲染占位色块，停稳后再补全内容，用视觉连续性换真实完整性。"
            }
        ]
    },
    {
        "id": "ssr-hydration",
        "name": "服务端渲染与水合机制 (SSR Hydration)",
        "aliases": ["ssr", "ssg", "hydration", "水合机制", "服务端渲染", "next.js", "同构渲染", "islands架构", "流式ssr"],
        "category": "前端工程",
        "definition": "SSR 在服务端直出完整 HTML 首屏秒开，SSG 在构建期预渲染静态页，水合是浏览器下载 JS 后为静态 HTML 重新绑定事件与状态、使其可交互的过程。同构要求服务端与客户端渲染结果逐字节一致，否则水合 mismatch 会丢弃重建，白白浪费直出优势。",
        "detailed_explanation": "水合本质是 React 在已有 DOM 上复用节点并挂载事件系统，逐节点校验服务端 HTML 与客户端虚拟树，不一致即报错并客户端重渲染。流式 SSR 把页面按 Suspense 边界分块flush，首屏先可读再渐进水合；Islands 架构只水合需要交互的岛屿，静态区保持纯 HTML。工程坑集中在服务端无 window 与 document 导致的直出崩溃、随机数与时间戳造成 mismatch、Node 与浏览器双环境依赖，以及水合 JS 体积过大让可交互时间反而劣于纯 CSR。",
        "project_relevance": "本项目是典型 CSR 单页加 SSE 实时推送的架构，SSR 是其对照方案：若未来要做架构图分享页的秒开与搜索引擎收录，需评估直出首屏加客户端接管 SSE 流的混合路线。",
        "related_concepts": ["browser-rendering-pipeline", "cdn-edge", "web-vitals"],
        "interview_questions": [
            {
                "question": "【字节/阿里】什么是水合 mismatch？线上最常见的三种成因与排查手段是什么？",
                "answer": "1. mismatch 是服务端直出 HTML 与客户端首次渲染结果不一致，React 丢弃服务端节点重建，首屏优势归零还伴随闪烁；\n2. 成因一是随机数、时间戳、本地存储等双端不一致的数据源；\n3. 成因二是服务端缺浏览器 API 导致分支渲染不同，成因三是样式注水顺序差异；\n4. 排查靠 React 的水合警告定位节点，把随机与环境相关逻辑收敛到 useEffect 只在客户端执行。"
            },
            {
                "question": "【腾讯/美团】SSR、SSG、CSR 如何选型？Islands 架构解决了什么痛点？",
                "answer": "1. 强 SEO 与首屏秒开的内容页选 SSR 或 SSG，内容静态用 SSG 构建期直出，个性化用 SSR 请求期直出；\n2. 重交互的后台与工具页用 CSR，省去双环境复杂度；\n3. Islands 只水合页面中需要交互的岛屿，静态区零 JS，解决整页水合 JS 体积过大的痛点；\n4. 代价是架构复杂度上升，交互稀疏的内容站收益最大，重交互应用收益有限。"
            }
        ]
    },
    {
        "id": "pwa-service-worker",
        "name": "渐进式应用与离线缓存 (PWA)",
        "aliases": ["pwa", "service worker", "离线缓存", "workbox", "manifest", "cache storage", "推送通知", "安装到桌面", "app shell"],
        "category": "前端工程",
        "definition": "PWA 是让网页获得接近原生体验的技术集合：Service Worker 在独立线程拦截网络请求实现离线缓存与推送，Manifest 描述图标与启动方式支持安装到桌面，App Shell 模型秒开应用骨架。核心是弱网离线可用，是移动端留存优化的利器。",
        "detailed_explanation": "Service Worker 生命周期分安装、激活、接管三步，更新时旧 worker 服务旧页面、新 worker 等待全部标签页关闭才接管，这是发版不生效最常见的根因。缓存策略按资源分级：App Shell 用 cache-first 常驻，业务数据用 network-first 配降级，静态资源用 stale-while-revalidate。工程坑是 SW 拦截范围含 SSE 长连接需显式放行、缓存配额超限被系统清理、以及 HTTPS 强制要求。",
        "project_relevance": "本项目可借鉴 App Shell 思想让架构图骨架秒开，但 Service Worker 必须显式放行 SSE 事件流长连接，否则离线缓存策略会误拦截实时推送导致图谱状态停滞。",
        "related_concepts": ["browser-cache", "websocket-protocol", "web-vitals"],
        "interview_questions": [
            {
                "question": "【阿里/字节】Service Worker 更新后用户迟迟拿不到新版本，根因是什么？如何设计可靠的更新流程？",
                "answer": "1. 根因是更新后的 worker 进入 waiting 状态，必须等所有受控标签页关闭才激活接管，已打开的页面一直由旧 worker 服务；\n2. 可靠流程是在新 worker 安装完成后弹层提示用户刷新，用 skipWaiting 加 clients.claim 主动接管；\n3. 激进方案是检测到新版本强制刷新，但要先持久化用户未保存状态；\n4. 配套给 SW 脚本本身设 no-cache，避免浏览器缓存旧的 worker 文件导致更新检查都发不出去。"
            },
            {
                "question": "【腾讯/美团】离线场景下 PWA 的缓存策略如何分级？SSE 这类长连接要怎么处理？",
                "answer": "1. App Shell 骨架用 cache-first 离线秒开，业务接口用 network-first 失败再读缓存，静态资源用 stale-while-revalidate 后台更新；\n2. SSE 与 WebSocket 长连接必须在 fetch 监听中显式放行走网络，绝不能缓存，否则事件流被切断；\n3. 缓存按版本命名空间隔离，激活新版本时清理旧缓存防配额爆炸；\n4. 弱网下给用户明确的离线态提示，而不是静默展示过期数据。"
            }
        ]
    },
    {
        "id": "web-vitals",
        "name": "Web 性能指标体系与优化 (Web Vitals)",
        "aliases": ["web vitals", "lcp", "cls", "inp", "性能指标", "首屏优化", "长任务", "ttfb", "fcp"],
        "category": "前端工程",
        "definition": "Google 定义的以用户体感为中心的核心性能指标：LCP 最大内容绘制衡量首屏加载，INP 下次绘制交互衡量响应延迟，CLS 累积布局偏移衡量视觉稳定。三者共同决定搜索排名与用户留存，是前端性能优化唯一的统一标尺。",
        "detailed_explanation": "LCP 优化抓关键资源： hero 图预加载、关键 CSS 内联、服务端直出，目标 2.5 秒内；INP 替代 FID 衡量全生命周期最差交互，优化靠拆分长任务、事件回调让出主线程、非关键脚本延迟；CLS 要求图片与广告预留尺寸、字体用 fallback 防闪动、动态插入内容避开首屏。工程落地靠 RUM 真实用户监控分位值而非实验室单次跑分，P75 达标才是真正的达标，长任务归因要结合 performance 面板定位具体函数。",
        "project_relevance": "本项目首屏架构图渲染速度对应 LCP，拖拽分栏与节点点击响应对应 INP，SSE 推送 late 到达导致图谱跳动则计入 CLS，三项指标直接决定用户对实时分析系统的流畅体感。",
        "related_concepts": ["browser-rendering-pipeline", "browser-cache", "cdn-edge"],
        "interview_questions": [
            {
                "question": "【字节/阿里】LCP、INP、CLS 三个指标分别衡量什么？各给出见效最快的两条优化手段。",
                "answer": "1. LCP 衡量首屏最大内容出现时间，最快手段是 hero 资源 preload 与服务端直出，减少关键链等待；\n2. INP 衡量用户交互到下帧绘制的最差延迟，手段是拆分超过 50ms 的长任务、第三方脚本延迟加载让出主线程；\n3. CLS 衡量非预期布局偏移总量，手段是媒体元素预留宽高比、动态内容禁止顶起首屏；\n4. 三者达标线看真实用户 P75 分位，实验室单次满分没有意义。"
            },
            {
                "question": "【腾讯/美团】线上 INP 超标但实验室跑分正常，如何定位？长任务归因的具体方法是什么？",
                "answer": "1. 实验室是空载单次，真实用户有低端机与长会话，必须看 RUM 按机型与页面分段的数据；\n2. 用 performance.longtask 采集归因到具体函数与调用栈，定位是框架重渲染、第三方脚本还是业务计算；\n3. 高频手段是把大计算拆成切片执行、事件处理函数内只做最小同步工作、重渲染用 memo 与虚拟列表收敛范围；\n4. 修完后按版本灰度对比 P75 曲线，确认真实用户体感回落再全量。"
            }
        ]
    },
    {
        "id": "typescript-system",
        "name": "TypeScript 类型系统与工程实践 (TypeScript)",
        "aliases": ["typescript", "类型体操", "泛型", "tsconfig配置", "类型收窄", "any与unknown", "声明文件", "d.ts", "类型推断"],
        "category": "前端工程",
        "definition": "TypeScript 是带静态类型检查的 JavaScript 超集，编译期捕获类型错误：泛型实现类型参数化复用，联合类型加类型收窄表达分支语义，unknown 强迫先断言后使用。与 any 放弃检查不同，严格模式用类型系统把运行时错误左移到编码期。",
        "detailed_explanation": "工程价值在重构信心与接口契约：strict 模式打开 strictNullChecks 后空指针错误减半，API 返回值用 zod 或 io-ts 做运行时校验桥接静态与动态边界。类型体操的 utility 类型如 Pick 与 Omit 在组件 props 裁剪中高频使用，infer 关键字做类型提取。常见坑是滥用 any 渗透导致类型系统名存实亡、enum 跨包膨胀、以及 tsconfig 路径别名与打包器解析不一致。大仓用增量构建避免全量检查拖慢循环。",
        "project_relevance": "本项目 SSE 事件载荷、图谱节点数据结构与词典条目 schema 都适合用 TypeScript 接口锁定，前后端字段一旦对不上在编译期即暴露，而不是等线上推送解析失败。",
        "related_concepts": ["ast-code-inspect", "monorepo-architecture", "cicd-pipeline"],
        "interview_questions": [
            {
                "question": "【字节/阿里】any、unknown、never 三者区别？为什么生产代码要禁 any 而推荐 unknown？",
                "answer": "1. any 关闭一切检查可任意赋值调用，是类型系统的逃生舱也是腐烂源头；\n2. unknown 是类型安全的 any，可接收任何值但使用前必须收窄或断言，强迫处理不确定性；\n3. never 表示不可能出现的值，用于穷尽检查兜底，switch 漏分支时编译期报错；\n4. 禁 any 是因为它会污染整条调用链的推断，一个 any 让下游全部失守，unknown 把校验成本放在边界一次性付清。"
            },
            {
                "question": "【腾讯/美团】后端接口返回的 JSON 如何与 TypeScript 类型安全对接？类型断言 as 为什么不可靠？",
                "answer": "1. as 只是编译期撒谎，运行时字段缺失照样崩，接口变更时类型与现实静默脱节；\n2. 可靠做法是在边界用 zod 或 io-ts 做运行时 schema 校验，校验通过后再收窄为静态类型；\n3. 用 openapi 或 protobuf 生成类型，保证前后端同一份契约源头；\n4. 对 SSE 这类流式载荷更要逐事件校验，坏数据隔离丢弃而不是让整条流崩溃。"
            }
        ]
    },
    {
        "id": "state-management",
        "name": "前端状态管理方案对比 (State Management)",
        "aliases": ["redux", "zustand", "pinia", "状态管理", "flux架构", "不可变更新", "selector", "中间件", "全局状态"],
        "category": "前端工程",
        "definition": "管理跨组件共享状态的方案谱系：Redux 以单一 store、纯 reducer 与不可变更新保证可预测，Zustand 用轻量 hooks store 按需订阅切分粒度，Pinia 是 Vue 生态的类型安全选项。选型本质是在可预测性、样板代码与渲染粒度之间取舍。",
        "detailed_explanation": "Redux 的心智负担来自样板代码与全量心智模型，但时间旅行调试与中间件生态在复杂业务无可替代，RTK 已把样板压到最低；Zustand 基于 selector 细粒度订阅，组件只在所选切片变化时重渲染，天然避免 Redux connect 时代的全树更新问题。工程铁律是服务端状态与客户端状态分离：SSE 推送与接口数据归 TanStack Query 管缓存失效，UI 状态才进全局 store。常见坑是把所有状态塞全局导致任何风吹草动整树重渲染，以及在 reducer 里写副作用破坏可预测性。",
        "project_relevance": "本项目 SSE 实时事件、高亮选中态与分栏布局尺寸三类状态并存，事件流归缓存层管理，选中与布局进轻量 store，若全放全局 store 每次推送都会引发整图重渲染。",
        "related_concepts": ["react-hooks", "sse-streaming-rendering", "react-virtual-dom-fiber"],
        "interview_questions": [
            {
                "question": "【字节/阿里】Redux、Zustand、Context 三者如何选型？什么状态根本不该进全局 store？",
                "answer": "1. 高频变更且多组件共享的 UI 状态用 Zustand，selector 细粒度订阅避免无关重渲染；\n2. 强审计、需时间旅行与中间件编排的复杂业务用 Redux Toolkit；\n3. 低频主题、语言等用 Context 足够，高频值进 Context 会导致所有消费者无差别重渲染；\n4. 服务端数据归 TanStack Query，表单局部态归组件内部，进全局 store 的应该是真正跨多处共享的最小 UI 状态。"
            },
            {
                "question": "【腾讯/美团】全局状态更新导致整树卡顿，如何定位与优化？不可变更新的性能代价怎么看？",
                "answer": "1. 用 React DevTools Profiler 录制提交，找出与本次变更无关却重渲染的组件；\n2. 根因多是订阅粒度太粗，解法是 selector 切片订阅加 memo 锁边界，让更新收敛到消费组件；\n3. 不可变更新的结构共享使大对象更新只复制路径节点，代价远小于深拷贝，但万级数组高频更新仍要考虑规范化存储；\n4. SSE 高频推送场景做批量合并与节流，把每秒几十次提交压到帧级别。"
            }
        ]
    },
    {
        "id": "frontend-security",
        "name": "前端安全攻防体系 (Frontend Security)",
        "aliases": ["xss", "csrf", "csp", "前端安全", "反射型xss", "存储型xss", "samesite", "内容安全策略", "转义编码"],
        "category": "前端工程",
        "definition": "浏览器侧攻防体系围绕三大攻击：XSS 注入恶意脚本窃取数据，CSRF 借用户身份伪造请求。防御纵深是输出编码、CSP 白名单限源、Cookie 的 SameSite 与 HttpOnly、敏感操作二次校验四层叠加。",
        "detailed_explanation": "XSS 分存储型、反射型与 DOM 型，React 默认转义文本但 dangerouslySetInnerHTML 与 javascript 协议 href 是敞开的口子，富文本必须用 DOMPurify 按白名单清洗；CSRF 利用浏览器自动带 Cookie，防御靠 SameSite 默认 Lax、关键操作加一次性 token；CSP 用 script-src 白名单兜底外链脚本。常见坑是 unsafe-inline 让 CSP 失效，以及 token 存 localStorage 被一锅端。",
        "project_relevance": "本项目词典弹窗渲染外部知识库文本与面试题内容，若直接插入 HTML 即引入存储型 XSS，架构图节点名同样不可信，必须默认转义加白名单清洗。",
        "related_concepts": ["cors-cross-origin", "http-protocol", "tls-ssl-protocol"],
        "interview_questions": [
            {
                "question": "【字节/腾讯】存储型、反射型、DOM 型 XSS 的区别？React 项目是否就天然免疫 XSS？",
                "answer": "1. 存储型经数据库持久化杀伤面最大，反射型经 URL 参数一次性触发，DOM 型完全在前端拼接执行不经过服务端；\n2. React 默认转义文本插值，能防住大部分反射与存储场景；\n3. 但 dangerouslySetInnerHTML、用户可控的 href 与 img src、以及直接操作 innerHTML 的第三方库都是缺口；\n4. 富文本必须用 DOMPurify 按白名单清洗，CSP 配 script-src 限源做最后一道兜底。"
            },
            {
                "question": "【阿里/美团】CSRF 的完整攻击链路是什么？SameSite、token、验证码三道防线各自防住哪一环？",
                "answer": "1. 攻击链是用户登录态下诱导访问恶意页，浏览器自动携带 Cookie 向目标站发伪造请求；\n2. SameSite 让跨站请求默认不带 Cookie，从协议层掐断攻击前提，兼容性要求 Lax 起步；\n3. CSRF token 要求请求携带攻击者拿不到的一次性密钥，即使带上 Cookie 也校验失败；\n4. 敏感操作再加短信或密码二次确认，三道防线分别卡携带、卡伪造、卡授权，纵深缺一不可。"
            }
        ]
    },
    {
        "id": "cdn-edge",
        "name": "内容分发与边缘渲染 (CDN Edge)",
        "aliases": ["cdn", "内容分发网络", "边缘节点", "回源", "缓存命中", "边缘渲染", "anycast", "静态加速", "边缘函数"],
        "category": "前端工程",
        "definition": "CDN 把静态资源副本下沉到离用户最近的边缘节点，用 DNS 调度与 Anycast 就近接入，命中则毫秒返回，未命中回源拉取。边缘渲染更进一步，把 SSR 与个性化逻辑跑在边缘函数上，动态内容也在离用户一跳的位置生成，是全球化站点的标配。",
        "detailed_explanation": "加速来自三处：物理距离缩短降低 RTT，边缘命中省去回源链路，HTTP2 与 TLS 会话在边缘复用。缓存键设计是核心，query 参数、Cookie 与 UA 是否参与组键决定命中率，个性化内容误缓存会导致串号事故，回源策略用分级缓存与预热兜底。边缘函数把轻量 SSR 与 AB 分流放在边缘执行，动态首屏也能百毫秒级，但重计算与长状态仍要回中心。工程坑是发版后边缘旧副本滞留，必须配版本化文件名加主动刷新，否则缓存即事故。",
        "project_relevance": "本项目单页静态资源经 CDN 分发决定全球打开速度，若未来做架构图分享页的直出，边缘渲染可在离用户最近处生成首屏 HTML，比中心 SSR 快一个数量级。",
        "related_concepts": ["browser-cache", "http-protocol", "ssr-hydration"],
        "interview_questions": [
            {
                "question": "【阿里/字节】CDN 缓存命中率上不去，如何从缓存键与回源链路排查？个性化内容如何防串号？",
                "answer": "1. 先看缓存键：query 参数、Cookie、UA 是否被无意义地纳入组键， utm 参数是经典命中率杀手；\n2. 个性化内容按用户维度组键或直接 bypass 缓存回源，宁可慢不能串；\n3. 回源链路做分级缓存，边缘 miss 到区域上级再 miss 才回源，源站压力指数下降；\n4. 发版用内容哈希文件名天然隔离版本，入口文件主动刷新，杜绝旧副本滞留。"
            },
            {
                "question": "【腾讯/美团】边缘渲染与中心 SSR 的本质区别？什么逻辑适合放边缘函数？",
                "answer": "1. 区别在执行位置：边缘函数跑在离用户一跳的节点，省去到中心机房的跨国 RTT；\n2. 适合放轻量无状态逻辑：AB 分流、地域定向、简单 SSR 组装；\n3. 重计算、大依赖、长连接与强一致状态不适合，边缘资源受限且无状态；\n4. 本质是用边缘算力换延迟，静态与轻动态收益最大，重业务逻辑仍归中心。"
            }
        ]
    },
    {
        "id": "request-animation-frame",
        "name": "动画帧调度与帧率优化 (rAF)",
        "aliases": ["raf", "requestanimationframe", "帧率优化", "60fps", "掉帧", "vsync", "节流渲染", "动画调度", "settimeout对比"],
        "category": "前端工程",
        "definition": "requestAnimationFrame 是与显示器垂直同步信号对齐的动画调度 API，浏览器在每次重绘前回调，保证动画一帧一次不早不晚。对比 setTimeout 的固定延时，它在切后台时自动暂停省电，且回调时机恰好落在渲染流水线起点，是流畅动画的唯一正确时钟。",
        "detailed_explanation": "机制优势有三：与 VSync 对齐避免撕裂与无效帧，后台标签页暂停节省 CPU，多个 rAF 回调合并到同一帧批量执行。帧率优化围绕 16.6ms 预算：单帧任务超时即掉帧，解法是长任务切片、非关键计算丢进 Web Worker、动画属性收敛到 transform 与 opacity 走合成层。工程模式是时间驱动而非帧数驱动，用 timestamp 计算进度保证 120Hz 与 60Hz 屏动画时长一致，滚动与拖拽回调统一收敛到 rAF 节流，避免高频事件直接写 DOM 引发布局抖动。",
        "project_relevance": "本项目 SVG 架构图拖拽缩放、节点 hover 联动高亮与 SSE 高频推送重绘都必须收敛到 rAF 节流，否则鼠标移动事件每秒上百次直接写 DOM 会把帧率打穿。",
        "related_concepts": ["js-event-loop", "browser-rendering-pipeline", "virtual-list"],
        "interview_questions": [
            {
                "question": "【字节/腾讯】rAF 与 setTimeout 做动画的本质区别？为什么后台标签页中 rAF 会停止？",
                "answer": "1. rAF 与显示器 VSync 对齐，每次重绘前恰好执行一次，不多不少不撕裂；\n2. setTimeout 是固定延时，多次回调可能落在同一帧造成跳帧，也可能错过帧造成卡顿；\n3. 后台标签页无重绘需求，浏览器暂停 rAF 省电，这是特性而非 bug；\n4. 依赖它做倒计时会在切后台时停走，计时逻辑必须用时间戳差值，rAF 只负责视觉刷新。"
            },
            {
                "question": "【美团/快手】拖拽场景掉帧严重，你的定位与优化步骤是什么？120Hz 高刷屏动画时长不一致怎么解？",
                "answer": "1. 先录 performance 火焰图，看单帧是否超 16.6ms 预算，定位是 JS 计算、布局还是绘制；\n2. 高频 mousemove 收敛到 rAF 每帧最多处理一次，读写分离防强制同步布局；\n3. 位移走 transform 合成层，重计算切片或丢进 Worker，主线程只做提交；\n4. 高刷屏用 rAF 回调的 timestamp 算进度做时间驱动，固定每帧步长的写法在 120Hz 屏会快一倍。"
            }
        ]
    },
    {
        "id": "sourcemap-debug",
        "name": "SourceMap 与前端监控体系 (SourceMap)",
        "aliases": ["sourcemap", "source map", "错误监控", "sentry", "mappings字段", "堆栈还原", "前端埋点", "白屏监控", "错误上报"],
        "category": "前端工程",
        "definition": "SourceMap 是压缩混淆产物与原始源码的位置映射文件，用 VLQ 编码记录行列对应关系，让线上报错堆栈能还原到源码行号。配套错误监控采集、上报、聚合与告警，构成从崩溃发现到源码定位的完整可观测闭环。",
        "detailed_explanation": "mappings 字段是核心：分号分行、逗号分段，每段记录产物列、源文件、源码行列与符号名五元组。上线必须上传 map 到监控平台但禁止对外公开，否则等于开源。监控体系分四层：全局 error 与 unhandledrejection 抓异常，performance 采性能分位，白屏检测用根节点采样加骨架断言，行为埋点串联崩溃前的用户路径。工程坑是 map 与产物版本错位导致堆栈还原到错行，必须用构建哈希严格绑定；上报本身要用 sendBeacon 或空闲时批量，避免监控流量压垮业务。",
        "project_relevance": "本项目单页前端压缩上线后，SSE 推送解析异常与 SVG 渲染崩溃的堆栈全是混淆代码，必须靠 SourceMap 还原到源码行号，否则线上故障完全无法定位。",
        "related_concepts": ["bundler-vite-webpack", "cicd-pipeline", "js-event-loop"],
        "interview_questions": [
            {
                "question": "【字节/阿里】SourceMap 的 mappings 字段原理是什么？为什么 map 文件绝不能放到公网 CDN 上？",
                "answer": "1. mappings 用 VLQ 编码记录压缩产物位置到源码文件行列与符号名的映射，监控平台靠它把混淆堆栈还原；\n2. 放公网等于把完整源码拱手送人，竞品与攻击者直接读业务逻辑与接口密钥；\n3. 正确做法是构建时上传到 Sentry 等监控平台内部，公网只留去 map 引用的产物；\n4. map 与产物必须按构建哈希严格绑定，错位一个版本堆栈就还原到错误行号，比没有更误导。"
            },
            {
                "question": "【腾讯/美团】从零设计前端监控体系，白屏、JS 异常、性能三类数据分别怎么采？上报本身如何避免反压业务？",
                "answer": "1. JS 异常靠全局 error、unhandledrejection 与框架错误边界三层捕获，带面包屑记录崩溃前操作路径；\n2. 白屏用根节点 DOM 采样加关键元素断言，结合首屏截图抽样确认；\n3. 性能用 performance API 采 LCP 与 INP 上报 P75 分位；\n4. 上报走 sendBeacon 保障页面关闭时送达，采样率按错误等级分级，监控流量与业务隔离域名，避免互相拖垮。"
            }
        ]
    }
]
