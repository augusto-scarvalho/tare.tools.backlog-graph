# Changelog

Notable changes to `tare.tools.backlog-graph` are recorded here, newest first. This file starts with a concise retrospective of the current public baseline; Git history remains authoritative for commit-level detail.

## Unreleased

### Added

- Added `backlog ground`, a bounded, deterministic and read-only execution
  envelope under `tare.tools/work-grounding/1`, with exact graph, item and
  execution-scope identities plus optional drift fencing through
  `--expected-scope-sha256`.
- Added fail-closed statuses for stale, blocked, unbounded, missing, invalid and
  drifted work items. Strict managed execution requires fresh operational
  readiness and explicit exit criteria.
- Added optional, bounded `target_repositories`, `grounding_refs`,
  `target_paths`, and `target_symbols` fields so a Work item can select its
  SpecGraph context explicitly without coupling either graph implementation.
- Added per-repository `repository_scopes` as the strict multirepository SSOT.
  Legacy flat selection remains valid for one repository; ambiguous multi-repo
  or mixed selection fails closed.

### Fixed

- Removed frozen-harness paths and invented implementation directives from
  Markdown work packets. Missing exit criteria are now reported honestly.

### Changed

- Bumped the package and CLI to `1.2.0` for strict multirepository selection.

## 2026-08-21

### Changed

- Converted README diagrams to Mermaid and added the Portuguese README ([4d0a4d2](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/commit/4d0a4d2)).

## 2026-08-19

### Fixed

- Allowed validation to omit an unprovided relation taxonomy ([51bd86a](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/commit/51bd86a)).

### Changed

- Strengthened stale-lock eviction and repository hygiene ([77d8bd5](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/commit/77d8bd5)).

## 2026-08-17

### Fixed

- Hardened graph locking with fail-closed acquisition and safe stale-lock recovery ([be10bed](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/commit/be10bed)).
- Added transactional cleanup when file-descriptor wrapping fails ([c3934da](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/commit/c3934da)).
