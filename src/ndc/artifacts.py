"""Write-once, content-addressed artifact store: <root>/<sha[:2]>/<sha>.<ext>."""

import hashlib
import os
from pathlib import Path

DEFAULT_ROOT = "/data/artifacts"


def root() -> Path:
    return Path(os.environ.get("NDC_ARTIFACTS") or DEFAULT_ROOT)


def path(sha: str, ext: str) -> Path:
    return root() / sha[:2] / f"{sha}.{ext}"


def put(data: bytes, ext: str) -> str:
    """Store bytes under their sha256 (no-op if already present); return the sha256."""
    sha = hashlib.sha256(data).hexdigest()
    p = path(sha, ext)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)
    return sha
