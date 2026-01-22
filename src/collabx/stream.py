from __future__ import annotations

import json
import time
from typing import Optional

import httpx
from rich.console import Console
from rich.table import Table

console = Console()


def _render_event(e: dict) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_row("[bold]id[/bold]", str(e.get("id", "")))
    table.add_row("[bold]time[/bold]", str(e.get("received_at", "")))
    table.add_row("[bold]method[/bold]", str(e.get("method", "")))
    table.add_row("[bold]path[/bold]", str(e.get("path", "")))
    q = e.get("query", "")
    if q:
        table.add_row("[bold]query[/bold]", str(q))
    table.add_row("[bold]client_ip[/bold]", str(e.get("client_ip", "")))
    ua = e.get("user_agent", "")
    if ua:
        table.add_row("[bold]ua[/bold]", str(ua)[:200])
    origin = e.get("origin", "")
    if origin:
        table.add_row("[bold]origin[/bold]", str(origin)[:200])
    referer = e.get("referer", "")
    if referer:
        table.add_row("[bold]referer[/bold]", str(referer)[:200])
    if e.get("body_truncated"):
        table.add_row("[bold]body[/bold]", "[yellow]truncated[/yellow]")
    console.print(table)
    console.print("-" * 60)


def poll_logs(
    *,
    logs_url: str,
    interval_s: float = 5.0,
    start_after_id: int = 0,
    limit: int = 50,
    json_mode: bool = False,
    timeout_s: float = 10.0,
) -> None:
    after_id = max(0, int(start_after_id))
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        while True:
            try:
                r = client.get(logs_url, params={"after_id": after_id, "limit": limit})
                r.raise_for_status()
                payload = r.json()
                events = payload.get("events", []) or []
                next_after_id = int(payload.get("next_after_id", after_id))

                for e in events:
                    if json_mode:
                        console.print_json(data=e)
                    else:
                        _render_event(e)
                after_id = max(after_id, next_after_id)
            except KeyboardInterrupt:
                raise
            except Exception as ex:
                console.print(f"[red]poll error[/red]: {ex}")
            time.sleep(max(0.2, interval_s))


def stream_sse(*, events_url: str, json_mode: bool = False) -> None:
    console.print(f"Streaming {events_url} (Ctrl+C to stop)")
    with httpx.Client(timeout=None, follow_redirects=True) as client:
        with client.stream("GET", events_url, headers={"Accept": "text/event-stream"}) as r:
            r.raise_for_status()
            buf = []
            for line in r.iter_lines():
                if line is None:
                    continue
                if line == "":
                    data_lines = [l for l in buf if l.startswith("data:")]
                    buf = []
                    if not data_lines:
                        continue
                    data = "\n".join([l[5:].lstrip() for l in data_lines])
                    try:
                        evt = json.loads(data)
                    except Exception:
                        continue
                    if json_mode:
                        console.print_json(data=evt)
                    else:
                        _render_event(evt)
                    continue
                if line.startswith(":"):
                    continue
                buf.append(line)
