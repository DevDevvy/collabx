from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_STATE_PATH = Path.home() / ".collabx" / "state.json"


@dataclass
class TargetState:
    base_url: str
    token: str
    provider: str = "local"  # local|gcp|manual|...
    resources: Dict[str, Any] = None

    def __post_init__(self):
        if self.resources is None:
            self.resources = {}

    @property
    def collector_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.token}/c"

    @property
    def logs_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.token}/logs"

    @property
    def events_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.token}/events"


def load_state(path: Path = DEFAULT_STATE_PATH) -> Optional[TargetState]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TargetState(
            base_url=data["base_url"],
            token=data["token"],
            provider=data.get("provider", "local"),
            resources=data.get("resources") or {},
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None


def save_state(state: TargetState, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload = {
        "base_url": state.base_url,
        "token": state.token,
        "provider": state.provider,
        "resources": state.resources or {},
    }
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def clear_state(path: Path = DEFAULT_STATE_PATH) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
