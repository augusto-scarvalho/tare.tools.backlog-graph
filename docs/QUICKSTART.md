# Quickstart Guide

This guide gets you up and running with **Graph Backlog** in under 5 minutes.

---

## 1. Inspect an Existing Backlog

Use the bundled sample backlog:
```bash
# Check summary statistics
python graph_ops.py --graph fixtures/sample-backlog.json summary

# See what is ready to work on right now
python graph_ops.py --graph fixtures/sample-backlog.json frontier

# See the ranked top recommendation
python graph_ops.py --graph fixtures/sample-backlog.json next --limit 1
```

---

## 2. Understand Dependencies

If a task is blocked, ask the graph why:
```bash
python graph_ops.py --graph fixtures/sample-backlog.json why TASK-03
```
Output shows:
```json
{
  "id": "TASK-03",
  "title": "Create User Interface Dashboard",
  "profile": "planning",
  "ready": false,
  "reasons": [
    "unresolved_prerequisites"
  ],
  "unresolved_prerequisites": [
    {
      "id": "TASK-02",
      "title": "Build Core Business API",
      "completion": "NOT_DONE",
      "edge_type": "UNLOCKS",
      "satisfied": false
    }
  ]
}
```

---

## 3. Generate Agent Prompt / Implementation Packet

Compile full context for task execution:
```bash
python graph_ops.py --graph fixtures/sample-backlog.json packet TASK-02 --format md
```

---

## 4. Visualize the Backlog in Browser

Open the interactive visualizer:
```bash
# Option A: Start local HTTP server
python graph_ops.py --graph fixtures/sample-backlog.json visualize

# Option B: Export standalone HTML and open directly
python graph_ops.py --graph fixtures/sample-backlog.json export --output my-backlog.html
```

---

## 5. Integrating with Python Code

```python
from graph_backlog import WorkGraph, compute_frontier, ranked_next

graph = WorkGraph.from_file("fixtures/sample-backlog.json")
frontier = compute_frontier(graph)

for task in frontier:
    print(f"Ready: {task['id']} - {task['title']}")
```
