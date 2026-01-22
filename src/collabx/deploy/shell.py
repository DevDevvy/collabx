from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CmdResult:
    code: int
    out: str
    err: str


def run(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> CmdResult:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    res = CmdResult(code=p.returncode, out=(p.stdout or "").strip(), err=(p.stderr or "").strip())
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{res.err or res.out}")
    return res
