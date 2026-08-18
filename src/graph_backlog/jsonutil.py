from __future__ import annotations
import contextlib
import ctypes
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

def assert_no_symlinks_in_path(p: Path | str) -> None:
    """Validate that no component of the path (target or any ancestor) is a symlink."""
    curr = Path(p).absolute()
    for component in [curr] + list(curr.parents):
        if component.is_symlink():
            raise UsageError(f"Security Violation: Refusing symlink in path component: '{component}'")

def stable_dict(v: Any, exclude_keys: tuple[str, ...] = ()) -> Any:
    """Recursively sort dictionary keys for deterministic serialization, optionally omitting excluded keys."""
    if isinstance(v, dict):
        return {k: stable_dict(v[k], exclude_keys=()) for k in sorted(v) if k not in exclude_keys}
    if isinstance(v, list):
        return [stable_dict(x, exclude_keys=()) for x in v]
    return v

def canonical_json(v: Any, exclude_keys: tuple[str, ...] = ()) -> str:
    """Return deterministically sorted compact JSON string."""
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

def atomic_write(path: Path | str, text: str, overwrite: bool = True) -> None:
    """Safely write text to file atomically using an isolated scratch directory with symlink guards and fsync."""
    assert_no_symlinks_in_path(path)
    path = Path(path).resolve(strict=False)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise UsageError(f"File already exists (overwrite=False): {path}")
    
    # Isolated private atomic write scratch directory to unequivocally namespace temp writes
    scratch_dir = parent / f".{path.name}.atomic_scratch"
    assert_no_symlinks_in_path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    
    fd, tmp = tempfile.mkstemp(prefix="atomic_chunk_", suffix=".tmp", dir=str(scratch_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
            
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                os.replace(tmp, path)
                break
            except (PermissionError, OSError):
                if attempt == max_attempts - 1:
                    raise
                time.sleep(0.02 * (attempt + 1))
                
        if hasattr(os, "O_DIRECTORY"):
            try:
                dir_fd = os.open(str(parent), os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

def is_pid_alive(pid: int) -> bool:
    """Verify whether a process with given PID is actively running (handling cross-user permissions correctly)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle == 0:
            err = ctypes.GetLastError()
            # ERROR_ACCESS_DENIED (5) means the process is alive but runs under another account/elevation
            return err == 5
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    else:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            # Process exists and is alive, but owned by another user (EPERM)
            return True
        except (OSError, ProcessLookupError):
            return False

def get_machine_id() -> str:
    """Unique machine and hardware node identity to prevent hostname collision across machines."""
    return f"{socket.gethostname()}_{uuid.getnode()}"

@contextlib.contextmanager
def graph_lock(
    path: Path | str,
    timeout: float = 5.0,
    stale_age_s: float = 30.0
) -> Generator[dict[str, Any], None, None]:
    """Acquire an exclusive lockfile on the target work-graph with monotonic timeouts and verified local stale recovery."""
    assert_no_symlinks_in_path(path)
    target = Path(path).resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file = target.parent / f".{target.name}.lock"
    start_mono = time.monotonic()
    lease_token = str(uuid.uuid4())
    current_machine = get_machine_id()
    acquired = False
    lock_data = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "machine_id": current_machine,
        "acquired_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lease_token": lease_token,
        "target_file": str(target)
    }

    while (time.monotonic() - start_mono) < timeout:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(lock_data, ensure_ascii=False, indent=2))
                f.flush()
                os.fsync(f.fileno())
            acquired = True
            break
        except FileExistsError:
            try:
                mtime = os.path.getmtime(str(lock_file))
                if (time.time() - mtime) > stale_age_s:
                    try:
                        raw = lock_file.read_text(encoding="utf-8", errors="ignore")
                        parsed = json.loads(raw) if raw.strip() else {}
                        owner_pid = parsed.get("pid", 0)
                        owner_machine = parsed.get("machine_id", "")
                        
                        # STRICT: ONLY break stale lock if owner is verified on SAME hardware machine and PID is DEAD
                        if owner_machine == current_machine and owner_pid > 0:
                            if not is_pid_alive(owner_pid):
                                try:
                                    check_raw = lock_file.read_text(encoding="utf-8", errors="ignore")
                                    if check_raw == raw:
                                        os.unlink(str(lock_file))
                                except OSError:
                                    pass
                    except (json.JSONDecodeError, OSError, ValueError):
                        pass
            except OSError:
                pass
            time.sleep(0.05)

    if not acquired:
        raise LockTimeoutError(
            f"Could not acquire exclusive lock on '{target}' after {timeout:.1f}s (held by {lock_file})"
        )

    try:
        yield lock_data
    finally:
        if acquired and lock_file.exists():
            try:
                raw = lock_file.read_text(encoding="utf-8", errors="ignore")
                parsed = json.loads(raw) if raw.strip() else {}
                if parsed.get("lease_token") == lease_token:
                    os.unlink(str(lock_file))
            except Exception:
                pass
