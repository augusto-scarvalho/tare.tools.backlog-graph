# Managed Work Guard

## Goal

Keep an agent bound to one approved backlog item without turning the backlog
projection into an orchestrator. The mode is opt-in, read-only and fail-closed.

## Contract

1. The host selects an explicit work graph and item ID.
2. `backlog ground` emits `tare.tools/work-grounding/1` canonical JSON only when
   the item is fresh, operationally ready and has explicit exit criteria.
3. `execution_scope_sha256` covers the full work node, incident edges, direct
   prerequisites and referenced source records. Unrelated graph metadata does
   not invalidate the fence.
4. Optional bounded `target_repositories`, `grounding_refs`, `target_paths`,
   and `target_symbols` let Work select downstream repository context
   explicitly. They are opaque data here; Backlog Graph never calls SpecGraph.
5. Kernel preserves the exact bytes and re-runs `ground` with the expected
   digest at bounded checkpoints.
6. Agent Runtime blocks before dispatch, after a provider result and before a
   terminal claim if the scope drifted or could not be revalidated.

The projection always declares `NONE / READ_ONLY PROJECTION`. Binding,
Authority, provider routing, evidence acceptance and canonical settlement stay
outside Backlog Graph.

## Strict progress policy

Strict mode also requires a Kernel-observed progress signal after every
`CONTINUE` or `SUCCEEDED` result. Progress is cumulative only when unresolved
obligations decrease without losing verified evidence, or verified evidence
increases without adding obligations.

- Regression blocks immediately.
- Missing verifiable progress blocks.
- A bounded number of consecutive no-progress windows blocks with
  `STAGNATION_DETECTED`.
- Changed prose, repeated tool calls, new micro-tasks and state novelty alone do
  not count as progress.

This targets the practical Zeno anti-pattern: indefinitely slicing or repeating
work while getting no closer to the accepted exit criteria. It is deliberately
small: no new daemon, scheduler, database, policy language or autonomous
backlog writer.

## Statuses

- `READY`: safe to create a managed `WorkEnvelope`.
- `DRIFT`: execution-relevant state changed; stop and obtain a new binding.
- `BLOCKED`, `STALE`, `UNBOUNDED_WORK`: do not dispatch the agent.
- `UNAVAILABLE`, `SOURCE_INVALID`, `WORK_CONTEXT_TOO_LARGE`: fail closed and
  repair the input or transport.

## Hooks

A provider-native static hook cannot safely infer which dynamic work binding is
authoritative. The primary enforcement point is therefore the managed runtime,
shared by all provider adapters. A native Claude, Codex or Antigravity hook may
only act as a fallback for unmanaged sessions when the host supplies an
authenticated binding; it must not guess from branch names, prompts or the
current directory.
