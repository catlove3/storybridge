# StoryBridge 严格评审与优化方案

> 评审日期：2026-08-28  
> 范围：产品定位、评测可信度、Agent 工作流、图模型、存储与并发、LLM 接入、API、前端、测试、部署、安全与数据治理。  
> 原则：先保证比赛演示和实验结论可信，再处理生产化扩展；不建议为了“智能体感”盲目增加 Agent 数量。

## 实施状态（2026-08-29）

本文第 1～8 节保留的是审查当时的证据快照，便于解释为什么要改；其中的测试数量、失败现象和“当前没有”类表述不再代表最新代码。当前运行说明以根目录与前后端 README 为准。

已完成并分别提交：

| 范围 | 结果 | Commit |
|---|---|---|
| 审查基线 | 严格评审、研究依据、分阶段验收标准 | `ac2cc07` |
| 可复现性 | `uv.lock`、Python/Node 版本、CI、ruff、coverage、前端构建 | `7933ea7`、`e1586af` |
| Schema 与 Graph | 业务不变量、跨引用校验、MultiDiGraph、多关系传播和置信度 | `922480a` |
| 验证 | strategy-aware 静态规则、commitment coverage、非虚假绿色状态 | `170ed00` |
| 状态正确性 | 原子写、提交标记、state/plan version、项目锁、幂等 operation | `74b9f4d` |
| 任务与 LLM | 持久化 queued/cancel/TTL job、共享 client、退避与 usage | `04c63fe` |
| 产物与评测 | 版本化目标语言稿、统一 baseline、外部 annotations | `19969cc` |
| API 与隐私 | owner/API key、配额、typed OpenAPI、通用错误、SFT opt-in、导出删除 | `f7ce6dd` |
| 前端 | 刷新恢复、服务端取消、关系可读、组件拆分、Playwright E2E | `443542d` |

本轮最终补齐：每项目 LLM token 上限、仅元数据运行账本、token/成本估算、BLAKE2b 输入输出指纹、baseline run manifest、85% coverage gate，以及全部运行/交接文档同步。

### 明确保留为后续工作的项目

以下内容没有被包装成“已完成”：

1. **人工评测执行**：代码已支持外部 gold annotations、统一目标语言与 run manifest，但冻结 8～12 个样本、多人盲评、每样本多次真实模型运行需要真实评审者和模型预算。
2. **SQLite 与 migration**：已完成单机 WAL、版本 migration、事务化项目/job 存储和旧 JSON 幂等导入；多 worker claim 仍未实现。
3. **长文本分块**：尚未实现 scene checkpoint、跨块实体合并与二次承诺链接，API 字符上限不等于已验证的长篇质量。
4. **OpenAPI client 自动生成**：后端 response model 已严格化，前端契约仍是手工维护。
5. **大型图交互**：关系已有键盘/触屏可读文本，但缩放、筛选和降噪仍可继续增强。

这些边界需要在实验报告、答辩和部署说明中保持一致，不能用 mock E2E 或自动指标替代人工质量证据。

## 1. 结论先行

StoryBridge 已不是一个空壳 Demo：显式 `StoryState`、依赖传播、局部改写、双层验证、版本记录和完整前端闭环都已落地，120 个非 API 测试可以快速通过。项目当前大致处于“功能型 MVP 已成立，但实验与工程可复现性不足”的阶段。

最需要优先修复的不是页面样式，也不是增加模型，而是以下四件事：

1. **统一产品承诺和输出口径**：当前项目宣称面向中文内容出海，但 StoryBridge 输出仍是中文改编稿，两个 baseline 输出是英文稿，三者不可直接比较。
2. **重做可辩护的评测**：现有 baseline 的残留检测是中文字符串探针，对英文输出失效；场景“真值”又部分来自系统自己的图，存在循环论证。
3. **固定依赖并恢复全量测试可复现**：当前无 Python 锁文件，新解析出的依赖组合会让 15 个 API 测试挂起，README 的“132 测试全绿”已与实际 135 个测试不一致。
4. **保证状态写入和任务执行一致**：文件存储由多次非原子写组成，同项目并发、服务崩溃或重复操作都可能造成 state、revision、plan 和 adaptation 互相不一致。

