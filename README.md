# tare.tools.backlog-graph

A backlog kept as a dependency graph. It tells which work is ready now, what blocks the rest and what finishing an
item would unlock, and it compiles a self-contained brief for whoever takes an item, a person or a coding agent.
Python 3.10 or newer, standard library only.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![CI](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/actions/workflows/ci.yml)

🇧🇷 [Leia em português](README.pt-BR.md)

---

## What it does

The backlog is a JSON work graph: items with a status, priority (`P0`–`P3`), horizon (`H0`–`H3`), criticality and
definition of done, linked by typed dependency edges. On it the engine computes:

- **Ready work** (`frontier`, `next`): the open items whose prerequisites are all done, ranked by priority, horizon
  and how much downstream work each one unlocks.
- **Blockers and reach** (`why`, `blockers`, `deps`, `impact`, `path`, `critical-path`): direct and transitive
  prerequisites, downstream dependents, the shortest dependency path between two items and the longest chain of
  open work.
- **Implementation packets** (`packet`): a Markdown brief of one item with its context, prerequisites and definition
  of done.
- **Managed-work grounding** (`ground`): canonical, byte-bounded JSON, only for operationally ready work with
  explicit exit criteria. Its execution-scope digest changes when the item, incident dependencies, direct
  prerequisites or referenced sources change, so a managed runtime can stop on drift. It grants no Authority and
  never writes the canonical backlog ([`docs/MANAGED_WORK_GUARD.md`](docs/MANAGED_WORK_GUARD.md)).
- **What-if** (`simulate`): which items would become ready if candidate items were completed, without changing the
  graph.
- **Checks** (`validate`, `doctor`): schema and integrity validation, cycles (Tarjan's strongly connected
  components), dangling references, orphaned requirements and gaps in evidence grades.
- **History**: changes run as locked compare-and-swap transactions on the graph's revision hash, and an append-only
  ledger chains each event to the previous one by SHA-256, so editing or removing an earlier event breaks the chain.
- **Views** (`export`, `visualize`): a standalone HTML viewer, and JSON, Markdown, Mermaid, CSV and GraphML exports.

---

## Importing a backlog

The importers read exports from other tools and need no extra packages:

```bash
# GitHub Issues (reads via GitHub CLI or JSON export)
gh issue list --limit 100 --json number,title,body,labels,state | python graph_ops.py import-github --out work-graph.json

# Linear (reads from Linear CSV export or GraphQL/JSON API)
python graph_ops.py import-linear linear-export.csv --out work-graph.json

# GitLab Issues (reads via GitLab CLI or JSON export)
glab issue list --output json | python graph_ops.py import-gitlab --out work-graph.json

# Jira Cloud & Server (reads from Jira CSV export or REST API search JSON)
python graph_ops.py import-jira jira-export.csv --out work-graph.json

# Markdown Tasklists (reads checklists with dependency annotations)
python graph_ops.py import-md backlog.md --out work-graph.json
```

---

## Quickstart and Installation

### What you need
- Python 3.10 or newer. The engine uses only the standard library.
- Git, to clone the repository.
- For the tests: `pytest` (installed by the `dev` extra below).

### Run without installing
`graph_ops.py` puts `src/` on the import path, so a fresh clone runs directly:
```bash
git clone https://github.com/augusto-scarvalho/tare.tools.backlog-graph.git
cd tare.tools.backlog-graph

# Inspect graph summary
python graph_ops.py --graph fixtures/sample-backlog.json summary

# Query ready execution frontier
python graph_ops.py --graph fixtures/sample-backlog.json frontier --format ids

# Pull top recommended task
python graph_ops.py --graph fixtures/sample-backlog.json next --limit 1
```

