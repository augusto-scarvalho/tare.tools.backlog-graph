# Changelog

Notable changes to `tare.tools.backlog-graph` are recorded here, newest first.

## Unreleased

- Saving a graph no longer fails when the volume root's metadata cannot be read. The symlink guard asked every ancestor of the graph's path whether it is a link, the drive root included, and a sandbox that denies the root while allowing the folders below it made every write stop with "Access is denied". The root cannot be a link, so the guard now starts below it; every other component is still checked.
- The READMEs describe what the engine does in plain terms: the "paradigm shift" pitch, the comparison table and the "Mission Control" and "Copilot Bridge" names are gone, horizons read `H0`–`H3` as the code defines them, and the ledger is no longer listed as a CLI command.
- First public release. The repository starts from a single commit; earlier history is not published. It contains the
  backlog graph engine the README describes (ready frontier, ranked pull, blocker and impact tracing, implementation
  packets, what-if simulation, the hash-chained audit ledger and the graph doctor), its CLI, Python API and browser
  viewer, and the test suite.
