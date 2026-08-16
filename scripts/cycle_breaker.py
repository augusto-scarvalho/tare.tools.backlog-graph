#!/usr/bin/env python3
"""Automated Cycle Breaker & Governance Triage Generator for tare.tools Work Graphs.

Applies deterministic topological rules to break circular dependencies without data loss,
AND automatically flags all affected tasks for architectural review so human architects
or review agents can examine whether the underlying component design requires structural decoupling.

Rules applied:
1. Bidirectional Deduplication: Resolves 2-node mutual cross-reference loops (A <-> B).
2. Horizon Inversion Correction: Inverts informational edges that point backward from future horizons to earlier horizons.
3. Minimum Feedback Arc Removal: Identifies and relaxes back-edges in causal loops.

For every modified node:
- Sets `work_status: "NEEDS_ARCHITECTURAL_REVIEW"` (if NOT_DONE).
- Injects a `[CYCLE_BREAK_AUDIT]` note describing the change and architectural question.
- Emits a Markdown Triage Dossier (`CYCLE_REPAIR_TRIAGE.md`).

Zero external dependencies (pure Python stdlib).
"""
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

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

def find_all_cycles(nodes, edges):
    adj = defaultdict(list)
    edge_map = {}
    for e in edges:
        src, dst, rel = e.get('from'), e.get('to'), e.get('type')
        if src in nodes and dst in nodes:
            adj[src].append(dst)
            edge_map[(src, dst)] = rel

    visited = set()
    rec_stack = set()
    cycles = []

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj[node]:
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                idx = path.index(neighbor) if neighbor in path else 0
                cycle = path[idx:] + [neighbor]
                rels = [edge_map.get((cycle[i], cycle[i+1]), 'UNKNOWN') for i in range(len(cycle)-1)]
                cycles.append((cycle, rels))
        rec_stack.remove(node)

    for n in nodes:
        if n not in visited:
            dfs(n, [n])
            
    return cycles

def flag_node_for_review(node, reason_note):
    if not node:
        return
    status = (node.get("completion") or {}).get("status")
    if status != "DONE":
        node["work_status"] = "NEEDS_ARCHITECTURAL_REVIEW"
    notes = node.setdefault("notes", [])
    if reason_note not in notes:
        notes.append(reason_note)

def generate_triage_markdown(actions_taken, initial_cycles_count):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    lines = [
        "# Cycle Repair & Architectural Triage Dossier",
        "",
        f"- **Timestamp:** {ts}",
        f"- **Initial Cycles Detected:** {initial_cycles_count}",
        f"- **Actions Applied:** {len(actions_taken)}",
        "- **Status:** TOPOLOGICAL_LIVENESS_RESTORED / ARCHITECTURAL_REVIEW_PENDING",
        "",
        "## 1. Executive Summary",
        "Automated cycle-breaking normalized the Directed Acyclic Graph (DAG) to ensure execution liveness.",
        "However, circular dependencies often indicate underlying architectural coupling, circular bootstrap patterns, or conflicting design decisions.",
        "The tasks below have been tagged with `work_status: NEEDS_ARCHITECTURAL_REVIEW` for explicit review by human architects or review agents.",
        "",
        "## 2. Actions & Triage Questions Matrix",
        "",
        "| ID | Rule Applied | Edge Modified | Action | Architectural Review Question |",
        "|---|---|---|---|---|"
    ]
    
    for idx, act in enumerate(actions_taken, 1):
        rule = act.get("rule")
        edge = act.get("edge") or act.get("original")
        action_name = act.get("action")
        q = act.get("triage_question", "Verify if components require interface extraction or decoupling.")
        lines.append(f"| T-{idx:02d} | `{rule}` | `{edge}` | {action_name} | {q} |")
        
    lines.extend([
        "",
        "## 3. Recommended Review Checklist",
        "1. **Is the circular dependency a design flaw?** Check if Component A and Component B can be decoupled by extracting a shared interface or common data model.",
        "2. **Is it a Two-Phase Bootstrap issue?** Check if Component A only needs Component B during runtime execution, while Component B needs Component A during registration (e.g. split into Phase 1 Registration + Phase 2 Execution).",
        "3. **Is it purely a documentation/metadata link?** If it is a non-causal relation (e.g. `INFORMS`, `RELATED_RESEARCH`), ensure it does not use a blocking execution edge type (`UNLOCKS`).",
        ""
    ])
    return "\n".join(lines)

