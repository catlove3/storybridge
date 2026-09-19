import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "../../frontend/node_modules/playwright/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const evidencePath = path.join(here, "evidence/method_evidence.json");
const assetsPath = path.join(here, "assets");
const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));

const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

const option = evidence.plan.options.find(
  (candidate) => candidate.option_label === evidence.selected_option.option_label,
);
const affected = evidence.propagation.affected_scenes;
const sceneTitle = (id) => evidence.scene_titles[id] || id;
const statusText = {
  pass: "检查通过",
  needs_review: "需要人工确认",
  fail: "存在阻塞问题",
}[evidence.verification.overall_status] || evidence.verification.overall_status;

const sharedCss = `
  :root {
    --paper:#f3f0e8; --card:#fbfaf6; --ink:#16263b; --muted:#66717e;
    --line:#d8d2c6; --green:#1f6c57; --green-soft:#e6efeb;
    --gold:#b57b25; --gold-soft:#f4ead8; --red:#9a493d;
    --red-soft:#f4e6e2; --blue:#294e7b; --blue-soft:#e8edf3;
  }
  * { box-sizing:border-box; }
  html,body { margin:0; width:1600px; height:900px; overflow:hidden; }
  body {
    font-family:"Noto Sans CJK SC","Source Han Sans SC","Microsoft YaHei",sans-serif;
    color:var(--ink);
    background:linear-gradient(rgba(22,38,59,.026) 1px,transparent 1px),linear-gradient(90deg,rgba(22,38,59,.026) 1px,transparent 1px),var(--paper);
    background-size:32px 32px;
  }
  .page { height:100%; padding:38px 50px 26px; display:flex; flex-direction:column; gap:17px; }
  .top { display:flex; justify-content:space-between; align-items:flex-start; }
  .eyebrow { margin:0 0 6px; color:var(--green); font:700 13px/1.2 ui-monospace,monospace; letter-spacing:.14em; }
  h1 { margin:0; font-size:38px; line-height:1.12; letter-spacing:-.03em; }
  .subtitle { margin:8px 0 0; color:var(--muted); font-size:15px; }
  .stamp { min-width:250px; padding:12px 16px; border:1px solid #cbbfa9; border-radius:12px; background:rgba(251,250,246,.9); }
  .stamp strong { display:block; color:var(--red); font-size:13px; letter-spacing:.06em; }
  .stamp span { display:block; margin-top:5px; color:var(--muted); font-size:12px; }
  .panel { min-height:0; padding:19px; border:1px solid var(--line); border-radius:15px; background:rgba(251,250,246,.95); }
  .panel-title { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:13px; }
  .panel-title h2 { margin:0; font-size:20px; }
  .panel-title small { color:var(--muted); font:12px/1.2 ui-monospace,monospace; }
  code,.id { color:var(--green); font:700 12px/1.2 ui-monospace,monospace; letter-spacing:.04em; }
  .chip { display:inline-block; margin:4px 5px 0 0; padding:4px 8px; border-radius:999px; background:var(--blue-soft); color:var(--blue); font-size:11px; }
  .chip.gold { background:var(--gold-soft); color:#7e551b; }
  .chip.green { background:var(--green-soft); color:var(--green); }
  .muted { color:var(--muted); }
  footer { display:flex; align-items:center; justify-content:space-between; color:var(--muted); font-size:11px; }
  footer strong { color:var(--ink); }
`;

const documentFor = (body, extraCss = "") => `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>${sharedCss}${extraCss}</style></head><body>${body}</body></html>`;

