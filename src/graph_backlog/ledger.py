from __future__ import annotations
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .jsonutil import canonical_json, sha256_canonical, load_json, atomic_write

class GraphLedger:
    """Append-only tamper-evident ledger for graph state transitions and events."""
    
    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self.events: list[dict[str, Any]] = events or []
        
    @classmethod
    def load(cls, path: str | Path) -> GraphLedger:
        data = load_json(path)
        if isinstance(data, list):
            return cls(data)
        if isinstance(data, dict) and "events" in data:
            return cls(data["events"])
        return cls([])
        
    def last_hash(self) -> str:
        if not self.events:
            return "0000000000000000000000000000000000000000000000000000000000000000"
        return self.events[-1].get("event_hash", "")
        
    def append_event(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        timestamp: str | None = None
    ) -> dict[str, Any]:
        """Create and append an event linking back to the previous event hash."""
        prev_hash = self.last_hash()
        ts = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        event_body = {
            "index": len(self.events),
            "timestamp": ts,
            "event_type": event_type,
            "actor": actor,
            "prev_hash": prev_hash,
            "payload": payload
        }
        event_hash = sha256_canonical(event_body)
        full_event = {**event_body, "event_hash": event_hash}
        self.events.append(full_event)
        return full_event
        
    def verify_integrity(self) -> dict[str, Any]:
        """Verify the cryptographic hash chain of all events in the ledger."""
        expected_prev = "0000000000000000000000000000000000000000000000000000000000000000"
        for i, ev in enumerate(self.events):
            if ev.get("index") != i:
                return {"valid": False, "error": f"Invalid index at event {i}: expected {i}, got {ev.get('index')}"}
            if ev.get("prev_hash") != expected_prev:
                return {"valid": False, "error": f"Broken chain at event {i}: prev_hash mismatch"}
            body = {k: v for k, v in ev.items() if k != "event_hash"}
            expected_hash = sha256_canonical(body)
            if ev.get("event_hash") != expected_hash:
                return {"valid": False, "error": f"Hash mismatch at event {i}"}
            expected_prev = expected_hash
        return {"valid": True, "event_count": len(self.events)}
        
    def save(self, path: str | Path, overwrite: bool = True) -> None:
        import json
        text = json.dumps(self.events, ensure_ascii=False, indent=2) + "\n"
        atomic_write(path, text, overwrite)
