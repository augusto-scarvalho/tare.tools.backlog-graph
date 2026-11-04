# Backlog Graph contributor instructions

Backlog Graph owns the deterministic task DAG, dependency frontier, graph
mutations and source-bound observations. Read `docs/SPEC-BACKLOG-001.md` and
the relevant engine contract before changing behavior. OS owns strategic Work
and settlement; other satellites own their implementations and documents.
The retired `tare.tools.harness` is frozen and must not be imported, copied
or resumed.

- Write code, comments, prompts and documentation in English; agents still reply in the user's language.
  The Portuguese version for Brazilian readers lives only in README.pt-BR.md: update it with its English source.

Keep tests offline with synthetic graphs and disposable storage. Source
validation must not require an operator database or private historical records.
See `docs/guides/REPOSITORY_CONTENT.md` for what the tree contains. Preserve source hashes,
original outcomes and the distinction between observation and canonical delivery.

Add a concise Unreleased entry for material changes without rewriting prior
changelog entries. Run relevant tests and the required hermetic mutation
canaries; integrate main through a reviewed PR after CI passes. Broad mutation
campaigns and functional Work qualifications are separate from repository cleanup.
