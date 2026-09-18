# StoryBridge 手机扫码体验

## 启动与停止

在项目根目录运行：

```bash
./speed_run.sh --share
```

首次启动会同步依赖、加密 `backend/.env` 中现有的模型密钥、构建网站，并准备官方 `cloudflared`。无需注册、填写前端 API key、购买域名或安装手机应用。等待终端显示 `StoryBridge is ready (real mode)` 和 HTTPS 地址后，打开网站右上角“手机扫码体验”，可放大或下载二维码。二维码只包含首页地址。

模型沿用现有 `LLM_BASE_URL` 和 `LLM_MODEL`，真实调用失败不会切换为模拟结果。开发时显式运行 `./speed_run.sh --share --mock`；页面会显示“开发演示模式”，数据库也使用临时目录。原有 `./speed_run.sh` 与 `./speed_run.sh --mock` 仍提供本地 Vite 开发方式。

同时选择核心设定与文化背景时，系统先完成核心设定改写，再从新版中文稿重新抽取当前实际存在的文化名词，交给用户复核后才生成下一批方案。已经从场景中消失的旧名词不会继续出现“保留并解释”选项。中间结构稿固定使用简体中文，目标语言只在最终渲染阶段生成。

保持电脑联网、终端运行；按 Ctrl+C 会停止后端和隧道。日志目录在退出时显示。公开模式只启动一个后端 worker，不要运行多个进程共享同一数据库。

临时地址可能随重启改变，没有稳定性保证。[Cloudflare Quick Tunnel 官方说明](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)明确将它用于测试和开发。网络限制可能导致下载、隧道连接或微信打开失败；现场务必先用实际网络测试。

## 固定地址

已有 HTTPS 反向代理或固定隧道时，将它转发到 `127.0.0.1:8000`，然后运行：

```bash
STORYBRIDGE_PUBLIC_URL=https://stories.example.com ./speed_run.sh --share
```

此配置跳过临时隧道的创建，仍会构建前端、检查加密配置和公网健康状态。地址必须是 HTTPS 首页，不带路径、用户名、参数或片段。匿名写请求的 Origin 必须与该地址完全一致。前端与 API 使用同一域名；反向代理应保留 Host。二维码和运行政策都会显示这个配置的地址。

## 添加、更新和下架教学短剧

1. 将 UTF-8 `.txt` 或 `.md` 正文放入 `backend/data/scripts/`。
2. 在 `backend/config/demo_scripts.yaml` 添加记录，例如：

```yaml
- id: funny_story_01
  title: 今天开始当反派
  genre: 都市喜剧
  summary: 一个总被误认为反派的普通人的故事。
  file: funny_story_01.md
  enabled: true
  order: 40
```

ID 应保持唯一稳定。`file` 是正文目录内的相对路径；目录外文件、绝对路径和指向目录外的符号链接不会公开。只有明确 `enabled: true` 的记录可读；返回值不包含服务器路径。按 `order` 升序排列，同序按 ID 排列。

服务每次请求重新读取配置和正文。编辑、排序、添加或下架后，再次打开示例选择器即可看到变化，无需重启后端或发布前端。配置整体损坏时仅示例入口报错；单条无效记录跳过；正文缺失时读取失败且保留原草稿。

导入不创建项目、不调用模型，也不覆盖市场或语言。用户可以修改正文，点击“开始分析”时提交的是输入框中的实际内容。已有故事须先点击“开始新故事”。

## 模型密钥与备份

首次真实公开启动会运行可重复执行的迁移，也可手动运行：

```bash
cd backend
.venv/bin/python -m app.secrets
```

