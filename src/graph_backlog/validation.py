from __future__ import annotations
import json
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
        
    allowed_root = {"meta", "sources", "nodes", "edges", "revision", "schema_version"}
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
    
    optional_node = {"spec_ref", "superseded_by", "superseded_at", "supersession_reason"}
    for i, n in enumerate(nodes):
        p = f"$.nodes[{i}]"
        if not isinstance(n, dict):
            err("NODE_TYPE", p, "node must be object")
            continue
            
        missing = sorted(required_node - set(n))
        unknown = sorted(set(n) - required_node - optional_node)
        for k in missing:
            err("NODE_REQUIRED", f"{p}.{k}", "missing required field")
        for k in unknown:
            err("NODE_UNKNOWN", f"{p}.{k}", "unknown node field")
            
        nid = n.get("id")
        if "id" not in n:
            err("MISSING_ID", f"{p}.id", "node is missing the required id field")
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
                    err("INVALID_SOURCE_REF", f"{p}.source_refs", f"unknown source ref {ref!r}")
                    
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
        if not isinstance(a, str):
            err("EDGE_FIELD_TYPE", f"{p}.from", f"from must be string, got {type(a).__name__}")
        elif a not in node_set:
            err("EDGE_SOURCE", f"{p}.from", f"missing node {a!r}")
            
        if not isinstance(b, str):
            err("EDGE_FIELD_TYPE", f"{p}.to", f"to must be string, got {type(b).__name__}")
        elif b not in node_set:
            err("EDGE_TARGET", f"{p}.to", f"missing node {b!r}")
            
        if not isinstance(t, str):
            err("EDGE_FIELD_TYPE", f"{p}.type", f"type must be string, got {type(t).__name__}")
        elif t not in rels:
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
            
        if isinstance(a, str) and isinstance(b, str) and isinstance(t, str):
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
    """Perform full validation of a work graph JSON (structural + revision + DAG cycle detection)."""
    from .core import load_default_policy, load_default_taxonomy
    from .jsonutil import compute_revision_hash
    policy = policy or load_default_policy()
    taxonomy = taxonomy or load_default_taxonomy()
    
    errors = structural_errors(raw, taxonomy, policy.get("graph_schema"))

    # Revision Integrity Check
    if "revision" in raw and isinstance(raw["revision"], str):
        expected_rev = compute_revision_hash(raw)
        if raw["revision"] != expected_rev:
            errors.append({
                "code": "REVISION_MISMATCH",
                "path": "$.revision",
                "message": f"Graph revision '{raw['revision']}' does not match content hash '{expected_rev}'"
            })
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
    # A literal self-loop (edge from == to) also fails closed under its own named
    # code, in ADDITION to the SCC's BLOCKING_CYCLE (FAL-01).
    for i, e in enumerate(raw.get("edges", []) if isinstance(raw.get("edges"), list) else []):
        if isinstance(e, dict) and e.get("from") is not None and e.get("from") == e.get("to"):
            errors.append({"code": "SELF_LOOP", "path": f"$.edges[{i}]",
                           "message": f"edge source == target ({e.get('from')!r}): self-loop forbidden"})
        
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

