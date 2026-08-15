from __future__ import annotations
from collections import Counter
from typing import Any

from .core import WorkGraph, VALID_STATUSES, VALID_STALENESS, EVIDENCE_ORDER
from .algorithms import find_cycles_scc, readiness

def structural_errors(
    raw: Any,
    taxonomy: dict[str, Any] | None = None,
    expected_schema: str | None = None
) -> list[dict[str, Any]]:
    """Validate structure, types, mandatory fields, status enums, source refs, and relation validity."""
    errors: list[dict[str, Any]] = []
    
    def err(code: str, path: str, msg: str) -> None:
        errors.append({"code": code, "path": path, "message": msg})
        
    if not isinstance(raw, dict):
        return [{"code": "ROOT_TYPE", "path": "$", "message": "root must be object"}]
        
    allowed_root = {"meta", "sources", "nodes", "edges"}
    for k in raw:
        if k not in allowed_root:
            err("UNKNOWN_ROOT_FIELD", f"$.{k}", "unknown root field")
            
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        err("META_TYPE", "$.meta", "meta must be object")
    elif expected_schema:
        actual_schema = meta.get("schema")
        compatible = {expected_schema, "work-graph-poc/0.5", "tare.tools/work-graph/0.5"}
        if actual_schema not in compatible:
            err("SCHEMA_VERSION", "$.meta.schema", f"expected {expected_schema!r}")
        
    sources = raw.get("sources")
    if not isinstance(sources, dict):
        err("SOURCES_TYPE", "$.sources", "sources must be object")
    else:
        allowed_recoverability = {
            "RECOVERABLE_REFERENCE", "EXACT_BYTES", "CONTENT_ADDRESSED",
            "UNRESOLVED_REFERENCE", "PARTIAL_REFERENCE"
        }
        for sid, src in sources.items():
            sp = f"$.sources.{sid}"
            if not isinstance(sid, str) or not sid:
                err("SOURCE_ID", sp, "source id must be non-empty string")
            if not isinstance(src, dict):
                err("SOURCE_TYPE", sp, "source must be object")
                continue
            if not (src.get("kind") or src.get("type")):
                err("SOURCE_KIND", sp, "source requires kind or type")
            if not (src.get("fact") or src.get("title")):
                err("SOURCE_TITLE", sp, "source requires fact or title")
            rec = src.get("recoverability")
            if rec not in allowed_recoverability:
                err("SOURCE_RECOVERABILITY", sp, f"invalid recoverability {rec!r}")
            if rec in {"RECOVERABLE_REFERENCE", "EXACT_BYTES", "CONTENT_ADDRESSED"} and not isinstance(src.get("locator"), str):
                err("SOURCE_LOCATOR", sp, "recoverable source requires locator")
                
    nodes = raw.get("nodes")
    edges = raw.get("edges")
    if not isinstance(nodes, list):
        err("NODES_TYPE", "$.nodes", "nodes must be array")
        nodes = []
    if not isinstance(edges, list):
        err("EDGES_TYPE", "$.edges", "edges must be array")
        edges = []
        
    node_ids: list[str] = []
    required_node = {
        "id", "title", "kind", "cluster", "horizon", "work_status", "admission_state",
        "epistemic_status", "bounded_contexts", "priority", "criticality",
        "authority_required", "evidence_required", "confidence", "summary",
        "exit_criteria", "source_refs", "source_details", "provenance",
        "source_claim_ids", "unlock_score", "tags", "metrics", "notes", "items",
        "canonical_system", "canonical_id", "canonical_revision", "observed_at",
        "projection_run_id", "staleness_state", "readiness", "completion"
    }
    
    for i, n in enumerate(nodes):
        p = f"$.nodes[{i}]"
        if not isinstance(n, dict):
            err("NODE_TYPE", p, "node must be object")
            continue
            
        missing = sorted(required_node - set(n))
        unknown = sorted(set(n) - required_node)
        for k in missing:
            err("NODE_REQUIRED", f"{p}.{k}", "missing required field")
        for k in unknown:
            err("NODE_UNKNOWN", f"{p}.{k}", "unknown node field")
            
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            err("NODE_ID", f"{p}.id", "id must be non-empty string")
        else:
            node_ids.append(nid)
            
        for k in (
            "title", "kind", "cluster", "horizon", "work_status", "admission_state",
            "epistemic_status", "priority", "criticality", "summary",
            "projection_run_id", "staleness_state"
        ):
            if k in n and not isinstance(n[k], str):
                err("NODE_FIELD_TYPE", f"{p}.{k}", "must be string")
                
        for k in (
            "bounded_contexts", "evidence_required", "exit_criteria", "source_refs",
            "source_details", "provenance", "source_claim_ids", "tags", "notes", "items"
        ):
            if k in n and not isinstance(n[k], list):
                err("NODE_FIELD_TYPE", f"{p}.{k}", "must be array")
                
        if "confidence" in n and not isinstance(n["confidence"], dict):
            err("CONFIDENCE_TYPE", f"{p}.confidence", "must be object")
        if "metrics" in n and not isinstance(n["metrics"], dict):
            err("METRICS_TYPE", f"{p}.metrics", "must be object")
        if "readiness" in n and not isinstance(n["readiness"], dict):
            err("READINESS_TYPE", f"{p}.readiness", "must be object")
            
        c = n.get("completion")
        if not isinstance(c, dict):
            err("COMPLETION_TYPE", f"{p}.completion", "must be object")
        else:
            st = c.get("status")
            if st not in VALID_STATUSES:
                err("COMPLETION_STATUS", f"{p}.completion.status", f"invalid status {st!r}")
            if not isinstance(c.get("dod_satisfied"), bool):
                err("DOD_TYPE", f"{p}.completion.dod_satisfied", "must be boolean")
            if st == "DONE" and c.get("dod_satisfied") is not True:
                err("DONE_DOD", p, "DONE requires dod_satisfied=true")
            if st == "NOT_DONE" and c.get("dod_satisfied") is True:
                err("NOT_DONE_DOD", p, "NOT_DONE cannot have dod_satisfied=true")
                
        if n.get("staleness_state") not in VALID_STALENESS:
            err("STALENESS_ENUM", f"{p}.staleness_state", f"invalid staleness {n.get('staleness_state')!r}")
            
        if isinstance(sources, dict):
            for ref in n.get("source_refs", []) if isinstance(n.get("source_refs"), list) else []:
                if ref not in sources:
                    err("SOURCE_REF", f"{p}.source_refs", f"unknown source ref {ref!r}")
                    
    for nid, cnt in Counter(node_ids).items():
        if cnt > 1:
            err("DUPLICATE_NODE_ID", "$.nodes", f"duplicate node id {nid!r}")
            
    node_set = set(node_ids)
    rels = (taxonomy or {}).get("relations", {}) if isinstance(taxonomy, dict) else {}
    if not isinstance(rels, dict):
        rels = {}
        
    edge_keys: list[tuple[str, str, str, bool]] = []
    required_edge = {
        "from", "to", "type", "semantic", "source_refs", "source_details",
        "confidence", "notes", "requirements"
    }
    
    for i, e in enumerate(edges):
        p = f"$.edges[{i}]"
        if not isinstance(e, dict):
            err("EDGE_TYPE", p, "edge must be object")
            continue
        for k in sorted(required_edge - set(e)):
            err("EDGE_REQUIRED", f"{p}.{k}", "missing required field")
        for k in sorted(set(e) - required_edge):
            err("EDGE_UNKNOWN", f"{p}.{k}", "unknown edge field")
            
        a, b, t = e.get("from"), e.get("to"), e.get("type")
        if a not in node_set:
            err("EDGE_SOURCE", f"{p}.from", f"missing node {a!r}")
        if b not in node_set:
            err("EDGE_TARGET", f"{p}.to", f"missing node {b!r}")
        if t not in rels:
            err("RELATION_TAXONOMY", f"{p}.type", f"relation {t!r} has no taxonomy")
        if not isinstance(e.get("semantic"), bool):
            err("EDGE_SEMANTIC", f"{p}.semantic", "must be boolean")
        if not isinstance(e.get("source_refs"), list):
            err("EDGE_SOURCE_REFS", f"{p}.source_refs", "must be array")
        if not isinstance(e.get("source_details"), list):
            err("EDGE_SOURCE_DETAILS", f"{p}.source_details", "must be array")
        if isinstance(sources, dict):
            for ref in e.get("source_refs", []) if isinstance(e.get("source_refs"), list) else []:
                if ref not in sources:
                    err("EDGE_SOURCE_REF", f"{p}.source_refs", f"unknown source ref {ref!r}")
        if not isinstance(e.get("notes"), list):
            err("EDGE_NOTES", f"{p}.notes", "must be array")
        if not isinstance(e.get("confidence"), dict):
            err("EDGE_CONFIDENCE", f"{p}.confidence", "must be object")
        if not isinstance(e.get("requirements"), dict):
            err("EDGE_REQUIREMENTS", f"{p}.requirements", "must be object")
            
        edge_keys.append((a, b, t, bool(e.get("semantic", True))))
        
    for ek, cnt in Counter(edge_keys).items():
        if cnt > 1:
            err("DUPLICATE_EDGE", "$.edges", f"duplicate edge {ek!r}")
            
    return errors

