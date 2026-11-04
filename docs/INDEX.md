# Documentation index — tare.tools.backlog-graph

> **Technical documentation, architecture and specifications of the deterministic task DAG engine.**

---

## 1. Architectural decisions and North Star
* **[`ADR-001_BACKLOG_GRAPH_NORTH_STAR.md`](ADR-001_BACKLOG_GRAPH_NORTH_STAR.md):** the North Star decision: stdlib-only engine, total frontier ordering, canonical revision hash and locked CAS transactions.

---

## 2. Architecture and ontology
* **[`ARCHITECTURE.md`](ARCHITECTURE.md):** the directed acyclic graph model, frontier and ranking algorithms, and mutation safety.
* **[`ONTOLOGY.md`](ONTOLOGY.md):** node kinds, completion statuses, blocking/dependency relations and evidence grades.
* **[`SPEC-BACKLOG-001.md`](SPEC-BACKLOG-001.md):** verifiable criteria for the DAG engine, incremental frontier, atomic reopen and CAS concurrency.

---

## 3. Guides and CLI reference
* **[`QUICKSTART.md`](QUICKSTART.md):** first steps and essential commands.
* **[`CLI_REFERENCE.md`](CLI_REFERENCE.md):** full reference of the CLI commands (`graph_ops.py`) and the validation/doctor options.
* **[`MANAGED_WORK_GUARD.md`](MANAGED_WORK_GUARD.md):** scope fence, drift blocking and a small guard against Zeno-style stagnation.
* **[`MUTATION_TESTING.md`](MUTATION_TESTING.md):** hermetic runner, PR canaries and broader qualification campaigns.
* **[`CHANGELOG_POLICY.md`](CHANGELOG_POLICY.md):** the append-only changelog rule and its guard.
* **[`guides/REPOSITORY_CONTENT.md`](guides/REPOSITORY_CONTENT.md):** what the repository contains, the synthetic fixtures and the removed historical records ([RECORDS_ARCHIVE.json](RECORDS_ARCHIVE.json)).