如果比赛时间只剩 72 小时，建议把 60% 时间投到“同口径评测 + 可复现 Demo”，30% 投到状态正确性，10% 投到界面收尾。此时不要上复杂多 Agent、向量数据库或分布式队列。

## 2. 本次核验结果

| 检查项 | 实际结果 | 判断 |
|---|---|---|
| Python 测试收集 | 135 个 | README/HANDOFF 写 132 个，已过时 |
| 非 API 测试 | 120 passed in 2.97s | 核心 schema、workflow、graph、LLM 兼容层基础较好 |
| API 测试 | 首个 `TestClient` 请求挂起，15 个无法跑完 | 依赖未锁导致不可复现，不可继续宣称 fresh install 全绿 |
| Python 依赖 | FastAPI 0.141.1、Starlette 1.6.0、httpx 0.28.1 | Starlette 当前已将普通 httpx TestClient 标为弃用并推荐 httpx2 |
| 前端类型检查 | 通过 | TypeScript 契约在当前源码下可编译 |
| 前端 lint | 当前 Node 18 环境下 oxlint native binding 无法加载 | 仓库未声明 Node engine，环境约束不透明 |
| 前端生产构建 | 失败 | Vite 8 要求 Node 20.19+ 或 22.12+，当前 Node 18.19 不满足 |
| npm audit | 0 个已知漏洞 | 锁定的前端依赖当前无已知公告漏洞 |
| CI / 容器 / Python lock | 均不存在 | 无法自动证明不同机器上的可复现性 |
| 工作区 | 审查前后源码保持 clean | 本文档是本轮唯一源码树新增内容 |

