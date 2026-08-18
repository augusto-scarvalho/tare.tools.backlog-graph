from __future__ import annotations
import copy
from datetime import datetime, timezone
from typing import Any

from .core import WorkGraph
from .jsonutil import UsageError, RevisionMismatchError, compute_revision_hash
from .validation import validate_work_graph
from .algorithms import find_cycles_scc

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
    exit_criteria: list[str] | None = None,
    spec_ref: str | None = None
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
        "source_refs": [f"spec:{spec_ref}"] if spec_ref else [],
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
    if spec_ref:
        new_node["spec_ref"] = spec_ref
    
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
        
    new_raw["revision"] = compute_revision_hash(new_raw)
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
        
    new_raw["revision"] = compute_revision_hash(new_raw)
    return new_raw

def land_train_tasks(
    graph: WorkGraph,
    train_id: str,
    task_ids: list[str],
    evidence_summary: str | None = None,
    expected_rev: str | None = None
) -> dict[str, Any]:
    """Atomically mark a batch of tasks as DONE under a train landing, enforcing CAS revision check (BG-05)."""
    current_dict = graph.to_dict()
    current_hash = compute_revision_hash(current_dict)
    
    if expected_rev and expected_rev != current_hash:
        raise RevisionMismatchError(
            f"CAS conflict during landing of train '{train_id}': expected revision '{expected_rev}', but current revision is '{current_hash}'"
        )
        
    new_raw = copy.deepcopy(current_dict)
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    target_set = set(task_ids)
    found_set = set()
    
    for n in new_raw.get("nodes", []):
        nid = n.get("id")
        if nid in target_set:
            found_set.add(nid)
            if not isinstance(n.get("completion"), dict):
                n["completion"] = {}
            n["completion"]["status"] = "DONE"
            n["completion"]["dod_satisfied"] = True
            n["completion"]["evidence_grade"] = "A"
            n["completion"]["completed_at"] = now_iso
            n["completion"]["landed_train"] = train_id
            
            dod_ev = n["completion"].get("dod_evidence") or []
            ev_text = f"Landed in train {train_id}" + (f": {evidence_summary}" if evidence_summary else "")
            dod_ev.append(ev_text)
            n["completion"]["dod_evidence"] = dod_ev

    missing = target_set - found_set
    if missing:
        raise UsageError(f"Cannot land tasks: missing task IDs in graph: {sorted(missing)}")
        
    val = validate_work_graph(new_raw, graph.policy, graph.taxonomy)
    if val["status"] != "PASS":
        raise UsageError(f"Landing failed validation: {val.get('errors')}")
        
    new_raw["revision"] = compute_revision_hash(new_raw)
    return new_raw

def supersede_node_in_graph(
    graph: WorkGraph,
    node_id: str,
    superseded_by_id: str,
    reason: str | None = None
) -> dict[str, Any]:
    """Formally mark a node as SUPERSEDED by another active node with acyclic Tarjan validation (BG-04)."""
    if node_id not in graph.by_id:
        raise UsageError(f"Node '{node_id}' not found in graph")
    if superseded_by_id not in graph.by_id:
        raise UsageError(f"Successor node '{superseded_by_id}' not found in graph")
    if node_id == superseded_by_id:
        raise UsageError(f"A node cannot supersede itself: '{node_id}'")
        
    new_raw = copy.deepcopy(graph.to_dict())
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # 1. Update node status to SUPERSEDED
    for n in new_raw.get("nodes", []):
        if n.get("id") == node_id:
            if not isinstance(n.get("completion"), dict):
                n["completion"] = {}
            n["completion"]["status"] = "SUPERSEDED"
            n["completion"]["superseded_by"] = superseded_by_id
            n["completion"]["superseded_at"] = now_iso
            if reason:
                n["completion"]["supersession_reason"] = reason
            break
            
    # 2. Add explicit SUPERSEDED_BY edge from node_id to superseded_by_id
    new_raw.setdefault("edges", []).append({
        "from": node_id,
        "to": superseded_by_id,
        "type": "SUPERSEDED_BY",
        "semantic": True,
        "source_refs": [],
        "source_details": [],
        "confidence": {"score": 1.0},
        "requirements": {},
        "notes": [reason or f"Superseded by {superseded_by_id}"]
    })
    
    # 3. Check for cycles using temporary WorkGraph
    temp_wg = WorkGraph(new_raw)
    cycles = find_cycles_scc(temp_wg)
    if cycles:
        raise UsageError(f"Supersession would create circular dependency: {cycles}")
        
    val = validate_work_graph(new_raw, graph.policy, graph.taxonomy)
    if val["status"] != "PASS":
        raise UsageError(f"Supersession failed validation: {val.get('errors')}")
        
    new_raw["revision"] = compute_revision_hash(new_raw)
    return new_raw
