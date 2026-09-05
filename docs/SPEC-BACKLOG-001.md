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

## Python implementation reconciliation — 2026-09-05

The criteria above are preserved, not silently weakened to match implementation.
This note records the standalone Python baseline at `60bf2e8`; it neither amends
the governing ADR nor qualifies the local Rust port.

| Criterion | Observed Python contract | Disposition |
|---|---|---|
| AC-01 | Core uses the Python standard library. | Implemented. |
| AC-02 | `compute_frontier` visits nodes and sorts eligible work; `ranked_next` limits the result afterward. | Deterministic selection exists; incremental O(1) selection is not established. |
| AC-03 | The public mutation surface provides add, complete, land and supersede. | No dedicated atomic reopen-cascade implementation was found in that surface. |
| AC-04 | `execute_graph_transaction` locks and reloads the graph, checks its content revision when `expected_rev` is supplied, then writes atomically. | Graph-level CAS exists; mandatory per-task `task_version` CAS is not established. |

[ADR-001 sections B–D](ADR-001_BACKLOG_GRAPH_NORTH_STAR.md) describe total
ordering, a graph content revision and locked atomic transactions, consistent
with those current mechanisms. The narrower O(1), reopen and task-version
claims require explicit contract reconciliation before either changing these
criteria or scheduling new runtime implementation. An ontology concept does
not demonstrate that its lifecycle operation is implemented.

Relevant sources: `src/graph_backlog/algorithms.py:compute_frontier` and
`src/graph_backlog/mutations.py:execute_graph_transaction`.
Existing mechanism checks:

```powershell
py -m pytest tests/test_north_star_invariants.py tests/test_adapters_and_mutations.py -q
```

These tests validate the current mechanisms, not all four criteria above.