这里的 API 挂起不是业务断言失败，而是环境重新解析后测试栈发生兼容迁移。Starlette 官方文档已说明当前 TestClient 以 `httpx2` 为主，普通 `httpx` 已弃用；FastAPI 官方也给出了 `AsyncClient + ASGITransport` 的异步 API 测试方式。参考：[Starlette TestClient](https://www.starlette.io/testclient/)、[FastAPI Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/)。

前端失败同样不是 TypeScript 源码错误，而是运行环境未被仓库约束。Vite 官方当前要求 Node.js 20.19+ 或 22.12+。参考：[Vite Getting Started](https://vite.dev/guide/)。

## 3. 做得好的地方

- **核心差异化成立**：`StoryState -> StoryGraph -> Propagation -> Rewrite -> Verify/Repair` 确实由代码编排，不是把多个 prompt 顺序拼接。
- **LLM 与确定性逻辑边界清楚**：图查询、修改范围和静态检查由代码控制，LLM 负责抽取、方案、改写和语义判断。
- **数据契约意识较强**：Pydantic schema、枚举、ID 规范和结构化生成重试，明显降低了脏输出穿透概率。
- **Mock 和离线联调实用**：前端可以在不消耗真实模型费用的情况下跑完整 HTTP/job/storage 流程。
- **测试覆盖广度不错**：已经覆盖脏 JSON、路径穿越、图环、重复 ID、repair 边界和并发调用等大量异常路径。
- **前端已覆盖比赛主链路**：分析、方案选择、传播、图、改写、Diff、验证和 revision 都有真实 API 对接。
- **产品边界总体克制**：没有过早引入多 Agent、RAG、视频、配音等与核心论点无关的系统。

这些能力应保留，不建议推倒重写。

## 4. P0 问题：赛前必须处理

### P0-1 产品承诺与实际产物不一致

证据：

- `MarketProfile` 只有 market/audience/format/genre，没有 `source_language` 和 `target_language`。
- `rewrite_scene_user()` 要求“使用与原文一致的剧本文体”，没有要求输出目标语言。
- 已提交的 `storybridge.txt` 是中文；`baseline_translate.txt` 和 `baseline_strong_prompt.txt` 是英文。
- `SYSTEM_LOCALIZATION_EXPERT` 固定写“熟悉北美短剧市场”，但前端市场是自由文本，理论上允许日本、东南亚等任何市场。

影响：

- “中文内容出海”听起来像交付目标语言成稿，当前实际更接近“中文语义层的跨文化改编规划与重写”。
- 三系统语言不同，字符探针、自然度、局部改动率和场景 diff 都不在同一空间，实验结论容易被直接否定。

建议二选一，并在 README、演示和论文材料中统一：

**推荐方案：两层产物。**

1. `localized_story_state`：保留中文，负责文化机制迁移、依赖传播和叙事一致性；这是项目最强的核心。
2. `target_script`：在结构决策冻结后，再逐场景生成英文等目标语言成稿；使用术语表、人物名表和风格指南保持一致。

新增字段：

```text
source_language
target_language
target_locale
target_market_profile
style_guide
terminology_map
```

若来不及做第二层，就明确将产品改称“跨文化改编决策与一致性维护工具”，不要声称已经完成端到端翻译。

验收标准：三个系统收到相同输入、生成相同目标语言，比较同一种最终产物。

### P0-2 当前 baseline 不能支撑强结论

主要问题：

1. `count_stale_references()` 用中文机制名和 surface text 扫描文本；英文输出天然容易得到 0，并不等于文化机制已正确本土化。
2. 直接翻译被手工设为 `N/A`，强 Prompt 却仍使用同一中文探针，处理口径不一致。
3. expected affected scenes 先来自系统自己的抽取结果和传播结果，再用它证明系统传播正确，存在循环论证。
4. 强 Prompt 输出被重新 parse 后按 `S01/S02...` 对齐；模型若合并、拆分或重排场景，scene ID 对比会失真。
5. baseline 的 commitment 没有检查，StoryBridge 由自己的 verifier 检查，裁判不一致。
6. `Consistency Score` 是固定罚分公式；`needs_review` 不扣分，因此“所有承诺都未被模型覆盖”仍可能显示 1.0。
7. 已提交的 `demo_real.md`、`demo_real.json` 和当前 formatter 字段不一致，说明实验产物没有 run manifest 和自动再生约束。
8. 当前只有两个已提交汇总，无法支撑跨题材稳定性结论；README 中“10 样本 × 7 题材”的原始运行记录和统计未完整入库。

建议建立小而可靠的比赛评测集：

- 12 个冻结剧本：4 个题材 × 3 个样本，每个 6～12 场。
- 人工标注：文化机制、叙事功能、affected scenes、must-preserve commitments。
- 三个系统使用同一底模、同一目标语言、近似相同 token budget；每个样本至少跑 3 次并报告均值和标准差。
- 输出匿名、随机顺序，由至少 2 名评审独立评分；有条件时至少 1 名具备目标文化/语言背景。
- LLM Judge 只作辅助，不能由生成模型在知道系统名称时自评。

建议指标：

| 层级 | 指标 |
|---|---|
| 抽取 | 文化机制 Precision/Recall/F1；依赖边 Precision/Recall/F1 |
| 传播 | affected-scene Precision/Recall/F1；漏改数；误改数 |
| Preservation | 人工标注 commitment 保持率；关键剧情功能保持率 |
| Consistency | 经人工确认的事实冲突、动机断裂、残留引用、伏笔未回收数 |
| Naturalness | 目标语言自然度 1～5；文化可理解度 1～5；刻板印象风险 |
| Locality | 未受影响场景改动率；改动 token 比例 |
| 工程 | 成功率、P50/P95 延迟、输入/输出 token、单剧本成本、repair 次数 |

WMT 2023/2024 篇章级文学翻译任务的官方排名以总体人工判断为主，而不是只靠字符串或 BLEU；TransAgents 也分别使用目标语单语者偏好和双语比较来评价长文本。参考：[WMT 2023 findings](https://arxiv.org/abs/2311.03127)、[WMT 2024 findings](https://arxiv.org/abs/2412.11732)、[TransAgents](https://aclanthology.org/2025.tacl-1.42.pdf)。

### P0-3 依赖不可复现，测试声明已失真

现状：

- Python 依赖全部是宽松的 `>=`，没有 `uv.lock` 或 constraints 文件。
- fresh resolution 得到的新 FastAPI/Starlette 测试栈使 API 测试挂起。
- 前端有 package-lock，但没有 `engines`、`.nvmrc` 或 Volta 配置；Node 18 下无法 build。
- 没有 CI，因此 README 的测试数字只能靠人工维护。

建议：

1. 生成并提交 `uv.lock`，CI 和 README 都使用 `uv sync --frozen --extra dev`。
2. 明确 Python 3.12.x，加入 ruff、mypy/pyright、coverage；不要只写最低版本范围。
3. API 测试短期固定一组已验证的 FastAPI/Starlette/httpx 版本；随后迁移为官方异步测试写法，或按 Starlette 当前方式加入 httpx2。
4. `package.json` 增加 `engines.node: ">=20.19 <21 || >=22.12"`，提交 `.nvmrc`（建议 Node 22 LTS）。
5. GitHub Actions 至少跑：Python unit/integration、frontend typecheck/lint/build、mock E2E、依赖审计。
6. 测试数量不要写死在文档中；改成 CI badge 和最近一次 commit/run ID。

验收标准：一台干净机器仅按 README 操作，可以稳定完成全部测试和生产构建。

### P0-4 状态、revision、plan 与 adaptation 不是原子操作

`ProjectStore.save_state()` 依次覆盖 `state.json`、写 history、读写 `revisions.json`；apply 随后另写 `adaptations.json`。任何一步崩溃都可能留下半完成状态。`write_text()` 还会先截断目标文件，进程中断可能直接产生坏 JSON。

并发时还会出现：

- 两个 apply 都从同一旧 state 开始，后写者覆盖先写者。
- 两个 writer 可能计算出同一个 revision ID。
- state 已提交而 adaptations 未追加，verify 摘要与实际 state 不一致。
- job 返回 done，但 revision/history 可能并非该 job 的结果。

最低成本的赛前修复：

1. JobManager 增加 **project_id 级 `asyncio.Lock`**，analyze/plan/apply/verify 同项目串行；不同项目仍可并行。
2. 文件写改为“同目录临时文件 + flush/fsync + `os.replace`”的原子替换。
3. 一个 apply 先生成候选结果，全部验证完成后再一次性 commit；失败时不改变当前 revision。
4. state 增加 `version`；plan 记录 `based_on_version`，apply 必须校验版本一致，否则返回 409。
5. 增加 operation/idempotency key，禁止浏览器重试造成重复 apply。

赛后推荐迁移到 SQLite：将 project、story_state_version、revision、plan、adaptation、job 放在一次事务内；MVP 单机可启用 WAL。SQLite 官方说明 WAL 允许读写并发，但仍只有一个 writer，因此仍需控制写事务长度。参考：[SQLite WAL](https://www.sqlite.org/wal.html)、[SQLite Transactions](https://www.sqlite.org/lang_transaction.html)。

## 5. P1 问题：正确性与质量

### P1-1 Schema 只校验形状，没有校验业务不变量

需要补充以下 validator：

- `AdaptationPlan` 必须恰好包含 A/B/C，标签唯一，并强制 A/B/C 与 preserve/functional_replacement/plot_reconstruction 一一对应。
- plan 的 `culture_mechanism_id` 必须等于请求 ID，`original_name` 应与 state 对应。
- friction 结果必须完整覆盖输入机制，不能静默漏项或带未知 ID。
- rewrite 输出 `id` 必须与输入 scene ID 相同；`text` 不得为空或异常缩短。
- scene 的 character/event IDs、event/cm 的 scene IDs、commitment 的 scene IDs、dependency 两端都必须存在。
- 节点跨类型 ID 冲突应直接报错，而不是静默保留第一个。
- 依赖图应输出数据质量报告：悬空边、孤立机制、无场景文化机制、低置信边比例。

当前不少测试只验证“不崩溃”，例如重复 apply 和并发 apply，没有验证最终语义、revision 唯一性和不丢更新。应升级为 invariant 测试。

### P1-2 Graph 使用 `DiGraph` 会吞掉同一节点对的多种关系

`StoryState` 允许相同 source/target 存在不同 relation，但 `networkx.DiGraph` 每对节点只能保留一条边。当前实现会保留置信度更高的那条，另一条关系、证据和 impact kind 被静默丢弃。

建议：

- 改为 `MultiDiGraph`，edge key 使用 `dependency_key`；或把同一方向的 relations/evidence 聚合成列表。
- propagation 记录全部 path kinds，并选择“最高路径置信度”或“最短且最高置信”的解释路径。
- 默认 `min_confidence` 不应是 0；建议图展示保留全部边，自动改写只使用经过阈值或人工确认的边。
- 给每个 affected scene 返回 `path_confidence`，UI 展示“确定 / 建议复核”。

### P1-3 Preserve 方案与 stale-reference 静态检查互相冲突

A 方案定义为“保留中国语境，仅加注或弱化”，但 apply 后会设置 `adapted_to`；静态检查只要看到 `adapted_to` 就把旧机制名视为 error。这会推动 repair 把本应保留的词删掉。

修复：

- `adapted_strategy == preserve` 时不做“旧词必须清零”检查，而检查首次出现是否有解释、上下文是否足够。
- functional replacement 才检查旧机制残留；plot reconstruction 还应检查旧因果链是否残留。
- 验证规则由 strategy 驱动，不应只有一个全局字符串规则。

### P1-4 `Consistency Score` 容易制造虚假确定性

问题：

- `needs_review` 不扣分。
- error/warning 的固定扣分不随故事长度、承诺数量和检查覆盖率变化。
- LLM 漏掉 commitment 时系统补 `needs_review`，仍可能显示 100 分。
- 不同剧本的分数不可直接比较。

建议 UI 不再只显示单一总分，改成：

```text
Static checks: 5/5 passed
Commitments verified: 3/4 (1 needs review)
Semantic issues: 0 error, 1 warning
Coverage: 8/8 scenes checked
Overall status: NEEDS_REVIEW
```

若保留分数，必须同时显示 coverage，并将任何 must-preserve `needs_review/violated` 设为非绿色状态。

### P1-5 缓存和重复操作缺少版本语义

- 前端按钮写“重新生成 Adaptation Plan”，后端却总返回缓存，实际不会重生成。
- analyze 重跑后旧 plans/adaptations 仍保留，可能绑定上一版图。
- 先为多个机制生成 plan，再 apply 第一个机制，其他缓存 plan 可能已过时。
- 重复 apply 同一机制会再次调用模型、追加 revision/adaptation；这不是幂等，只是“不崩溃”。

建议：

- `POST /plans` 支持 `force_regenerate`，并记录 `based_on_state_version`、model、prompt_version。
- analyze 产生新的主版本；旧计划归档，不再作为当前缓存。
- apply 使用 idempotency key；相同 key 返回原结果，不重复扣费或改写。
- 已适配机制再次操作应明确为“重新适配”，从指定 revision 创建新分支，而不是继续改当前文本。

### P1-6 长文本策略不能只靠增大 max_tokens

README 已承认 2 万字以上未测。仅把 max_tokens 调大不能解决输入上下文、输出截断、费用和全局一致性。

建议采用分层解析：

1. 规则/模型先切 scene，保留稳定 scene ID 和原始 byte/line span。
2. 分块抽取局部人物、事件、机制和承诺。
3. 全局 merge/dedupe，生成 canonical entity/term table。
4. 对跨块承诺和因果做第二遍 link。
5. 每块保存 checkpoint，可重试单块。

研究上可以借鉴 TransAgents 的角色分工，但本项目无需复制多 Agent 公司结构；更值得借鉴的是长文本记忆、术语一致性和独立校对。

## 6. P1 问题：后端、任务和 LLM 接入

### 6.1 JobManager 只适合单进程演示

当前问题：

- job 和结果全部在内存；重启丢失。
- semaphore 等待中的 job 也显示 `running`，没有 `queued`。
- 无取消、TTL、清理、进度、重试策略和幂等。
- `create_task()` 没保存 task handle，无法在 shutdown 时统一取消/等待。
- 多 worker 时，提交 job 和轮询 job 可能落到不同进程并返回 404。
- 浏览器超时只停止轮询，服务端 job 仍继续消耗 token。

赛前保持单 worker，但把限制写清楚，并补 queued/cancel/TTL/project lock。赛后将 job 持久化到 SQLite；只有确实需要多机时再上 Redis + 独立 worker，不要现在引入 Celery 全家桶。

### 6.2 LLM 客户端缺少生产级韧性和成本控制

- 每次 complete 都新建 `httpx.AsyncClient`，无法复用连接池。
- 只对 502/503/504 立即重试一次；没有 429、408、连接错误、指数退避、jitter 和 `Retry-After`。
- 无每项目 token/cost budget、最大 rewrite scene 数和全局并发配额。
- stream 未显式请求 usage，部分兼容服务会始终返回 0 token。
- provider 400 时会逐个删除可选参数，可能掩盖真正的请求错误。
- 模型、prompt、参数和调用成本没有进入项目 revision/run manifest。

建议在 FastAPI lifespan 中创建并复用 AsyncClient；统一 retry policy；每次调用记录 run_id、step、provider、model、prompt_version、latency、tokens、estimated_cost、attempt、finish_reason。OpenTelemetry 已定义 GenAI token usage 和 duration 等语义指标，可直接作为字段命名参考：[OpenTelemetry GenAI metrics](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-metrics.md)。

### 6.3 配置路径依赖启动目录

YAML 中 `data/projects` 和 `data/sft_logs` 是相对路径，Pydantic 不会自动相对 `backend/` 解析。若从仓库根目录用 `PYTHONPATH=backend` 启动，数据会写到根目录的 `data/`；从 backend 启动则写到 `backend/data/`。

修复：所有相对路径在 load config 时显式 resolve 到 `BACKEND_ROOT`，并在启动日志打印最终路径（不打印 secret）。

### 6.4 API 边界不足

比赛本机 Demo 可以接受，但任何联网部署前至少需要：

- 身份认证和项目所有权隔离；当前任何用户都能枚举、读取和改写全部项目。
- script/name/profile 长度限制，拒绝超大请求。
- 每用户并发、调用次数和 token 预算限制，防止模型费用失控。
- 统一错误码，不把 provider/内部异常原样返回客户端。
- depth、kind、option 使用枚举和范围，不接受任意字符串。
- OpenAPI `response_model`，并由 OpenAPI 自动生成前端 types/client，减少手写漂移。
- bible 端点返回文件或正文，不返回服务器文件路径。
- readiness 检查 storage/config/provider；`healthz` 只代表进程还活着。

OWASP 将 Prompt Injection 和 Sensitive Information Disclosure 列为 LLM 应用核心风险。StoryBridge 暂无工具调用，注入的直接破坏面较小，但剧本文本仍是不可信输入，且完整 prompt/completion 会被默认记录，数据泄露风险更现实。参考：[OWASP GenAI LLM Top 10](https://genai.owasp.org/llm-top-10/)。

## 7. P1 问题：隐私、SFT 与数据治理

当前 `sft_log_enabled: true` 默认记录完整剧本、system prompt、messages 和 completion。对真实影视/网文稿件，这可能包含未发布 IP、个人信息和商业秘密。

建议：

1. 默认关闭 SFT 日志；由项目级明确 opt-in 开启。
2. UI 展示“数据将发送到哪家模型供应商、是否保存、保存多久”。
3. SFT 数据与运行日志分离；运行日志默认只存 metadata/hash，不存全文。
4. 提供脱敏、删除、导出和 retention policy。
5. 每条 SFT 样本记录来源、许可、consent、prompt_version、model 和人工质量状态。
6. 未经人工验收的真实模型输出不得直接作为微调 gold data，否则会把错误和偏见回灌模型。
7. 对 GuoFeng、Kunpeng、OpenSubtitles 等分别维护 license/provenance 清单，不把“可下载”误认为“可再分发/可商用”。

## 8. P2 问题：前端和可维护性

### 前端

- `App.tsx` 约 660 行、`App.css` 约 1973 行，所有业务状态集中在一个组件；继续加功能后很难测试。
- 刷新页面无法恢复当前 project/job/workbench；后端虽有 list API，前端没有项目列表和 resume。
- browser abort/timeout 不会取消服务端 job，用户重试可能重复计费。
- 没有组件测试、API contract test 或 Playwright E2E。
- Graph 边关系只在 hover title 中，键盘和触屏用户难以读取；大图也缺少缩放、筛选和降噪。

建议拆为 `AnalyzePage/WorkbenchPage/ProjectPage`，用 reducer 或轻量状态机表达流程；将 project_id/job_id 写入 URL/localStorage，支持刷新恢复。比赛后再评估是否需要 TanStack Query，不必为 MVP 立即引入大型状态库。

### Python 代码质量

- 目前没有 ruff/mypy/coverage gate，存在未使用 import、未使用常量和 dead code。
- FastAPI 使用 `on_event("startup")`，应迁移 lifespan，顺便集中管理 AsyncClient、task shutdown 和 storage lifecycle。
- API handler 缺少明确返回类型/response model。
- 同步文件 I/O 在 async 请求路径中执行；数据增长后会阻塞 event loop。

## 9. 推荐目标架构

```text
Create Project
  -> Validate input / language / budget
  -> Scene segmentation with stable source spans
  -> Chunked story extraction
  -> Graph invariant & confidence checks
  -> Friction analysis
  -> Human selects mechanism + option
  -> Plan bound to state_version
  -> Deterministic propagation + confidence paths
  -> Generate rewrite candidates (not yet committed)
  -> Static strategy-aware checks
  -> Independent semantic verification
  -> Human review when coverage incomplete
  -> Atomic commit to new StoryStateVersion
  -> Optional target-language rendering
  -> Export + evaluation manifest
```

建议的核心持久化对象：

```text
Project
StoryStateVersion
Plan(based_on_version, prompt_version, model)
AdaptationOperation(idempotency_key, from_version, to_version)
Job(status, progress, cancel_requested)
LLMCall(run_id, step, usage, latency, cost, privacy_mode)
EvaluationRun(dataset_version, systems, judge_config, metrics)
```

每个新版本不可变；“重新分析/重新适配”产生新版本或分支，避免覆盖历史。

## 10. 分阶段实施路线

### Phase A：赛前 0～24 小时——先让结论可信

1. 明确产品是“中文改编决策稿”还是“英文最终稿”；推荐加入 `target_language` 并补目标语言渲染。
2. 三个 baseline 统一目标语言和模型预算。
3. 冻结 8～12 个评测样本和人工标注，不再用系统传播结果当唯一真值。
4. 修正 preserve 检查、needs_review 绿色满分、A/B/C schema 约束。
5. 生成 Python lock；声明 Node 22；恢复全量测试与 build。
6. 更新 README：测试数、真实边界、baseline 口径、运行环境。

验收：干净环境一键运行；演示样本至少连续跑 3 次；所有结果都有 run manifest。

### Phase B：24～48 小时——保证 Demo 不丢状态

1. project-level lock。
2. 原子 JSON 写；state version + plan version check。
3. job 增加 queued/progress/cancel/TTL，明确单 worker。
4. 修复“重新生成 plan”缓存语义和重复 apply 幂等。
5. MultiDiGraph/聚合边修复，并补同节点多关系回归测试。

验收：并发双 apply 不丢更新；中途异常不产生半 revision；重复请求不重复计费。

### Phase C：48～72 小时——形成比赛证据

1. 跑完三系统 × 评测集 × 3 次重复。
2. 自动生成 Markdown/CSV：均值、标准差、失败率、成本和延迟。
3. 人工盲评 naturalness/preservation，保留评分表。
4. 录一条真实模型 Demo 和一条 mock 兜底 Demo。
5. 答辩只主张已被数据支持的结论。

验收：任何一张对比表都能追溯到 dataset version、commit、model、prompt 和原始输出。

### Phase D：赛后 1～2 周——从 Demo 到可用内测

1. SQLite + migration + persistent jobs。
2. 长文本分块、术语表和目标语言渲染。
3. Auth、quota、privacy opt-in、retention/delete。
4. 连接池、重试/退避、token/cost observability。
5. OpenAPI 生成前端 client；前端项目恢复、取消任务和 E2E。
6. CI quality gates：coverage、ruff、typecheck、build、mock E2E、eval smoke。

## 11. 建议新增的验收测试

### 状态与并发

- 两个 apply 同一项目：一个串行等待或 409，revision ID 唯一，不丢更新。
- save_state 任一步故障：旧 state 完整可读，没有半 revision。
- analyze 后旧 plan 不可用于新 state。
- 相同 idempotency key 重试：LLM 调用次数不增加。

### Schema 与 Graph

- 缺 B、重复 A、A 使用错误 strategy：plan 校验失败。
- rewrite 返回错误 ID/空文本/异常缩短：拒绝 commit。
- 同一节点对存在 motivates + causes：两条语义都能传播并展示。
- 悬空 scene/character/event/dependency 引用：分析失败并返回可修复诊断。
- 低置信边不会自动触发改写，只进入 needs_review。

### 验证

- preserve 方案保留旧词并正确解释：不报 stale error。
- 所有 commitment 都 needs_review：总体不得显示绿色 100 分。
- violated commitment 即使没有 issue.scene_id，也必须阻止“验证通过”。
- 目标语言英文中的旧机制译法/音译残留可以被双语规则或 judge 检出。

### API/任务

- 超长输入、非法 depth/kind/option、未授权项目访问。
- job queued/running/done/failed/cancelled 全状态。
- 浏览器取消后服务端停止后续 LLM step。
- 服务重启后 job 和结果仍可查询。

### 前端 E2E

- mock 模式完整跑 Analyze -> Plan -> Propagate -> Apply -> Verify。
- 刷新后恢复 job 轮询和当前项目。
- plan/apply 失败后可重试且不会重复提交。
- 键盘可以选择机制和方案，并读取 Graph 的关系说明。

## 12. 最终优先级清单

| 优先级 | 工作 | 收益 | 工作量 |
|---|---|---:|---:|
| P0 | 统一目标语言与三系统口径 | 极高：决定比赛结论是否成立 | 中 |
| P0 | 冻结人工 gold eval + 盲评 | 极高：形成可辩护证据 | 中 |
| P0 | Python lock、Node engine、CI | 极高：恢复可复现性 | 小 |
| P0 | project lock + 原子写 + version check | 极高：防止数据错乱 | 中 |
| P1 | strategy-aware verifier + coverage 状态 | 高：避免虚假 1.0 | 小 |
| P1 | 严格 schema/invariant | 高：阻止脏图进入主流程 | 中 |
| P1 | MultiDiGraph 与置信传播 | 高：修复核心创新正确性 | 中 |
| P1 | cache/idempotency/version 语义 | 高：防重复扣费和陈旧方案 | 中 |
| P1 | LLM 连接池、retry、budget、usage | 高：稳定性和成本 | 中 |
| P1 | SFT opt-in 与数据治理 | 高：真实内容隐私 | 小～中 |
| P2 | SQLite persistent jobs | 中高：支撑内测 | 中～大 |
| P2 | 长文本分块 + 目标语术语表 | 高：扩大真实场景 | 大 |
| P2 | 前端拆分、恢复、E2E | 中：可维护和体验 | 中 |

## 13. 一句话建议

StoryBridge 下一阶段不该证明“我们能再多调用几个 LLM”，而应证明：**在同一目标语言、同一预算和人工标注真值下，显式状态与依赖传播能显著减少漏改和误改，并且每次结果可复现、可追踪、可安全提交。**
