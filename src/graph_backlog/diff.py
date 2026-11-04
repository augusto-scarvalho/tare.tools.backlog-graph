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
            # Align only unambiguous identities; otherwise preserve the entire list.
            if (all(isinstance(x, dict) and isinstance(x.get("id"), str) for x in a + b)
                    and len({x["id"] for x in a}) == len(a)
                    and len({x["id"] for x in b}) == len(b)):
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


def shadow_parity(samples: list[dict[str, Any]], min_window_seconds: float) -> dict[str, Any]:
    """Check supplied offline snapshots, not source authenticity or a cutover."""
    import math
    from datetime import datetime
    from .jsonutil import compute_revision_hash
    from .validation import validate_work_graph

    gaps = []
    comparisons = []
    times = []
    if not math.isfinite(min_window_seconds) or min_window_seconds <= 0:
        gaps.append("positive_finite_window_required")
    if len(samples) < 2:
        gaps.append("at_least_two_samples_required")
    for index, sample in enumerate(samples):
        try:
            observed = datetime.fromisoformat(sample["observed_at"].replace("Z", "+00:00"))
            if observed.utcoffset() is None:
                raise ValueError("timezone required")
            times.append(observed)
            canonical, shadow = sample["canonical"], sample["shadow"]
            if not isinstance(canonical, dict) or not isinstance(shadow, dict):
                raise ValueError("graph objects required")
            validations = {"canonical": validate_work_graph(canonical),
                           "shadow": validate_work_graph(shadow)}
            if any(result["status"] != "PASS" for result in validations.values()):
                gaps.append(f"sample[{index}]:invalid_graph")
            comparisons.append({"sample": index, "observed_at": sample["observed_at"],
                                "canonical_sha256": compute_revision_hash(canonical),
                                "shadow_sha256": compute_revision_hash(shadow),
                                "validation": validations,
                                "changes": semantic_diff(canonical, shadow)})
        except (KeyError, TypeError, ValueError, AttributeError):
            gaps.append(f"sample[{index}]:invalid_sample")
    span = 0.0
    if len(times) == len(samples) and len(times) >= 2:
        if any(b <= a for a, b in zip(times, times[1:])):
            gaps.append("strictly_increasing_observations_required")
        span = (times[-1] - times[0]).total_seconds()
        if span < min_window_seconds:
            gaps.append("window_too_short")
    if any(row["changes"] for row in comparisons):
        gaps.append("semantic_divergence")
    return {"status": "PASS" if not gaps else "FAIL", "authority": "NONE",
            "verification_scope": "SUPPLIED_OFFLINE_SNAPSHOTS_ONLY",
            "content_verification": "NOT_PERFORMED", "cutover_performed": False,
            "eligible_for_cutover_review": not gaps, "window_seconds": span,
            "min_window_seconds": min_window_seconds, "samples": comparisons, "gaps": gaps}
