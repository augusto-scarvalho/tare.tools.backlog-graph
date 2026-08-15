from __future__ import annotations
from typing import Any
from .jsonutil import canonical_json

def semantic_diff(
    old: Any,
    new: Any,
    ignore_fields: set[str] | None = None
) -> list[dict[str, Any]]:
    """Compute deep semantic difference between two objects, aligning list items by 'id' when available."""
    ignore = ignore_fields or set()
    changes: list[dict[str, Any]] = []
    
    def walk(a: Any, b: Any, path: str = "$") -> None:
        leaf = path.split(".")[-1]
        if leaf in ignore:
            return
        if type(a) is not type(b):
            changes.append({"path": path, "old": a, "new": b})
            return
            
        if isinstance(a, dict):
            for k in sorted(set(a) | set(b)):
                if k in ignore:
                    continue
                if k not in a:
                    changes.append({"path": f"{path}.{k}", "old": "<MISSING>", "new": b[k]})
                elif k not in b:
                    changes.append({"path": f"{path}.{k}", "old": a[k], "new": "<MISSING>"})
                else:
                    walk(a[k], b[k], f"{path}.{k}")
        elif isinstance(a, list):
            if all(isinstance(x, dict) and "id" in x for x in a + b):
                ma = {x["id"]: x for x in a}
                mb = {x["id"]: x for x in b}
                for k in sorted(set(ma) | set(mb)):
                    if k not in ma:
                        changes.append({"path": f"{path}[id={k}]", "old": "<MISSING>", "new": mb[k]})
                    elif k not in mb:
                        changes.append({"path": f"{path}[id={k}]", "old": ma[k], "new": "<MISSING>"})
                    else:
                        walk(ma[k], mb[k], f"{path}[id={k}]")
            elif canonical_json(a) != canonical_json(b):
                changes.append({"path": path, "old": a, "new": b})
        elif a != b:
            changes.append({"path": path, "old": a, "new": b})
            
    walk(old, new)
    return changes

def validate_change(
    old_graph: dict[str, Any],
    new_graph: dict[str, Any],
    ignore_fields: list[str] | None = None
) -> dict[str, Any]:
    """Validate transition from old_graph to new_graph and summarize differences."""
    from .validation import validate_work_graph
    
    new_val = validate_work_graph(new_graph)
    if new_val["status"] != "PASS":
        return {
            "status": "FAIL",
            "validation": new_val,
            "change_count": 0,
            "changes": []
        }
        
    changes = semantic_diff(old_graph, new_graph, set(ignore_fields or []))
    return {
        "status": "PASS",
        "new_graph_validation": "PASS",
        "change_count": len(changes),
        "changes": changes
    }
