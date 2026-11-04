# Repository content

The repository contains the graph engine, its contracts (`policies/`,
`schemas/` and their packaged copies under `src/graph_backlog/contracts/`), the
maintained guides, the ontology and the offline tests.

Dated delivery observations and recovered publication packets used to live in
`docs/`. They were removed from the tree because nothing in the code, tests or
guides needs them. [RECORDS_ARCHIVE.json](../RECORDS_ARCHIVE.json) lists each
removed file with the commit that last held it, its size and its SHA-256, so the
original bytes can still be found in Git history. Their outcomes are historical
observations, not release qualification or authority to settle Work.

The graphs under `fixtures/` are synthetic: every project, issue and locator in
them is fictional. Tests build their own graphs and storage from these fixtures
or in temporary directories. They never read private records, old Git objects or
an operator database, and they need no network access.
