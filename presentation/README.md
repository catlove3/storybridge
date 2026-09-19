# StoryBridge · 通俗易懂版

打开 `StoryBridge_最终版.pptx` 或 `StoryBridge_智理杯_5分钟展示.pptx`，两份内容一致。13 页主讲＋3 页隐藏备答；讲稿建议 5 分钟，包含第 11 页的 18 秒视频。

按案例贯穿方法：项目与问题 → 案例 → Story State → 文化节点与方案 → Dependency Graph → 检查与按场修复 → 早期测试短板 → 对应的产品优势 → 操作与交付。第 4—7 页分别使用真实保存结果生成的四张 16:9 证据图，并明确标注为内部证据排版、非访客 UI。第 8 页汇总“改不全、改错、缺少依赖追踪”；三栏分别来自后续测试反馈、早期冻结输出与流程对照，不能与第 4—7 页视为同一轮运行。本次没有重跑模型。

修改前文件在 `remake/readable_20260917/before/`。重建：`python3.12 presentation/remake/build_readable_deck.py`；重新导出与验证：运行同目录下 `verify_readable.ps1`，再运行 `package_readable.py`。不要用历史生成器覆盖本稿。

四张方法证据图位于 `remake/assets/story_state.png`、`evidence_culture_plan.png`、`evidence_dependency_paths.png`、`evidence_verification_repairs.png`。冻结数据与重建脚本见 `remake/evidence/method_evidence.json`、`export_method_evidence.py` 和 `render_method_evidence.mjs`。