function pageOne() {
  const node = evidence.culture_node;
  const functions = Object.entries(node.functions || {});
  const choices = evidence.plan.options.map((choice) => {
    const selected = choice.option_label === option.option_label;
    return `<section class="choice ${selected ? "selected" : ""}">
      <header><span class="choice-letter">${esc(choice.option_label)}</span><div><small>${esc(choice.strategy)}</small><h3>${esc(choice.title)}</h3></div>${selected ? '<b class="selected-badge">已选定</b>' : ""}</header>
      <p class="choice-copy">${esc(choice.replacement_definition)}</p>
      <div class="choice-foot"><strong>保留功能</strong><div>${choice.preserved_functions.slice(0, selected ? 7 : 4).map((item) => `<span>${esc(item)}</span>`).join("")}</div></div>
      ${selected ? `<aside><strong>选择原因</strong><p>${esc(choice.rationale)}</p></aside>` : ""}
    </section>`;
  }).join("");
  const body = `<main class="page">
    <header class="top"><div><p class="eyebrow">METHOD EVIDENCE 01 · REAL SAVED OUTPUT</p><h1>文化节点 ＋ 选定改编方案</h1><p class="subtitle">${esc(evidence.project.name)}｜从高摩擦文化机制生成 A / B / C，再记录最终选择。</p></div><div class="stamp"><strong>系统内部证据排版 · 非访客 UI</strong><span>Story State v1 → ${esc(node.id)} → 方案 ${esc(option.option_label)} → v2</span></div></header>
    <section class="plan-layout">
      <article class="panel culture-node">
        <div class="panel-title"><h2>原始文化节点</h2><small>culture_mechanisms[]</small></div>
        <div class="node-head"><code>${esc(node.id)}</code><span class="priority">优先调整</span></div>
        <h3>${esc(node.name)}</h3><p class="node-desc">${esc(node.description)}</p>
        <h4>原文表层词</h4><div>${node.surface_text.map((item) => `<span class="chip gold">${esc(item)}</span>`).join("")}</div>
        <h4>关联场景</h4><div>${node.scene_ids.map((id) => `<span class="chip green">${esc(id)} · ${esc(sceneTitle(id))}</span>`).join("")}</div>
        <h4>承担的叙事功能</h4>
        <div class="functions">${functions.map(([kind, items]) => `<section><strong>${esc(kind)}</strong><p>${items.map(esc).join(" · ")}</p></section>`).join("")}</div>
        <div class="node-metrics"><span>文化摩擦 <b>${esc(node.friction_level)}</b></span><span>叙事重要度 <b>${esc(node.narrative_importance)}</b></span></div>
      </article>
      <article class="panel options"><div class="panel-title"><h2>三个候选方案</h2><small>adaptation_plan.options[]</small></div><div class="choice-grid">${choices}</div></article>
    </section>
    <footer><span><strong>数据：</strong>真实分析节点、真实生成方案、真实应用记录</span><span>选定 B：${esc(option.title)}</span></footer>
  </main>`;
  const css = `
    .plan-layout { flex:1; min-height:0; display:grid; grid-template-columns:430px 1fr; gap:16px; }
    .culture-node h3 { margin:9px 0 7px; font-size:32px; }
    .node-head { display:flex; align-items:center; justify-content:space-between; }
    .priority { padding:5px 9px; border-radius:999px; color:var(--red); background:var(--red-soft); font-size:12px; font-weight:700; }
    .node-desc { margin:0; color:#43515f; font-size:14px; line-height:1.55; }
    .culture-node h4 { margin:16px 0 4px; font-size:13px; }
    .functions { margin-top:5px; display:grid; gap:6px; }
    .functions section { padding:8px 10px; border-radius:9px; background:#f0eee8; }
    .functions strong { color:var(--green); font:700 11px/1.2 ui-monospace,monospace; text-transform:uppercase; }
    .functions p { margin:3px 0 0; color:#53606c; font-size:11px; line-height:1.35; }
    .node-metrics { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:14px; }
    .node-metrics span { padding:9px; border:1px solid var(--line); border-radius:9px; color:var(--muted); font-size:11px; }
    .node-metrics b { float:right; color:var(--red); }
    .options { display:flex; flex-direction:column; }
    .choice-grid { flex:1; display:grid; grid-template-columns:.9fr 1.16fr .9fr; gap:11px; min-height:0; }
    .choice { display:flex; flex-direction:column; padding:15px; border:1px solid var(--line); border-radius:12px; background:#fffdf8; }
    .choice.selected { border:2px solid var(--blue); background:#edf2f7; box-shadow:0 8px 24px rgba(41,78,123,.09); }
    .choice header { display:flex; align-items:flex-start; gap:10px; min-height:86px; }
    .choice-letter { flex:none; display:grid; place-items:center; width:34px; height:34px; border-radius:50%; background:var(--ink); color:white; font:700 19px/1 serif; }
    .selected .choice-letter { background:var(--blue); }
    .choice header div { min-width:0; }
    .choice header small { color:var(--muted); font:10px/1.2 ui-monospace,monospace; }
    .choice h3 { margin:5px 0 0; font-size:17px; line-height:1.35; }
    .selected-badge { margin-left:auto; padding:4px 7px; border-radius:999px; background:var(--blue); color:white; font-size:10px; white-space:nowrap; }
    .choice-copy { display:-webkit-box; margin:6px 0 12px; overflow:hidden; color:#4b5865; font-size:12px; line-height:1.55; -webkit-box-orient:vertical; -webkit-line-clamp:11; }
    .choice-foot { margin-top:auto; padding-top:10px; border-top:1px solid var(--line); }
    .choice-foot strong,.choice aside strong { color:var(--muted); font-size:11px; }
    .choice-foot span { display:inline-block; margin:5px 4px 0 0; padding:3px 6px; border-radius:999px; background:var(--green-soft); color:var(--green); font-size:9px; }
    .choice aside { margin-top:10px; padding:9px; border-radius:9px; background:white; }
    .choice aside p { display:-webkit-box; margin:4px 0 0; overflow:hidden; color:#4c5966; font-size:10px; line-height:1.45; -webkit-box-orient:vertical; -webkit-line-clamp:4; }
  `;
  return documentFor(body, css);
}

