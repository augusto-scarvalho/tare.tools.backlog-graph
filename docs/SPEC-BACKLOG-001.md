# SPEC-BACKLOG-001: Mathematical Task DAG and atomic CAS concurrency

- **Status:** `CANONICAL_SSOT`
- **Canonical repository:** `tare.tools.backlog-graph`
- **Governing decision:** [ADR-001](ADR-001_BACKLOG_GRAPH_NORTH_STAR.md)
- **Version:** 1.0.0
- **Relocated from:** `tare.tools.library@d5473e69:specs/SPEC-BACKLOG-001.md`

## Purpose

Define the deterministic task-DAG engine, its finite lifecycle, constant-time
execution frontier and atomic reopen propagation.

## Verifiable acceptance criteria

- **AC-01 — Pure Python standard-library core:** the critical graph engine has
  no heavyweight runtime dependency such as NetworkX.
- **AC-02 — O(1) execution frontier:** eligible work is maintained incrementally
  as graph mutations resolve or reopen prerequisites.
- **AC-03 — Atomic reopen cascade:** reopening a parent invalidates completed
  descendants in the same transaction.
- **AC-04 — CAS-leased transitions:** state changes require the expected
  `task_version`, preventing unordered concurrent writes.

