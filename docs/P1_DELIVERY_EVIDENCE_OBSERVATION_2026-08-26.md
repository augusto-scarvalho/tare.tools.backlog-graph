# P1 Delivery Evidence Observation — 2026-08-26

## Scope and state

- Policy: `ADR-058`
- Repository: `tare.tools.backlog-graph`
- Mode: `OBSERVE`; no CI or admission gate was enabled.
- Declared/effective class: `E3_CRITICAL` / `E3_CRITICAL`
- Honest delivery state: `PREPARED`
- Classification manifest SHA-256: `127493fe1c8cbfab71eb0c4515aa6275c87c76e7de0d71d4273eac849c0c599d`
- Bootstrap treatment: the first manifest has no parent, so the manifest and classifier retain an intrinsic `E3_CRITICAL` floor.

## Evidence

| Evidence | Result |
|---|---|
| Pre-change repository baseline | `138 passed, 2 skipped in 58.85s` |
| Focused classification falsifiers | `17 passed in 0.13s` |
| Risk-selected classifier mutants | `9 killed / 9 evaluated`; `0 SURVIVED`, `0 ERROR`, `0 TIMEOUT` |
| Post-change repository suite | `155 passed, 2 skipped in 57.01s` |
| Source containment | Mutation engine used a temporary shadow and retained its production-source hash check |
| Line coverage | `UNAVAILABLE`: the active Python environment has no `coverage` module |
| Independent E3 audit | Fable 5 `xhigh`: initial `REVISE`, follow-up `PASS` at confidence `0.92`, zero remaining findings |
| CI | Not run; therefore this observation is not `VALIDATED_CI` or `ADMITTED` |

The selected mutants challenged manifest validation, path traversal rejection,
parent-manifest use, the intrinsic manifest floor, underclassification, and the
two no-authority flags. Adding `policies/` to the mutation shadow was necessary
for the focused tests to remain hermetic.

## Ecosystem guidance and visible gaps

`specgraph ground` returned `READY_TRUNCATED` for this repository: 28 entries
matched, 16 were returned, and 12 were omitted by the byte bound. The receipt
records `specgraph_output_truncated`; this did not lower the effective class or
authorize admission.

No false classification block was observed. The full local suite exceeded the
policy's initial 45-second PR target in this environment, while the new focused
classification tests added only 0.13 seconds. P2 should examine the existing
mutation-canary selection before making any new PR gate blocking.

## Independent audit receipt

The independent auditor used the exact CLI model `claude-fable-5` with effort
`xhigh`, declared bias domain `anthropic/fable`, and implementer bias domain
`openai/gpt`. The CLI reported the canonical model as `claude-fable-5`, no
permission denials, and no subagents.

- Initial session `51f4328c-eb9f-4866-b429-f6b34dde40f9`: `REVISE` at
  confidence `0.86`. It reproduced Windows drive-path acceptance and an E0
  default for unknown executable suffixes; three smaller findings covered path
  casing, a reproduction-command omission, and the unasserted bootstrap label.
- Follow-up session `20e97e93-6275-4f79-a12f-f5ad428420b3`: `PASS` at
  confidence `0.92`; all five findings resolved and no remaining findings.
- Combined reported CLI cost: `$3.707334`. The auditor was read-only and did
  not re-execute tests; the local test and mutation receipts above remain the
  executable evidence.

The accepted correction rejects Windows drive/UNC paths, matches risk paths
case-insensitively, defaults unknown or extensionless paths to E1, and reserves
E0 for a short list of known-inert prose/image artifacts. No dependency,
service, generalized framework, or new CI gate was added.

## Reproduction

```powershell
py -m pytest -q tests/test_delivery_evidence.py
py -m pytest -q
py -m graph_backlog.delivery_evidence --declared E3_CRITICAL `
  --path policies/delivery-evidence.json `
  --path src/graph_backlog/delivery_evidence.py `
  --path src/graph_backlog/mutation_testing.py `
  --path tests/test_delivery_evidence.py `
  --graph-status READY_TRUNCATED
```
