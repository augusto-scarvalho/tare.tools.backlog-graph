from __future__ import annotations
import copy
from datetime import datetime, timezone
from typing import Any

from .core import WorkGraph
from .jsonutil import UsageError
from .validation import validate_work_graph

def add_node_to_graph(
    graph: WorkGraph,
    node_id: str,
    title: str,
    cluster: str = "general",
    priority: str = "P1",
    horizon: str = "H1",
    criticality: str = "MEDIUM",
    summary: str | None = None,
    depends_on: list[str] | None = None,
    tags: list[str] | None = None,
    exit_criteria: list[str] | None = None
) -> dict[str, Any]:
    """Add a new node and optional prerequisite edges to the work graph, validating integrity."""
    if node_id in graph.by_id:
        raise UsageError(f"Node '{node_id}' already exists in graph")
        
    deps = depends_on or []
    for dep in deps:
        if dep not in graph.by_id:
            raise UsageError(f"Prerequisite node '{dep}' does not exist in graph")
            
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    new_node: dict[str, Any] = {
        "id": node_id,
        "title": title,
        "kind": "task",
        "cluster": cluster,
        "horizon": horizon,
        "work_status": "PROPOSED",
        "admission_state": "ADMITTED",
        "epistemic_status": "CERTAIN",
        "bounded_contexts": [cluster],
        "priority": priority,
        "criticality": criticality,
        "authority_required": "none",
        "evidence_required": [],
        "confidence": {"score": 1.0},
        "summary": summary or title,
        "exit_criteria": exit_criteria or [f"Complete {title}"],
        "source_refs": [],
        "source_details": [],
        "provenance": [],
        "source_claim_ids": [],
        "unlock_score": 1,
        "tags": tags or [],
        "metrics": {},
        "notes": [],
        "items": [],
        "canonical_system": "local",
        "canonical_id": node_id,
        "canonical_revision": "r1",
        "observed_at": now_str,
        "projection_run_id": "manual-mutation",
        "staleness_state": "FRESH",
        "readiness": {"operational_identity_required": False},
        "completion": {
            "status": "NOT_DONE",
            "dod_satisfied": False,
            "evidence_grade": None,
            "materialization_scope": "local"
        }
    }
    
    new_raw = copy.deepcopy(graph.to_dict())
    new_raw["nodes"].append(new_node)
    
    for dep in deps:
        new_raw["edges"].append({
            "from": dep,
            "to": node_id,
            "type": "UNLOCKS",
            "semantic": True,
            "source_refs": [],
            "source_details": [],
            "confidence": {"score": 1.0},
            "notes": ["Added via add_node"],
            "requirements": {}
        })
        
    val = validate_work_graph(new_raw, graph.policy, graph.taxonomy)
    if val["status"] != "PASS":
        raise UsageError(f"Cannot add node: validation failed with errors: {val.get('errors')}")
        
    return new_raw

def complete_node_in_graph(
    graph: WorkGraph,
    node_id: str,
    evidence_summary: str | None = None,
    evidence_grade: str = "B"
) -> dict[str, Any]:
    """Mark a node as DONE and record its Definition of Done satisfaction."""
    if node_id not in graph.by_id:
        raise UsageError(f"Node '{node_id}' not found in graph")
        
    new_raw = copy.deepcopy(graph.to_dict())
    for n in new_raw["nodes"]:
        if n["id"] == node_id:
            if not isinstance(n.get("completion"), dict):
                n["completion"] = {}
            n["completion"]["status"] = "DONE"
            n["completion"]["dod_satisfied"] = True
            n["completion"]["evidence_grade"] = evidence_grade
            n["completion"]["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if evidence_summary:
                dod_ev = n["completion"].get("dod_evidence") or []
                dod_ev.append(evidence_summary)
                n["completion"]["dod_evidence"] = dod_ev
            break
            
    val = validate_work_graph(new_raw, graph.policy, graph.taxonomy)
    if val["status"] != "PASS":
        raise UsageError(f"Cannot complete node: validation failed: {val.get('errors')}")
        
    return new_raw
