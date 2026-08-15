# Architecture & Technical Design

## 1. Overview

**Graph Backlog** transforms traditional static backlog lists into a computable Directed Acyclic Graph (DAG). 

In modern software development and especially in multi-agent or hybrid human-AI workflows, tasks are deeply interdependent. Simple priority lists or Kanban boards fail because:
- They assume independence between items.
- They hide prerequisites and transitive blockers.
- They cannot automatically compute what is actionable *right now*.

By framing the backlog as a DAG:
- Every task is a **Node**.
- Every dependency, enablement, or succession is an **Edge** with explicit semantics.
- Algorithms compute the **Frontier** (ready work) deterministically.

---

## 2. Core Concepts

```
┌─────────────────────────────────────────────────────────────┐
│                       Work Graph (DAG)                      │
│                                                             │
│   [TASK-01: DONE] ──UNLOCKS──> [TASK-02: NOT_DONE]          │
│                                       │                     │
│                                    UNLOCKS                  │
│                                       ▼                     │
│                                [TASK-03: NOT_DONE]          │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                   Frontier Engine (algorithms.py)
                                │
         ┌──────────────────────┴──────────────────────┐
         ▼                                             ▼
  [Feasible Frontier]                           [Blocked Items]
     • TASK-02 (Ready)                       • TASK-03 (Blocked by 02)
         │
         ▼
  Ranked Next (Score: priority + horizon + criticality)
```

### 2.1 Nodes
Nodes represent discrete work units (tasks, spikes, implementation packets, bug fixes, candidates). Key attributes:
- `id`: Unique identifier (e.g. `TASK-01`, `TCP-02`).
- `title` & `summary`: Descriptive intent and scope.
- `cluster`: Functional or architectural domain grouping.
- `horizon`: Time/planning horizon (`H0` immediate, `H1` near-term, `H2` medium-term).
- `priority`: Declared importance (`P0` to `P3`).
- `criticality`: Impact severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- `completion`: Status (`NOT_DONE`, `PARTIAL`, `DONE`, `SUPERSEDED`) and `dod_satisfied` (boolean).
- `exit_criteria`: Concrete checkboxes for Definition of Done (DoD).
- `provenance` & `source_refs`: Traceability to architectural specs, issues, or customer requirements.

### 2.2 Edges and Relation Semantics
Edges connect nodes with explicit semantic effects defined in `policies/relation-taxonomy.json`:
- `UNLOCKS`: `Source` is a mandatory prerequisite that blocks `Target` until completed.
- `DEPENDS_ON`: `Target` is a mandatory prerequisite for `Source`.
- `ENABLES`: `Source` provides capabilities or foundation for `Target`.
- `SUPERSEDED_BY`: `Source` was replaced by `Target`. If `Target` is satisfied, `Source` is considered transitively satisfied.
- `RELATION_TO`: Informational or associative link (non-blocking).

---

## 3. Algorithm Details

### 3.1 Frontier Computation
An item is in the **Frontier** (actionable) if and only if:
1. Its current status is NOT `DONE` and NOT `SUPERSEDED`.
2. Its kind is declared as actionable in `graph-ops-policy.json`.
3. All upstream prerequisite edges are **satisfied** (the prerequisite node has `status == "DONE"` and `dod_satisfied == true`, or valid superseded chain).

### 3.2 Cycle Detection (Tarjan's SCC)
A valid work graph must not contain blocking cycles (e.g. A blocks B and B blocks A). We use Tarjan's Strongly Connected Components algorithm to find all cycles and self-loops in $O(V + E)$ time.

### 3.3 Scoring & Ranking
The `next` command ranks the feasible frontier according to configurable policy weights:
$$\text{Score} = W_{\text{priority}} + W_{\text{horizon}} + W_{\text{criticality}} + (\text{unlock\_score} \times M) - P_{\text{partial}} - P_{\text{authority}}$$

---

## 4. Single-Writer & Mutation Safety
- The query and analyzer engine operates as a **read-only projection**.
- Mutations create new immutable snapshots or append structured events to the `GraphLedger`.
- Change diffing (`diff` and `validate-change`) verifies semantic compatibility before applying updates.
