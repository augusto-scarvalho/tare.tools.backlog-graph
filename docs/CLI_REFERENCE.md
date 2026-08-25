# CLI Command Reference

The `graph_ops.py` (and installed `graph-backlog` command) provides a comprehensive set of subcommands for querying, inspecting, and manipulating the DAG backlog.

## Global Flags

- `--graph <path>`: Path to the JSON work graph file (default: `work-graph.json`).
- `--policy <path>`: Path to a custom `graph-ops-policy.json`.
- `--taxonomy <path>`: Path to a custom `relation-taxonomy.json`.
- `--format {json,jsonl,ids,md}`: Output format (default: `json`).
- `--version`: Show version and exit.

---

## Subcommands

### Managed execution: `ground <id>`

Emits canonical compact JSON for one operationally ready item. The graph path is
mandatory so hooks cannot silently bind to an unintended default.

```bash
python graph_ops.py --format json ground TASK-02 \
  --work-graph fixtures/sample-backlog.json \
  --profile operational \
  --max-bytes 8192
```

- Exit `0` means `READY`; every other status exits non-zero.
- `--expected-scope-sha256 <digest>` revalidates an existing fence and returns
  `DRIFT` if execution-relevant state changed.
- Output has no trailing newline and `byte_count` is the exact stdout length.
- The command is read-only and grants no Authority.

This is the managed-agent contract. `packet` remains a human-readable context
view and must not be used as a drift fence.

### 1. `validate`
Performs structural, schema, and DAG cycle validation on the graph.
```bash
python graph_ops.py --graph my-graph.json validate
```
- **Exit Codes:** `0` on PASS, `1` on FAIL.

---

### 2. `summary`
Prints high-level metrics: total nodes, edges, completion breakdown, clusters, and frontier counts.
```bash
python graph_ops.py --graph my-graph.json summary
```

---

### 3. `frontier`
Calculates all items whose prerequisites are satisfied and can be worked on immediately.
```bash
python graph_ops.py frontier --profile planning --format ids
```
- `--profile {planning,operational}`: Filter profile (default: `planning`).
- `--exclude-partial`: Exclude items with status `PARTIAL`.
- `--all-active`: Include all non-done items regardless of kind filter.
- `--limit <int>`: Maximum number of returned items (default: `50`).

---

### 4. `next`
Computes the feasible frontier and ranks items using deterministic policy weights.
```bash
python graph_ops.py next --limit 5
```

---

### 5. `why <id>`
Explains why a specific node is ready or blocked, listing exact unsatisfied prerequisites.
```bash
python graph_ops.py why TASK-03
```

---

### 6. `blockers <id>`
Lists all direct unsatisfied prerequisite nodes blocking `<id>`.
```bash
python graph_ops.py blockers TASK-03
```

---

### 7. `deps <id>`
Computes all transitive upstream dependencies for `<id>`.
```bash
python graph_ops.py deps TASK-03 --format md
```

---

### 8. `impact <id>`
Finds all downstream nodes that depend on `<id>` directly or transitively.
```bash
python graph_ops.py impact TASK-01
```

---

### 9. `path <source> <target>`
Computes the shortest dependency path between two nodes.
```bash
python graph_ops.py path TASK-01 TASK-03
```

---

### 10. `critical-path`
Calculates the longest DAG sequence in the graph (the critical chain of work).
```bash
python graph_ops.py critical-path
```

---

### 11. `packet <id>`
Generates a complete implementation context packet for developer or AI agent prompts.
```bash
python graph_ops.py packet TASK-02 --format md
```

---

### 12. `simulate`
Simulates "what-if" scenarios (e.g. marking specific tasks as completed) to predict unlocked frontier items.
```bash
python graph_ops.py simulate --mode complete --complete TASK-02
```

---

### 13. `diff <other>`
Performs deep semantic diffing against another snapshot file.
```bash
python graph_ops.py diff previous-snapshot.json
```

---

### 14. `doctor`
Runs comprehensive health checks (structural validation, cycle checks, evidence coverage, operational reconciliation).
```bash
python graph_ops.py doctor
```

---

### 15. `export`
Exports the graph to standalone HTML visualizer, JSON, or Markdown.
```bash
python graph_ops.py export --output backlog.html --export-format html
```

---

### 16. `visualize`
Starts a local web server with the interactive graph backlog UI.
```bash
python graph_ops.py visualize --port 8080
```

---

### 17. `import-github`
Imports issues from GitHub CLI (`gh issue list`) JSON export or piped stdin, automatically resolving dependencies from issue descriptions and tasklists.
```bash
# Via file:
python graph_ops.py import-github issues.json --out work-graph.json

# Via piped stdin from GitHub CLI:
gh issue list --limit 100 --json number,title,body,labels,state | python graph_ops.py import-github --out work-graph.json
```

---

### 18. `import-linear`
Imports issues from Linear CSV or JSON export payloads, mapping status, priorities, projects, and blocking links into DAG nodes and UNLOCKS edges.
```bash
# From Linear CSV export:
python graph_ops.py import-linear linear-export.csv --out work-graph.json

# From Linear API / JSON payload:
python graph_ops.py import-linear linear-export.json --type json --out work-graph.json
```

---

### 19. `import-gitlab`
Imports issues from GitLab Issues JSON (from `glab issue list` or GitLab REST API), mapping scoped labels (`cluster::*`, `priority::*`) and quick action `/depends_on` / `/blocks` dependencies.
```bash
# Via file:
python graph_ops.py import-gitlab gitlab-issues.json --out work-graph.json

# Via piped stdin from GitLab CLI:
glab issue list --output json | python graph_ops.py import-gitlab --out work-graph.json
```

---

### 20. `import-jira`
Imports issues from Jira CSV export or Jira Cloud/Server REST API JSON payloads, mapping status categories, priorities, components, and outward/inward `issuelinks` (e.g. `Blocks`, `is blocked by`, `Depends`).
```bash
# From Jira CSV export:
python graph_ops.py import-jira jira-export.csv --out work-graph.json

# From Jira REST API / JSON search payload:
python graph_ops.py import-jira jira-search.json --type json --out work-graph.json
```

---

### 21. `import-md`
Imports tasks and dependency relations from structured Markdown tasklists (`backlog.md`).
```bash
python graph_ops.py import-md backlog.md --out work-graph.json
```

