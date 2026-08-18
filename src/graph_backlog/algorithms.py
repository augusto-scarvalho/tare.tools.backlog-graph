from __future__ import annotations
import sys
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from .core import WorkGraph, EVIDENCE_ORDER, normalize_key

PRIORITY_WEIGHTS: dict[str, int] = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4
}

def readiness(graph: WorkGraph, node: dict[str, Any], profile: str = "planning") -> dict[str, Any]:
    """Compute deterministic readiness of a node under the specified profile ('planning' or 'operational')."""
    node_id = node.get("id", "")
    blockers = unresolved_prereqs(graph, node_id, profile)
    reasons = []
    st = graph.status_of(node)
    
    if st in graph.hidden_statuses:
        reasons.append(f"completion={st}")
    if graph.actionable_kinds and node.get("kind") not in graph.actionable_kinds:
        reasons.append("non_actionable_kind")
    if blockers:
        reasons.append("unresolved_prerequisites")
        
    r = node.get("readiness") or {}
    if profile == "operational":
        if r.get("operational_identity_required", True) and not all(node.get(k) for k in ("canonical_system", "canonical_id", "canonical_revision")):
            reasons.append("canonical_identity_missing")
        if node.get("staleness_state") != "FRESH":
            reasons.append("canonical_revision_or_freshness_unproven")
        scopes = r.get("required_materialization_scopes") or []
        if scopes and (node.get("completion") or {}).get("materialization_scope") not in scopes:
            reasons.append("materialization_scope_insufficient")
        min_grade = r.get("minimum_evidence_grade")
        grade = (node.get("completion") or {}).get("evidence_grade")
        if min_grade and EVIDENCE_ORDER.get(grade, -1) < EVIDENCE_ORDER.get(min_grade, 99):
            reasons.append("evidence_grade_insufficient")
        req_rev = r.get("required_canonical_revision")
        if req_rev and node.get("canonical_revision") != req_rev:
            reasons.append("canonical_revision_mismatch")
        max_age = r.get("max_evidence_age_days")
        observed = (node.get("completion") or {}).get("evidence_observed_at")
        asof = graph.meta.get("generated_at")
        if max_age is not None:
            try:
                if not observed or not asof:
                    raise ValueError
                parse = lambda x: datetime.fromisoformat(str(x).replace("Z", "+00:00"))
                if (parse(asof) - parse(observed)).total_seconds() > float(max_age) * 86400:
                    reasons.append("evidence_too_old")
            except (ValueError, TypeError):
                reasons.append("evidence_freshness_unproven")
                
    return {
        "profile": profile,
        "ready": len(reasons) == 0,
        "reasons": reasons,
        "unresolved_prerequisites": blockers,
        "authority_granted_by_graph": False,
        "note": "Readiness is projection feasibility only; Authority/Permit/Capability/Runtime gates remain external."
    }

def unresolved_prereqs(graph: WorkGraph, node_id: str, profile: str = "planning") -> list[dict[str, Any]]:
    """Return all unsatisfied direct prerequisite nodes that block node_id."""
    out = []
    for edge, pre in graph.block_in.get(node_id, []):
        if not graph.prerequisite_satisfies(pre, edge):
            src = graph.by_id.get(pre, {})
            out.append({
                "id": pre,
                "title": src.get("title", ""),
                "edge_type": edge.get("type", ""),
                "completion": graph.status_of(src) if src else "MISSING",
                "satisfied": False
            })
    return sorted(out, key=lambda x: (x["completion"], x["id"]))

def downstream_critical_depth(graph: WorkGraph, node_id: str) -> int:
    """Compute the longest downstream chain depth unlocked by this node using safe iterative DAG traversal."""
    if node_id not in graph.by_id:
        return 0
        
    q = deque([(node_id, 0)])
    visited_depth: dict[str, int] = {node_id: 0}
    max_d = 0
    node_limit = len(graph.by_id)

    while q:
        curr, depth = q.popleft()
        if depth > max_d:
            max_d = depth
            
        for _, dst in graph.block_out.get(curr, []):
            if dst in graph.by_id:
                next_d = depth + 1
                if dst not in visited_depth or next_d > visited_depth[dst]:
                    visited_depth[dst] = next_d
                    # Cycle guard: depth cannot exceed number of nodes
                    if next_d <= node_limit:
                        q.append((dst, next_d))
                        
    return max_d

