import json

with open("work-graph.json", "r", encoding="utf-8") as f:
    g = json.load(f)

targets = {"p02", "x04", "relay-confinement", "remote-lanes-legacy"}
seen = set()
for e in g["edges"]:
    u, v, t = e["from"], e["to"], e.get("type")
    sem = e.get("semantic", False)
    if u in targets or v in targets:
        k = (u, v, t)
        if k not in seen:
            seen.add(k)
            print(f"{u} --({t}, semantic={sem})--> {v}")
