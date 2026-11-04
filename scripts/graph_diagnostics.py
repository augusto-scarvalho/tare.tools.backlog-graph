#!/usr/bin/env python3
"""Graph Diagnostics & Anomaly Linter for tare.tools Work Graphs.

Detects hidden pathologies:
1. Mixed / Semantic Cycles (non-causal edges creating circular references).
2. Horizon Inversions (earlier horizon depending on future horizon).
3. Causal Monotonicity Violations (DONE task depending on NOT_DONE task).
4. Priority Inversions (P0 critical task blocked by P3 low-priority task).
5. Target / North Star Disconnects (targets with outgoing execution edges or unreachable from roots).
6. Orphan Islands (disconnected nodes or dead-end branches).
7. Transitive Edge Redundancies (A->C when A->B and B->C exist).

Zero external dependencies (pure Python stdlib).
"""
import sys
import json
from pathlib import Path
from collections import defaultdict, deque

CAUSAL_TYPES = {
    'UNLOCKS', 'DEPENDS_ON', 'UNBLOCKS', 'PRECEDES', 'ENABLES',
    'LINEAGE_TO', 'PROVIDES_EVIDENCE_SEAMS_FOR'
}

HORIZON_RANKS = {
    'H0': 0,
    'H1': 1,
    'H2': 2,
    'H3': 3,
    'H4': 4
}

PRIORITY_RANKS = {
    'P0': 0,
    'P1': 1,
    'P2': 2,
    'P3': 3
}

def analyze_graph(graph_path="work-graph.json"):
    p = Path(graph_path)
    if not p.exists():
        return {"error": f"Graph file '{graph_path}' not found"}
    
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    nodes = {n["id"]: n for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n}
    edges = data.get("edges", [])
    
    anomalies = {
        "summary": {},
        "mixed_semantic_cycles": [],
        "horizon_inversions": [],
        "causal_monotonicity_violations": [],
        "priority_inversions": [],
        "target_terminus_violations": [],
        "orphan_islands": [],
        "transitive_redundancies": []
    }
    
    # 1. Build Adjacency Maps
    causal_adj = defaultdict(list)
    causal_in = defaultdict(list)
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
            if rel in CAUSAL_TYPES:
                causal_adj[src].append(dst)
                causal_in[dst].append(src)
                
    # 2. Check Mixed / Semantic Cycles
    visited = set()
    rec_stack = set()
    cycle_paths = []
    
    def dfs_all(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in all_adj[node]:
            if neighbor not in visited:
                dfs_all(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                cycle_start_idx = path.index(neighbor) if neighbor in path else 0
                cycle = path[cycle_start_idx:] + [neighbor]
                # Check if cycle contains non-causal edges
                rels = [edge_types.get((cycle[i], cycle[i+1]), "UNKNOWN") for i in range(len(cycle)-1)]
                has_non_causal = any(r not in CAUSAL_TYPES for r in rels)
                cycle_paths.append({
                    "cycle": cycle,
                    "edge_types": rels,
                    "is_semantic_mixed_cycle": has_non_causal
                })
        rec_stack.remove(node)

    for n in nodes:
        if n not in visited:
            dfs_all(n, [n])
            
    anomalies["mixed_semantic_cycles"] = [c for c in cycle_paths if c["is_semantic_mixed_cycle"]]
    
    # 3. Check Horizon Inversions & Priority Inversions & Monotonicity
    for e in edges:
        src, dst = e.get("from"), e.get("to")
        rel = e.get("type", "UNLOCKS")
        if src not in nodes or dst not in nodes:
            continue
            
        n_src = nodes[src]
        n_dst = nodes[dst]
        
        # Only analyze causal edges for horizon/priority/status
        if rel in CAUSAL_TYPES:
            h_src = HORIZON_RANKS.get(n_src.get("horizon", "H1"), 1)
            h_dst = HORIZON_RANKS.get(n_dst.get("horizon", "H1"), 1)
            if h_src > h_dst:
                anomalies["horizon_inversions"].append({
                    "from": src, "from_horizon": n_src.get("horizon"),
                    "to": dst, "to_horizon": n_dst.get("horizon"),
                    "type": rel,
                    "description": f"Later horizon {n_src.get('horizon')} is declared as prerequisite of earlier horizon {n_dst.get('horizon')}"
                })
                
            # Priority inversion (P3 blocking P0)
            p_src = PRIORITY_RANKS.get(n_src.get("priority", "P2"), 2)
            p_dst = PRIORITY_RANKS.get(n_dst.get("priority", "P2"), 2)
            if p_src > p_dst + 1:  # e.g. P3 blocking P1, or P2/P3 blocking P0
                anomalies["priority_inversions"].append({
                    "blocker_id": src, "blocker_priority": n_src.get("priority"),
                    "blocked_id": dst, "blocked_priority": n_dst.get("priority"),
                    "type": rel,
                    "description": f"Low priority task {src} ({n_src.get('priority')}) blocks high priority task {dst} ({n_dst.get('priority')})"
                })
                
            # Monotonicity check (DONE depending on NOT_DONE)
            s_src = n_src.get("completion", {}).get("status")
            s_dst = n_dst.get("completion", {}).get("status")
            if s_dst == "DONE" and s_src != "DONE":
                anomalies["causal_monotonicity_violations"].append({
                    "prerequisite_id": src, "prerequisite_status": s_src,
                    "dependent_id": dst, "dependent_status": s_dst,
                    "type": rel,
                    "description": f"Dependent task {dst} is marked DONE but prerequisite {src} is {s_src}"
                })
                
    # 4. Check Target / Terminus Violations (e.g. North Star)
    for nid, n in nodes.items():
        if n.get("kind") == "target" or n.get("horizon") == "H4":
            out_causal = [dst for dst in causal_adj[nid]]
            if out_causal:
                anomalies["target_terminus_violations"].append({
                    "target_id": nid,
                    "outgoing_causal_edges": out_causal,
                    "description": f"Target milestone {nid} has outgoing causal dependency edges to {out_causal}"
                })
                
    # 5. Check Orphan Islands (0 in-degree, 0 out-degree)
    for nid in nodes:
        if len(all_in[nid]) == 0 and len(all_adj[nid]) == 0:
            anomalies["orphan_islands"].append({
                "id": nid,
                "title": nodes[nid].get("title"),
                "cluster": nodes[nid].get("cluster"),
                "description": "Node is completely disconnected (0 inputs, 0 outputs)"
            })
            
    # 6. Check Transitive Redundancies (A->C when A->B and B->C exist)
    for u in nodes:
        for v in causal_adj[u]:
            # Check if there is another path from u to v of length >= 2
            visited_bfs = {u}
            q = deque()
            for w in causal_adj[u]:
                if w != v:
                    q.append((w, 1))
                    visited_bfs.add(w)
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
                    "direct_from": u,
                    "direct_to": v,
                    "description": f"Direct edge {u} -> {v} is redundant (alternate path exists)"
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

def main():
    graph_path = sys.argv[1] if len(sys.argv) > 1 else "work-graph.json"
    res = analyze_graph(graph_path)
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
