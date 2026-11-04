# Mutation Testing

Mutation testing in backlog-graph has two deliberately separate layers:

1. A bounded PR gate runs 41 curated canaries over operational readiness,
   graph validation, core prerequisite semantics, managed-work grounding,
   atomic graph mutations, canonical serialization, process liveness, and lock
   safety. It is intended to catch the loss of critical assertions quickly,
   not to claim project-wide mutation coverage.
2. Broader campaigns run per target file, manually or on a schedule. Their
   survivors are evidence for test review, not automatic proof of a defect.

The runner copies `src`, `tests`, fixtures, and root Python entrypoints into a
temporary repository. It requires a passing baseline, mutates only the shadow
target, imposes a per-run timeout, and verifies that the original target hash
did not change.

## Result meanings

- `KILLED`: pytest returned its ordinary test-failure exit code.
- `SURVIVED`: the focused tests still passed.
- `TIMEOUT`: the baseline or mutant exceeded its declared budget.
- `ERROR`: collection, usage, import, or pytest infrastructure failed.

Timeouts and errors do not count as killed mutants. A failing baseline aborts
the campaign because no mutation result would be trustworthy.

## Qualification snapshot

The current AST operators discover 783 candidates. The snapshot below records
focused suites, so it must not be presented as whole-project coverage.

| Target | Candidates | Killed | Survived | Score | Focused tests |
| --- | ---: | ---: | ---: | ---: | --- |
| `algorithms.py` | 77 | 31 | 46 | 40.3% | `tests.test_algorithms` |
| `validation.py` | 134 | 52 | 82 | 38.8% | `tests.test_validation` |
| `core.py` | 42 | 38 | 4 | 90.5% | `tests.test_relations`, `tests.test_algorithms` |
| `grounding.py` | 34 | 32 | 2 | 94.1% | `tests.test_grounding` |
| `mutations.py` | 36 | 36 | 0 | 100.0% | `tests.test_adapters_and_mutations`, `tests.test_north_star_invariants` |
| `jsonutil.py` | 38 | 35 | 3 | 92.1% | `tests.test_jsonutil` |
| Other production files | 422 | Not qualified | Not qualified | - | - |

Survivors must be triaged as missing coverage, equivalent mutations, or
behavior covered by a different focused suite. Only consequential,
non-equivalent survivors should normally become new tests or PR canaries.
The two remaining grounding survivors are redundant type guards behind the
structural graph validation used by the public grounding flow.
All discovered `mutations.py` candidates are killed by focused transaction,
graph-mutation, and supersession tests.
The three remaining `jsonutil.py` survivors are equivalent in the current
control flow: redundant `sort_keys` after recursive key sorting, recursive
scratch-directory creation after its parent already exists, and a cleanup
predicate reached only after lock acquisition.

## Commands

Run the bounded canaries:

```bash
pytest tests/test_mutation_testing.py -v
```

Run a broader target campaign through the CLI:

```bash
backlog --graph fixtures/sample-backlog.json mutation-test \
  --target src/graph_backlog/validation.py \
  --test-module tests.test_validation \
  --max-mutants 200 \
  --timeout-seconds 10
```

Select stable, reviewed candidates for a small diagnostic run by repeating
`--mutation-id`. The full campaign is intentionally absent from the per-PR
gate: hundreds of isolated subprocesses would add high recurring cost before
the surviving candidates have been classified.
