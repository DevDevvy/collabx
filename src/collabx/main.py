from __future__ import annotations

import os
import re
import secrets
import json
from typing import Optional

import typer
from rich.console import Console

from collabx.state import TargetState, load_state, save_state, clear_state, DEFAULT_STATE_PATH
from collabx.stream import poll_logs, stream_sse
from collabx.providers.gcp_cloudrun import gcp_up, gcp_down, gcp_status

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _normalize_token(token: str) -> str:
    t = (token or "").strip()
    if not t:
        return ""
    if t.startswith("<") and t.endswith(">") and len(t) > 2:
        console.print("[yellow]Warning:[/yellow] token looked like a placeholder with <...>. Stripping brackets.")
        t = t[1:-1].strip()
    if "<" in t or ">" in t:
        console.print("[yellow]Warning:[/yellow] token contains '<' or '>' characters. Did you paste a placeholder?")
    return t


def _warn_if_non_hex(token: str) -> None:
    if token and not re.fullmatch(r"[0-9a-fA-F]{16,}", token):
        console.print("[yellow]Note:[/yellow] token is not hex. That's OK if intentional, but double-check it.")


@app.command("gen-token")
def gen_token(length: int = typer.Option(32, help="Token length in bytes (encoded as hex).")):
    token = secrets.token_hex(max(16, int(length)))
    console.print(token)


@app.command("init")
def init(
    url: str = typer.Option("http://127.0.0.1:8080", "--url", help="Base URL to save as target."),
    length: int = typer.Option(32, help="Token length in bytes (encoded as hex)."),
):
    token = secrets.token_hex(max(16, int(length)))
    base = url.rstrip("/")
    save_state(TargetState(base_url=base, token=token, provider="local", resources={}))
    console.print("[green]initialized[/green]")
    console.print(f"state:    {DEFAULT_STATE_PATH}")
    console.print(f"base_url: {base}")
    console.print(f"token:    {token}")
    console.print("")
    console.print("[bold]Endpoints:[/bold]")
    console.print(f"collector: {base}/{token}/c")
    console.print(f"logs:      {base}/{token}/logs")
    console.print(f"events:    {base}/{token}/events")


@app.command("env")
def env(
    print_token: bool = typer.Option(False, "--print-token", help="Print only the token (for scripting)."),
):
    st = load_state()
    if not st:
        console.print("[yellow]No target set.[/yellow] Use: collabx up  OR  collabx init/target set")
        raise typer.Exit(code=1)

    if print_token:
        console.print(st.token)
        return

    console.print(f"export COLLABX_URL='{st.base_url}'")
    console.print(f"export TOKEN='{st.token}'")
    console.print(f"# collector: {st.collector_url}")
    console.print(f"# logs:      {st.logs_url}")
    console.print(f"# events:    {st.events_url}")


target_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(target_app, name="target")


@target_app.command("set")
def target_set(
    url: str = typer.Option(..., "--url", help="Base URL, e.g. https://example.com or http://127.0.0.1:8080"),
    token: str = typer.Option(..., "--token", help="Collector token used in URL path"),
):
    base = (url or "").strip().rstrip("/")
    t = _normalize_token(token)

    if not base:
        console.print("[red]url is empty[/red]")
        raise typer.Exit(code=1)

    if not t:
        console.print("[red]token is empty[/red] — paste the token or run: collabx init")
        raise typer.Exit(code=1)

    _warn_if_non_hex(t)

    save_state(TargetState(base_url=base, token=t, provider="manual", resources={}))
    console.print("[green]saved[/green]")
    console.print(f"collector: {base}/{t}/c")
    console.print(f"logs:      {base}/{t}/logs")
    console.print(f"events:    {base}/{t}/events")


@target_app.command("show")
def target_show():
    st = load_state()
    if not st:
        console.print("[yellow]No target set.[/yellow] Use: collabx up  OR  collabx init/target set")
        raise typer.Exit(code=1)
    console.print(f"provider:  {st.provider}")
    console.print(f"base_url:  {st.base_url}")
    console.print(f"token:     {st.token}")
    console.print(f"collector: {st.collector_url}")
    console.print(f"logs:      {st.logs_url}")
    console.print(f"events:    {st.events_url}")