function pageTwo() {
  const rows = affected.map((item) => `<section class="path-row">
    <div class="path-nodes">${item.reason_path.map((id, index) => `${index ? '<span class="arrow">→</span>' : ""}<span class="path-node ${id.startsWith("S") ? "scene" : id.startsWith("CM") ? "culture" : "event"}">${esc(id)}</span>`).join("")}</div>
    <small>${item.impact_kinds.map(esc).join(" + ")}</small>
  </section>`).join("");
  const list = affected.map((item) => `<section class="scene-row">
    <div class="scene-id"><code>${esc(item.scene_id)}</code><b>${esc(sceneTitle(item.scene_id))}</b></div>
    <div><div class="reason">${item.reason_path.map(esc).join(" → ")}</div><p>${esc(item.evidence)}</p></div>
  </section>`).join("");
  const body = `<main class="page">
    <header class="top"><div><p class="eyebrow">METHOD EVIDENCE 02 · REAL SAVED OUTPUT</p><h1>依赖图 ＋ 场景清单 ＋ 原因路径</h1><p class="subtitle">从 ${esc(evidence.propagation.changed_node_id)} 出发，代码沿依赖边计算改动范围，并为每个场景保存可追溯路径。</p></div><div class="stamp"><strong>系统内部证据排版 · 非访客 UI</strong><span>${affected.length} 个受影响场景｜${evidence.rewritten_scene_ids.length} 个实际改写场景</span></div></header>
    <section class="prop-layout">
      <article class="panel path-panel"><div class="panel-title"><h2>依赖路径图</h2><small>propagation.affected_scenes[].reason_path</small></div><div class="root"><code>${esc(evidence.culture_node.id)}</code><b>${esc(evidence.culture_node.name)}</b><span>改动起点</span></div><div class="paths">${rows}</div><div class="legend"><span><i class="culture"></i>文化节点</span><span><i class="event"></i>事件</span><span><i class="scene"></i>场景</span></div></article>
      <article class="panel scene-panel"><div class="panel-title"><h2>场景清单与判定依据</h2><small>scene + impact + evidence</small></div><div class="scene-list">${list}</div></article>
    </section>
    <footer><span><strong>传播摘要：</strong>${esc(evidence.propagation.summary)}</span><span>粗体路径来自真实 Dependency Graph；证据文本来自原始场景</span></footer>
  </main>`;
  const css = `
    .prop-layout { flex:1; min-height:0; display:grid; grid-template-columns:660px 1fr; gap:16px; }
    .path-panel { display:flex; flex-direction:column; }
    .root { display:flex; align-items:center; gap:10px; padding:12px 14px; border:2px solid var(--green); border-radius:11px; background:var(--green-soft); }
    .root b { font-size:18px; }.root span { margin-left:auto; color:var(--green); font-size:11px; font-weight:700; }
    .paths { position:relative; flex:1; display:grid; align-content:center; gap:9px; padding:16px 0 8px 28px; }
    .paths::before { content:""; position:absolute; left:8px; top:0; bottom:0; width:2px; background:#c9b17f; }
    .path-row { position:relative; display:flex; flex-direction:column; align-items:flex-start; justify-content:center; min-height:58px; padding:7px 10px; border:1px solid #e0d7c7; border-radius:10px; background:#fffdf8; }
    .path-row::before { content:""; position:absolute; left:-21px; top:50%; width:20px; height:2px; background:#c9b17f; }
    .path-nodes { display:flex; align-items:center; gap:6px; min-width:0; }
    .path-node { display:inline-grid; place-items:center; min-width:48px; padding:7px 9px; border-radius:8px; font:700 11px/1 ui-monospace,monospace; }
    .path-node.culture { color:var(--green); background:var(--green-soft); border:1px solid #bdd5cc; }
    .path-node.event { color:#7d571c; background:var(--gold-soft); border:1px solid #e5cea6; }
    .path-node.scene { color:var(--blue); background:var(--blue-soft); border:1px solid #cad5e1; }
    .arrow { color:#ac9268; font-weight:700; }.path-row small { margin-top:5px; color:var(--muted); font-size:9px; white-space:nowrap; }
    .legend { display:flex; gap:17px; padding-top:9px; color:var(--muted); font-size:10px; }
    .legend i { display:inline-block; width:9px; height:9px; margin-right:5px; border-radius:3px; }.legend i.culture{background:var(--green)}.legend i.event{background:var(--gold)}.legend i.scene{background:var(--blue)}
    .scene-panel { display:flex; flex-direction:column; }
    .scene-list { flex:1; display:grid; gap:7px; }
    .scene-row { display:grid; grid-template-columns:155px 1fr; align-items:center; gap:12px; min-height:72px; padding:8px 11px; border:1px solid #e0d7c7; border-radius:10px; background:#fffdf8; }
    .scene-id { display:flex; flex-direction:column; gap:4px; }.scene-id b { font-size:14px; }
    .reason { color:var(--blue); font:700 11px/1.2 ui-monospace,monospace; }
    .scene-row p { display:-webkit-box; margin:5px 0 0; overflow:hidden; color:#5b6670; font-size:10px; line-height:1.4; -webkit-box-orient:vertical; -webkit-line-clamp:2; }
  `;
  return documentFor(body, css);
}

