from __future__ import annotations
import contextlib
import hashlib
import json
import os
import socket
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

class UsageError(RuntimeError):
    """Raised on invalid user input or command invocation."""
    pass

class GraphInvalid(RuntimeError):
    """Raised when a graph fails validation checks."""
    pass

class LockTimeoutError(UsageError):
    """Raised when an exclusive graph lock cannot be acquired within timeout."""
    pass

class RevisionMismatchError(UsageError):
    """Raised when a CAS operation detects a divergent graph revision."""
    pass

def stable_dict(v: Any, exclude_keys: tuple[str, ...] = ()) -> Any:
    """Recursively sort dictionary keys for deterministic serialization, optionally omitting excluded keys."""
    if isinstance(v, dict):
        return {k: stable_dict(v[k], exclude_keys=()) for k in sorted(v) if k not in exclude_keys}
    if isinstance(v, list):
        return [stable_dict(x, exclude_keys=()) for x in v]
    return v

def canonical_json(v: Any, exclude_keys: tuple[str, ...] = ()) -> str:
    """Return deterministically sorted compact JSON string (RFC 8785 / JCS compatible)."""
    return json.dumps(stable_dict(v, exclude_keys=exclude_keys), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_canonical(v: Any, exclude_keys: tuple[str, ...] = ()) -> str:
    """Compute SHA-256 hash of canonical JSON string."""
    return hashlib.sha256(canonical_json(v, exclude_keys=exclude_keys).encode("utf-8")).hexdigest()

def compute_revision_hash(graph_dict: dict[str, Any]) -> str:
    """Compute the content-addressed revision hash of the graph excluding the 'revision' key (ADR-046)."""
    return sha256_canonical(graph_dict, exclude_keys=("revision",))

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
    """Safely write text to file atomically using a temporary file with fsync."""
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

@contextlib.contextmanager
def graph_lock(path: Path | str, timeout: float = 5.0, stale_age_s: float = 30.0) -> Generator[dict[str, Any], None, None]:
    """Acquire an exclusive lockfile on the target work-graph (.work-graph.json.lock) (BG-01, BG-07)."""
    target = Path(path).resolve(strict=False)
    lock_file = target.parent / f".{target.name}.lock"
    start_time = time.time()
    lease_token = str(uuid.uuid4())
    acquired = False
    lock_data = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "acquired_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lease_token": lease_token,
        "target_file": str(target)
    }

    while time.time() - start_time < timeout:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(lock_data, ensure_ascii=False, indent=2))
                f.flush()
                os.fsync(f.fileno())
            acquired = True
            break
        except FileExistsError:
            # Check for stale lockfile (> stale_age_s)
            try:
                mtime = os.path.getmtime(str(lock_file))
                if time.time() - mtime > stale_age_s:
                    # Broken process left stale lock
                    try:
                        os.unlink(str(lock_file))
                    except OSError:
                        pass
            except OSError:
                pass
            time.sleep(0.05)

    if not acquired:
        raise LockTimeoutError(f"Could not acquire exclusive lock on '{target}' after {timeout:.1f}s (locked by {lock_file})")

    try:
        yield lock_data
    finally:
        if acquired and lock_file.exists():
            try:
                # Only delete if we own this lease
                raw = lock_file.read_text(encoding="utf-8", errors="ignore")
                parsed = json.loads(raw) if raw.strip() else {}
                if parsed.get("lease_token") == lease_token:
                    os.unlink(str(lock_file))
            except Exception:
                try:
                    os.unlink(str(lock_file))
                except OSError:
                    pass
