from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime_io import write_json, write_text


MONITOR_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ABC Agent Chat Monitor</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3f0e8;
      --ink: #1b1a17;
      --muted: #716b5f;
      --panel: #fffdf7;
      --panel-strong: #f8f2e7;
      --line: #d9d0bf;
      --line-strong: #2d2a23;
      --accent: #0e7490;
      --accent-ink: #06313d;
      --accent-soft: #d7edf2;
      --good: #0f766e;
      --warn: #b45309;
      --danger: #c2410c;
      --shadow: 0 18px 40px rgba(55, 45, 28, .12);
      --mono: "SFMono-Regular", "Menlo", "Consolas", monospace;
      font-family: "Avenir Next", "Gill Sans", "Helvetica Neue", sans-serif;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --bg: #090b0d;
      --ink: #eef1ea;
      --muted: #a3a092;
      --panel: #121518;
      --panel-strong: #191e22;
      --line: #30363b;
      --line-strong: #f5f0df;
      --accent: #67e8f9;
      --accent-ink: #ddfbff;
      --accent-soft: #102e35;
      --good: #5eead4;
      --warn: #fbbf24;
      --danger: #fb7185;
      --shadow: 0 20px 48px rgba(0, 0, 0, .38);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background:
        linear-gradient(90deg, rgba(14,116,144,.08) 1px, transparent 1px),
        linear-gradient(180deg, rgba(180,83,9,.06) 1px, transparent 1px),
        var(--bg);
      background-size: 56px 56px, 56px 56px, auto;
      color: var(--ink);
    }
    main { max-width: 1440px; margin: 0 auto; padding: 22px; }
    header {
      position: sticky;
      top: 0;
      z-index: 3;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
      margin: -22px -22px 18px;
      padding: 20px 22px 18px;
      border-bottom: 3px solid var(--line-strong);
      background: color-mix(in srgb, var(--bg) 90%, transparent);
      backdrop-filter: blur(18px);
    }
    h1 { margin: 0; font-size: clamp(34px, 4vw, 64px); line-height: .92; letter-spacing: 0; }
    h2 { font-size: 15px; margin: 0 0 10px; text-transform: uppercase; letter-spacing: .04em; }
    .topline { color: var(--muted); font: 700 12px/1 var(--mono); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
    .scenario-title { margin-top: 12px; font-size: clamp(19px, 2vw, 28px); font-weight: 800; color: var(--accent-ink); }
    .header-tools { display: flex; flex-direction: column; gap: 10px; align-items: flex-end; }
    .muted { color: var(--muted); font-size: 13px; text-align: right; }
    .theme-toggle {
      width: 42px;
      height: 42px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line-strong);
      border-radius: 50%;
      background: var(--panel);
      color: var(--ink);
      box-shadow: var(--shadow);
      cursor: pointer;
      font: 900 20px/1 "Avenir Next", sans-serif;
    }
    .theme-toggle:hover { transform: translateY(-1px); }
    .grid { display: grid; grid-template-columns: repeat(7, minmax(128px, 1fr)); gap: 10px; margin: 18px 0; }
    .tile, section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      box-shadow: var(--shadow);
    }
    .tile { min-height: 96px; border-top: 4px solid var(--line-strong); }
    .label { color: var(--muted); font: 800 11px/1.2 var(--mono); text-transform: uppercase; letter-spacing: .06em; }
    .value { margin-top: 8px; font-size: clamp(20px, 2vw, 29px); line-height: 1; font-weight: 900; overflow-wrap: anywhere; }
    .small { margin-top: 6px; color: var(--muted); font-size: 12px; line-height: 1.42; }
    section { margin-top: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { color: var(--ink); background: var(--panel-strong); font: 800 11px/1.2 var(--mono); text-transform: uppercase; letter-spacing: .05em; }
    .event { font-family: var(--mono); white-space: pre-wrap; line-height: 1.5; color: var(--accent-ink); }
    .phase { display: grid; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 12px; }
    section[hidden] { display: none; }
    .batch-summary { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .batch-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
    .case-card { border: 1px solid var(--line); border-top: 4px solid var(--line-strong); border-radius: 8px; background: var(--panel-strong); padding: 12px; min-height: 150px; }
    .case-card.done { border-top-color: var(--good); }
    .case-card.running { border-top-color: var(--accent); }
    .case-card.error { border-top-color: var(--danger); }
    .case-card.pending { border-top-color: var(--warn); }
    .case-head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
    .case-index { color: var(--muted); font: 900 12px/1 var(--mono); letter-spacing: .06em; }
    .case-title { margin-top: 6px; font-size: 16px; font-weight: 900; line-height: 1.25; color: var(--ink); }
    .case-status { font: 900 12px/1 var(--mono); text-transform: uppercase; color: var(--accent-ink); }
    .case-meta { margin-top: 10px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; color: var(--muted); font-size: 12px; }
    .case-link { display: inline-block; margin-top: 10px; color: var(--accent-ink); font: 900 12px/1 var(--mono); text-decoration: none; border-bottom: 1px solid currentColor; }
    .progress { height: 12px; overflow: hidden; background: var(--panel-strong); border: 1px solid var(--line); border-radius: 999px; margin-top: 10px; }
    .progress > div { height: 100%; background: linear-gradient(90deg, var(--accent), var(--warn)); width: 0%; transition: width .25s ease; }
    .pill { display: inline-block; padding: 4px 8px; border: 1px solid var(--line); border-radius: 999px; background: var(--accent-soft); color: var(--accent-ink); margin: 0 6px 6px 0; font: 700 12px/1.2 var(--mono); }
    .preview-toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .preview-button { border: 1px solid var(--line); background: var(--panel-strong); color: var(--ink); border-radius: 6px; padding: 8px 10px; font: 800 13px/1 var(--mono); cursor: pointer; }
    .preview-button:hover { border-color: var(--line-strong); }
    .preview-button.active { background: var(--accent); border-color: var(--accent); color: var(--bg); }
    .preview-meta { margin-bottom: 8px; color: var(--muted); font-size: 12px; }
    .preview-box { margin: 0; max-height: 540px; overflow: auto; white-space: pre-wrap; border: 1px solid var(--line); background: color-mix(in srgb, var(--panel-strong) 82%, var(--bg)); color: var(--ink); border-radius: 8px; padding: 14px; font: 12px/1.58 var(--mono); }
    .ok { color: var(--good); }
    .warn { color: var(--warn); }
    .danger { color: var(--danger); }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    @media (max-width: 1120px) { .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .phase { grid-template-columns: 1fr; } }
    @media (max-width: 720px) { main { padding: 14px; } header { margin: -14px -14px 14px; padding: 16px 14px; grid-template-columns: 1fr; } .header-tools { align-items: flex-start; } .muted { text-align: left; } .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <div class="topline">live run console</div>
        <h1>ABC Agent Chat Monitor</h1>
        <div class="scenario-title" id="scenario">loading</div>
      </div>
      <div class="header-tools">
        <button class="theme-toggle" id="themeToggle" type="button" aria-label="切换亮色或暗色模式" title="切换亮色或暗色模式">
          <span id="themeIcon" aria-hidden="true">☾</span>
          <span class="sr-only">切换主题</span>
        </button>
        <div class="muted" id="updated">waiting</div>
      </div>
    </header>
    <div class="grid">
      <div class="tile"><div class="label">状态</div><div class="value" id="status">-</div></div>
      <div class="tile"><div class="label">循环</div><div class="value" id="loop">-</div></div>
      <div class="tile"><div class="label">阶段</div><div class="value" id="phaseName">-</div><div class="small" id="phaseSub">-</div></div>
      <div class="tile"><div class="label">调用</div><div class="value" id="calls">-</div><div class="small" id="callSub">-</div></div>
      <div class="tile"><div class="label">Tokens</div><div class="value" id="tokens">-</div><div class="small" id="tokenSub">-</div></div>
      <div class="tile"><div class="label">估算费用</div><div class="value" id="cost">-</div><div class="small" id="costSub">USD，按官方每百万 token 单价</div></div>
      <div class="tile"><div class="label">错误</div><div class="value" id="errors">-</div></div>
    </div>
    <div class="progress"><div id="progressBar"></div></div>
    <section id="batchSection" hidden>
      <h2>测试流程总览</h2>
      <div class="batch-summary" id="batchSummary"></div>
      <div class="batch-grid" id="batchGrid"></div>
    </section>
    <div class="phase">
      <section>
        <h2>当前阶段说明</h2>
        <div id="phaseDescription">-</div>
        <div class="small" id="phaseDetail">-</div>
      </section>
      <section>
        <h2>Token 用量拆分</h2>
        <div id="tokenBreakdown">-</div>
      </section>
    </div>
    <section>
      <h2>最近事件</h2>
      <div class="event" id="events">-</div>
    </section>
    <section>
      <h2>运行产物预览</h2>
      <div class="preview-toolbar" id="previewTabs"></div>
      <div class="preview-meta" id="previewMeta">等待产物生成</div>
      <pre class="preview-box" id="previewBox">-</pre>
    </section>
    <section>
      <h2>调用分布</h2>
      <table><thead><tr><th>类型</th><th>数量</th><th>Prompt</th><th>Output</th><th>Reasoning</th><th>Total</th><th>估算费用</th></tr></thead><tbody id="bytype"></tbody></table>
    </section>
    <section>
      <h2>模型与计费假设</h2>
      <div class="small" id="pricingNote">-</div>
    </section>
  </main>
  <script>
    const PRICE_USD_PER_M = {
      'deepseek-v4-pro': { hit: 0.145, miss: 1.74, out: 3.48 },
      'deepseek-v4-flash': { hit: 0.028, miss: 0.14, out: 0.28 },
      'deepseek-chat': { hit: 0.028, miss: 0.14, out: 0.28 },
      'deepseek-reasoner': { hit: 0.028, miss: 0.14, out: 0.28 }
    };
    const fmt = n => Number(n || 0).toLocaleString();
    const money = n => '$' + Number(n || 0).toFixed(n >= 1 ? 4 : 6);
    let selectedPreviewPath = '';
    function applyTheme(theme) {
      const next = theme === 'dark' ? 'dark' : 'light';
      document.documentElement.dataset.theme = next;
      localStorage.setItem('abc-monitor-theme', next);
      const icon = document.getElementById('themeIcon');
      const button = document.getElementById('themeToggle');
      if (icon) icon.textContent = next === 'dark' ? '☀' : '☾';
      if (button) button.setAttribute('aria-label', next === 'dark' ? '切换到亮色模式' : '切换到暗色模式');
    }
    applyTheme(localStorage.getItem('abc-monitor-theme') || 'light');
    document.addEventListener('click', event => {
      const button = event.target && event.target.closest ? event.target.closest('#themeToggle') : null;
      if (!button) return;
      applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    });
    const DEFAULT_BATCH_CASES = [
      { index: 1, slug: '01_ebike_charging_governance', title: '电动自行车社区充电收费与安全治理议案', scenario: 'scenarios/01_ebike_charging_governance.md' },
      { index: 2, slug: '02_old_community_elevator', title: '老旧小区加装电梯与低楼层补偿议案', scenario: 'scenarios/02_old_community_elevator.md' },
      { index: 3, slug: '03_complete_community_priorities', title: '完整社区建设项目排序议案', scenario: 'scenarios/03_complete_community_priorities.md' },
      { index: 4, slug: '04_platform_worker_rights', title: '新就业形态骑手权益协商议案', scenario: 'scenarios/04_platform_worker_rights.md' },
      { index: 5, slug: '05_community_eldercare_station', title: '社区养老服务站资源配置议案', scenario: 'scenarios/05_community_eldercare_station.md' },
      { index: 6, slug: '06_primary_health_chronic_disease', title: '基层慢病筛查与社区健康服务议案', scenario: 'scenarios/06_primary_health_chronic_disease.md' },
      { index: 7, slug: '07_urban_underground_space', title: '城市地下空间与公共通道使用议案', scenario: 'scenarios/07_urban_underground_space.md' },
      { index: 8, slug: '08_embedded_community_services', title: '社区嵌入式服务设施运营议案', scenario: 'scenarios/08_embedded_community_services.md' },
      { index: 9, slug: '09_university_ai_academic_integrity', title: '大学 AI 学术诚信与学生权益建议议案', scenario: 'scenarios/09_university_ai_academic_integrity.md' },
      { index: 10, slug: '10_university_evening_self_study', title: '大学是否应该有晚自习议案', scenario: 'scenarios/10_university_evening_self_study.md' },
      { index: 11, slug: '11_ai_created_art_status', title: 'AI 创作内容是否算作艺术议案', scenario: 'scenarios/11_ai_created_art_status.md' },
      { index: 12, slug: '12_ai_regulation_next_steps', title: 'AI 应该如何进一步监管议案', scenario: 'scenarios/12_ai_regulation_next_steps.md' },
      { index: 13, slug: '13_ai_teen_education_use', title: 'AI 是否应被用于青少年教育议案', scenario: 'scenarios/13_ai_teen_education_use.md' },
      { index: 14, slug: '14_sexual_content_social_harm', title: '色情内容与软色情是否对社会有害议案', scenario: 'scenarios/14_sexual_content_social_harm.md' },
      { index: 15, slug: '15_metaverse_real_world_impact', title: '元宇宙概念对现实社会冲击议案', scenario: 'scenarios/15_metaverse_real_world_impact.md' },
      { index: 16, slug: '16_ai_productivity_communism', title: 'AI 生产力爆炸后是否可能达成共产主义社会议案', scenario: 'scenarios/16_ai_productivity_communism.md' },
      { index: 17, slug: '17_new_confucianism_reasonableness', title: '新儒家理论是否具有合理性议案', scenario: 'scenarios/17_new_confucianism_reasonableness.md' },
      { index: 18, slug: '18_china_next_20_years_expansion', title: '中国未来二十年影响力扩张路径议案', scenario: 'scenarios/18_china_next_20_years_expansion.md' },
      { index: 19, slug: '19_betel_nut_drug_classification', title: '槟榔是否应被视为毒品或成瘾性风险品议案', scenario: 'scenarios/19_betel_nut_drug_classification.md' },
      { index: 20, slug: '20_online_social_relationships', title: '线上社交是否毁灭现实人际关系议案', scenario: 'scenarios/20_online_social_relationships.md' }
    ];
    function modelKey(model) {
      const m = String(model || '').toLowerCase();
      if (m.includes('v4-pro')) return 'deepseek-v4-pro';
      if (m.includes('v4-flash')) return 'deepseek-v4-flash';
      if (m.includes('reasoner')) return 'deepseek-reasoner';
      if (m.includes('chat')) return 'deepseek-chat';
      return 'deepseek-v4-pro';
    }
    function costFor(row) {
      const usage = row.usage || {};
      const pricing = PRICE_USD_PER_M[modelKey(row.request && row.request.model)];
      const prompt = Number(usage.prompt_tokens || 0);
      let hit = Number(usage.prompt_cache_hit_tokens || 0);
      let miss = Number(usage.prompt_cache_miss_tokens || 0);
      const hasCacheSplit = hit > 0 || miss > 0;
      if (!hasCacheSplit) miss = prompt;
      const out = Number(usage.completion_tokens || 0);
      return {
        usd: (hit * pricing.hit + miss * pricing.miss + out * pricing.out) / 1000000,
        cacheKnown: hasCacheSplit,
        hit,
        miss,
        out
      };
    }
    async function fetchText(path) {
      const res = await fetch(path + '?ts=' + Date.now());
      if (!res.ok) return '';
      return await res.text();
    }
    async function fetchJsonMaybe(path) {
      try {
        const res = await fetch(path + '?ts=' + Date.now());
        if (!res.ok) return null;
        return await res.json();
      } catch (_) {
        return null;
      }
    }
    function parseJsonl(text) {
      return text.split('\\n').map(line => line.trim()).filter(Boolean).map(line => {
        try { return JSON.parse(line); } catch (_) { return null; }
      }).filter(Boolean);
    }
    function truncatePreview(text, limit = 9000) {
      if (!text) return '';
      if (text.length <= limit) return text;
      const head = text.slice(0, Math.floor(limit * 0.62)).trimEnd();
      const tail = text.slice(-Math.floor(limit * 0.28)).trimStart();
      return `${head}\\n\\n...[中间预览省略 ${fmt(text.length - head.length - tail.length)} 字符；完整内容见原文件]...\\n\\n${tail}`;
    }
    function renderJsonlPreview(text) {
      const rows = parseJsonl(text);
      if (!rows.length) return text;
      return rows.map((row, index) => {
        const who = [row.slot, row.role_name].filter(Boolean).join(' ');
        const title = row.call_type || who || `record ${index + 1}`;
        const content = row.content || row.content_preview || JSON.stringify(row, null, 2);
        return `## ${title}\\n${content}`;
      }).join('\\n\\n');
    }
    async function fetchPreview(path) {
      const text = await fetchText(path);
      if (!text) return '';
      if (path.endsWith('.jsonl')) return renderJsonlPreview(text);
      if (path.endsWith('.json')) {
        try { return JSON.stringify(JSON.parse(text), null, 2); } catch (_) { return text; }
      }
      return text;
    }
    function latestModelPreview(rows) {
      const latest = rows.slice(-8).reverse();
      if (!latest.length) return '暂无模型输出预览。';
      return latest.map(row => {
        const usage = row.usage || {};
        return `## ${row.call_type || 'unknown'} · ${row.client_key || ''}\\nmodel: ${(row.request && row.request.model) || 'unknown'} · tokens: ${fmt(usage.total_tokens)}\\n\\n${row.content_preview || ''}`;
      }).join('\\n\\n');
    }
    function previewCandidates(s, rows, phase) {
      const loop = String(s.current_loop || 1).padStart(2, '0');
      const base = `loop_${loop}`;
      const candidates = [
        { label: '最新模型输出', path: '__latest_model_outputs__' },
        { label: 'Compact', path: `${base}/compact.md` },
        { label: 'Planning', path: `${base}/discussion_plan.md` },
        { label: 'Stage Report', path: `${base}/stage_report.md` },
        { label: 'Final', path: 'final/final_summary.md' },
        { label: 'Run Index', path: 'run_index.md' }
      ];
      const lowerPhase = String(phase.desc.name || '').toLowerCase();
      if (!selectedPreviewPath) {
        if (lowerPhase.includes('planning')) selectedPreviewPath = `${base}/discussion_plan.md`;
        else if (lowerPhase.includes('stage')) selectedPreviewPath = `${base}/stage_report.md`;
        else if (lowerPhase.includes('final')) selectedPreviewPath = 'final/final_summary.md';
        else if (lowerPhase.includes('compact')) selectedPreviewPath = `${base}/compact.md`;
        else selectedPreviewPath = '__latest_model_outputs__';
      }
      return candidates;
    }
    async function updatePreview(s, rows, phase) {
      const candidates = previewCandidates(s, rows, phase);
      if (!candidates.some(item => item.path === selectedPreviewPath)) {
        selectedPreviewPath = candidates[0].path;
      }
      document.getElementById('previewTabs').innerHTML = candidates.map(item => (
        `<button class="preview-button ${item.path === selectedPreviewPath ? 'active' : ''}" data-preview-path="${item.path}">${item.label}</button>`
      )).join('');
      for (const button of Array.from(document.querySelectorAll('[data-preview-path]'))) {
        button.onclick = async () => {
          selectedPreviewPath = button.getAttribute('data-preview-path') || '';
          await updatePreview(s, rows, phase);
        };
      }
      let content = '';
      if (selectedPreviewPath === '__latest_model_outputs__') {
        content = latestModelPreview(rows);
      } else {
        content = await fetchPreview(selectedPreviewPath);
      }
      document.getElementById('previewMeta').textContent = selectedPreviewPath === '__latest_model_outputs__'
        ? '最近 8 次模型输出预览，来自 transcript.jsonl 的 content_preview'
        : `文件：${selectedPreviewPath}`;
      document.getElementById('previewBox').textContent = truncatePreview(content || '当前文件还没有生成。');
    }
    function summarizeTranscript(rows) {
      const totals = { prompt: 0, completion: 0, reasoning: 0, visible: 0, total: 0, cacheHit: 0, cacheMiss: 0, cost: 0, cacheKnownRows: 0 };
      const byType = {};
      const models = new Set();
      for (const row of rows) {
        const type = row.call_type || 'unknown';
        const usage = row.usage || {};
        const model = (row.request && row.request.model) || 'unknown';
        models.add(model);
        if (!byType[type]) byType[type] = { count: 0, prompt: 0, completion: 0, reasoning: 0, total: 0, cost: 0 };
        byType[type].count += 1;
        byType[type].prompt += Number(usage.prompt_tokens || 0);
        byType[type].completion += Number(usage.completion_tokens || 0);
        byType[type].reasoning += Number(usage.reasoning_tokens || 0);
        byType[type].total += Number(usage.total_tokens || 0);
        const c = costFor(row);
        byType[type].cost += c.usd;
        totals.prompt += Number(usage.prompt_tokens || 0);
        totals.completion += Number(usage.completion_tokens || 0);
        totals.reasoning += Number(usage.reasoning_tokens || 0);
        totals.visible += Number(usage.visible_answer_tokens_estimate || 0);
        totals.total += Number(usage.total_tokens || 0);
        totals.cacheHit += c.hit;
        totals.cacheMiss += c.miss;
        totals.cost += c.usd;
        if (c.cacheKnown) totals.cacheKnownRows += 1;
      }
      return { totals, byType, models: Array.from(models) };
    }
    function normalizeBatchCases(batch) {
      const raw = batch && (batch.cases || batch.runs || batch.items || batch.results || batch.scenarios);
      if (!raw) return [];
      const list = Array.isArray(raw) ? raw : Object.entries(raw).map(([key, value]) => ({ key, ...(value || {}) }));
      return list.map((item, index) => ({
        index: Number(item.index || item.case_index || item.order || index + 1),
        slug: String(item.slug || item.id || item.key || item.name || `case_${index + 1}`),
        title: String(item.title || item.scenario_title || item.name || item.slug || `Case ${index + 1}`),
        scenario: item.scenario || item.scenario_path || '',
        status: item.status || item.state || '',
        monitor_url: item.monitor_url || item.monitor || '',
        run_dir: item.run_dir || item.output_dir || item.dir || '',
        status_path: item.status_path || '',
        error_count: item.error_count,
        call_count: item.call_count,
        total_tokens: item.total_tokens,
        current_loop: item.current_loop,
        total_loops: item.total_loops
      })).sort((a, b) => a.index - b.index);
    }
    function stripToRelativeRunPath(path) {
      const value = String(path || '').replaceAll(String.fromCharCode(92), '/');
      const marker = '/runs/nightly-all-tests/';
      const markerIndex = value.indexOf(marker);
      if (markerIndex >= 0) return value.slice(markerIndex + marker.length).replace(/^\\/+/, '');
      return value.replace(/^\\.\\//, '').replace(/^\\/+/, '');
    }
    function caseStatusCandidates(item) {
      const candidates = [];
      if (item.status_path) candidates.push(stripToRelativeRunPath(item.status_path));
      if (item.run_dir) candidates.push(stripToRelativeRunPath(item.run_dir).replace(/\\/$/, '') + '/status.json');
      return Array.from(new Set(candidates.filter(Boolean)));
    }
    function caseMonitorHref(item) {
      if (item.monitor_url) return item.monitor_url;
      if (item.run_dir) return stripToRelativeRunPath(item.run_dir).replace(/\\/$/, '') + '/monitor.html';
      if (item.slug) return `${item.slug}/monitor.html`;
      return '';
    }
    function statusBucket(status) {
      const value = String(status || '').toLowerCase();
      if (value === 'done' || value === 'completed' || value === 'passed') return 'done';
      if (value === 'running' || value === 'starting') return 'running';
      if (value === 'error' || value === 'failed' || value === 'stalled') return 'error';
      return 'pending';
    }
    async function enrichBatchCase(item, rootStatus) {
      let child = null;
      if (rootStatus && rootStatus.scenario_title && item.title === rootStatus.scenario_title) {
        child = rootStatus;
      }
      if (!child) {
        for (const candidate of caseStatusCandidates(item)) {
          child = await fetchJsonMaybe(candidate);
          if (child) break;
        }
      }
      const merged = { ...item, ...(child || {}) };
      const status = merged.status || (child ? 'running' : item.status) || 'pending';
      return {
        ...item,
        child,
        status,
        bucket: statusBucket(status),
        title: merged.scenario_title || item.title,
        current_loop: Number(merged.current_loop || item.current_loop || 0),
        total_loops: Number(merged.total_loops || item.total_loops || 5),
        call_count: Number(merged.call_count || item.call_count || 0),
        total_tokens: Number(merged.total_tokens || item.total_tokens || 0),
        error_count: Number(merged.error_count || item.error_count || 0),
        current_step: merged.current_step || item.current_step || '',
        monitor_href: caseMonitorHref(item)
      };
    }
    async function updateBatchSection(rootStatus) {
      const batch = await fetchJsonMaybe('batch_status.json');
      const isBatchPath = /nightly-all-tests|all-tests|batch/i.test(location.pathname);
      let cases = normalizeBatchCases(batch);
      if (!cases.length && isBatchPath) cases = DEFAULT_BATCH_CASES;
      const section = document.getElementById('batchSection');
      if (!cases.length) {
        section.hidden = true;
        return { visible: false, isBatchPath, hasBatchData: false };
      }
      const rootCaseStatus = batch ? null : rootStatus;
      const enriched = await Promise.all(cases.map(item => enrichBatchCase(item, rootCaseStatus)));
      const counts = enriched.reduce((acc, item) => {
        acc[item.bucket] = (acc[item.bucket] || 0) + 1;
        acc.total += 1;
        acc.calls += Number(item.call_count || 0);
        acc.tokens += Number(item.total_tokens || 0);
        acc.errors += Number(item.error_count || 0);
        return acc;
      }, { total: 0, done: 0, running: 0, error: 0, pending: 0, calls: 0, tokens: 0, errors: 0 });
      section.hidden = false;
      document.getElementById('batchSummary').innerHTML = [
        `<span class="pill">流程总数: ${counts.total}</span>`,
        `<span class="pill">完成: ${counts.done || 0}</span>`,
        `<span class="pill">运行中: ${counts.running || 0}</span>`,
        `<span class="pill">等待/未知: ${counts.pending || 0}</span>`,
        `<span class="pill">错误: ${counts.error || 0}</span>`,
        `<span class="pill">Tokens: ${fmt(counts.tokens)}</span>`
      ].join('');
      document.getElementById('batchGrid').innerHTML = enriched.map(item => {
        const href = item.monitor_href ? `<a class="case-link" href="${item.monitor_href}">打开单流程 monitor</a>` : '';
        return `<article class="case-card ${item.bucket}">
          <div class="case-head">
            <div>
              <div class="case-index">CASE ${String(item.index).padStart(2, '0')}</div>
              <div class="case-title">${item.title}</div>
            </div>
            <div class="case-status">${item.status}</div>
          </div>
          <div class="case-meta">
            <div>Loop<br><strong>${fmt(item.current_loop)}/${fmt(item.total_loops)}</strong></div>
            <div>Calls<br><strong>${fmt(item.call_count)}</strong></div>
            <div>Tokens<br><strong>${fmt(item.total_tokens)}</strong></div>
          </div>
          <div class="small">${item.current_step || item.scenario || '等待状态文件'}</div>
          ${href}
        </article>`;
      }).join('');
      return {
        visible: true,
        isBatchPath,
        hasBatchData: Boolean(batch),
        total: counts.total,
        done: counts.done || 0,
        running: counts.running || 0,
        error: counts.error || 0,
        pending: counts.pending || 0,
        callCount: counts.calls,
        totalTokens: counts.tokens,
        errorCount: counts.errors,
        status: (batch && batch.status) || (counts.error ? 'error' : counts.running ? 'running' : counts.done === counts.total ? 'done' : 'starting'),
        updatedAt: (batch && batch.updated_at) || ''
      };
    }
    function activePhase(events, currentStep) {
      const list = events || [];
      const lastNonCall = [...list].reverse().find(e => !/\\bcall finished:/.test(e)) || '';
      const base = currentStep && !currentStep.startsWith('call finished:') ? currentStep : lastNonCall.replace(/^\\d\\d:\\d\\d:\\d\\d\\s+/, '');
      const desc = describePhase(base || currentStep || '');
      const callReturnsAfterPhase = list.slice(Math.max(0, list.lastIndexOf(lastNonCall))).filter(e => /\\bcall finished:/.test(e)).length;
      return { base, desc, callReturnsAfterPhase };
    }
    function describePhase(step) {
      const s = String(step || '');
      let m;
      if ((m = s.match(/loop (\\d+): compact/))) {
        return { name: 'Compact', detail: `第 ${m[1]} 回合：生成开放讨论状态账本，继承历史事实、硬约束、概念争点和未决分歧。` };
      }
      if ((m = s.match(/archive compact summary 1-(\\d+)/))) {
        return { name: 'Archive', detail: `归档第 1-${m[1]} 回合较早 compact，压缩成长期开放讨论账本。` };
      }
      if ((m = s.match(/loop (\\d+): discussion planning/))) {
        return { name: 'Planning', detail: `第 ${m[1]} 回合：规划子讨论组和 A/B/C/D 角色人格。` };
      }
      if ((m = s.match(/loop (\\d+): subcycle (\\d+)\\s*(.*)/))) {
        return { name: 'Role Round', detail: `第 ${m[1]} 回合 · 第 ${m[2]} 个子讨论组：${m[3] || '角色并行讨论'}。四个角色并行返回，页面会在每个调用完成后更新。` };
      }
      if ((m = s.match(/loop (\\d+): stage report/))) {
        return { name: 'Stage Report', detail: `第 ${m[1]} 回合：汇总本回合共识、分歧、条款修订、外部审批事项和下一轮重点。` };
      }
      if (/final summary/.test(s)) {
        return { name: 'Final Summary', detail: '标准最终总结：汇总全部阶段报告并生成最终议案概览。' };
      }
      if (/repair planning JSON/.test(s)) {
        return { name: 'Repair', detail: '修复规划 JSON：模型输出无法直接解析，正在走修复链路。' };
      }
      if (/completed|done/.test(s)) {
        return { name: 'Completed', detail: '运行已经完成。下方预览、调用分布、token 和费用估算均来自最终落盘产物。' };
      }
      if (/call finished:/.test(s)) {
        return { name: 'Call Returned', detail: `刚完成模型调用：${s.replace('call finished:', '').trim()}。实际进行中的阶段以上一个非调用事件为准。` };
      }
      return { name: 'Running', detail: s || '-' };
    }
    function statusClass(status) {
      if (status === 'done') return 'value ok';
      if (status === 'error' || status === 'offline') return 'value danger';
      return 'value warn';
    }
    function showLoadError(err) {
      document.getElementById('scenario').textContent = 'Monitor data unavailable';
      document.getElementById('updated').textContent = '等待 status.json';
      document.getElementById('status').textContent = 'offline';
      document.getElementById('status').className = 'value danger';
      document.getElementById('loop').textContent = '0/0';
      document.getElementById('phaseName').textContent = 'No Status';
      document.getElementById('phaseSub').textContent = 'status.json not readable';
      document.getElementById('calls').textContent = '0';
      document.getElementById('callSub').textContent = '没有可读取的 transcript.jsonl';
      document.getElementById('tokens').textContent = '0';
      document.getElementById('tokenSub').textContent = 'Prompt 0 · Output 0';
      document.getElementById('cost').textContent = money(0);
      document.getElementById('costSub').textContent = '等待真实用量';
      document.getElementById('errors').textContent = '-';
      document.getElementById('progressBar').style.width = '0%';
      document.getElementById('phaseDescription').textContent = '当前目录下没有可读取的 status.json。请确认运行是否已经启动，或者确认浏览器 URL 指向正确的 run 目录。';
      document.getElementById('phaseDetail').innerHTML = `<span class="pill">${String(err && err.message || err || 'fetch failed')}</span>`;
      document.getElementById('tokenBreakdown').innerHTML = '<span class="pill">No data</span>';
      document.getElementById('events').textContent = '等待运行写入事件。';
      document.getElementById('previewTabs').innerHTML = '';
      document.getElementById('previewMeta').textContent = '没有可预览的产物';
      document.getElementById('previewBox').textContent = 'monitor.html 已加载，但 status.json / transcript.jsonl 尚不可用。';
      document.getElementById('bytype').innerHTML = '<tr><td colspan="7">暂无调用记录</td></tr>';
      document.getElementById('pricingNote').textContent = '页面正常加载；等待运行产物后会自动刷新。';
    }
    async function refresh() {
      try {
        const res = await fetch('status.json?ts=' + Date.now());
        let s = res.ok ? await res.json() : null;
        const batchInfo = await updateBatchSection(s);
        if (!s && !batchInfo.visible) throw new Error(`status.json HTTP ${res.status}`);
        if (!s) {
          s = {
            scenario_title: `Nightly All Tests · ${batchInfo.total} 个流程`,
            total_loops: batchInfo.total,
            current_loop: batchInfo.done,
            status: batchInfo.status,
            current_step: 'batch monitor',
            updated_at: '',
            events: [],
            call_count: batchInfo.callCount,
            total_tokens: batchInfo.totalTokens,
            error_count: batchInfo.errorCount,
            by_type: {}
          };
        }
        const transcriptRows = parseJsonl(await fetchText('transcript.jsonl'));
        const ts = summarizeTranscript(transcriptRows);
        const phase = activePhase(s.events || [], s.current_step || '');
        const tokenTotal = ts.totals.total || s.total_tokens || 0;
        const pct = (s.total_loops || 0) ? Math.max(0, Math.min(100, ((s.current_loop || 0) - (s.status === 'done' ? 0 : 0.35)) / (s.total_loops || 1) * 100)) : 0;
        document.getElementById('scenario').textContent = s.scenario_title || '';
        document.getElementById('updated').textContent = '更新：' + (s.updated_at || '');
        document.getElementById('status').textContent = s.status || '-';
        document.getElementById('status').className = statusClass(s.status);
        document.getElementById('loop').textContent = `${s.current_loop || 0}/${s.total_loops || 0}`;
        document.getElementById('phaseName').textContent = phase.desc.name;
        document.getElementById('phaseSub').textContent = phase.base || s.current_step || '-';
        document.getElementById('loop').parentElement.querySelector('.label').textContent = '循环';
        document.getElementById('calls').textContent = transcriptRows.length || s.call_count || 0;
        document.getElementById('callSub').textContent = `本阶段已返回 ${phase.callReturnsAfterPhase || 0} 个调用`;
        document.getElementById('tokens').textContent = fmt(tokenTotal);
        document.getElementById('tokenSub').textContent = `Prompt ${fmt(ts.totals.prompt)} · Output ${fmt(ts.totals.completion)}`;
        document.getElementById('cost').textContent = money(ts.totals.cost);
        document.getElementById('costSub').textContent = ts.totals.cacheKnownRows ? `含 ${ts.totals.cacheKnownRows} 条缓存拆分记录` : '缓存命中未知，按 input cache miss 保守估算';
        document.getElementById('errors').textContent = s.error_count || 0;
        document.getElementById('progressBar').style.width = `${pct}%`;
        if (batchInfo.visible && batchInfo.isBatchPath) {
          const batchPct = batchInfo.total ? Math.round((batchInfo.done / batchInfo.total) * 100) : 0;
          document.getElementById('scenario').textContent = `Nightly All Tests · ${batchInfo.total} 个流程`;
          document.getElementById('updated').textContent = '更新：' + (batchInfo.updatedAt || '');
          document.getElementById('status').textContent = batchInfo.status;
          document.getElementById('status').className = statusClass(batchInfo.status);
          document.getElementById('loop').parentElement.querySelector('.label').textContent = '流程';
          document.getElementById('loop').textContent = `${batchInfo.done}/${batchInfo.total}`;
          document.getElementById('phaseName').textContent = 'Batch Monitor';
          document.getElementById('phaseSub').textContent = `${batchInfo.running} running · ${batchInfo.pending} pending`;
          document.getElementById('calls').textContent = fmt(batchInfo.callCount || 0);
          document.getElementById('callSub').textContent = `${batchInfo.total} 个流程的聚合调用数`;
          document.getElementById('tokens').textContent = fmt(batchInfo.totalTokens || 0);
          document.getElementById('tokenSub').textContent = `${batchInfo.total} 个流程的聚合 token`;
          document.getElementById('cost').textContent = batchInfo.totalTokens ? '见单流程' : money(0);
          document.getElementById('costSub').textContent = '总控页只聚合 token；精确费用和缓存命中在单流程 monitor 查看。';
          document.getElementById('errors').textContent = batchInfo.errorCount || s.error_count || 0;
          document.getElementById('progressBar').style.width = `${batchPct}%`;
        }
        document.getElementById('phaseDescription').textContent = phase.desc.detail;
        document.getElementById('phaseDetail').innerHTML = [
          `<span class="pill">原始步骤：${s.current_step || '-'}</span>`,
          `<span class="pill">活跃阶段：${phase.base || '-'}</span>`,
          `<span class="pill">状态文件调用：${fmt(s.call_count || 0)}</span>`
        ].join('');
        if (batchInfo.visible && batchInfo.isBatchPath) {
          document.getElementById('phaseDescription').textContent = `总控页正在聚合 ${batchInfo.total} 个测试流程。每个流程会优先读取 batch_status.json 中的状态，也可以读取子目录 status.json；单流程详情继续在各自 monitor 页面查看。`;
          document.getElementById('phaseDetail').innerHTML = [
            `<span class="pill">完成：${batchInfo.done}/${batchInfo.total}</span>`,
            `<span class="pill">运行中：${batchInfo.running}</span>`,
            `<span class="pill">等待/未知：${batchInfo.pending}</span>`,
            `<span class="pill">错误：${batchInfo.error}</span>`
          ].join('');
          document.getElementById('tokenBreakdown').innerHTML = [
            `<span class="pill">聚合调用：${fmt(batchInfo.callCount || 0)}</span>`,
            `<span class="pill">聚合 token：${fmt(batchInfo.totalTokens || 0)}</span>`,
            `<span class="pill">聚合错误：${fmt(batchInfo.errorCount || 0)}</span>`,
            `<span class="pill">批次完成：${batchInfo.done}/${batchInfo.total}</span>`
          ].join('');
          document.getElementById('events').textContent = `批量运行中：${batchInfo.running} running · ${batchInfo.pending} pending · ${batchInfo.done} done`;
          document.getElementById('previewTabs').innerHTML = '';
          document.getElementById('previewMeta').textContent = '批量总控';
          document.getElementById('previewBox').textContent = `当前页面聚合 ${batchInfo.total} 个流程。点击每个 CASE 卡片的单流程 monitor 查看该 case 的阶段、token、费用估算和产物预览。`;
          document.getElementById('bytype').innerHTML = '<tr><td colspan="7">批量页不混用根目录旧 transcript；调用类型拆分请打开单流程 monitor 查看。</td></tr>';
          document.getElementById('pricingNote').textContent = '批量页只展示跨流程进度和 token 聚合，精确模型/缓存费用以单流程 monitor 和 DeepSeek 账单为准。';
          return;
        }
        document.getElementById('tokenBreakdown').innerHTML = [
          `<span class="pill">Prompt: ${fmt(ts.totals.prompt)}</span>`,
          `<span class="pill">Output: ${fmt(ts.totals.completion)}</span>`,
          `<span class="pill">Reasoning: ${fmt(ts.totals.reasoning)}</span>`,
          `<span class="pill">Visible Output: ${fmt(ts.totals.visible)}</span>`,
          `<span class="pill">Cache Hit: ${fmt(ts.totals.cacheHit)}</span>`,
          `<span class="pill">Cache Miss/估算: ${fmt(ts.totals.cacheMiss)}</span>`
        ].join('');
        document.getElementById('events').textContent = (s.events || []).slice(-12).join('\\n');
        await updatePreview(s, transcriptRows, phase);
        const byType = Object.entries(ts.byType).length ? ts.byType : Object.fromEntries(Object.entries(s.by_type || {}).map(([k,v]) => [k, { count: v, prompt: 0, completion: 0, reasoning: 0, total: 0, cost: 0 }]));
        document.getElementById('bytype').innerHTML = Object.entries(byType).length
          ? Object.entries(byType).map(([k,v]) => `<tr><td>${k}</td><td>${fmt(v.count)}</td><td>${fmt(v.prompt)}</td><td>${fmt(v.completion)}</td><td>${fmt(v.reasoning)}</td><td>${fmt(v.total)}</td><td>${money(v.cost)}</td></tr>`).join('')
          : '<tr><td colspan="7">暂无调用记录</td></tr>';
        document.getElementById('pricingNote').textContent = `模型：${ts.models.join(', ') || 'unknown'}。价格表：deepseek-v4-pro input hit $0.145/M、input miss $1.74/M、output $3.48/M；deepseek-v4-flash/chat/reasoner input hit $0.028/M、input miss $0.14/M、output $0.28/M。当前费用为前端估算，实际扣费以 DeepSeek 账单和缓存命中返回为准。`;
      } catch (err) {
        showLoadError(err);
      }
    }
    refresh();
    setInterval(refresh, 2500);
  </script>
</body>
</html>
"""


class RunMonitor:
    def __init__(self, run_dir: Path, *, scenario_title: str, total_loops: int) -> None:
        self.run_dir = run_dir
        self.state: dict[str, Any] = {
            "scenario_title": scenario_title,
            "total_loops": total_loops,
            "current_loop": 0,
            "status": "starting",
            "current_step": "initializing",
            "events": [],
            "call_count": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "visible_answer_tokens_estimate": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
            "error_count": 0,
            "by_type": {},
        }
        write_text(run_dir / "monitor.html", MONITOR_HTML)
        self.update("starting", "monitor ready")

    def update(self, status: str, step: str, **extra: Any) -> None:
        events = list(self.state.get("events") or [])
        events.append(f"{datetime.now().strftime('%H:%M:%S')} {step}")
        self.state.update(extra)
        self.state["status"] = status
        self.state["current_step"] = step
        self.state["events"] = events[-80:]
        self.state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        write_json(self.run_dir / "status.json", self.state)

    def record_call(self, call_type: str, usage_or_total_tokens: int | dict[str, Any]) -> None:
        if isinstance(usage_or_total_tokens, dict):
            usage = usage_or_total_tokens
            total_tokens = int(usage.get("total_tokens") or 0)
        else:
            usage = {"total_tokens": int(usage_or_total_tokens or 0)}
            total_tokens = int(usage_or_total_tokens or 0)
        by_type = dict(self.state.get("by_type") or {})
        by_type[call_type] = by_type.get(call_type, 0) + 1
        self.update(
            "running",
            f"call finished: {call_type}",
            call_count=int(self.state.get("call_count") or 0) + 1,
            total_tokens=int(self.state.get("total_tokens") or 0) + int(total_tokens or 0),
            prompt_tokens=int(self.state.get("prompt_tokens") or 0) + int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(self.state.get("completion_tokens") or 0) + int(usage.get("completion_tokens") or 0),
            reasoning_tokens=int(self.state.get("reasoning_tokens") or 0) + int(usage.get("reasoning_tokens") or 0),
            visible_answer_tokens_estimate=int(self.state.get("visible_answer_tokens_estimate") or 0)
            + int(usage.get("visible_answer_tokens_estimate") or 0),
            prompt_cache_hit_tokens=int(self.state.get("prompt_cache_hit_tokens") or 0)
            + int(usage.get("prompt_cache_hit_tokens") or 0),
            prompt_cache_miss_tokens=int(self.state.get("prompt_cache_miss_tokens") or 0)
            + int(usage.get("prompt_cache_miss_tokens") or 0),
            by_type=by_type,
        )

    def record_error(self, step: str) -> None:
        self.update(
            "error",
            step,
            error_count=int(self.state.get("error_count") or 0) + 1,
        )


class NullMonitor:
    def update(self, status: str, step: str, **extra: Any) -> None:
        return

    def record_call(self, call_type: str, usage_or_total_tokens: int | dict[str, Any]) -> None:
        return

    def record_error(self, step: str) -> None:
        return