def diagnose_graph(raw: dict[str, Any] | WorkGraph) -> dict[str, Any]:
    """Perform deep diagnostics and anomaly linting over graph topology."""
    from collections import defaultdict, deque
    if isinstance(raw, WorkGraph):
        nodes = {n["id"]: n for n in raw.nodes}
        edges = raw.edges
    else:
        nodes = {n["id"]: n for n in raw.get("nodes", []) if isinstance(n, dict) and "id" in n}
        edges = raw.get("edges", [])

    causal_types = {
        'UNLOCKS', 'DEPENDS_ON', 'UNBLOCKS', 'PRECEDES', 'ENABLES',
        'LINEAGE_TO', 'PROVIDES_EVIDENCE_SEAMS_FOR'
    }
    horizon_ranks = {'H0': 0, 'H1': 1, 'H2': 2, 'H3': 3, 'H4': 4}
    priority_ranks = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

    anomalies: dict[str, Any] = {
        "summary": {},
        "mixed_semantic_cycles": [],
        "horizon_inversions": [],
        "causal_monotonicity_violations": [],
        "priority_inversions": [],
        "target_terminus_violations": [],
        "orphan_islands": [],
        "transitive_redundancies": []
    }

    causal_adj = defaultdict(list)
    all_adj = defaultdict(list)
    all_in = defaultdict(list)
    edge_types = {}

    for e in edges:
        src, dst = e.get("from"), e.get("to")
        rel = e.get("type", "UNLOCKS")
        if src in nodes and dst in nodes:
            all_adj[src].append(dst)
            all_in[dst].append(src)
            edge_types[(src, dst)] = rel
            if rel in causal_types:
                causal_adj[src].append(dst)

    # Check mixed semantic cycles
    visited, rec_stack = set(), set()
    cycle_paths = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in all_adj[node]:
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                idx = path.index(neighbor) if neighbor in path else 0
                c = path[idx:] + [neighbor]
                rels = [edge_types.get((c[i], c[i+1]), "UNKNOWN") for i in range(len(c)-1)]
                has_non_causal = any(r not in causal_types for r in rels)
                cycle_paths.append({"cycle": c, "edge_types": rels, "is_semantic_mixed_cycle": has_non_causal})
        rec_stack.remove(node)

    for n in nodes:
        if n not in visited:
            dfs(n, [n])

    anomalies["mixed_semantic_cycles"] = [c for c in cycle_paths if c["is_semantic_mixed_cycle"]]

    for e in edges:
        src, dst = e.get("from"), e.get("to")
        rel = e.get("type", "UNLOCKS")
        if src not in nodes or dst not in nodes or rel not in causal_types:
            continue
        n_src, n_dst = nodes[src], nodes[dst]
        h_src = horizon_ranks.get(n_src.get("horizon", "H1"), 1)
        h_dst = horizon_ranks.get(n_dst.get("horizon", "H1"), 1)
        if h_src > h_dst:
            anomalies["horizon_inversions"].append({
                "from": src, "from_horizon": n_src.get("horizon"),
                "to": dst, "to_horizon": n_dst.get("horizon"),
                "type": rel
            })
        p_src = priority_ranks.get(n_src.get("priority", "P2"), 2)
        p_dst = priority_ranks.get(n_dst.get("priority", "P2"), 2)
        if p_src > p_dst + 1:
            anomalies["priority_inversions"].append({
                "blocker_id": src, "blocker_priority": n_src.get("priority"),
                "blocked_id": dst, "blocked_priority": n_dst.get("priority"),
                "type": rel
            })
        s_src = (n_src.get("completion") or {}).get("status")
        s_dst = (n_dst.get("completion") or {}).get("status")
        if s_dst == "DONE" and s_src != "DONE":
            anomalies["causal_monotonicity_violations"].append({
                "prerequisite_id": src, "prerequisite_status": s_src,
                "dependent_id": dst, "dependent_status": s_dst,
                "type": rel
            })

    for nid, n in nodes.items():
        if n.get("kind") == "target" and n.get("horizon") == "H4":
            out_causal = [dst for dst in causal_adj[nid]]
            if out_causal:
                anomalies["target_terminus_violations"].append({
                    "target_id": nid,
                    "outgoing_causal_edges": out_causal
                })
        if len(all_in[nid]) == 0 and len(all_adj[nid]) == 0:
            anomalies["orphan_islands"].append({
                "id": nid, "title": n.get("title"), "cluster": n.get("cluster")
            })

    for u in nodes:
        for v in causal_adj[u]:
            visited_bfs = {u}
            q = deque([(w, 1) for w in causal_adj[u] if w != v])
            visited_bfs.update(w for w, _ in q)
            has_alt = False
            while q:
                curr, dist = q.popleft()
                if curr == v:
                    has_alt = True
                    break
                for nxt in causal_adj[curr]:
                    if nxt not in visited_bfs:
                        visited_bfs.add(nxt)
                        q.append((nxt, dist + 1))
            if has_alt:
                anomalies["transitive_redundancies"].append({
                    "direct_from": u, "direct_to": v
                })

    anomalies["summary"] = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "mixed_semantic_cycles_count": len(anomalies["mixed_semantic_cycles"]),
        "horizon_inversions_count": len(anomalies["horizon_inversions"]),
        "causal_monotonicity_violations_count": len(anomalies["causal_monotonicity_violations"]),
        "priority_inversions_count": len(anomalies["priority_inversions"]),
        "target_terminus_violations_count": len(anomalies["target_terminus_violations"]),
        "orphan_islands_count": len(anomalies["orphan_islands"]),
        "transitive_redundancies_count": len(anomalies["transitive_redundancies"]),
        "health_status": "CLEAN" if all(len(v) == 0 for k, v in anomalies.items() if k != "summary") else "ANOMALIES_DETECTED"
    }
    return anomalies