def validate_work_graph(
    raw: dict[str, Any],
    policy: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Perform full validation of a work graph JSON (structural + DAG cycle detection)."""
    from .core import load_default_policy, load_default_taxonomy
    policy = policy or load_default_policy()
    taxonomy = taxonomy or load_default_taxonomy()
    
    errors = structural_errors(raw, taxonomy, policy.get("graph_schema"))
    if errors:
        return {
            "status": "FAIL",
            "error_count": len(errors),
            "errors": errors
        }
        
    graph = WorkGraph(raw, policy, taxonomy)
    cycles = find_cycles_scc(graph)
    if cycles:
        errors.append({
            "code": "BLOCKING_CYCLE",
            "path": "$.edges",
            "message": f"blocking SCC/self-loop: {cycles}"
        })
        
    return {
        "status": "PASS" if not errors else "FAIL",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "blocking_sccs": cycles,
        "error_count": len(errors),
        "errors": errors
    }

def verify_evidence(graph: WorkGraph) -> dict[str, Any]:
    """Verify evidence coverage and detect high-grade claims lacking recoverable source locators."""
    issues = []
    recoverable = 0
    for n in graph.nodes:
        refs = n.get("source_refs", [])
        ok = False
        for r in refs:
            src = graph.sources.get(r, {})
            if src.get("locator") and src.get("recoverability") in ("RECOVERABLE_REFERENCE", "EXACT_BYTES", "CONTENT_ADDRESSED"):
                ok = True
        if ok:
            recoverable += 1
        grade = (n.get("completion") or {}).get("evidence_grade")
        if grade in ("A", "B") and not ok:
            issues.append({
                "id": n["id"],
                "issue": "HIGH_GRADE_WITHOUT_RECOVERABLE_SOURCE",
                "grade": grade
            })
            
    cov = round(recoverable / max(1, len(graph.nodes)), 4)
    status = "FAIL" if issues else ("PASS" if recoverable == len(graph.nodes) else "PASS_WITH_GAPS")
    return {
        "status": status,
        "nodes": len(graph.nodes),
        "recoverable_source_nodes": recoverable,
        "coverage": cov,
        "issues": issues
    }

def reconcile(graph: WorkGraph) -> dict[str, Any]:
    """Evaluate operational divergence between planning readiness and operational readiness."""
    rows = []
    for n in graph.nodes:
        op = n.get("kind") in graph.actionable_kinds
        ident = all(n.get(k) for k in ("canonical_system", "canonical_id", "canonical_revision"))
        rows.append({
            "id": n["id"],
            "operational_candidate": op,
            "canonical_identity_complete": ident,
            "staleness_state": n.get("staleness_state"),
            "planning_ready": readiness(graph, n, "planning")["ready"],
            "operational_ready": readiness(graph, n, "operational")["ready"]
        })
    divergent = [x for x in rows if x["operational_candidate"] and not x["operational_ready"]]
    return {
        "status": "SHADOW_ONLY",
        "authority": "NONE",
        "checked": len(rows),
        "operational_divergence_count": len(divergent),
        "operational_divergences": divergent,
        "note": "This proposes/reports reconciliation only. Canonical single-writer remains outside Graph Ops."
    }

def doctor_check(graph: WorkGraph | dict[str, Any], version: str = "0.2.0") -> dict[str, Any]:
    """Run comprehensive health checks across validation, evidence, reconciliation, and cycle detection."""
    if isinstance(graph, dict):
        graph = WorkGraph(graph)
    ev = verify_evidence(graph)
    rec = reconcile(graph)
    cycles = find_cycles_scc(graph)
    
    if cycles or ev["status"] == "FAIL":
        status = "FAIL"
    elif ev["coverage"] == 1.0 and rec["operational_divergence_count"] == 0:
        status = "PASS"
    else:
        status = "PASS_SHADOW_WITH_GAPS"
        
    return {
        "status": status,
        "validation": "PASS",
        "blocking_cycles": cycles,
        "evidence_verification": ev,
        "reconcile": rec,
        "graph_ops_version": version
    }