迁移使用 [Fernet 认证加密](https://cryptography.io/en/latest/fernet/)，先验证解密再原子替换 `.env`，保留地址、模型等其他设置，移除 `LLM_API_KEY` 明文项并写入 `LLM_API_KEY_ENCRYPTED`。主密钥位于 `.storybridge/secrets/master.key`，权限为 `0600`；`.env` 也以 `0600` 写入。两者均已被 Git 忽略。

分别安全备份加密后的 `.env` 和主密钥；丢失主密钥就不能恢复模型凭据。不要把二者放进公开目录、截图、前端或代码仓库。可用 `STORYBRIDGE_MASTER_KEY_FILE` 指定独立主密钥文件。错误密钥、解密失败或公开模式只有明文配置时，后端停止启动，不回退到明文。

更新 API key 时，先在私密编辑器中移除旧加密项，填入新的 `LLM_API_KEY`，再运行迁移；如果两项同时存在且内容不一致，迁移拒绝覆盖。请勿把真实密钥写进 shell 命令历史。

公开构建禁止 `VITE_STORYBRIDGE_API_KEY`。如构建被拒绝，移除前端环境文件和终端中这个变量。原有后端 `X-API-Key` 调用仍受 owner 检查，在公开模式也统一遵守额度。

## 访客与数据

匿名凭据保存在 30 天有效的 HttpOnly、Secure、SameSite=Lax Cookie；SQLite 只存凭据哈希。每个访客有独立 owner，不能访问其他访客或原有本地项目。写操作检查来源和 CSRF；项目、任务、导出、删除均校验归属。

草稿和进度按访客隔离保存在当前浏览器。清除 Cookie、使用新浏览器或临时地址变化后，不会自动恢复原身份。没有微信登录、跨设备同步或公开管理员入口。“我的故事”支持重新打开和删除；删除故事不清除当日用量。

默认关闭全文训练样本收集。正常运行日志保留模型、步骤、用量和内容指纹，不记录完整模型输入输出。故事与生成结果仍保存在组织者的数据库中，用于恢复和下载；请使用有权提交的内容。

## 调整额度

修改 `backend/config/models.yaml` 的 `share` 段，重启服务生效：

```yaml
share:
  visitor_daily_tokens: 300000
  site_daily_tokens: 100000000
  visitor_concurrency: 1
  site_concurrency: 32
  visitor_submissions_per_minute: 6
  site_submissions_per_minute: 120
```

以上各项也可用对应大写环境变量覆盖，例如 `STORYBRIDGE_SITE_DAILY_TOKENS`、`STORYBRIDGE_VISITOR_CONCURRENCY`。每日输入与输出合计，按北京时间 00:00 恢复。公开模式停用原来的每项目累计上限，次日可以继续原故事。

每次实际模型 HTTP 请求（含重试）在 SQLite 事务中预占输入估算量与最大输出量，成功后按供应商完整 usage 结算；缺少 usage、超时、断流或结果不明时保留预占费用。重启不会释放未知调用的 token 预占。输入以 UTF-8 字节加消息开销保守估算，因此剩余 tokens 可能不足以启动较长的请求，即使还未归零。

任务提交、同步生成共用并发和频率规则。查看、复制、下载不扣生成额度。浏览器回到前台或联网时更新额度，也会定时刷新，以便跨日恢复。tokens 限额不是固定金额的账单上限；价格由模型服务决定。

账本与项目分开保存，没有项目级级联删除。保留 `STORYBRIDGE_DATABASE_FILE` 指定的数据库及其正常 SQLite 备份；人为删除或替换数据库会丢失历史账本，不属于额度重置操作。备份运行中的 SQLite 应使用 SQLite backup API，或先停止服务再复制。

## 恢复与常见故障

- **断网、微信切后台、刷新**：只暂停前端查询，不取消后台任务；回到页面后继续。只有点击“取消”才发出取消请求。
- **某个生成步骤失败**：之前完成的分析、改写稿和检查结果保留；“重试当前步骤”只重跑这一阶段。提交前保存幂等键，响应丢失后可以安全重提。
- **服务重启**：未完成任务标记中断；返回页面后重试当前步骤。已提交的改写会按操作记录核对，避免再改一遍。语言输出可复用同版本产物。
- **检查存在阻塞**：暂停目标语言生成，展开检查详情；可重新检查或选择新的改编方案。不要把阻塞状态当作成功。
- **复制或下载受限**：复制失败会出现手动复制文本框；微信可用右上角菜单“在浏览器打开”。二维码也可长按保存。
- **分享下载失败**：检查代理和 GitHub 连通性；脚本会在代理连接失败后尝试直接下载公开的官方发布文件，并验证发布方 SHA-256 摘要。也可自行安装官方 `cloudflared` 到 PATH。
- **无法建立隧道**：查看退出时显示的 `tunnel.log`；换可访问 Cloudflare 的网络，或配置固定 HTTPS 地址。现有命名隧道配置不会被修改。
- **无法启动**：8000 端口必须空闲。请检查后端日志、主密钥权限和模型配置。使用 `--refresh` 可重新同步依赖。

## 验收与现场记录

自动验证：

```bash
cd backend
.venv/bin/ruff check app tests
.venv/bin/pytest tests -q --cov=app --cov-fail-under=85
cd ../frontend
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run e2e
```

真实模型验收（会消耗 tokens）可运行：

```bash
cd backend
.venv/bin/python -m scripts.acceptance_smoke --option A
```

它通过实际匿名 HTTP 接口导入示例、修改结尾、分析、生成方案、改写、检查并输出英文全文；后台调用真实模型，沿用正常持久额度账本。`--option B` 或 `C` 可验证其他策略。结果写入 `.storybridge/acceptance-real-{选项}.json` 与对应 `.txt`。验证未通过就停止，不强行输出。

现场验收仍需组织者执行，自动化手机视口不能替代真机微信和真实新用户：

| 参与者 | 设备与浏览器 | 网络 | 是否无指导完成 | 卡点与修改记录 |
|---|---|---|---|---|
| 1 | Android / 微信 | 移动网络 | 待测 | |
| 2 | iPhone / 微信 | Wi-Fi | 待测 | |
| 3 | 手机或电脑 | 不同网络 | 待测 | |

让至少三位新用户自行扫码、选择并修改示例、选择方案、取得结果。额外验证微信切后台、断网返回、刷新、复制、下载、额度提示和两位访客相互隔离。此表未填写前，不声称这些现场项目已验收。