function repairSummary(revision) {
  const summaries = {
    12: "统一重生后分数归属",
    13: "区分原始成绩与交换后成绩",
    14: "统一换分规则与人物记忆",
    15: "清除“送分决定锁定”的残留表述",
    16: "润色台词、人物反应与叙事节奏",
  };
  return summaries[revision.state_version] || revision.description;
}

function pageThree() {
  const report = evidence.verification;
  const issues = report.issues;
  const warnings = issues.filter((issue) => issue.severity === "warning");
  const errors = issues.filter((issue) => issue.severity === "error");
  const repairs = evidence.revisions.filter((revision) => revision.kind === "repair" && revision.state_version >= 12);
  const sceneIds = Array.from({ length: 12 }, (_, index) => `S${String(index + 1).padStart(2, "0")}`);
  const matrixHead = repairs.map((repair) => `<b>v${repair.state_version}</b>`).join("");
  const matrixRows = sceneIds.map((id) => `<div class="matrix-row"><span>${id}</span>${repairs.map((repair) => `<i class="${repair.changed_scene_ids.includes(id) ? "changed" : ""}"></i>`).join("")}</div>`).join("");
  const repairCards = repairs.map((repair) => `<section class="repair-card"><div><code>v${repair.state_version}</code><b>${esc(repairSummary(repair))}</b></div><p>${repair.changed_scene_ids.map((id) => `<span>${id}</span>`).join("")}</p></section>`).join("");
  const issueCards = issues.map((issue) => `<section class="issue ${esc(issue.severity)}"><header><span>${issue.severity === "error" ? "需要修改" : "待确认"}</span><code>${esc(issue.issue_type)}</code></header><p>${esc(issue.description)}</p><small>${esc(issue.evidence)}</small></section>`).join("");
  const checks = report.commitment_checks.slice(0, 4).map((check) => `<section class="check"><code>${esc(check.commitment_id)}</code><div><b>已保留</b><p>${esc(check.explanation)}</p></div></section>`).join("");
  const body = `<main class="page">
    <header class="top"><div><p class="eyebrow">METHOD EVIDENCE 03 · REAL SAVED OUTPUT</p><h1>检查报告 ＋ 按场修复记录</h1><p class="subtitle">检查不是一句“通过”：报告保留问题、证据、承诺回收结果，以及每轮实际改动的场景。</p></div><div class="stamp"><strong>${esc(statusText)}</strong><span>当前 Story State v${evidence.project.current_state_version}｜报告一致性 ${Math.round(report.consistency_score * 100)}%</span></div></header>
    <section class="report-stats"><div><b>${report.scenes_checked}/${report.scenes_total}</b><span>场景已检查</span></div><div><b>${report.commitments_verified}/${report.commitments_total}</b><span>承诺已确认</span></div><div><b>${report.static_checks_passed}/${report.static_checks_total}</b><span>静态检查通过</span></div><div><b>${errors.length}</b><span>阻塞错误</span></div><div><b>${warnings.length}</b><span>待确认警告</span></div><div><b>${evidence.project.current_state_version}</b><span>状态版本</span></div></section>
    <section class="verify-layout">
      <article class="panel report-panel"><div class="panel-title"><h2>检查报告</h2><small>verification_report</small></div>${issueCards}<h3 class="checks-title">叙事承诺回收 · ${report.commitments_verified}/${report.commitments_total}</h3><div class="checks">${checks}</div><p class="more">另有 ${Math.max(0, report.commitment_checks.length - 4)} 项承诺已确认，完整记录保存在报告中。</p></article>
      <article class="panel repair-panel"><div class="panel-title"><h2>按场修复记录</h2><small>revisions[] · 最后五轮</small></div><div class="repair-content"><div class="repair-list">${repairCards}</div><div class="matrix"><h3>每轮实际修改了哪些场景</h3><div class="matrix-head"><span>场景</span>${matrixHead}</div>${matrixRows}<div class="matrix-legend"><i></i>本轮修改</div></div></div></article>
    </section>
    <footer><span><strong>状态：</strong>${esc(statusText)}；错误 ${errors.length}，警告 ${warnings.length}，已有内容和修复历史均保留</span><span>数据来自 verification_reports + revisions；画面为证据排版，非访客 UI</span></footer>
  </main>`;
  const css = `
    .report-stats { display:grid; grid-template-columns:repeat(6,1fr); gap:9px; }
    .report-stats div { padding:10px 12px; border:1px solid var(--line); border-radius:10px; background:rgba(251,250,246,.94); }
    .report-stats b { color:var(--green); font:700 21px/1 ui-monospace,monospace; }.report-stats span { margin-left:7px; color:var(--muted); font-size:11px; }
    .verify-layout { flex:1; min-height:0; display:grid; grid-template-columns:610px 1fr; gap:16px; }
    .report-panel,.repair-panel { display:flex; flex-direction:column; }
    .issue { padding:12px; border-radius:10px; background:var(--gold-soft); border-left:4px solid var(--gold); }
    .issue.error { background:var(--red-soft); border-left-color:var(--red); }
    .issue header { display:flex; align-items:center; justify-content:space-between; }.issue header span { font-size:12px; font-weight:700; color:#7e551b; }
    .issue p { margin:7px 0 5px; font-size:13px; line-height:1.45; }.issue small { color:#6f6250; font-size:10px; }
    .checks-title { margin:14px 0 8px; padding-top:12px; border-top:1px solid var(--line); font-size:15px; }
    .checks { display:grid; gap:6px; }.check { display:grid; grid-template-columns:45px 1fr; gap:8px; padding:8px 9px; border:1px solid #d8e2dc; border-radius:9px; background:var(--green-soft); }
    .check b { color:var(--green); font-size:11px; }.check p { display:-webkit-box; margin:2px 0 0; overflow:hidden; color:#506059; font-size:10px; line-height:1.4; -webkit-box-orient:vertical; -webkit-line-clamp:2; }
    .more { margin:7px 0 0; color:var(--muted); font-size:10px; }
    .repair-content { flex:1; min-height:0; display:grid; grid-template-columns:1.23fr .77fr; gap:14px; }
    .repair-list { display:grid; gap:8px; align-content:start; }.repair-card { padding:10px 11px; border:1px solid #dfd5c3; border-radius:10px; background:#fffdf8; }
    .repair-card div { display:flex; align-items:center; gap:9px; }.repair-card b { font-size:13px; }.repair-card p { margin:7px 0 0; }
    .repair-card p span { display:inline-block; margin:2px 3px 0 0; padding:3px 5px; border-radius:5px; color:var(--blue); background:var(--blue-soft); font:700 9px/1 ui-monospace,monospace; }
    .matrix { padding:12px; border-radius:11px; background:#efede7; }.matrix h3 { margin:0 0 11px; font-size:14px; }
    .matrix-head,.matrix-row { display:grid; grid-template-columns:48px repeat(5,1fr); align-items:center; gap:5px; }
    .matrix-head { margin-bottom:6px; color:var(--muted); font:10px/1 ui-monospace,monospace; text-align:center; }.matrix-head span { text-align:left; }
    .matrix-row { min-height:27px; border-top:1px solid #ddd8cd; }.matrix-row span { color:#5f6972; font:700 10px/1 ui-monospace,monospace; }
    .matrix-row i { justify-self:center; width:10px; height:10px; border-radius:50%; background:#d5d0c7; }.matrix-row i.changed { background:var(--gold); box-shadow:0 0 0 3px #ead9b9; }
    .matrix-legend { margin-top:10px; color:var(--muted); font-size:9px; }.matrix-legend i { display:inline-block; width:9px; height:9px; margin-right:5px; border-radius:50%; background:var(--gold); }
  `;
  return documentFor(body, css);
}

fs.mkdirSync(assetsPath, { recursive: true });
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
for (const [filename, html] of [
  ["evidence_culture_plan.png", pageOne()],
  ["evidence_dependency_paths.png", pageTwo()],
  ["evidence_verification_repairs.png", pageThree()],
]) {
  await page.setContent(html, { waitUntil: "load" });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(assetsPath, filename) });
  console.log(path.join(assetsPath, filename));
}
await browser.close();
