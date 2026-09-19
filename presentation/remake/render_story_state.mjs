import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "../../frontend/node_modules/playwright/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.join(here, "evidence/method_evidence.json");
const outputPath = path.join(here, "assets/story_state.png");
const evidence = JSON.parse(fs.readFileSync(sourcePath, "utf8"));
const state = evidence.story_state;

const escapeHtml = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

const byId = (items, id) => {
  const item = items.find((candidate) => candidate.id === id);
  if (!item) throw new Error(`Missing ${id} in ${sourcePath}`);
  return item;
};

const characters = ["C01", "C02", "C03"].map((id) => byId(state.characters, id));
const settings = ["SET04", "SET05"].map((id) => byId(state.settings, id));
const scenes = ["S04", "S05", "S06", "S09", "S10"].map((id) => byId(state.scenes, id));
const mechanisms = ["CM01", "CM12", "CM08", "CM10"].map((id) => byId(state.culture_mechanisms, id));
const commitments = ["NC01", "NC03", "NC06"].map((id) => byId(state.commitments, id));

const stats = [
  [evidence.counts.scenes, "场景"],
  [evidence.counts.characters, "角色"],
  [evidence.counts.events, "事件"],
  [evidence.counts.settings, "核心设定"],
  [evidence.counts.culture_mechanisms, "文化机制"],
  [evidence.counts.commitments, "叙事承诺"],
  [evidence.counts.dependencies, "依赖关系"],
];

