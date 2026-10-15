# Ontology & Relation Taxonomy

The canonical machine-readable vocabulary owned by this repository is
[`../ontology/domain_ontology.yaml`](../ontology/domain_ontology.yaml). This
document explains the operational taxonomies in human-readable form; it is not
a second ontology payload.

## 1. Node Types (Kinds)

| Kind | Purpose | Actionable by Default |
|---|---|---|
| `task` | Concrete development task | Yes |
| `implementation_packet` | Fully scoped implementation unit | Yes |
| `spike` | Research or exploratory investigation | Yes |
| `work_item` | General unit of delivery | Yes |
| `bug_candidate` | Candidate bug fix or defect | Yes |
| `architecture_decision` | Architectural baseline or policy | No (informational) |
| `epic` / `milestone` | High-level parent container | No (structural) |

---

## 2. Status Lifecycle

- **`NOT_DONE`**: Work not yet begun or in progress without satisfying exit criteria (`dod_satisfied = false`).
- **`PARTIAL`**: Work partially delivered or in intermediate evaluation state (`dod_satisfied = false`).
- **`DONE`**: Work completed and fully meeting Definition of Done (`dod_satisfied = true`).
- **`SUPERSEDED`**: Replaced by successor item(s) through a `SUPERSEDED_BY` edge.

---

## 3. Relation Taxonomy

| Relation | Dependency Effect | Role of Source Node |
|---|---|---|
| `UNLOCKS` | Prerequisite | Mandatory prerequisite that blocks target until source is satisfied. |
| `DEPENDS_ON` | Prerequisite | Target is prerequisite for source (inverted direction). |
| `ENABLES` | Prerequisite / Foundation | Source enables capability in target. |
| `SUPERSEDED_BY` | Successor | Source is superseded by target. |
| `RELATION_TO` | Informational | Non-blocking associative reference. |

---

## 4. Evidence Grades

For operational and high-rigor environments:
- **`A`**: Cryptographically verified artifact with deterministic build/run logs.
- **`B`**: Automated unit/integration test run with complete stdout/stderr logs.
- **`C`**: Manual verification or reviewer sign-off.
- **`D`**: Informal or subjective completion statement.

New or revised actionable `DONE` declarations must provide `evidence_grade`,
`evidence_grade_reason`, nonempty `dod_evidence`, and declared provenance or
registered `source_refs`. Grades A/B also require a registered source with a
nonempty locator and recoverability `RECOVERABLE_REFERENCE`, `EXACT_BYTES`, or
`CONTENT_ADDRESSED`. The existing `readiness.minimum_evidence_grade` still applies.
The deterministic check validates these declarations; it does not retrieve the
reference content or attest independence, log completeness, or cryptographic
authenticity. Callers remain responsible for declaring a grade that matches the
taxonomy above.

`complete-node` and `land` (also `land-train`) require explicit `--grade`,
`--grade-reason`, and `--evidence` for actionable targets. Use repeatable
`--source-ref` for IDs already in `graph.sources`; these commands never invent
sources or infer A/B from a test summary or a train marker. Pure mutation APIs
use the same guard as the locked transaction, which validates before writing.

Existing untouched closures remain readable and do not block unrelated edits.
`verify-evidence` reports their missing declarations without changing history.
Reopening an item does not require a completion grade; reviewing its closure
again does. Historical grades are preserved, including `evidence_grade_original`.
