# BacklogGraph ontology

`domain_ontology.yaml` is the canonical, repository-owned vocabulary for
concepts implemented by `tare.tools.backlog-graph`.

`docs/ONTOLOGY.md` remains the human guide to node, lifecycle, relation and
evidence semantics. The machine-readable ontology names stable architectural
concepts and points back to `ADR-001` and `SPEC-BACKLOG-001`; it does not copy
the complete relation policy or invent runtime state.

Other repositories may consume this file through an exact commit, path and
SHA-256. They must not commit a second payload copy.
