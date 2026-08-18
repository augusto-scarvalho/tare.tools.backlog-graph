from __future__ import annotations
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

class UsageError(RuntimeError):
    """Raised on invalid user input or command invocation."""
    pass

class GraphInvalid(RuntimeError):
    """Raised when a graph fails validation checks."""
    pass

def stable_dict(v: Any) -> Any:
    """Recursively sort dictionary keys for deterministic serialization."""
    if isinstance(v, dict):
        return {k: stable_dict(v[k]) for k in sorted(v)}
    if isinstance(v, list):
        return [stable_dict(x) for x in v]
    return v

def canonical_json(v: Any) -> str:
    """Return deterministically sorted compact JSON string."""
    return json.dumps(stable_dict(v), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_canonical(v: Any) -> str:
    """Compute SHA-256 hash of canonical JSON string."""
    return hashlib.sha256(canonical_json(v).encode("utf-8")).hexdigest()

def load_json(path: str | Path) -> Any:
    """Load JSON from file path with utf-8-sig encoding support."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"Cannot load JSON from {path}: {exc}") from exc

def dump_formatted(obj: Any, fmt: str = "json") -> None:
    """Output object to stdout in the requested format."""
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if fmt == "json":
        print(json.dumps(stable_dict(obj), ensure_ascii=False, indent=2))
    elif fmt == "jsonl":
        items = obj if isinstance(obj, list) else [obj]
        for x in items:
            print(json.dumps(stable_dict(x), ensure_ascii=False))
    elif fmt == "ids":
        items = obj if isinstance(obj, list) else [obj]
        for x in items:
            print(x.get("id", x) if isinstance(x, dict) else x)
    elif fmt == "md":
        print(to_markdown(obj))
    else:
        raise UsageError(f"Unsupported format: {fmt}")

def to_markdown(obj: Any) -> str:
    """Convert object to Markdown representation."""
    if isinstance(obj, list):
        lines = []
        for x in obj:
            if isinstance(x, dict):
                node_id = x.get("id", "")
                title = x.get("title", "")
                status = (x.get("completion") or {}).get("status", "")
                cluster = x.get("cluster", "")
                badge = f" `[{status}]`" if status else ""
                cluster_str = f" `({cluster})`" if cluster else ""
                lines.append(f"- **`{node_id}`**{badge}{cluster_str}: {title}")
            else:
                lines.append(f"- {x}")
        return "\n".join(lines)
    if isinstance(obj, dict):
        return "```json\n" + json.dumps(stable_dict(obj), ensure_ascii=False, indent=2) + "\n```"
    return str(obj)

def atomic_write(path: Path | str, text: str, overwrite: bool = False) -> None:
    """Safely write text to file atomically using a temporary file."""
    path = Path(path).resolve(strict=False)
    parent = path.parent
    if parent.is_symlink():
        raise UsageError("Refusing symlink parent directory")
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise UsageError(f"File already exists (overwrite=False): {path}")
    if path.is_symlink():
        raise UsageError("Refusing to overwrite a symlink")
    
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