@app.command("listen")
def listen(
    mode: str = typer.Option("poll", help="Log mode: poll (default) or stream (SSE, opt-in)."),
    interval: float = typer.Option(5.0, help="Polling interval seconds (poll mode)."),
    limit: int = typer.Option(50, help="Max events per poll (1-200)."),
    after_id: int = typer.Option(0, help="Start cursor (event id)."),
    json_mode: bool = typer.Option(False, "--json", help="Print each event as raw JSON."),
):
    st = load_state()
    if not st:
        console.print("[yellow]No target set.[/yellow] Use: collabx up  OR  collabx init/target set")
        raise typer.Exit(code=1)

    if mode == "poll":
        console.print(f"Polling {st.logs_url} every {interval}s (Ctrl+C to stop)")
        try:
            poll_logs(
                logs_url=st.logs_url,
                interval_s=interval,
                start_after_id=after_id,
                limit=limit,
                json_mode=json_mode,
            )
        except KeyboardInterrupt:
            console.print("\n[cyan]stopped[/cyan]")
        return

    if mode == "stream":
        try:
            stream_sse(events_url=st.events_url, json_mode=json_mode)
        except KeyboardInterrupt:
            console.print("\n[cyan]stopped[/cyan]")
        return

    console.print("[red]mode must be 'poll' or 'stream'[/red]")
    raise typer.Exit(code=2)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8080, help="Bind port"),
    token: str = typer.Option(..., help="Required token. Used in URL path: /{token}/c"),
    db_path: str = typer.Option("collabx.sqlite3", help="SQLite db file path"),
    set_target: bool = typer.Option(True, "--set-target/--no-set-target", help="Save this server as the active target."),
    public_url: Optional[str] = typer.Option(None, "--public-url", help="Override base URL saved to state (useful when binding 0.0.0.0)."),
):
    t = _normalize_token(token)
    if not t:
        console.print("[red]token is empty[/red]")
        raise typer.Exit(code=1)
    _warn_if_non_hex(t)

    os.environ["COLLABX_TOKEN"] = t
    os.environ["COLLABX_DB_PATH"] = db_path

    if public_url:
        base = public_url.rstrip("/")
    else:
        connect_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
        base = f"http://{connect_host}:{port}"

    if set_target:
        save_state(TargetState(base_url=base, token=t, provider="local", resources={}))
        console.print(f"[green]saved target[/green] → {base} (state: {DEFAULT_STATE_PATH})")

    console.print(f"Starting server on http://{host}:{port}")
    console.print(f"Collector: {base}/{t}/c")
    console.print(f"Logs:      {base}/{t}/logs")
    console.print(f"Events:    {base}/{t}/events")

    import uvicorn
    uvicorn.run("collabx_server.main:app", host=host, port=port, reload=False, log_level="info")


@app.command("up")
def up(
    provider: str = typer.Option("gcp", help="Provider to deploy to (v1 supports: gcp)."),
    region: str = typer.Option("us-central1", help="Region (GCP Cloud Run region)."),
    project: Optional[str] = typer.Option(None, help="GCP project id (optional; uses gcloud config if omitted)."),
    service: Optional[str] = typer.Option(None, help="Cloud Run service name (optional; auto-generated)."),
    repo: str = typer.Option("collabx", help="Artifact Registry repo name."),
    image_name: str = typer.Option("collector", help="Container image name."),
    token: Optional[str] = typer.Option(None, help="Optional token override (auto-generated if omitted)."),
):
    provider = provider.lower().strip()
    if provider != "gcp":
        console.print("[red]Only provider 'gcp' is implemented right now.[/red]")
        raise typer.Exit(code=2)

    repo_root = os.getcwd()
    url, tkn, resources = gcp_up(
        repo_root=repo_root,
        region=region,
        project=project,
        service=service,
        repo=repo,
        image_name=image_name,
        token=token,
    )

    save_state(TargetState(base_url=url, token=tkn, provider="gcp", resources=resources))

    console.print("[green]deployed[/green]")
    console.print(f"base_url:  {url}")
    console.print(f"token:     {tkn}")
    console.print(f"collector: {url}/{tkn}/c")
    console.print(f"logs:      {url}/{tkn}/logs")
    console.print(f"events:    {url}/{tkn}/events")
    console.print("")
    console.print("Tip: default listen mode is polling every 5s: [bold]collabx listen[/bold]")
    console.print("Opt-in SSE streaming: [bold]collabx listen --mode stream[/bold]")


@app.command("status")
def status():
    st = load_state()
    if not st:
        console.print("[yellow]No target set.[/yellow] Use: collabx up  OR  collabx init/target set")
        raise typer.Exit(code=1)

    console.print(f"provider: {st.provider}")
    console.print(f"base_url: {st.base_url}")
    console.print(f"collector: {st.collector_url}")

    if st.provider == "gcp":
        info = gcp_status(st.resources)
        try:
            console.print_json(data=json.loads(info["raw"]))
        except Exception:
            console.print(info["raw"])
    else:
        console.print("[yellow]No provider status available for this target.[/yellow]")


@app.command("down")
def down(
    delete_image: bool = typer.Option(True, "--delete-image/--keep-image", help="Delete pushed container image tag (best-effort)."),
    clear: bool = typer.Option(True, "--clear-state/--keep-state", help="Clear local saved state after teardown."),
):
    st = load_state()
    if not st:
        console.print("[yellow]No target set.[/yellow]")
        raise typer.Exit(code=1)

    if st.provider == "gcp":
        gcp_down(st.resources, delete_image=delete_image)
        console.print("[green]torn down[/green]")
    else:
        console.print("[yellow]Current target is not a cloud deployment.[/yellow] Nothing to tear down.")

    if clear:
        clear_state()
        console.print(f"[green]state cleared[/green] ({DEFAULT_STATE_PATH})")


if __name__ == "__main__":
    app()
