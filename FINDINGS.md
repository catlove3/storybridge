# 短剧本土化翻译 Agent —— 数据/Bench 调研笔记

调研日期：2026-08-25 | 目录：/tmp/opencode/drama-l10n

## 一、已下载到本地的数据（可直接用）

### 1. OpenSubtitles en-zh（OPUS v2016）✅ 已下载
- 文件：`opensubtitles-en-zh.zip` / `OpenSubtitles.en-zh.{en,zh,ids}`（解压后 1.2GB）
- 规模：**930 万句对**，99%+ 含汉字
- 来源：https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2016/moses/en-zh.txt.zip（299MB）
- 优点：纯影视台词、高度口语化（"你大爷的→Damn life!"），风格最接近短剧字幕
- 缺点：对齐噪声（约存在错位句对）、简繁混杂、无剧名/角色元数据
- 用途：风格对齐 / 域适配微调 / 字幕长度约束训练

### 2. Kunpeng 系列（WebNovelTrans org，HF，共 26 个数据集）✅ 已下载 train split
| 子集 | 行数 | 任务 | 样例观察 |
|---|---|---|---|
| kunpeng-idiom | 2,743 | 文化负载词（成语/俗语/网络梗） | 「患得患失→worried about what would happen」；**人名归化：霍老夫人→Mrs. Horton、霍言川→Castro** |
| kunpeng-ner | 1,736 | 命名实体（人名/地名/**武功名**/术语） | 「普通医术→Common Medical Skill」 |
| kunpeng-zpt | 4,684 | 零指代消解（中文省略主语） | 「或许[他们]可以…→maybe they were…」 |
| Kunpeng-la | 4,600 | 一词多义 | 玄幻语境词义消歧 |
| kunpeng-tense | 4,881 | 时态/语态（含 context 字段） | 上下文定过去时 |
| Kunpeng-tt | 4,881 | 时态+上下文版（5 列含 context） | |
| kunpeng-doc-level-webnovel-instruction | 128 | **整章网文翻译** | 杀手流网文整章，篇章级一致性 |

- 统一格式：`query`（中文指令）+ `text` + `answer`（英译）(+ `context`)
- 均为指令微调格式，可直接用于 SFT
- 下载方式：`https://huggingface.co/datasets/WebNovelTrans/<name>/resolve/main/data/train-00000-of-00001.parquet`
- 注意：answer 里有质量波动（ner 样例英文略生硬），建议清洗后再用

## 二、需申请的核心数据集

### 3. GuoFeng Webnovel Corpus V1/V2 ⭐ 强烈推荐申请
- WMT23/24 Discourse-Level Literary Translation 赛道官方数据，**主语言对就是 zh→en**
- V1：179 本网文 / 22,567 章 / **194 万句对**，专业译者人工翻译，篇章级+句对齐，
  含 Simple（同书）/ Difficult（异书）测试集，14 种题材（玄幻、言情等——短剧的主要内容源头）
- 附赠领域预训练模型：Chinese-Llama-2-7B、in-domain RoBERTa / mBART
- 入口：https://github.com/longyuewangdcu/GuoFeng-Webnovel（205 stars，填注册表单拿下载链接）
- 许可：CC-BY 4.0，仅限非商业研究，禁止改写再分发

### 4. BigVideo（ACL Findings'23）
- `fringek/BigVideo`（HF，gated）：~31 万句对，短视频字幕多模态翻译
- **注意方向是 en→zh**（可反向用作平行语料）；2.2TB 含原始视频+ViT/SlowFast 特征
- 申请：发邮件 liyankang@stu.xmu.edu.cn 说明身份用途（直接点申请不会通过），仅研究用
- 代码：github.com/XMUDeepLIT/BigVideo-VMT

### 5. TriFine（COLING'25）
- 视觉+音频+字幕三模态 VMT，带 7 种细粒度标注 tag（第一个三模态 VMT 数据集）
- 申请：guanboyu2022@ia.ac.cn，需 .edu 邮箱 + 机构证明 + 承诺学术用途
- 代码：github.com/BoyuGuan/TriFine

## 三、评测 / Bench

| Bench | 语言对 | 用途 |
|---|---|---|
| WMT23/24 literary testsets（GuoFeng） | zh→en ✅ | 篇章级文学翻译评测（d-BLEU/d-COMET + MQM + A/B） |
| Kunpeng 各 test split | zh→en ✅ | 细粒度诊断：成语/NER/零指代/多义/时态 |
| davidstap/IdiomsInCtx-MT（ACL'24） | en-de/ru **无中文** | 习语评测方法可借鉴，数据本身不适用 |
| facebook/flores FLORES-200 | zh→en | 通用底座 sanity check |
| AraDiCE-Culture / CultureBank | 阿语/文化知识 | 本土化评测维度设计可参考 |

## 四、Agent 架构参考

### 6. napnow/DramaTranslate（V2.1）——最完整的开源短剧译制管线
```
MP4 → ①ffmpeg抽音 → ②faster-whisper ASR → ③Ollama+Qwen2.5 中英翻译
    → ④Reviewer 超长/风格打回(≤2次) → ⑤CosyVoice2 多角色音色克隆 TTS
    → ⑥STTN 字幕擦除 → ⑦QA(长度/对齐/完整性) → ⑧横竖屏合成烧字幕
```
- 步骤级断点续跑（checkpoint.json）、Web 控制台、按显存自动选 7b/14b
- 用户 agent 的工程骨架可直接参考：加"本土化审校"环节即可

### 7. TransAgents 论文（arXiv:2405.11804）⭐
- "(Perhaps) Beyond Human Translation: Multi-Agent Collaboration for Ultra-Long Literary Texts"
- WMT24 literary 赛道推荐阅读：高级编辑+初级译者+校对的多角色协作翻译小说
- 与用户"本土化翻译 agent"的定位最吻合，策略可直接移植（角色分工、术语表、反思迭代）

### 8. 其他
- zsbai780518/drama-translate-system：SaaS 化短剧翻译配音平台（DeepL/阿里云+Azure TTS），偏产品形态
- cola11011/SimvooAI：短剧出海译制工具（仅介绍页）

## 五、给 Agent 的数据配方建议

1. **主训练**：GuoFeng V1（申请后）——篇章级人工译文，学"本土化表达"
2. **风格对齐**：OpenSubtitles en-zh（已下载）——台词口语感，注意先做繁转简+长度过滤+LaBSE相似度去噪
3. **能力专项（SFT）**：Kunpeng 系列（已下载）——成语/NER/零指代/时态各建一个能力模块或混合采样
4. **评测自建**：WMT literary test + Kunpeng test + 自建三层 LLM-judge：
   - 忠实度（含义保留）
   - 本土化度（文化词/人名归化、idiomatic、无翻译腔）
   - 字幕约束（CPS 字符/秒、单行长度、与画面同步）

## 六、本地文件清单
```
.venv/                          # python 环境（pandas+pyarrow）
opensubtitles-en-zh.zip         # 299MB
OpenSubtitles.en-zh.en/.zh/.ids # 9.3M 行 x3
kunpeng-{idiom,zpt,tense,ner}-train.parquet
Kunpeng-{la,tt}-train.parquet
kunpeng-doclevel.parquet        # 128 章篇章级
```