### Install as a package
In a virtual environment, from the repository root:
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
```
After installation, the `backlog`, `graph-backlog` and `graph-ops` commands become available in the environment path. They are the same CLI as `python graph_ops.py`.

---

## CLI Command Reference

Every command reads the graph given by `--graph <file>` (default: `work-graph.json` in the current directory). The examples below assume such a file; add `--graph fixtures/sample-backlog.json` to try them on the bundled sample.

| Subcommand | Purpose and Output | Example Usage |
|---|---|---|
| `validate` | Validates graph schema, DAG integrity, and absence of cycles | `python graph_ops.py validate` |
| `summary` | Computes metric counts across clusters, statuses, and frontier | `python graph_ops.py summary` |
| `frontier` | Computes all ready tasks with satisfied dependencies | `python graph_ops.py frontier --format ids` |
| `next` | Ranks actionable tasks by priority, horizon, and unlock score | `python graph_ops.py next --limit 3` |
| `why <id>` | Explains why a task is ready or blocked, listing prerequisites | `python graph_ops.py why TASK-03` |
| `blockers <id>` | Lists direct unsatisfied prerequisite blockers | `python graph_ops.py blockers TASK-03` |
| `deps <id>` | Computes all transitive upstream dependencies | `python graph_ops.py deps TASK-03 --format md` |
| `impact <id>` | Computes all downstream dependents unlocked by `<id>` | `python graph_ops.py impact TASK-01` |
| `path <a> <b>` | Computes the shortest dependency path from `A` to `B` | `python graph_ops.py path TASK-01 TASK-03` |
| `critical-path` | Calculates the longest bottleneck sequence in the DAG | `python graph_ops.py critical-path` |
| `packet <id>` | Compiles self-contained Markdown prompt context for AI agents | `python graph_ops.py packet TASK-02 --format md` |
| `ground <id>` | Emits bounded operational JSON and an execution-scope fence | `python graph_ops.py --format json ground TASK-02 --work-graph fixtures/sample-backlog.json` |
| `simulate` | Projects frontier changes when completing candidate work | `python graph_ops.py simulate --complete TASK-02` |
| `diff <other>` | Computes deep semantic diff between two graph snapshots | `python graph_ops.py diff previous-graph.json` |
| `doctor` | Runs structural, cycle, evidence, and reconciliation audit | `python graph_ops.py doctor` |
| `export` | Exports to standalone HTML visualizer, JSON, Markdown, Mermaid, CSV, or GraphML | `python graph_ops.py export -o index.html --export-format html` |
| `visualize` | Starts local web server with interactive DAG UI | `python graph_ops.py visualize --port 8080` |
| `import-github` | Ingests GitHub Issues JSON / piped stdin into DAG graph | `python graph_ops.py import-github issues.json` |
| `import-linear` | Ingests Linear CSV or JSON export payloads | `python graph_ops.py import-linear export.csv` |
| `import-gitlab` | Ingests GitLab Issues JSON / piped stdin into DAG graph | `python graph_ops.py import-gitlab gitlab.json` |
| `import-jira` | Ingests Jira CSV export or REST API search JSON | `python graph_ops.py import-jira jira.csv` |
| `import-md` | Ingests structured Markdown tasklists (`backlog.md`) | `python graph_ops.py import-md backlog.md` |

The full list, including the mutation commands (`add-node`, `complete-node`, `land`, `supersede`), is in [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md).

---

## Python Library API

The same engine as a Python library:

```python
from graph_backlog import (
    WorkGraph,
    compute_frontier,
    ranked_next,
    generate_packet,
    critical_path,
    simulate_completions
)
from graph_backlog.packet import format_packet_markdown

# 1. Load work graph
graph = WorkGraph.from_file("fixtures/saas-backlog.json")

# 2. Compute actionable execution frontier
ready_tasks = compute_frontier(graph)
print(f"Ready to execute: {[t['id'] for t in ready_tasks]}")

# 3. Deterministic ranking
top_work = ranked_next(graph, limit=1)
target_task_id = top_work[0]["id"]
print(f"Next recommended task: {target_task_id} (Score: {top_work[0]['score']})")

# 4. Generate implementation packet for AI prompt context
packet = generate_packet(graph, target_task_id)
markdown_prompt = format_packet_markdown(packet)
print(markdown_prompt)

# 5. Counterfactual What-If simulation
sim = simulate_completions(graph, [target_task_id])
print(f"Newly unlocked tasks: {sim['newly_unlocked_nodes']}")
```

---

## The HTML viewer

`export --export-format html` and `visualize` produce a standalone page, with no framework, for any graph;
[`visualizer/index.html`](visualizer/index.html) is a pre-built copy that opens on the synthetic
`fixtures/work-graph-v0.5.json` and also carries the demo backlogs. It has three views (dependency graph, Kanban
board, clusters), twelve color themes (six dark, six light) and a panel with the analysis tools, the what-if sandbox
and the ledger.

### Reading the graph from a script in the browser

1. **`window.tareGraph`**, from the DevTools console or a browser assistant:
   ```javascript
   window.tareGraph.getSummary();
   window.tareGraph.getFrontier();
   window.tareGraph.getCriticalPath();
   window.tareGraph.simulate(["AUTH-01"], true);
   ```
2. **A JSON manifest in the page**, `<script id="signal-agentic-manifest" type="application/json">`, kept in step
   with the graph, so a script can read its structure without parsing the SVG.
3. **A briefing prompt**: text that summarizes the current bottlenecks and ready items, to paste into an assistant.

---

## In CI and with coding agents

### A GitHub Actions check
```yaml
name: Work Graph Quality Gate
on: [pull_request, push]

