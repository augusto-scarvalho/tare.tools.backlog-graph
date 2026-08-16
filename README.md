<div align="center">

# tare.tools — Graph Backlog

**Deterministic Directed Acyclic Graph (DAG) Backlog Engine and Topological Execution Framework for Software Engineering Teams and Autonomous AI Agents.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Pure%20Stdlib)-orange.svg)](#zero-dependencies-pure-python-stdlib)
[![Tests](https://img.shields.io/badge/Tests-47%20Passed%20(100%25)-success.svg)](#automated-testing)
[![Agentic Protocol](https://img.shields.io/badge/Agentic%20Protocol-tare.tools%2Fv1-purple.svg)](#in-browser-ai-agent-discovery-and-copilot-bridge)

<p align="center">
  <a href="#why-graph-backlog-the-paradigm-shift">Why Graph Backlogs</a> •
  <a href="#key-architectural-pillars">Key Features</a> •
  <a href="#third-party-backlog-ingestion">Integrations and Adapters</a> •
  <a href="#quickstart-and-installation">Quickstart</a> •
  <a href="#cli-command-reference">CLI Reference</a> •
  <a href="#python-library-api">Python Library</a> •
  <a href="#interactive-mission-control-and-copilot-bridge">Interactive UI</a> •
  <a href="#license-and-attribution">License</a>
</p>

</div>

---

## Why Graph Backlog? (The Paradigm Shift)

Modern software delivery is a **topological dependency graph**, not a flat list or an unconstrained Kanban column.

When autonomous AI agents (Copilot, Claude, Devin) and multi-developer teams work on complex codebases using traditional issue trackers (Jira, Linear, GitHub Projects), they face three systemic failures:

1. **Blocker Blindness:** It is not immediately obvious which task unblocks downstream milestones or why a high-priority task cannot be started.
2. **Blind Prioritization:** Critical-priority items (`P0`) are frequently stalled because low-priority prerequisites were forgotten or buried in the backlog.
3. **Execution Frontier Hallucination:** Agents and engineers must guess what is truly feasible to implement *right now* without breaking contractual dependencies.

```text
TRADITIONAL FLAT BACKLOG (Blind Linear Queue)
[Task A] ---> [Task B] ---> [Task C] ---> [Task D]   [!] No dependency awareness, arbitrary ordering.

DAG GRAPH BACKLOG (Deterministic Topological Execution)
   +---> [DB Schema] (DONE) ---> [Auth API] (READY / FRONTIER) --->+
   |                                                               |
[Core Setup] (DONE) ------------------------------> [User Portal] (BLOCKED)
   |                                                               ^
   +---> [Stripe Vault] (IN_PROGRESS) ---> [Checkout Webhook] -----+
```

### Comparative Analysis

| Capability | Flat Lists & Linear Kanban | tare.tools Graph Backlog |
|---|---|---|
| **Execution Frontier (`frontier`)** | Manual guesswork | **Deterministic mathematical computation** (all prerequisites provably satisfied) |
| **Root-Cause Analysis (`why`)** | Manual reading of ticket comments | **Instant automated blocker resolution and dependency tree** |
| **Critical Path Analysis (`critical-path`)** | Not computable | **Exact longest bottleneck chain identification** |
| **Agent Implementation Packets (`packet`)** | Ad-hoc copy-pasting of issue descriptions | **Fully compiled Markdown context with DoD and grounding** |
| **What-If Simulation (`simulate`)** | Impossible without altering production state | **Counterfactual topological projection overlay** |
| **Auditability and Governance (`ledger`)** | Destructive state transitions | **Append-only SHA-256 Merkle audit trail** |
| **Runtime Dependencies** | Heavy server or complex SDKs | **Zero external dependencies (pure Python 3.10+ stdlib)** |

---

## Key Architectural Pillars

### 1. Deterministic Ready Frontier
Calculates the exact subset of non-completed nodes whose upstream dependencies are 100% satisfied (`DONE` with Definition of Done verified). Agents and developers always pull mathematically sound work.

### 2. Multi-Criteria Ranked Pull Engine
Ranks eligible frontier work using deterministic multi-criteria scoring balancing business priority (`P0`–`P3`), execution horizon (`H0`–`H3`), and downstream unlock impact (unlock score).

### 3. Root-Cause Blocker and Impact Tracing
- **`why <id>` and `blockers <id>`:** Pinpoints the exact prerequisite bottlenecks preventing a task from moving forward.
- **`impact <id>` and `deps <id>`:** Traces complete downstream and upstream topological reach across all transitive relations.
- **`path <a> <b>`:** Computes the shortest dependency path between any two tasks.

### 4. Implementation Packet Compiler
Compiles self-contained, high-signal Markdown implementation packets ready for LLM prompts, agentic sidecars, and automated code review pipelines.

### 5. Counterfactual "What-If" Simulation
Simulates the downstream impact of marking candidate tasks as completed *before writing code*, projecting exactly which tasks will be unlocked next.

### 6. Cryptographic Audit Ledger (Merkle Hash Chain)
Maintains an append-only cryptographic event ledger sealed with SHA-256 hashes (`event_hash = SHA256(index + timestamp + prev_hash + canonical_json(payload))`), ensuring tamper-evident history and non-repudiation across multi-agent workflows.

### 7. Automated Graph Doctor and Integrity Audits
Detects topological cycles (Tarjan Strongly Connected Components), dangling edge references, orphaned requirements, and epistemic gaps in evidence grades.

---

## Third-Party Backlog Ingestion

Ingest real-world backlogs from existing tools using standard CLI pipelines with **zero external dependencies**:

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

### Zero Dependencies (Pure Python Stdlib)
Run `graph_ops.py` directly without installing third-party packages:
```bash
# Inspect graph summary
python graph_ops.py --graph fixtures/sample-backlog.json summary

# Query ready execution frontier
python graph_ops.py --graph fixtures/sample-backlog.json frontier --format ids

# Pull top recommended task
python graph_ops.py --graph fixtures/sample-backlog.json next --limit 1
```

### Install as a Global Package
```bash
pip install -e .
```
After installation, both `graph-backlog` and `graph-ops` executables become available in the environment path.

---

## CLI Command Reference

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
| `simulate` | Projects frontier changes when completing candidate work | `python graph_ops.py simulate --complete TASK-02` |
| `diff <other>` | Computes deep semantic diff between two graph snapshots | `python graph_ops.py diff previous-graph.json` |
| `doctor` | Runs structural, cycle, evidence, and reconciliation audit | `python graph_ops.py doctor` |
| `export` | Exports to standalone HTML visualizer, JSON, or Markdown | `python graph_ops.py export -o index.html --export-format html` |
| `visualize` | Starts local web server with interactive DAG UI | `python graph_ops.py visualize --port 8080` |
| `import-github` | Ingests GitHub Issues JSON / piped stdin into DAG graph | `python graph_ops.py import-github issues.json` |
| `import-linear` | Ingests Linear CSV or JSON export payloads | `python graph_ops.py import-linear export.csv` |
| `import-gitlab` | Ingests GitLab Issues JSON / piped stdin into DAG graph | `python graph_ops.py import-gitlab gitlab.json` |
| `import-jira` | Ingests Jira CSV export or REST API search JSON | `python graph_ops.py import-jira jira.csv` |
| `import-md` | Ingests structured Markdown tasklists (`backlog.md`) | `python graph_ops.py import-md backlog.md` |

---

## Python Library API

Use `graph_backlog` as an embedded Python engine inside custom agents, orchestrators, and CI scripts:

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
sim = simulate_completions(graph, completed_ids=[target_task_id])
print(f"Newly unlocked tasks: {sim['newly_unlocked']}")
```

---

## Interactive Mission Control and Copilot Bridge

The project includes an **interactive, zero-framework, standalone HTML visualizer** (`visualizer/index.html`):

- **3 Canvas Modes:** Dynamic DAG Physics Canvas, Kanban Board, and Domain Clusters.
- **12 Curated Themes:** 
  - *Dark:* Signal Mission Control (Default), Dracula, Tokyo Night, Nord Frost, Monokai Pro, Catppuccin Mocha.
  - *Light:* Solar Paper, Solarized Light, GitHub Light, Nord Snow Storm, Catppuccin Latte, Gruvbox Light.
- **Graph Operations Station:** Modal station featuring 13 analysis tools, What-If Simulation sandbox, and Merkle Crypto Ledger.

### In-Browser AI Agent Discovery and Copilot Bridge

The visualizer provides native **Agentic Discovery Protocols** designed for browser-based AI assistants (such as Microsoft 365 Copilot, Edge Sidecar, and DevTools agents):

1. **Global Runtime API (`window.tareGraph`):**
   ```javascript
   // Query graph summary and ready frontier directly in DevTools console or agent runtime:
   window.tareGraph.getSummary();
   window.tareGraph.getFrontier();
   window.tareGraph.getCriticalPath();
   window.tareGraph.simulate(["AUTH-01"], true);
   ```
2. **In-DOM JSON Manifest:** Real-time synchronized `<script id="signal-agentic-manifest" type="application/json">` allowing AI scrapers to ingest topological structure without parsing SVG elements.
3. **Context Prompts:** Generates pre-formatted Copilot briefing prompts summarizing active bottlenecks and ready tasks.

---

## CI/CD and Autonomous Agent Orchestration

### Automated PR Audit Workflow (GitHub Actions)
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

### Feeding Context to LLM Agents (Claude / Devin / Copilot)
```bash
# Extract the highest-ranked ready task and compile prompt context:
NEXT_ID=$(python graph_ops.py frontier --format ids | head -n 1)
python graph_ops.py packet $NEXT_ID --format md > .agent/current-context.md
```

---

## Repository Structure

```text
tare.tools.graph-backlog/
├── README.md                      # General documentation
├── LICENSE                        # Apache License 2.0
├── NOTICE                         # Formal attribution and author copyright notice
├── pyproject.toml                 # Package configuration
├── graph_ops.py                   # Zero-config direct CLI executable
├── src/
│   └── graph_backlog/             # Core Python package
│       ├── __init__.py            # API exports
│       ├── core.py                # Data model (WorkGraph, Node, Edge)
│       ├── algorithms.py          # Frontier, cycles (Tarjan SCC), paths, ranking
│       ├── validation.py          # Structural, schema, and integrity validation
│       ├── diff.py                # Semantic diff and mutation verification
│       ├── ledger.py              # Append-only cryptographic audit ledger (SHA-256)
│       ├── simulation.py          # Counterfactual what-if overlays
│       ├── packet.py              # Implementation packet compiler
│       ├── adapters.py            # GitHub, Linear, GitLab, Jira, Markdown, CSV adapters
│       ├── visualizer.py          # HTML exporter and interactive web visualizer
│       └── cli.py                 # CLI argument parser and dispatcher
├── docs/
│   ├── ARCHITECTURE.md            # Conceptual architecture and design decisions
│   ├── CLI_REFERENCE.md           # Full reference of all CLI subcommands
│   ├── QUICKSTART.md              # 5-minute step-by-step tutorial
│   └── ONTOLOGY.md                # Relation taxonomy and vocabulary
├── fixtures/                      # Work graph fixtures and test sets
│   ├── sample-backlog.json        # Core 3-node starter backlog
│   ├── saas-backlog.json          # CloudPulse SaaS backlog (33 nodes)
│   ├── rag-chatbot-backlog.json   # AI RAG pipeline backlog (27 nodes)
│   ├── transmedia-book-comic-film-backlog.json # Epic transmedia saga (42 nodes)
│   └── negative-*.json            # Edge-case error validation fixtures
├── visualizer/
│   └── index.html                 # Standalone interactive visualizer artifact
└── tests/                         # Automated test suite (100% passing)
    ├── test_algorithms.py         # Algorithm tests (Tarjan, frontier, critical path)
    ├── test_validation.py         # Schema, structural, and evidence validation
    ├── test_diff_and_ledger.py    # Diffing, simulation, and crypto ledger tests
    ├── test_external_adapters.py  # GitHub, Linear, GitLab, Jira, Markdown tests
    ├── test_e2e_visualizer.py     # Playwright E2E visualizer & Copilot tests
    └── test_mutation_testing.py   # AST mutation resilience testing
```

---

## Automated Testing

Run the full automated test suite:
```bash
# Using pytest
pytest

# Or using unittest (pure stdlib)
python -m unittest discover -s tests -v
```

---

## License and Attribution

Licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.

### Author and Research Origin
- **Author:** Augusto Carvalho ([augusto-scarvalho@users.noreply.github.com](mailto:augusto-scarvalho@users.noreply.github.com))
- **Project:** [tare.tools.graph-backlog](https://github.com/augusto-scarvalho/tare.tools.graph-backlog)
- **Origin:** Decoupled from the Universal Agent Harness research initiative ([Issue #35](https://github.com/augusto-scarvalho/universal-agent-harness-prototype/issues/35) / [PR #38](https://github.com/augusto-scarvalho/universal-agent-harness-prototype/pull/38)).