def frontier_sort_key(graph: WorkGraph, node: dict[str, Any]) -> tuple[int, int, str]:
    """Canonical total order tuple: Priority (P0 > P1 > P2) -> -CriticalPathDepth -> Lexicographical ID (BG-03)."""
    p_str = str(node.get("priority", "P2")).strip().upper()
    p_weight = PRIORITY_WEIGHTS.get(p_str, 99)
    depth = downstream_critical_depth(graph, node.get("id", ""))
    return (p_weight, -depth, str(node.get("id", "")))

def compute_frontier(
    graph: WorkGraph,
    profile: str = "planning",
    include_partial: bool = True,
    all_active: bool = False
) -> list[dict[str, Any]]:
    """Compute the dependency-feasible frontier with deterministic total ordering (BG-03)."""
    out = []
    for n in graph.nodes:
        if not isinstance(n, dict) or "id" not in n:
            continue
        if graph.status_of(n) == "PARTIAL" and not include_partial:
            continue
        rd = readiness(graph, n, profile)
        if all_active:
            if graph.status_of(n) not in graph.hidden_statuses:
                out.append(n)
        elif rd["ready"]:
            out.append(n)
    return sorted(out, key=lambda x: frontier_sort_key(graph, x))

def find_cycles_scc(graph: WorkGraph) -> list[list[str]]:
    """Find all blocking cycles (strongly connected components with size > 1 or self-loops) using Tarjan's algorithm."""
    idx = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    comps: list[list[str]] = []
    
    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(max(1000, len(graph.nodes) * 4))
        
        def strongconnect(v: str) -> None:
            nonlocal idx
            indices[v] = lowlink[v] = idx
            idx += 1
            stack.append(v)
            on_stack.add(v)
            
            for _, w in graph.block_out.get(v, []):
                if w not in graph.by_id:
                    continue
                if w not in indices:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], indices[w])
                    
            if lowlink[v] == indices[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    comp.append(w)
                    if w == v:
                        break
                self_loop = (len(comp) == 1 and any(w2 == comp[0] for _, w2 in graph.block_out.get(comp[0], [])))
                if len(comp) > 1 or self_loop:
                    comps.append(sorted(comp))
                    
        for node_id in sorted(graph.by_id):
            if node_id not in indices:
                strongconnect(node_id)
                
        return sorted(comps)
    finally:
        sys.setrecursionlimit(old_limit)

def score_breakdown(graph: WorkGraph, node: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic ranking score and component breakdown for a node."""
    r = graph.policy.get("ranking", {})
    def lookup(group: str, val: Any) -> float:
        norm = {normalize_key(k): float(v) for k, v in (r.get(group, {}) or {}).items()}
        return norm.get(normalize_key(val), 0.0)
        
    parts: dict[str, float] = {
        "priority": lookup("priority", node.get("priority")),
        "horizon": lookup("horizon", node.get("horizon")),
        "criticality": lookup("criticality", node.get("criticality"))
    }
    try:
        parts["unlock_score"] = float(node.get("unlock_score") or 0.0) * float(r.get("unlock_score_multiplier", 1.0))
    except (TypeError, ValueError):
        parts["unlock_score"] = 0.0
        
    parts["partial_penalty"] = -float(r.get("partial_penalty", 0.0)) if graph.status_of(node) == "PARTIAL" else 0.0
    auth = str(node.get("authority_required") or "").strip().lower()
    parts["authority_penalty"] = -float(r.get("authority_penalty", 0.0)) if auth not in ("", "none", "n/a", "n/a — source archaeology") else 0.0
    
    return {"parts": parts, "score": sum(parts.values())}

def ranked_next(graph: WorkGraph, profile: str = "planning", limit: int = 10) -> list[dict[str, Any]]:
    """Rank the feasible frontier using canonical total ordering and policy breakdown."""
    rows = []
    for n in compute_frontier(graph, profile):
        sc = score_breakdown(graph, n)
        rows.append({
            "id": n["id"],
            "title": n.get("title", ""),
            "cluster": n.get("cluster", ""),
            "priority": n.get("priority", "P2"),
            "critical_depth": downstream_critical_depth(graph, n["id"]),
            "score": sc["score"],
            "score_parts": sc["parts"],
            "profile": profile,
            "authority_granted_by_graph": False
        })
    return rows[:limit]

def downstream_reach(graph: WorkGraph, start_id: str, blocking_only: bool = True) -> list[dict[str, Any]]:
    """Find all nodes that depend downstream on start_id."""
    adj = graph.block_out if blocking_only else {
        k: [(e, e["to"]) for e in v if "to" in e] for k, v in graph.out_edges.items()
    }
    q = deque([start_id])
    seen = {start_id}
    rows = []
    while q:
        v = q.popleft()
        for e, w in adj.get(v, []):
            if w not in seen:
                seen.add(w)
                q.append(w)
                node = graph.by_id.get(w, {})
                rows.append({
                    "id": w,
                    "title": node.get("title", ""),
                    "via": e.get("type", ""),
                    "from": v
                })
    return rows

def upstream_dependencies(graph: WorkGraph, start_id: str) -> list[dict[str, Any]]:
    """Find all transitive prerequisite nodes that start_id depends upon."""
    q = deque([start_id])
    seen = {start_id}
    rows = []
    while q:
        v = q.popleft()
        for e, w in graph.block_in.get(v, []):
            if w not in seen:
                seen.add(w)
                q.append(w)
                n = graph.by_id.get(w, {})
                rows.append({
                    "id": w,
                    "title": n.get("title", ""),
                    "completion": graph.status_of(n) if n else "MISSING",
                    "via": e.get("type", ""),
                    "to": v,
                    "satisfied": graph.is_satisfied(w)
                })
    return rows

def shortest_path(
    graph: WorkGraph,
    source_id: str,
    target_id: str,
    types: list[str] | None = None,
    semantic_only: bool = False
) -> list[dict[str, str]] | None:
    """Find shortest path from source_id to target_id via BFS."""
    allowed = set(types or [])
    q = deque([source_id])
    parent: dict[str, str | None] = {source_id: None}
    pedge: dict[str, dict[str, Any]] = {}
    
    while q:
        v = q.popleft()
        if v == target_id:
            break
        for e in graph.out_edges.get(v, []):
            if allowed and e.get("type") not in allowed:
                continue
            if semantic_only and not e.get("semantic", True):
                continue
            w = e.get("to")
            if w and w not in parent:
                parent[w] = v
                pedge[w] = e
                q.append(w)
                
    if target_id not in parent:
        return None
        
    path: list[dict[str, str]] = []
    cur: str | None = target_id
    while cur != source_id and cur is not None:
        e = pedge[cur]
        path.append({"from": e["from"], "type": e["type"], "to": e["to"]})
        cur = parent[cur]
    return list(reversed(path))

def critical_path(graph: WorkGraph) -> dict[str, Any]:
    """Compute the longest dependency chain (critical path) in the DAG."""
    cycles = find_cycles_scc(graph)
    if cycles:
        return {"status": "BLOCKED_BY_CYCLE", "blocking_sccs": cycles}
        
    indeg = {n: 0 for n in graph.by_id}
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for src, pairs in graph.block_out.items():
        for e, dst in pairs:
            adj[src].append((dst, e.get("type", "")))
            indeg[dst] = indeg.get(dst, 0) + 1
            
    q = deque(sorted([n for n, d in indeg.items() if d == 0]))
    dist = {n: 0 for n in graph.by_id}
    parent: dict[str, tuple[str, str]] = {}
    
    while q:
        v = q.popleft()
        for w, t in adj[v]:
            if dist[v] + 1 > dist.get(w, 0):
                dist[w] = dist[v] + 1
                parent[w] = (v, t)
            indeg[w] -= 1
            if indeg[w] == 0:
                q.append(w)
                
    if not dist:
        return {"status": "PASS", "edge_length": 0, "path": []}
        
    end = max(dist, key=lambda k: (dist[k], k))
    path = []
    cur = end
    while cur in parent:
        prev, t = parent[cur]
        path.append({"from": prev, "type": t, "to": cur})
        cur = prev
    return {"status": "PASS", "edge_length": dist[end], "path": list(reversed(path))}