const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  :root {
    --paper: #f3f0e8;
    --card: #fbfaf6;
    --ink: #16263b;
    --muted: #66717e;
    --line: #d8d2c6;
    --green: #1f6c57;
    --green-soft: #e6efeb;
    --gold: #b57b25;
    --gold-soft: #f4ead8;
    --red: #9a493d;
    --blue: #294e7b;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; width: 1600px; height: 900px; overflow: hidden; }
  body {
    font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
    color: var(--ink);
    background:
      linear-gradient(rgba(22,38,59,.026) 1px, transparent 1px),
      linear-gradient(90deg, rgba(22,38,59,.026) 1px, transparent 1px),
      var(--paper);
    background-size: 32px 32px;
  }
  .page { height: 100%; padding: 38px 50px 28px; display: flex; flex-direction: column; gap: 18px; }
  .top { display: flex; align-items: flex-start; justify-content: space-between; }
  .eyebrow { margin: 0 0 6px; color: var(--green); font: 700 13px/1.2 ui-monospace, monospace; letter-spacing: .14em; }
  h1 { margin: 0; font-size: 38px; line-height: 1.12; letter-spacing: -.03em; }
  .subtitle { margin: 8px 0 0; color: var(--muted); font-size: 16px; }
  .internal {
    display: flex; align-items: center; gap: 13px; padding: 12px 16px;
    border: 1px solid #cbbfa9; border-radius: 12px; background: rgba(251,250,246,.86);
  }
  .internal strong { display: block; color: var(--red); font-size: 13px; letter-spacing: .08em; }
  .internal span { display: block; margin-top: 4px; color: var(--muted); font-size: 13px; }
  .internal .version { font: 700 27px/1 ui-monospace, monospace; color: var(--blue); }
  .stats { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; }
  .stat { padding: 10px 14px; border: 1px solid var(--line); border-radius: 10px; background: rgba(251,250,246,.9); }
  .stat b { font: 700 23px/1 ui-monospace, monospace; color: var(--green); }
  .stat span { margin-left: 7px; color: var(--muted); font-size: 13px; }
  .columns { flex: 1; min-height: 0; display: grid; grid-template-columns: 360px 1fr 455px; gap: 16px; }
  .panel { min-height: 0; padding: 19px; border: 1px solid var(--line); border-radius: 15px; background: rgba(251,250,246,.94); }
  .panel-title { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 13px; }
  h2 { margin: 0; font-size: 20px; }
  .panel-title small { color: var(--muted); font: 12px/1.2 ui-monospace, monospace; }
  .person { padding: 13px 0; border-top: 1px solid var(--line); }
  .person:first-of-type { border-top: 0; }
  .row-head { display: flex; align-items: center; gap: 9px; }
  code, .id { color: var(--green); font: 700 12px/1.2 ui-monospace, monospace; letter-spacing: .04em; }
  .person h3, .rule h3, .scene h3 { margin: 0; font-size: 17px; }
  .role { margin-left: auto; padding: 3px 8px; border-radius: 999px; color: var(--blue); background: #e6ebf1; font-size: 11px; }
  .copy { display: -webkit-box; margin: 8px 0 0; overflow: hidden; color: #475565; font-size: 13px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
  .rule-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .rule { min-height: 112px; padding: 13px; border-radius: 11px; background: var(--green-soft); border: 1px solid #c8dcd4; }
  .rule .copy { -webkit-line-clamp: 3; }
  .chain-label { margin: 15px 0 9px; color: var(--muted); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
  .chain { position: relative; display: grid; gap: 7px; }
  .chain::before { content: ""; position: absolute; left: 16px; top: 21px; bottom: 21px; width: 2px; background: #d8c29e; }
  .scene { position: relative; display: grid; grid-template-columns: 34px 105px 1fr; align-items: center; min-height: 58px; padding: 9px 11px; border: 1px solid #e0d5c2; border-radius: 10px; background: #fffdf8; }
  .scene .dot { position: relative; z-index: 1; display: grid; place-items: center; width: 18px; height: 18px; border: 4px solid var(--gold-soft); border-radius: 50%; background: var(--gold); }
  .scene h3 { font-size: 14px; }
  .scene p { display: -webkit-box; margin: 0; overflow: hidden; color: #53606d; font-size: 12px; line-height: 1.42; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
  .mechanisms { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 17px; }
  .mechanism { width: calc(50% - 4px); padding: 10px 11px; border-radius: 10px; background: #edf1f5; border: 1px solid #d5dde5; }
  .mechanism b { display: block; margin-top: 4px; font-size: 14px; }
  .mechanism span { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; }
  .commitment-title { margin: 0 0 8px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 15px; }
  .commitment { margin-top: 8px; padding: 10px 11px; border-left: 3px solid var(--gold); border-radius: 0 9px 9px 0; background: var(--gold-soft); }
  .commitment p { display: -webkit-box; margin: 5px 0 0; overflow: hidden; color: #4f5963; font-size: 12px; line-height: 1.43; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
  footer { display: flex; align-items: center; justify-content: space-between; color: var(--muted); font-size: 11px; }
  footer strong { color: var(--ink); }
</style>
</head>
<body>
<main class="page">
  <header class="top">
    <div>
      <p class="eyebrow">SYSTEM EVIDENCE · REAL SAVED OUTPUT</p>
      <h1>Story State：系统怎样理解《借笔换分》</h1>
      <p class="subtitle">从完整剧本抽取人物、规则、场景、文化机制与叙事承诺，再交给依赖传播和改写流程。</p>
    </div>
    <div class="internal">
      <div class="version">v${escapeHtml(state.version)}</div>
      <div><strong>系统内部结构化结果 · 节选</strong><span>非访客操作界面｜zh-CN → ${escapeHtml(state.target_locale)}</span></div>
    </div>
  </header>
  <section class="stats">
    ${stats.map(([value, label]) => `<div class="stat"><b>${value}</b><span>${label}</span></div>`).join("")}
  </section>
  <section class="columns">
    <article class="panel">
      <div class="panel-title"><h2>人物状态</h2><small>characters[]</small></div>
      ${characters.map((character) => `
        <section class="person">
          <div class="row-head"><code>${escapeHtml(character.id)}</code><h3>${escapeHtml(character.name)}</h3><span class="role">${escapeHtml(character.role)}</span></div>
          <p class="copy">${escapeHtml(character.description)}</p>
        </section>`).join("")}
    </article>
    <article class="panel">
      <div class="panel-title"><h2>规则与关键场景链</h2><small>settings[] → scenes[]</small></div>
      <div class="rule-grid">
        ${settings.map((setting) => `<section class="rule"><code>${escapeHtml(setting.id)}</code><h3>${escapeHtml(setting.name)}</h3><p class="copy">${escapeHtml(setting.description)}</p></section>`).join("")}
      </div>
      <p class="chain-label">STRUCTURED SCENE SEQUENCE</p>
      <div class="chain">
        ${scenes.map((scene) => `<section class="scene"><span class="dot"></span><div><code>${escapeHtml(scene.id)}</code><h3>${escapeHtml(scene.title)}</h3></div><p>${escapeHtml(scene.summary)}</p></section>`).join("")}
      </div>
    </article>
    <article class="panel">
      <div class="panel-title"><h2>文化机制与承诺</h2><small>mechanisms[] / commitments[]</small></div>
      <div class="mechanisms">
        ${mechanisms.map((mechanism) => `<section class="mechanism"><code>${escapeHtml(mechanism.id)}</code><b>${escapeHtml(mechanism.name)}</b><span>${escapeHtml(mechanism.friction_level)} friction · ${mechanism.scene_ids.length} 个场景</span></section>`).join("")}
      </div>
      <h3 class="commitment-title">必须追踪到后文的叙事承诺</h3>
      ${commitments.map((commitment) => `<section class="commitment"><code>${escapeHtml(commitment.id)}</code><p>${escapeHtml(commitment.description)}</p></section>`).join("")}
    </article>
  </section>
  <footer>
    <span><strong>来源：</strong>真实完成项目 method_evidence.json · initial Story State v1</span>
    <span>画面仅做展示排版；字段、ID 与统计均取自保存的 StoryState</span>
  </footer>
</main>
</body>
</html>`;

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
await page.setContent(html, { waitUntil: "load" });
await page.screenshot({ path: outputPath });
await browser.close();
console.log(outputPath);
