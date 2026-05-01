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
    main { max-width: 1120px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; border-bottom: 2px solid #111; padding-bottom: 14px; }
    h1 { margin: 0; font-size: 24px; letter-spacing: 0; }
    .muted { color: #666; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
    .tile, section { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }
    .label { color: #666; font-size: 12px; }
    .value { margin-top: 6px; font-size: 22px; font-weight: 700; }
    section { margin-top: 12px; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }
    th { color: #444; background: #fafafa; }
    .event { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; line-height: 1.45; }
    .ok { color: #007a3d; }
    .warn { color: #a65300; }
    @media (max-width: 760px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } header { display: block; } }
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
      <div class="tile"><div class="label">调用</div><div class="value" id="calls">-</div></div>
      <div class="tile"><div class="label">Tokens</div><div class="value" id="tokens">-</div></div>
      <div class="tile"><div class="label">错误</div><div class="value" id="errors">-</div></div>
    </div>
    <section>
      <h2>当前步骤</h2>
      <div class="event" id="current">-</div>
    </section>
    <section>
      <h2>最近事件</h2>
      <div class="event" id="events">-</div>
    </section>
    <section>
      <h2>调用分布</h2>
      <table><thead><tr><th>类型</th><th>数量</th></tr></thead><tbody id="bytype"></tbody></table>
    </section>
  </main>
  <script>
    async function refresh() {
      try {
        const res = await fetch('status.json?ts=' + Date.now());
        const s = await res.json();
        document.getElementById('scenario').textContent = s.scenario_title || '';
        document.getElementById('updated').textContent = '更新：' + (s.updated_at || '');
        document.getElementById('status').textContent = s.status || '-';
        document.getElementById('status').className = s.status === 'done' ? 'value ok' : 'value warn';
        document.getElementById('loop').textContent = `${s.current_loop || 0}/${s.total_loops || 0}`;
        document.getElementById('calls').textContent = s.call_count || 0;
        document.getElementById('tokens').textContent = (s.total_tokens || 0).toLocaleString();
        document.getElementById('errors').textContent = s.error_count || 0;
        document.getElementById('current').textContent = s.current_step || '-';
        document.getElementById('events').textContent = (s.events || []).slice(-12).join('\\n');
        document.getElementById('bytype').innerHTML = Object.entries(s.by_type || {}).map(([k,v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');
      } catch (err) {
        document.getElementById('current').textContent = 'status.json 暂不可读';
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

    def record_call(self, call_type: str, total_tokens: int) -> None:
        by_type = dict(self.state.get("by_type") or {})
        by_type[call_type] = by_type.get(call_type, 0) + 1
        self.update(
            "running",
            f"call finished: {call_type}",
            call_count=int(self.state.get("call_count") or 0) + 1,
            total_tokens=int(self.state.get("total_tokens") or 0) + int(total_tokens or 0),
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

    def record_call(self, call_type: str, total_tokens: int) -> None:
        return

    def record_error(self, step: str) -> None:
        return
