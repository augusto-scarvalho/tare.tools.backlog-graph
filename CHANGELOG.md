# Changelog

Notable changes to `tare.tools.backlog-graph` are recorded here, newest first. This file starts with a concise retrospective of the current public baseline; Git history remains authoritative for commit-level detail.

## Unreleased

No entries yet.

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
