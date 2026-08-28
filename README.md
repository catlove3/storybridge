# StoryBridge

> 面向中文短剧 / 网文出海的 AI 跨文化故事改编智能体（"智理杯"参赛项目）

它不只是翻译文本，而是理解文化元素在故事中的**叙事功能**，
通过显式的故事状态与依赖关系规划本土化方案，
并在一个设定变化后自动追踪、修改和验证受影响的后续剧情。

## 核心闭环

```
识别文化摩擦点 → 分析叙事功能 → 生成改编方案 → 用户选择
→ 依赖图定位受影响场景 → 局部重写 → 双层一致性验证 → 自动修复
```

## 快速开始

```bash
cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env        # 填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

python -m pytest tests/ -q                              # 132 个离线测试
python -m app.cli --mock demo data/scripts/demo_v0.md   # 零成本跑通全闭环
uvicorn app.main:app --reload                           # 起服务 http://localhost:8000/docs
```

## 文档

- [`backend/README.md`](backend/README.md) — 架构、API 契约、Skill 层与微调兼容、CLI
- [`backend/docs/HANDOFF.md`](backend/docs/HANDOFF.md) — 交接文档：前端联调指南、改动热力图、bug 档案

## 目录

```
backend/    FastAPI + Agent 核心（Python 3.12）
frontend/   React 前端（同学B负责，建设中）
docs/       竞赛方案与调研笔记
```