jobs:
  graph-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Validate DAG & Check Cycles
        run: |
          python graph_ops.py --graph work-graph.json doctor
          python graph_ops.py --graph work-graph.json validate
```

### Handing a ready item to a coding agent
```bash
# Compile the brief of the first ready item:
NEXT_ID=$(python graph_ops.py frontier --format ids | head -n 1)
python graph_ops.py packet $NEXT_ID --format md > .agent/current-context.md
```

---

## Use in tare.tools.os

[tare.tools.os](https://github.com/augusto-scarvalho/tare.tools.os) pins this repository as a Git submodule at
`satellites/tare.tools.backlog-graph` and installs it as the `tare-tools-backlog-graph` package. The OS uses it for
work-graph validation, revision hashes and compare-and-swap graph transactions, ranking and readiness, and managed-work
grounding. This repository stays usable on its own: nothing here imports the OS.

---

## Repository Structure

```text
tare.tools.backlog-graph/
├── README.md / README.pt-BR.md    # English and Brazilian-Portuguese documentation
├── LICENSE, NOTICE                # Apache License 2.0 and attribution
├── CHANGELOG.md                   # Append-only change record
├── pyproject.toml                 # Package configuration
├── graph_ops.py                   # Zero-config direct CLI executable
├── src/
│   └── graph_backlog/             # Core Python package
│       ├── core.py                # Data model (WorkGraph) and default policy loading
│       ├── algorithms.py          # Frontier, cycles (Tarjan SCC), paths, ranking
│       ├── validation.py          # Structural, schema, and integrity validation
│       ├── mutations.py           # Locked compare-and-swap graph transactions
│       ├── grounding.py           # Managed-work grounding (`ground`)
│       ├── diff.py                # Semantic diff and mutation verification
│       ├── ledger.py              # Append-only hash-chained audit ledger
│       ├── simulation.py          # Counterfactual what-if overlays
│       ├── packet.py              # Implementation packet compiler
│       ├── adapters.py            # GitHub, Linear, GitLab, Jira, Markdown, Mermaid, CSV, GraphML adapters
│       ├── visualizer.py          # HTML exporter and interactive web visualizer
│       ├── cli.py                 # CLI argument parser and dispatcher
│       └── contracts/             # Packaged copies of the policies and schemas
├── policies/, schemas/            # Relation taxonomy, graph-ops policy, JSON schemas
├── ontology/                      # Machine-readable domain ontology
├── docs/                          # Architecture, ontology, CLI reference, guides (see docs/INDEX.md)
├── fixtures/                      # Synthetic work graphs used by tests and demos
│   ├── sample-backlog.json        # Core 3-node starter backlog
│   ├── work-graph-v0.5.json       # Full v0.5 schema example (fictional notes app)
│   ├── saas-backlog.json          # CloudPulse SaaS backlog (33 nodes)
│   ├── crm-rag-chatbot-backlog.json # AI RAG pipeline backlog (27 nodes)
│   ├── transmedia-book-comic-film-backlog.json # Epic transmedia saga (42 nodes)
│   └── negative-*.json            # One defect each: dangling edge, self loop, invalid status, ...
├── visualizer/index.html          # Pre-built standalone visualizer
├── scripts/                       # Graph diagnostics, cycle breaker, topology report
├── tools/                         # Changelog guard and Git hook installer
└── tests/                         # Offline test suite
```

Every graph under `fixtures/` is synthetic. [docs/guides/REPOSITORY_CONTENT.md](docs/guides/REPOSITORY_CONTENT.md)
explains what the tree contains and where removed historical records are listed.

---

## Automated Testing

With the `dev` extra installed (see [Install as a package](#install-as-a-package)), run the same commands as CI:
```bash
# Hermetic mutation canaries (a few minutes)
python -m pytest tests/test_mutation_testing.py -v

# Main test suite
python -m pytest tests/ -v --ignore=tests/test_mutation_testing.py

# Changelog guard tests
python -m unittest discover -s tools/tests -p "test_changelog_guard.py"
```

The tests are offline and use only the bundled fixtures and temporary directories. The browser end-to-end test in
`tests/test_e2e_visualizer.py` is skipped unless Playwright is installed.

The bounded PR canaries and broader manual mutation campaigns are documented
in [docs/MUTATION_TESTING.md](docs/MUTATION_TESTING.md).

---

## License and Attribution

Licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.

### Author
- **Author:** Augusto Carvalho ([augusto-scarvalho@users.noreply.github.com](mailto:augusto-scarvalho@users.noreply.github.com))
- **Project:** [tare.tools.backlog-graph](https://github.com/augusto-scarvalho/tare.tools.backlog-graph)
- **Origin:** Extracted from the tare.tools agent harness research prototype.
