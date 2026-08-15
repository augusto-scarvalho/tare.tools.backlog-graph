# tare.tools — Graph Backlog

Deterministic **Directed Acyclic Graph (DAG) Backlog Engine**, dependency analyzer, and implementation packet generator for human developers and autonomous AI agents.

> **Origin:** This project was decoupled from the main repository (`universal-agent-harness-prototype`, [Issue #35](https://github.com/augusto-scarvalho/universal-agent-harness-prototype/issues/35) and [PR #38](https://github.com/augusto-scarvalho/universal-agent-harness-prototype/pull/38)), becoming an **independent side project** with zero required external dependencies (runs with pure Python 3.10+ stdlib).

---

## 🎯 Why Graph Backlog? (vs. Flat Lists & Traditional Kanban)

Flat lists and linear Kanban boards suffer from critical limitations in complex or AI agent-driven workflows:
1. **Lack of blocker visibility:** It is not immediately obvious which task unblocks what.
2. **Blind prioritization:** High-priority items can be completely blocked by forgotten low-priority dependencies.
3. **Inability to compute execution frontier:** A developer or AI agent must guess what can actually be worked on *now* without breaking contracts.

With **Graph Backlog**:
- **Deterministic `frontier`:** Instantly computes which tasks are ready for immediate execution (all prerequisites satisfied).
- **Blocker Analysis (`why` / `blockers`):** Explains the exact root cause why a task is blocked.
- **Impact Radius (`impact` / `deps`):** Traces the full downstream chain (what this task unblocks) and upstream ancestors (what it depends on).
- **Critical Path (`critical-path`):** Identifies the longest dependency bottleneck sequence in the project.
- **Implementation Packets (`packet`):** Compiles complete task context into Markdown to guide LLM prompts or code reviews.
- **What-If Simulation (`simulate`):** Projects which downstream tasks will be unblocked upon completing specific candidate work.
- **Interactive Web Visualizer:** Standalone local or exportable static HTML with real-time DAG canvas, 12 curated dark/light themes, and in-browser Microsoft 365 Copilot agentic bridge.

---

## 🚀 Quickstart & Installation

### Zero Dependencies (Pure Python Stdlib)
You can run it directly without installing any third-party dependencies:
```bash
python graph_ops.py --graph fixtures/sample-backlog.json summary
python graph_ops.py --graph fixtures/sample-backlog.json frontier --format ids
```

### Install as a Python Package
```bash
pip install -e .
```
Once installed, the `graph-backlog` and `graph-ops` commands become globally available in your terminal.

---

## ⚡ CLI Command Cheat Sheet

| Command | What it answers | Example |
|---|---|---|
| `validate` | Are the graph schema and DAG structure valid? | `python graph_ops.py validate` |
| `summary` | How many tasks, clusters, and status counts exist? | `python graph_ops.py summary` |
| `frontier` | What is ready to be executed **right now**? | `python graph_ops.py frontier --format ids` |
| `next` | What is the highest-ranked feasible task to pull? | `python graph_ops.py next --limit 5` |
| `why <id>` | Why is a task ready or blocked? | `python graph_ops.py why TASK-03` |
| `blockers <id>` | Which direct prerequisites block `<id>`? | `python graph_ops.py blockers TASK-03` |
| `deps <id>` | What are all transitive upstream prerequisites? | `python graph_ops.py deps TASK-03` |
| `impact <id>` | Which tasks will be unblocked in the future? | `python graph_ops.py impact TASK-01` |
| `path <a> <b>` | What is the dependency path from `A` to `B`? | `python graph_ops.py path TASK-01 TASK-03` |
| `critical-path` | What is the longest bottleneck sequence? | `python graph_ops.py critical-path` |
| `packet <id>` | Generates complete Markdown context for prompts | `python graph_ops.py packet TASK-02 --format md` |
| `simulate` | What unblocks if we complete `<id>`? | `python graph_ops.py simulate --mode complete --complete TASK-02` |
| `diff <other>` | What changed semantically between 2 versions? | `python graph_ops.py diff other-graph.json` |
| `doctor` | Full health, integrity, and cycle audit report | `python graph_ops.py doctor` |
| `export` | Exports to interactive HTML, JSON, or Markdown | `python graph_ops.py export --output backlog.html` |
| `visualize` | Starts local web server with DAG visualizer | `python graph_ops.py visualize --port 8080` |
| `import-github` | Ingests GitHub Issues JSON / piped stdin | `gh issue list --json ... \| python graph_ops.py import-github` |
| `import-linear` | Ingests Linear CSV or JSON export payloads | `python graph_ops.py import-linear export.csv` |
| `import-gitlab` | Ingests GitLab Issues JSON / piped stdin | `glab issue list --output json \| python graph_ops.py import-gitlab` |
| `import-md` | Ingests Markdown tasklists with `(depends: ...)` | `python graph_ops.py import-md backlog.md` |

---

## 💻 Python Library Usage

```python
from graph_backlog import WorkGraph, compute_frontier, ranked_next, generate_packet

# 1. Load work graph
graph = WorkGraph.from_file("fixtures/sample-backlog.json")

# 2. Query actionable frontier tasks
ready_tasks = compute_frontier(graph)
print(f"Frontier tasks: {[t['id'] for t in ready_tasks]}")

# 3. Deterministic multi-criteria priority ranking
top_work = ranked_next(graph, limit=3)
print(f"Top recommendation: {top_work[0]['id']} (score: {top_work[0]['score']})")

# 4. Generate Markdown implementation packet
packet = generate_packet(graph, "TASK-02")
from graph_backlog.packet import format_packet_markdown
print(format_packet_markdown(packet))
```

---

## 📊 Repository Structure

```text
tare.tools.graph-backlog/
├── README.md                      # General documentation
├── pyproject.toml                 # Packaging and build configuration
├── graph_ops.py                   # Direct zero-config CLI executable
├── src/
│   └── graph_backlog/             # Core Python package
│       ├── __init__.py            # API exports
│       ├── core.py                # Data model (WorkGraph, Node, Edge)
│       ├── algorithms.py          # Frontier, cycles (Tarjan SCC), paths, ranking
│       ├── validation.py          # Structural, schema, and integrity validation
│       ├── diff.py                # Semantic diff and mutation verification
│       ├── ledger.py              # Append-only cryptographic audit ledger
│       ├── simulation.py          # What-if counterfactual overlays
│       ├── packet.py              # Implementation packet compiler
│       ├── visualizer.py          # HTML exporter and interactive web visualizer
│       └── cli.py                 # CLI argument parser and dispatcher
├── docs/
│   ├── ARCHITECTURE.md            # Conceptual model and architectural decisions
│   ├── CLI_REFERENCE.md           # Full reference of all CLI subcommands
│   ├── QUICKSTART.md              # 5-minute step-by-step tutorial
│   └── ONTOLOGY.md                # Relation taxonomy and vocabulary
├── fixtures/                      # Sample work graphs and test fixtures
│   ├── sample-backlog.json        # Core 3-node starter backlog
│   ├── saas-backlog.json          # CloudPulse SaaS backlog (33 nodes)
│   ├── rag-chatbot-backlog.json   # AI RAG pipeline backlog (27 nodes)
│   ├── transmedia-book-comic-film-backlog.json # Epic transmedia saga (42 nodes)
│   ├── work-graph-v0.5.json       # Canonical specification graph
│   └── negative-*.json            # Edge-case error validation fixtures
├── visualizer/
│   └── index.html                 # Standalone interactive visualizer artifact
└── tests/                         # Automated test suite (100% passing)
```

---

## 🧪 Automated Testing

To run the complete test suite:
```bash
python -m unittest discover -s tests -v
# or with pytest
pytest
```

---

## 📄 License

MIT License.
