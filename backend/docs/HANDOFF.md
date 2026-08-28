# StoryBridge 交接文档

> 写给：前端同学（同学B）、负责继续迭代的后端同学（包括未来的自己）
> 更新：2026-08-27 | 对应 commit：`ffeefdc` 之后
> 读完这份 + README 就能接手。所有结论都有测试背书，不确定时先跑 `pytest tests/ -q`。

---

## 一、你现在拥有的东西

| 资产 | 位置 | 状态 |
|---|---|---|
| 完整后端闭环 | `backend/app/` | 135 测试全绿，真 LLM 7 题材验证过 |
| 测试语料库 | `backend/data/scripts/` | demo_v0（编制彩礼）+ 5 题材 corpus 剧本 |
| 外部数据 | `backend/data/external/` | kunpeng 章节 + idiom 验证集（50条）|
| SFT 语料积累 | `backend/data/sft_logs/`（gitignore）| 每次真实调用自动落盘，按 skill 分文件 |
| Baseline 数据 | `backend/data/baselines/` | 三系统对比表 + 各系统输出全文 |
| Git 历史 | 18 commits | 每轮测试一个 commit，bug 修复都有测试固化 |

真实调用的余额和单轮成本取决于 `.env` 当前配置的 OpenAI-compatible 供应商与模型，
请在对应供应商控制台确认，不要沿用旧供应商的历史余额口径。

---

## 二、前端同学必读（联调指南）

### 2.1 五个页面对应的 API

你们方案文档里的 5 屏，对应端点：

| 页面 | 端点 | 备注 |
|---|---|---|
| Screen1 剧本输入 | `POST /api/projects` | 传 market 画像 |
| Screen2 Friction Map | `POST /api/projects/{id}/jobs {kind:analyze}` → 轮询 → `GET /state` | state 里 `culture_mechanisms[].friction_level` 直接渲染红黄绿 |
| Screen3 方案选择 | `POST /adaptations/plan` → 渲染 A/B/C 卡片 | plan 结果会缓存，重复调用不花钱 |
| Screen4 影响传播 | `GET /propagate?mechanism=CM01` + `GET /graph?focus=CM01` | propagate 给 `affected_scenes[].impact_kinds` 和 `reason_path`（高亮用）；graph 给节点边数据 |
| Screen5 Before/After | `POST /adaptations/apply`（或 job）→ `GET /diff` → `GET /verify` | diff 已按场景聚合 before/after/diff 三份文本 |

### 2.2 联调必须知道的三件事

1. **长任务走 jobs**：analyze 30s~2min、apply 1~3min。`POST /jobs` 拿 job_id → 2s 间隔轮询 `GET /api/jobs/{job_id}` → status=done 时 result 就是完整结果；failed 时看 error 字段。
2. **离线联调**：不想烧钱的调试方式——后端改用 mock（见 §4.1），或直接拿 `tests/fixtures/*.json` 里的假数据对着写 UI。
3. **错误约定**：404=项目/节点不存在（body.detail 有原因）；400=参数缺；502=LLM 失败（detail 含重试详情）。验证失败不抛错——`apply` 的返回里 `report.issues` 数组 + `consistency_score`。

### 2.3 一条能跑通的联调脚本

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --port 8321 &
curl -s localhost:8321/healthz
# 用 python -m app.cli create data/scripts/demo_v0.md --name demo 预建项目，然后全在 UI 上操作
```

---

## 三、后端同学必读（继续迭代）

### 3.1 改动热力图（哪里安全、哪里危险）

| 想改什么 | 风险 | 规则 |
|---|---|---|
| 加 API 端点 | 低 | 照 `api/routes.py` 现有模式，`_project_or_404` 必加 |
| 加 prompt | 低 | 只改 `prompts/templates.py`，改完跑 `pytest`（fixtures 会验 schema）|
| 改 schema | **高** | `schemas/` 是全系统契约；改字段要同步 fixtures + 受影响测试；存储里旧 state.json 会因校验失败被当 None——**没有迁移机制**，老项目直接重建 |
| 改图引擎方向语义 | **极高** | `graph/build.py` 的三个方向集合是传播正确性的根；任何改动先跑 `test_graph*.py` 全家 |
| 换 LLM 供应商 | 低 | 默认只改 `.env` 的三个 `LLM_*` 变量；高级按-step路由再改 `config/models.yaml` |
| 上微调模型 | 低 | 见 README「Skill 层与微调兼容」，yaml 三行 |

### 3.2 九轮测试换来的设计决定（别回退）

这些决定各自踩过坑，回退会复现 bug：

1. **verify 的 stale_reference 以静态层为真源**——LLM 报的必须过"evidence 含旧机制名 AND 场景里真有旧词"才保留。曾出现：捏造引用（call15 彩礼冤案）、把改后的新表述当残留（婚礼基金案）、复读循环 15k 字符截断（frequency_penalty=0.3 压制）。
2. **静态探针只扫机制名，不扫 surface_text**——surface_text 是证据不是禁用词表（"家族"是"世家"的同义词但不是残留）。
3. **parse/friction 请求温度 0.0**——分析型任务，温度高会导致重复运行机制识别漂移；兼容层会把不被部分供应商接受的精确 0 规范化为 0.01。rewrite 保持默认温度（要创造性）。
4. **friction detector 有 drop 否决权**——抽取层宁多勿漏，审查层枪毙误抽（"以死相抗"案），剔除时联动清依赖边。
5. **repair 循环遇无 scene_id 的 issue 直接 break**——否则空转到 max_rounds 白烧 token。
6. **存储读操作绝不 mkdir**（`_peek_dir`）+ project_id 白名单校验——防路径穿越和目录污染。
7. **机制重复 apply 是幂等的**——二次 apply 同一机制会重新走流程但不炸；真要做增量，看 `engine.apply_adaptation` 的 plan 缓存逻辑。

### 3.3 已知未修（有意留下的边界）

- **并发写同一项目无锁**：两个 job 同时 apply 同一项目会交错写 state.json（测试 `test_concurrent_apply_same_project` 验证了不炸但结果取决于时序）。前端做一个"项目级操作锁"即可规避。
- **超长剧本**（>2万字）没测过 parse 的 max_tokens=8192 是否够；真遇到截断，structured.py 会抛 `StructuredGenerationError`（截断快败），把 `skills/registry.py` 里 PARSE_STORY 的 max_tokens 调大即可。
- **Naturalness 评分**未实现——初评材料里按"LLM Judge + 人工"口径写。

### 3.4 加一个新 LLM 步骤的标准流程

```python
# 1. schemas/ 加输出模型
class MyResult(BaseModel): ...

