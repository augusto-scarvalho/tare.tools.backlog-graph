import json
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("work-graph.json", "r", encoding="utf-8") as f:
    g = json.load(f)

nodes = {n["id"]: n for n in g.get("nodes", [])}
edges = g.get("edges", [])

in_edges = defaultdict(list)
out_edges = defaultdict(list)

for e in edges:
    in_edges[e["to"]].append(e)
    out_edges[e["from"]].append(e)

not_done = [n for n in nodes.values() if (n.get("completion") or {}).get("status") != "DONE"]

print("=== 1. ROOTS (In-Degree = 0) - NOT_DONE ===")
for n in not_done:
    nid = n["id"]
    if len(in_edges[nid]) == 0:
        outs = [e["to"] for e in out_edges[nid]]
        print(f"\nNode: [{nid}]")
        print(f"  Title: {n.get('title')}")
        print(f"  Cluster: {n.get('cluster')} | P: {n.get('priority')} | H: {n.get('horizon')}")
        print(f"  Summary: {n.get('summary')}")
        print(f"  Feeds into ({len(outs)}): {outs}")

print("\n" + "="*60)
print("=== 2. LEAVES (Out-Degree = 0) - NOT_DONE ===")
for n in not_done:
    nid = n["id"]
    if len(out_edges[nid]) == 0:
        ins = [e["from"] for e in in_edges[nid]]
        print(f"\nNode: [{nid}]")
        print(f"  Title: {n.get('title')}")
        print(f"  Cluster: {n.get('cluster')} | P: {n.get('priority')} | H: {n.get('horizon')}")
        print(f"  Summary: {n.get('summary')}")
        print(f"  Blocked by ({len(ins)}): {ins}")
