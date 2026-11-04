from __future__ import annotations
import copy
from typing import Any

from .core import WorkGraph
from .algorithms import compute_frontier, ranked_next, readiness

def simulate_completions(
    graph: WorkGraph,
    completed_node_ids: list[str],
    profile: str = "planning"
) -> dict[str, Any]:
    """Simulate the effect of marking specific nodes as DONE and see what becomes unlocked in the frontier."""
    simulated_raw = copy.deepcopy(graph.to_dict())
    
    before_frontier = [n["id"] for n in compute_frontier(graph, profile)]
    
    # Apply simulated completions
    for node in simulated_raw.get("nodes", []):
        if node.get("id") in completed_node_ids:
            if "completion" not in node or not isinstance(node["completion"], dict):
                node["completion"] = {}
            node["completion"]["status"] = "DONE"
            node["completion"]["dod_satisfied"] = True
            
    simulated_graph = WorkGraph(simulated_raw, graph.policy, graph.taxonomy)
    after_frontier_nodes = compute_frontier(simulated_graph, profile)
    after_frontier = [n["id"] for n in after_frontier_nodes]
    
    newly_unlocked = [nid for nid in after_frontier if nid not in before_frontier and nid not in completed_node_ids]
    
    return {
        "profile": profile,
        "simulated_completed_nodes": completed_node_ids,
        "before_frontier_count": len(before_frontier),
        "after_frontier_count": len(after_frontier),
        "newly_unlocked_nodes": newly_unlocked,
        "newly_unlocked_details": [simulated_graph.by_id[nid] for nid in newly_unlocked if nid in simulated_graph.by_id],
        "top_next_after_simulation": ranked_next(simulated_graph, profile, limit=5)
    }
