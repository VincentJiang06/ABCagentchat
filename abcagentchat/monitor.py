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
    :root { color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #05070a; color: #e8eef8; }
    main { max-width: 1360px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; border-bottom: 4px solid #f8fafc; padding-bottom: 18px; }
    h1 { margin: 0; font-size: 42px; line-height: 1; letter-spacing: 0; }
    .scenario-title { margin-top: 10px; font-size: 22px; font-weight: 700; color: #f8fafc; }
    .muted { color: #94a3b8; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
    .tile, section { background: #0f131a; border: 1px solid #293241; border-radius: 8px; padding: 14px; box-shadow: 0 0 0 1px rgba(255,255,255,.02) inset; }
    .label { color: #94a3b8; font-size: 12px; }
    .value { margin-top: 6px; font-size: 22px; font-weight: 700; }
    .small { margin-top: 5px; color: #94a3b8; font-size: 12px; line-height: 1.35; }
    section { margin-top: 12px; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #293241; vertical-align: top; }
    th { color: #cbd5e1; background: #151b24; }
    .event { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; line-height: 1.45; }
    .phase { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 12px; }
    .progress { height: 10px; overflow: hidden; background: #1f2937; border-radius: 999px; margin-top: 10px; }
    .progress > div { height: 100%; background: #38bdf8; width: 0%; transition: width .25s ease; }
    .pill { display: inline-block; padding: 2px 8px; border: 1px solid #334155; border-radius: 999px; background: #111827; color: #dbeafe; margin: 0 6px 6px 0; font-size: 12px; }
    .preview-toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .preview-button { border: 1px solid #334155; background: #111827; color: #e8eef8; border-radius: 6px; padding: 8px 10px; font: inherit; font-size: 13px; cursor: pointer; }
    .preview-button.active { background: #38bdf8; border-color: #38bdf8; color: #020617; font-weight: 700; }
    .preview-meta { margin-bottom: 8px; color: #94a3b8; font-size: 12px; }
    .preview-box { margin: 0; max-height: 520px; overflow: auto; white-space: pre-wrap; border: 1px solid #293241; background: #070b11; color: #dbeafe; border-radius: 8px; padding: 12px; font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .ok { color: #34d399; }
    .warn { color: #fbbf24; }
    .danger { color: #fb7185; }
    @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .phase { grid-template-columns: 1fr; } header { display: block; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>ABC Agent Chat Monitor</h1>
        <div class="scenario-title" id="scenario">loading</div>
      </div>
      <div class="muted" id="updated">waiting</div>
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
      if (/call finished:/.test(s)) {
        return { name: 'Call Returned', detail: `刚完成模型调用：${s.replace('call finished:', '').trim()}。实际进行中的阶段以上一个非调用事件为准。` };
      }
      return { name: 'Running', detail: s || '-' };
    }
    async function refresh() {
      try {
        const res = await fetch('status.json?ts=' + Date.now());
        const s = await res.json();
        const transcriptRows = parseJsonl(await fetchText('transcript.jsonl'));
        const ts = summarizeTranscript(transcriptRows);
        const phase = activePhase(s.events || [], s.current_step || '');
        const tokenTotal = ts.totals.total || s.total_tokens || 0;
        const pct = (s.total_loops || 0) ? Math.max(0, Math.min(100, ((s.current_loop || 0) - (s.status === 'done' ? 0 : 0.35)) / (s.total_loops || 1) * 100)) : 0;
        document.getElementById('scenario').textContent = s.scenario_title || '';
        document.getElementById('updated').textContent = '更新：' + (s.updated_at || '');
        document.getElementById('status').textContent = s.status || '-';
        document.getElementById('status').className = s.status === 'done' ? 'value ok' : 'value warn';
        document.getElementById('loop').textContent = `${s.current_loop || 0}/${s.total_loops || 0}`;
        document.getElementById('phaseName').textContent = phase.desc.name;
        document.getElementById('phaseSub').textContent = phase.base || s.current_step || '-';
        document.getElementById('calls').textContent = transcriptRows.length || s.call_count || 0;
        document.getElementById('callSub').textContent = `本阶段已返回 ${phase.callReturnsAfterPhase || 0} 个调用`;
        document.getElementById('tokens').textContent = fmt(tokenTotal);
        document.getElementById('tokenSub').textContent = `Prompt ${fmt(ts.totals.prompt)} · Output ${fmt(ts.totals.completion)}`;
        document.getElementById('cost').textContent = money(ts.totals.cost);
        document.getElementById('costSub').textContent = ts.totals.cacheKnownRows ? `含 ${ts.totals.cacheKnownRows} 条缓存拆分记录` : '缓存命中未知，按 input cache miss 保守估算';
        document.getElementById('errors').textContent = s.error_count || 0;
        document.getElementById('progressBar').style.width = `${pct}%`;
        document.getElementById('phaseDescription').textContent = phase.desc.detail;
        document.getElementById('phaseDetail').innerHTML = [
          `<span class="pill">原始步骤：${s.current_step || '-'}</span>`,
          `<span class="pill">活跃阶段：${phase.base || '-'}</span>`,
          `<span class="pill">状态文件调用：${fmt(s.call_count || 0)}</span>`
        ].join('');
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
        document.getElementById('bytype').innerHTML = Object.entries(byType).map(([k,v]) => `<tr><td>${k}</td><td>${fmt(v.count)}</td><td>${fmt(v.prompt)}</td><td>${fmt(v.completion)}</td><td>${fmt(v.reasoning)}</td><td>${fmt(v.total)}</td><td>${money(v.cost)}</td></tr>`).join('');
        document.getElementById('pricingNote').textContent = `模型：${ts.models.join(', ') || 'unknown'}。价格表：deepseek-v4-pro input hit $0.145/M、input miss $1.74/M、output $3.48/M；deepseek-v4-flash/chat/reasoner input hit $0.028/M、input miss $0.14/M、output $0.28/M。当前费用为前端估算，实际扣费以 DeepSeek 账单和缓存命中返回为准。`;
      } catch (err) {
        document.getElementById('phaseDescription').textContent = 'status.json 暂不可读';
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
