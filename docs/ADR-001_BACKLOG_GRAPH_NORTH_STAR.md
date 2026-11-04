# ADR-001: tare.tools.backlog-graph North Star — Deterministic Task DAG Engine and Topological Execution Framework

- **Status:** Accepted
- **Date:** 2026-08-17
- **Authors:** the maintainer, after a review with three AI models (Gemini, Claude and GPT)
- **Scope:** `tare.tools.backlog-graph` (standalone repository)

---

## 1. Context and motivation

Traditional task-management systems (Jira, Linear, GitHub Projects) work on **linear queues or flat Kanban boards** and ignore the topological structure inherent to software engineering. That approach causes three systemic problems:
1. **Blocker blindness:** it is hard to see the dependency chain that holds back critical deliveries;
2. **Blind prioritization:** P0 items blocked by forgotten secondary prerequisites;
3. **Frontier hallucination:** AI agents pick infeasible tasks because their preconditions are not satisfied.

**`tare.tools.backlog-graph`** solves this by turning the backlog into a **Directed Acyclic Graph (DAG)** with a deterministic computation of the executable work frontier.

---

## 2. Architectural decision

### A. Decoupling and zero dependencies (pure Python stdlib)
* `tare.tools.backlog-graph` is built **100% in pure Python (stdlib)** and runs without heavy dependencies in any CI/CD environment or local machine.
* Unit and integration tests cover schema validation, topological ordering, Tarjan cycle detection and reconciliation.

### B. Total ordering and mathematical determinism
* The execution frontier (`frontier` / `next`) follows a stable total order:
  $$\text{FrontierOrder} = \langle \text{Priority (P0 } > \text{ P1 } > \text{ P2)},\ -\text{CriticalPathDepth},\ \text{NodeID (lexicographic)} \rangle$$
* The `READY` state is **strictly derived**: a node becomes eligible if and only if all of its prerequisites are `DONE`.

### C. Canonical revision hash (RFC 8785 / JCS)
* The graph state is content-addressed:
  $$\text{revision\_hash} = \text{sha256}(\text{JCS\_CanonicalJSON}(\text{work-graph without revision}))$$

### D. CAS transaction with mutual exclusion
* Every mutation is serialized under an **exclusive lockfile (`.work-graph.json.lock`)** with a write to `.tmp`, `fsync` and an atomic `os.replace`.
* Concurrent landings based on a stale revision fail closed with `RevisionMismatchError`.

### E. Connectors
* One-way import from GitHub Issues, Linear, GitLab, Jira and Markdown task lists; export to JSON, Markdown, Mermaid, CSV, GraphML and a standalone HTML visualizer.

---

## 3. Implementation roadmap in 4 phases

1. **Phase 1 (core engine and validation):** topological algorithms, validation and the offline HTML visualizer.
2. **Phase 2 (one-way connectors and adapters):** ingestion of Jira/Linear/GitHub tickets and federated sub-graphs.
3. **Phase 3 (interactive visualizer and Copilot Bridge):** interactive canvas with *what-if* simulation and in-editor context injection.
4. **Phase 4 (distribution):** an official PyPI package (`pip install tare-tools-backlog-graph`) and a VS Code extension.
