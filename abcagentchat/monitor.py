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
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f6f7f8; color: #111; }
    main { max-width: 1280px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; border-bottom: 2px solid #111; padding-bottom: 14px; }
    h1 { margin: 0; font-size: 24px; letter-spacing: 0; }
    .muted { color: #666; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
    .tile, section { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }
    .label { color: #666; font-size: 12px; }
    .value { margin-top: 6px; font-size: 22px; font-weight: 700; }
    .small { margin-top: 5px; color: #666; font-size: 12px; line-height: 1.35; }
    section { margin-top: 12px; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }
    th { color: #444; background: #fafafa; }
    .event { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; line-height: 1.45; }
    .phase { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 12px; }
    .progress { height: 10px; overflow: hidden; background: #e5e7eb; border-radius: 999px; margin-top: 10px; }
    .progress > div { height: 100%; background: #111; width: 0%; transition: width .25s ease; }
    .pill { display: inline-block; padding: 2px 8px; border: 1px solid #ddd; border-radius: 999px; background: #fafafa; margin: 0 6px 6px 0; font-size: 12px; }
    .ok { color: #007a3d; }
    .warn { color: #a65300; }
    .danger { color: #b00020; }
    @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .phase { grid-template-columns: 1fr; } header { display: block; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>ABC Agent Chat Monitor</h1>
        <div class="muted" id="scenario">loading</div>
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