def break_graph_cycles(graph_path="work-graph.json", save=False, out_path=None, triage_md_path="CYCLE_REPAIR_TRIAGE.md"):
    p = Path(graph_path)
    if not p.exists():
        return {"error": f"Graph file '{graph_path}' not found"}
        
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    nodes = {n["id"]: n for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n}
    edges = list(data.get("edges", []))
    
    initial_cycles = find_all_cycles(nodes, edges)
    actions_taken = []
    
    # Pass 1: Resolve 2-node bidirectional cross-references (A <-> B)
    edge_pairs = defaultdict(list)
    for idx, e in enumerate(edges):
        pair = tuple(sorted([e.get("from"), e.get("to")]))
        edge_pairs[pair].append((idx, e))
        
    edges_to_remove = set()
    for pair, pair_edges in edge_pairs.items():
        if len(pair_edges) == 2:
            (idx1, e1), (idx2, e2) = pair_edges
            if e1.get("from") == e2.get("to") and e1.get("to") == e2.get("from"):
                rel1 = e1.get("type", "UNLOCKS")
                rel2 = e2.get("type", "UNLOCKS")
                
                src1, dst1 = e1.get("from"), e1.get("to")
                src2, dst2 = e2.get("from"), e2.get("to")
                
                if rel1 in CAUSAL_TYPES and rel2 not in CAUSAL_TYPES:
                    edges_to_remove.add(idx2)
                    note = f"[CYCLE_BREAK_AUDIT] Removed reverse edge '{src2} -> {dst2}' ({rel2}) in favor of causal edge '{src1} -> {dst1}' ({rel1})."
                    flag_node_for_review(nodes.get(src2), note)
                    flag_node_for_review(nodes.get(dst2), note)
                    actions_taken.append({
                        "rule": "BIDIRECTIONAL_DEDUPLICATION",
                        "action": "REMOVED_BACKWARD_METADATA_EDGE",
                        "edge": f"{src2} --({rel2})--> {dst2}",
                        "kept_edge": f"{src1} --({rel1})--> {dst1}",
                        "triage_question": f"Is '{src2}' truly dependent on '{dst2}', or was this link merely a cross-reference?"
                    })
                elif rel2 in CAUSAL_TYPES and rel1 not in CAUSAL_TYPES:
                    edges_to_remove.add(idx1)
                    note = f"[CYCLE_BREAK_AUDIT] Removed reverse edge '{src1} -> {dst1}' ({rel1}) in favor of causal edge '{src2} -> {dst2}' ({rel2})."
                    flag_node_for_review(nodes.get(src1), note)
                    flag_node_for_review(nodes.get(dst1), note)
                    actions_taken.append({
                        "rule": "BIDIRECTIONAL_DEDUPLICATION",
                        "action": "REMOVED_BACKWARD_METADATA_EDGE",
                        "edge": f"{src1} --({rel1})--> {dst1}",
                        "kept_edge": f"{src2} --({rel2})--> {dst2}",
                        "triage_question": f"Is '{src1}' truly dependent on '{dst1}', or was this link merely a cross-reference?"
                    })
                else:
                    h_from1 = HORIZON_RANKS.get(nodes.get(src1, {}).get("horizon", "H1"), 1)
                    h_to1 = HORIZON_RANKS.get(nodes.get(dst1, {}).get("horizon", "H1"), 1)
                    if h_from1 > h_to1:
                        edges_to_remove.add(idx1)
                        note = f"[CYCLE_BREAK_AUDIT] Removed backward horizon edge '{src1} -> {dst1}'."
                        flag_node_for_review(nodes.get(src1), note)
                        flag_node_for_review(nodes.get(dst1), note)
                        actions_taken.append({
                            "rule": "BIDIRECTIONAL_DEDUPLICATION",
                            "action": "REMOVED_BACKWARD_HORIZON_EDGE",
                            "edge": f"{src1} --({rel1})--> {dst1}",
                            "kept_edge": f"{src2} --({rel2})--> {dst2}",
                            "triage_question": f"Did future task '{src1}' depend on earlier task '{dst1}' or vice-versa?"
                        })
                    else:
                        edges_to_remove.add(idx2)
                        note = f"[CYCLE_BREAK_AUDIT] Removed backward horizon edge '{src2} -> {dst2}'."
                        flag_node_for_review(nodes.get(src2), note)
                        flag_node_for_review(nodes.get(dst2), note)
                        actions_taken.append({
                            "rule": "BIDIRECTIONAL_DEDUPLICATION",
                            "action": "REMOVED_BACKWARD_HORIZON_EDGE",
                            "edge": f"{src2} --({rel2})--> {dst2}",
                            "kept_edge": f"{src1} --({rel1})--> {dst1}",
                            "triage_question": f"Did future task '{src2}' depend on earlier task '{dst2}' or vice-versa?"
                        })

    edges = [e for idx, e in enumerate(edges) if idx not in edges_to_remove]
    
    # Pass 2: Invert or Relax High-Horizon to Low-Horizon Backward Links (e.g. North Star -> Repo)
    for e in edges:
        src = e.get("from")
        dst = e.get("to")
        rel = e.get("type", "UNLOCKS")
        
        n_src = nodes.get(src, {})
        n_dst = nodes.get(dst, {})
        
        h_src = HORIZON_RANKS.get(n_src.get("horizon", "H1"), 1)
        h_dst = HORIZON_RANKS.get(n_dst.get("horizon", "H1"), 1)
        
        if (n_src.get("kind") == "target" or h_src == 4) and h_dst < 3 and rel not in CAUSAL_TYPES:
            e["from"] = dst
            e["to"] = src
            e["type"] = "LINEAGE_TO"
            note = f"[CYCLE_BREAK_AUDIT] Inverted edge direction from '{src} -> {dst}' ({rel}) to '{dst} -> {src}' (LINEAGE_TO) to preserve time monotonicity."
            flag_node_for_review(n_src, note)
            flag_node_for_review(n_dst, note)
            actions_taken.append({
                "rule": "HORIZON_MONOTONICITY",
                "action": "INVERTED_EDGE_DIRECTION",
                "original": f"{src} --({rel})--> {dst}",
                "adjusted": f"{dst} --(LINEAGE_TO)--> {src}",
                "triage_question": f"Is '{src}' the terminus target milestone of '{dst}', or was '{src}' acting as an active prerequisite?"
            })
            
    # Pass 3: Iterative Cycle Check and Feedback Arc Set Resolution
    remaining_cycles = find_all_cycles(nodes, edges)
    iteration = 0
    while remaining_cycles and iteration < 10:
        iteration += 1
        cycle, rels = remaining_cycles[0]
        break_idx = None
        for i in range(len(cycle)-1):
            if rels[i] not in CAUSAL_TYPES:
                break_idx = i
                break
        if break_idx is None:
            break_idx = len(cycle) - 2
            
        u, v = cycle[break_idx], cycle[break_idx+1]
        edges = [e for e in edges if not (e.get("from") == u and e.get("to") == v)]
        note = f"[CYCLE_BREAK_AUDIT] Removed cycle-closing edge '{u} -> {v}' ({rels[break_idx]}) in loop: {' -> '.join(cycle)}."
        flag_node_for_review(nodes.get(u), note)
        flag_node_for_review(nodes.get(v), note)
        actions_taken.append({
            "rule": "FEEDBACK_ARC_SET",
            "action": "REMOVED_CYCLE_CLOSING_BACK_EDGE",
            "edge": f"{u} --({rels[break_idx]})--> {v}",
            "broken_cycle_length": len(cycle)-1,
            "triage_question": f"Loop detected: {' -> '.join(cycle)}. Does this reflect tight coupling that requires decoupling into separate phases?"
        })
        remaining_cycles = find_all_cycles(nodes, edges)
        
    data["edges"] = edges
    data["nodes"] = list(nodes.values())
    
    final_cycles = find_all_cycles(nodes, edges)
    triage_md = generate_triage_markdown(actions_taken, len(initial_cycles))
    
    result = {
        "status": "PASS" if not final_cycles else "PARTIAL",
        "initial_edge_count": len(data.get("edges", [])),
        "normalized_edge_count": len(edges),
        "actions_taken_count": len(actions_taken),
        "actions": actions_taken,
        "remaining_cycles_count": len(final_cycles),
        "remaining_cycles": final_cycles,
        "triage_dossier_markdown": triage_md
    }
    
    if save:
        dest = Path(out_path) if out_path else p
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        result["saved_to"] = str(dest)
        
        md_dest = dest.parent / triage_md_path
        with open(md_dest, "w", encoding="utf-8") as f:
            f.write(triage_md)
        result["triage_dossier_saved_to"] = str(md_dest)
        
    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: cycle_breaker.py <path_to_work_graph.json> [--save] [--out <dest_path>] [--triage <triage_file.md>]")
        return
        
    graph_path = sys.argv[1]
    save = "--save" in sys.argv
    out_path = None
    triage_file = "CYCLE_REPAIR_TRIAGE.md"
    
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]
            
    if "--triage" in sys.argv:
        idx = sys.argv.index("--triage")
        if idx + 1 < len(sys.argv):
            triage_file = sys.argv[idx + 1]
            
    res = break_graph_cycles(graph_path, save=save, out_path=out_path, triage_md_path=triage_file)
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