def doctor_check(graph: WorkGraph | dict[str, Any], version: str = "1.0.0") -> dict[str, Any]:
    """Run comprehensive health checks across validation, evidence, reconciliation, and cycle detection."""
    from .core import load_default_policy, load_default_taxonomy
    
    if isinstance(graph, dict):
        raw_dict = graph
        pol = load_default_policy()
        tax = load_default_taxonomy()
    else:
        raw_dict = graph.to_dict()
        pol = graph.policy
        tax = graph.taxonomy

    val = validate_work_graph(raw_dict, pol, tax)
    if val["status"] != "PASS":
        return {
            "status": "FAIL",
            "validation": "FAIL",
            "validation_errors": val.get("errors", []),
            "blocking_cycles": [],
            "evidence_verification": {"status": "FAIL", "coverage": 0.0},
            "reconcile": {"status": "FAIL", "operational_divergence_count": 0},
            "diagnostics_summary": {"health_status": "INVALID_SCHEMA"},
            "graph_ops_version": version
        }

    wg = graph if isinstance(graph, WorkGraph) else WorkGraph(raw_dict, policy=pol, taxonomy=tax)
    ev = verify_evidence(wg)
    rec = reconcile(wg)
    cycles = find_cycles_scc(wg)
    diag = diagnose_graph(wg)
    
    if cycles or ev["status"] == "FAIL":
        status = "FAIL"
    elif ev["coverage"] == 1.0 and rec["operational_divergence_count"] == 0 and diag["summary"]["health_status"] == "CLEAN":
        status = "PASS"
    else:
        status = "PASS_SHADOW_WITH_GAPS"
        
    return {
        "status": status,
        "validation": "PASS",
        "validation_errors": [],
        "blocking_cycles": cycles,
        "evidence_verification": ev,
        "reconcile": rec,
        "diagnostics_summary": diag["summary"],
        "graph_ops_version": version
    }

def migrate_v05_to_v10(raw: dict[str, Any]) -> dict[str, Any]:
    """Deterministically migrate a legacy v0.5 graph to schema v1.0.0 (BG-09)."""
    import copy
    from .jsonutil import compute_revision_hash
    migrated = copy.deepcopy(raw)
    
    migrated["schema_version"] = "1.0.0"
    if "meta" not in migrated or not isinstance(migrated["meta"], dict):
        migrated["meta"] = {}
    migrated["meta"]["schema"] = "tare.tools/work-graph/1.0"
    
    for n in migrated.get("nodes", []):
        if not isinstance(n.get("completion"), dict):
            n["completion"] = {
                "status": "NOT_DONE",
                "dod_satisfied": False,
                "evidence_grade": None,
                "materialization_scope": "local"
            }
        elif "dod_satisfied" not in n["completion"]:
            n["completion"]["dod_satisfied"] = (n["completion"].get("status") == "DONE")
            
    migrated["revision"] = compute_revision_hash(migrated)
    return migrated

def doctor_recover(
    graph_path: str | Path,
    stale_tmp_age_s: float = 60.0,
    force_unlock: bool = False,
    clean_tmp: bool = True
) -> dict[str, Any]:
    """Perform post-crash recovery and state stabilization on a work-graph (BG-07)."""
    import time
    from pathlib import Path
    from .jsonutil import load_json, atomic_write, graph_lock, compute_revision_hash, stable_dict, UsageError
    
    raw_p = Path(graph_path)
    if raw_p.is_symlink():
        raise UsageError(f"Refusing to recover a symlink target: {raw_p}")
    if raw_p.parent.is_symlink():
        raise UsageError(f"Refusing to recover inside a symlink directory: {raw_p.parent}")

    target = raw_p.resolve(strict=False)
    parent = target.parent
    lock_file = parent / f".{target.name}.lock"
    recovered_items = []

    # Operator intervention: force removal of an abandoned lock
    if force_unlock and lock_file.exists():
        try:
            lock_file.unlink()
            recovered_items.append("force_unlocked_stale_lock")
        except OSError:
            pass

    with graph_lock(target, timeout=5.0):
        # 1. Clean up only verified stale .tmp files from aborted writes (> stale_tmp_age_s)
        if clean_tmp:
            now = time.time()
            for tmp in parent.glob(f".{target.name}.tmp_*"):
                try:
                    if tmp.is_file() and not tmp.is_symlink() and (now - tmp.stat().st_mtime) > stale_tmp_age_s:
                        tmp.unlink()
                        recovered_items.append(f"cleaned_stale_tmp:{tmp.name}")
                except OSError:
                    pass
                    
        # 2. Re-read and stabilize state
        raw = load_json(target)
        migrated = migrate_v05_to_v10(raw) if raw.get("schema_version") != "1.0.0" else raw
        expected_hash = compute_revision_hash(migrated)
        if migrated.get("revision") != expected_hash:
            migrated["revision"] = expected_hash
            recovered_items.append("recalculated_canonical_revision_hash")
            
        atomic_write(target, json.dumps(stable_dict(migrated), ensure_ascii=False, indent=2) + "\n", overwrite=True)
        
    return {
        "status": "RECOVERED" if recovered_items else "STABLE",
        "target": str(target),
        "recovered_actions": recovered_items,
        "revision": migrated.get("revision")
    }