# 2. prompts/templates.py 加 system/user 工厂
def my_step_system(): ...
def my_step_user(**kwargs): ...

# 3. skills/registry.py 注册
MY_STEP = SkillSpec(name="my_step", schema=MyResult, ...)
_REGISTRY["my_step"] = MY_STEP   # all_skills 之外手动加或改列表

# 4. config/models.yaml 的 step_routes 加 my_step: general（不加则走 default_profile）

# 5. workflow 里注入调用：await MY_STEP.run(client, **kwargs)
# 完成。SFT 日志自动按 my_step.jsonl 落盘，路由自动生效。
```

---

## 四、常用命令速查

```bash
cd backend && source .venv/bin/activate

# 测试（改任何代码后必跑）
python -m pytest tests/ -q                     # 全量 135 个
python -m pytest tests/test_graph.py -q        # 只跑图引擎

# 真 LLM 全流程演示（~2元）
python -m app.cli demo data/scripts/corpus_urban.md --bible /tmp/b.md

# 离线 mock 演示（0元，给前端联调/录屏用）
python -m app.cli --mock demo data/scripts/demo_v0.md

# Baseline 对比（初评数据）
python -m app.cli baseline data/scripts/demo_v0.md --plans CM01:B

# 抽kunpeng新章节做测试样本
python -m app.external.kunpeng chapter --index <N> --out data/external/k_chN.md

# 查看当前选择的端点和模型（不打印 API key）
python -c "from app.config import get_config; p=get_config().llm.profile_for_step('parse_story'); print(p.base_url, p.model)"
```

### 4.1 让服务端跑 mock（前端零成本联调）

```python
# 临时改 app/main.py 的 startup:
from app.llm import MockLLMClient
from app.cli import _load_default_mock_fixtures
mock = MockLLMClient(); _load_default_mock_fixtures(mock)
app.state.workflow = build_default_workflow(mock)
```
（mock 返回的是 demo 剧本的固定数据，任何剧本 analyze 都返回同一套 state——够联调 UI，别用它判断质量。）

---

## 五、下一步建议（按你们 8/29-31 的计划）

1. **前端五屏**（同学B）：先用 mock 模式把 UI 全部搭完，最后一天切真 LLM 录 demo
2. **初评材料**：baseline 对比表（`data/baselines/*.md`）+ 一致性验证截图（verify issues 全绿）+ Adaptation Bible 样例（`export_bible` 输出）直接可用；架构图抄 README 那张调用链
3. **答辩押题**：评委必问"为什么不是 ChatGPT 套壳"——答案三件套：
   - `propagate` 端点现场演示（改"编制"→ 图查 5 场景，纯代码毫秒级）
   - baseline 表的"无关场景改动数"列（强Prompt 8 vs 我们 0）
   - `revisions` 版本历史（每次改动可审计）
4. 有余力再做的：GuoFeng 数据到了接 `external/`（格式见 FINDINGS.md）、verify 的 Naturalness 维度

---

## 六、档案：9 轮测试修过的 17 个 bug

| 轮 | bug | 一句话根因 |
|---|---|---|
| 真跑1 | max_tokens 截断致 JSON 解析失败 | 4096 不够 8 场剧本的完整结构 |
| 真跑1 | LLM 评审幻觉 | 从改编说明反推不存在的台词引用 |
| 测1 | schema 无去重 | 重复 ID/重复边穿透到 state |
| 测2 | repair 空转 | 无 scene_id 的 issue 反复 verify |
| 测3 | verify 误报未改编机制 | digest 没暴露 adapted_to 状态 |
| 测4 | 新表述被当残留 | 交叉验证没要求"含旧探针" |
| 测4 | 复读循环截断 | "但为了严谨…"套娃到 token 上限 |
| 测5 | （服务端全通）| — |
| 测6 | S10 排在 S9 前 | 字典序 vs 自然序 |
| 测7 | 读操作 mkdir 副作用 + 路径穿越 | `_dir` 不分校验 |
| 测8 | 同义词误判残留 | surface_text 被当禁用词表 |
| 测8 | 泛化词弱替换 | "世家"→"家族" 等于没改 |
| 测9 | 语义重复抽取 | "编制"和"宇宙的尽头是编制"两个机制 |

每一个都有对应测试盯着，改相关代码时这些测试就是活文档。
