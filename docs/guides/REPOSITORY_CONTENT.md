# Source distribution and private history

The distributable tree contains the deterministic graph engine, current
contracts, maintained guides, schema and offline tests. Recovered publication
packets and dated delivery observations have separate private custody.
[RECORDS_ARCHIVE.json](../RECORDS_ARCHIVE.json) preserves their original owner
commit, paths, hashes and sizes without including the record bodies.

Back up local records and verify hashes before integrating their removal from
Git. Restore private files to the same ignored paths after updating; do not
overwrite local changes. Historical links refer to the original owner commit
and may require authorized access. Their outcomes remain historical observations,
not new release qualification or authority to settle Work.

Ordinary tests create their own graphs and storage. They do not retrieve private
records, old Git objects or an operator database. CI retains the existing hermetic
mutation canaries and engine suite. Broad mutation campaigns, SpecGraph functional
backlog and eventual public distribution require their separate scopes; this
preparation does not execute them or download models.
