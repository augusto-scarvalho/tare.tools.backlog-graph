from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .core import WorkGraph, load_default_policy, load_default_taxonomy
from .jsonutil import UsageError, GraphInvalid, load_json, dump_formatted, atomic_write, stable_dict
from .algorithms import (
    readiness,
    unresolved_prereqs,
    compute_frontier,
    find_cycles_scc,
    score_breakdown,
    ranked_next,
    downstream_reach,
    upstream_dependencies,
    shortest_path,
    critical_path
)
from .validation import (
    validate_work_graph,
    verify_evidence,
    reconcile,
    doctor_check,
    diagnose_graph
)
from .diff import semantic_diff, validate_change
from .packet import generate_packet, format_packet_markdown
from .simulation import simulate_completions
from .visualizer import generate_html_viewer, serve_visualizer

VERSION = "0.2.0"
PASS, VALIDATION_FAIL, RUNTIME_ERROR = 0, 1, 2

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="graph-backlog",
        description="tare.tools DAG-based Work Graph Backlog tool & engine"
    )
    p.add_argument("--graph", default="work-graph.json", help="Path to work-graph.json")
    p.add_argument("--policy", help="Path to graph-ops-policy.json")
    p.add_argument("--taxonomy", help="Path to relation-taxonomy.json")
    p.add_argument("--format", choices=["json", "jsonl", "ids", "md"], default="json")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    sp = p.add_subparsers(dest="cmd", required=True)

    # Core inspection & health
    for name in ("validate", "summary", "cycles", "reconcile", "verify-evidence", "doctor", "history", "coverage", "critical-path", "diagnostics", "lint"):
        sp.add_parser(name)

    # Query
    q = sp.add_parser("query")
    q.add_argument("--text", help="Search text in ID, title, summary, cluster, tags")
    q.add_argument("--status", action="append", help="Filter by completion status")
    q.add_argument("--cluster", action="append", help="Filter by cluster")
    q.add_argument("--horizon", action="append", help="Filter by horizon")
    q.add_argument("--kind", action="append", help="Filter by node kind")
    q.add_argument("--scope", action="append", help="Filter by materialization scope")
    q.add_argument("--grade", action="append", help="Filter by evidence grade")
    q.add_argument("--include-done", action="store_true", help="Include completed nodes")
    q.add_argument("--limit", type=int, default=50, help="Max results")

    # Show
    s = sp.add_parser("show")
    s.add_argument("id", help="Node ID")

    # Frontier & Next
    for name in ("frontier", "next"):
        x = sp.add_parser(name)
        x.add_argument("--profile", choices=["planning", "operational"], default="planning")
        x.add_argument("--limit", type=int, default=50 if name == "frontier" else 10)
        if name == "frontier":
            x.add_argument("--exclude-partial", action="store_true")
            x.add_argument("--all-active", action="store_true")

    # Blocker & Dependencies
    w = sp.add_parser("why")
    w.add_argument("id", help="Node ID")
    w.add_argument("--profile", choices=["planning", "operational"], default="planning")

    b = sp.add_parser("blockers")
    b.add_argument("id", help="Node ID")

    d = sp.add_parser("deps")
    d.add_argument("id", help="Node ID")
    d.add_argument("--limit", type=int, default=100)

    im = sp.add_parser("impact")
    im.add_argument("id", help="Node ID")
    im.add_argument("--all-relations", action="store_true")
    im.add_argument("--limit", type=int, default=100)

    pa = sp.add_parser("path")
    pa.add_argument("source", help="Source node ID")
    pa.add_argument("target", help="Target node ID")
    pa.add_argument("--type", action="append", help="Filter edge types")
    pa.add_argument("--semantic-only", action="store_true")

    pk = sp.add_parser("packet")
    pk.add_argument("id", help="Node ID")
    pk.add_argument("--profile", choices=["planning", "operational"], default="planning")

    st = sp.add_parser("stale")
    st.add_argument("--limit", type=int, default=100)

    # Diff & validation
    df = sp.add_parser("diff")
    df.add_argument("other", help="Path to other work-graph.json")
    df.add_argument("--ignore-field", action="append", default=[])
    df.add_argument("--full", action="store_true", default=True)

    vc = sp.add_parser("validate-change")
    vc.add_argument("other", help="Path to other work-graph.json")
    vc.add_argument("--ignore-field", action="append", default=[])

    # Provenance
    src = sp.add_parser("sources")
    src.add_argument("id", nargs="?")

    tr = sp.add_parser("trace")
    tr.add_argument("id")

    # Simulation & score
    sim = sp.add_parser("simulate")
    sim.add_argument("--mode", choices=["critical-path", "complete"], default="critical-path")
    sim.add_argument("--complete", action="append", help="Node IDs to simulate as completed")
    sim.add_argument("--profile", choices=["planning", "operational"], default="planning")

    es = sp.add_parser("explain-score")
    es.add_argument("id")

    # Intake
    it = sp.add_parser("intake")
    it.add_argument("--id", required=True)
    it.add_argument("--title", required=True)
    it.add_argument("--cluster", required=True)
    it.add_argument("--context", action="append")
    it.add_argument("--priority", default="P1")
    it.add_argument("--horizon", default="H2")
    it.add_argument("--summary", required=True)
    it.add_argument("--depends-on", action="append")
    it.add_argument("--dod", action="append")
    it.add_argument("--evidence", action="append")
    it.add_argument("--rollback")
    it.add_argument("--out")
    it.add_argument("--overwrite", action="store_true")

    # Visualizer & export
    exp = sp.add_parser("export")
    exp.add_argument("--output", "-o", required=True, help="Destination output file path")
    exp.add_argument("--export-format", choices=["html", "json", "md", "mermaid", "csv-nodes", "csv-edges"], default="html")

    # Fast mutations
    an = sp.add_parser("add-node")
    an.add_argument("--id", required=True, help="Task ID")
    an.add_argument("--title", required=True, help="Task title")
    an.add_argument("--cluster", default="general", help="Cluster group")
    an.add_argument("--priority", default="P1", help="Priority (P0, P1, P2, P3)")
    an.add_argument("--horizon", default="H1", help="Horizon (H0, H1, H2)")
    an.add_argument("--criticality", default="MEDIUM", help="Criticality (CRITICAL, HIGH, MEDIUM, LOW)")
    an.add_argument("--summary", help="Task summary")
    an.add_argument("--depends-on", action="append", help="Prerequisite task ID(s)")
    an.add_argument("--tag", action="append", help="Tags")
    an.add_argument("--save", action="store_true", help="Save changes to graph file directly")

    cn = sp.add_parser("complete-node")
    cn.add_argument("id", help="Task ID to mark DONE")
    cn.add_argument("--evidence", help="Evidence statement / test log summary")
    cn.add_argument("--grade", default="B", help="Evidence grade (A, B, C, D)")
    cn.add_argument("--save", action="store_true", help="Save changes to graph file directly")

    # Mutation testing
    mt = sp.add_parser("mutation-test")
    mt.add_argument("--target", default="src/graph_backlog/algorithms.py", help="File to mutate")
    mt.add_argument("--max-mutants", type=int, default=25, help="Max mutants to test")
    mt.add_argument("--test-module", action="append", help="Test modules to run against mutants")

    # 3rd Party Adapters & Ingestion
    igh = sp.add_parser("import-github", help="Import graph from GitHub Issues JSON file or piped stdin")
    igh.add_argument("file", nargs="?", help="Path to GitHub Issues JSON (reads stdin if omitted)")
    igh.add_argument("--prefix", default="GH-", help="ID prefix for GitHub tasks (default: GH-)")
    igh.add_argument("--default-cluster", default="general", help="Default cluster group")
    igh.add_argument("--out", "-o", help="Destination JSON graph file (prints to stdout if omitted)")

    ilin = sp.add_parser("import-linear", help="Import graph from Linear CSV/JSON export file or piped stdin")
    ilin.add_argument("file", nargs="?", help="Path to Linear CSV or JSON (reads stdin if omitted)")
    ilin.add_argument("--type", choices=["csv", "json"], default="csv", help="Input format (default: csv)")
    ilin.add_argument("--default-cluster", default="general", help="Default cluster group")
    ilin.add_argument("--out", "-o", help="Destination JSON graph file (prints to stdout if omitted)")

    iglab = sp.add_parser("import-gitlab", help="Import graph from GitLab Issues JSON file or piped stdin")
    iglab.add_argument("file", nargs="?", help="Path to GitLab Issues JSON (reads stdin if omitted)")
    iglab.add_argument("--prefix", default="GL-", help="ID prefix for GitLab tasks (default: GL-)")
    iglab.add_argument("--default-cluster", default="general", help="Default cluster group")
    iglab.add_argument("--out", "-o", help="Destination JSON graph file (prints to stdout if omitted)")

    imd = sp.add_parser("import-md", help="Import graph from Markdown tasklist file or piped stdin")
    imd.add_argument("file", nargs="?", help="Path to Markdown tasklist (reads stdin if omitted)")
    imd.add_argument("--default-cluster", default="general", help="Default cluster group")
    imd.add_argument("--out", "-o", help="Destination JSON graph file (prints to stdout if omitted)")

    ijira = sp.add_parser("import-jira", help="Import graph from Jira CSV or JSON export file or piped stdin")
    ijira.add_argument("file", nargs="?", help="Path to Jira CSV or JSON (reads stdin if omitted)")
    ijira.add_argument("--type", choices=["csv", "json"], default="csv", help="Input format (default: csv)")
    ijira.add_argument("--default-cluster", default="general", help="Default cluster group")
    ijira.add_argument("--out", "-o", help="Destination JSON graph file (prints to stdout if omitted)")

    srv = sp.add_parser("visualize")
    srv.add_argument("--port", type=int, default=8080)
    srv.add_argument("--no-browser", action="store_true")

    return p

def normalize_format_argv(argv: list[str]) -> list[str]:
    argv = list(argv)
    if "--format" in argv:
        i = argv.index("--format")
        if i + 1 < len(argv):
            pair = argv[i:i + 2]
            del argv[i:i + 2]
            argv = pair + argv
    return argv

def select_nodes(graph: WorkGraph, args: argparse.Namespace) -> list[dict[str, Any]]:
    q = (args.text or "").lower()
    out = []
    for n in graph.nodes:
        st = graph.status_of(n)
        if not args.include_done and st in graph.hidden_statuses:
            continue
        c = n.get("completion") or {}
        filters = [
            ("status", st),
            ("cluster", n.get("cluster")),
            ("horizon", n.get("horizon")),
            ("kind", n.get("kind")),
            ("scope", c.get("materialization_scope")),
            ("grade", c.get("evidence_grade"))
        ]
        if any(getattr(args, k) and v not in getattr(args, k) for k, v in filters):
            continue
        hay = " ".join(map(str, [
            n.get("id", ""), n.get("title", ""), n.get("summary", ""),
            n.get("cluster", ""), n.get("tags", [])
        ])).lower()
        if q and q not in hay:
            continue
        out.append(n)
    return sorted(out, key=lambda n: (n.get("cluster", ""), n.get("id", "")))[:args.limit]

def handle_intake(graph: WorkGraph, args: argparse.Namespace) -> dict[str, Any]:
    if args.id in graph.by_id:
        raise UsageError(f"intake id already exists: {args.id}")
    deps = args.depends_on or []
    missing = [d for d in deps if d not in graph.by_id]
    if missing:
        raise UsageError("unknown --depends-on: " + ",".join(missing))
    obj = {
        "schema": "tare.tools/backlog-intake/0.2",
        "status": "PROPOSED / INTAKE_ONLY",
        "authority_boundary": "Does not write canonical TaskStore/Git/GitHub/CURRENT/TARGET.",
        "item": {
            "id": args.id,
            "title": args.title,
            "cluster": args.cluster,
            "bounded_contexts": args.context or [],
            "priority": args.priority,
            "horizon": args.horizon,
            "summary": args.summary,
            "depends_on": deps,
            "definition_of_done": args.dod or [],
            "evidence_required": args.evidence or [],
            "rollback": args.rollback,
            "current_target_proposed": "PROPOSED until canonical owner admission."
        }
    }
    if args.out:
        p = Path(args.out)
        j = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
        md = p.with_suffix(".md")
        m = (
            f"# {args.title}\n\n"
            f"**Status:** `PROPOSED / BACKLOG INTAKE`\n\n"
            f"> Intake provenance only; canonical TaskStore remains the single writer.\n\n"
            f"## Objective\n{args.summary}\n"
        )
        atomic_write(p, j, args.overwrite)
        atomic_write(md, m, args.overwrite)
        obj["written"] = {"json": str(p), "markdown": str(md)}
    return obj

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_format_argv(sys.argv[1:] if argv is None else argv))
    try:
        if args.cmd in ("import-github", "import-linear", "import-gitlab", "import-md", "import-jira"):
            if getattr(args, "file", None) and args.file != "-":
                with open(args.file, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = sys.stdin.read()

            if args.cmd == "import-github":
                from .adapters import GitHubIssuesAdapter
                parsed_json = json.loads(content)
                graph_dict = GitHubIssuesAdapter.from_issues(
                    parsed_json,
                    id_prefix=args.prefix,
                    default_cluster=args.default_cluster
                )
            elif args.cmd == "import-linear":
                from .adapters import LinearAdapter
                if args.type == "json" or content.strip().startswith(("[", "{")):
                    parsed_json = json.loads(content)
                    graph_dict = LinearAdapter.from_json(parsed_json, default_cluster=args.default_cluster)
                else:
                    graph_dict = LinearAdapter.from_csv(content, default_cluster=args.default_cluster)
            elif args.cmd == "import-gitlab":
                from .adapters import GitLabAdapter
                parsed_json = json.loads(content)
                graph_dict = GitLabAdapter.from_issues(
                    parsed_json,
                    id_prefix=args.prefix,
                    default_cluster=args.default_cluster
                )
            elif args.cmd == "import-jira":
                from .adapters import JiraAdapter
                if args.type == "json" or content.strip().startswith(("[", "{")):
                    parsed_json = json.loads(content)
                    graph_dict = JiraAdapter.from_json(parsed_json, default_cluster=args.default_cluster)
                else:
                    graph_dict = JiraAdapter.from_csv(content, default_cluster=args.default_cluster)
            elif args.cmd == "import-md":
                from .adapters import MarkdownAdapter
                graph_dict = MarkdownAdapter.from_markdown(
                    content,
                    default_cluster=args.default_cluster
                )

            if getattr(args, "out", None):
                atomic_write(args.out, json.dumps(stable_dict(graph_dict), ensure_ascii=False, indent=2) + "\n", overwrite=True)
                obj = {
                    "status": "PASS",
                    "action": args.cmd,
                    "exported": args.out,
                    "nodes": len(graph_dict.get("nodes", [])),
                    "edges": len(graph_dict.get("edges", []))
                }
            else:
                obj = graph_dict

            dump_formatted(obj, args.format)
            return PASS

        raw = load_json(args.graph)
        pol = load_json(args.policy) if args.policy else load_default_policy()
        tax = load_json(args.taxonomy) if args.taxonomy else load_default_taxonomy()

        if args.cmd == "validate":
            obj = validate_work_graph(raw, pol, tax)
            dump_formatted(obj, args.format)
            return PASS if obj["status"] == "PASS" else VALIDATION_FAIL

        # Perform initial validation check before operations
        errs = validate_work_graph(raw, pol, tax)
        if errs["status"] != "PASS":
            dump_formatted(errs, args.format)
            return VALIDATION_FAIL

        graph = WorkGraph(raw, pol, tax)

        if args.cmd == "summary":
            from collections import Counter
            count = lambda f: dict(sorted(Counter(f(n) for n in graph.nodes).items(), key=lambda x: str(x[0])))
            obj = {
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "completion": count(graph.status_of),
                "cluster": count(lambda n: n.get("cluster")),
                "kind": count(lambda n: n.get("kind")),
                "planning_frontier": len(compute_frontier(graph, "planning")),
                "operational_frontier": len(compute_frontier(graph, "operational")),
                "blocking_sccs": len(find_cycles_scc(graph))
            }
        elif args.cmd == "query":
            obj = select_nodes(graph, args)
        elif args.cmd == "show":
            obj = {
                "node": graph.by_id[args.id],
                "incoming": graph.in_edges[args.id],
                "outgoing": graph.out_edges[args.id]
            }
        elif args.cmd == "frontier":
            obj = compute_frontier(graph, args.profile, not args.exclude_partial, args.all_active)[:args.limit]
        elif args.cmd == "why":
            obj = {
                "id": args.id,
                "title": graph.by_id[args.id].get("title", ""),
                **readiness(graph, graph.by_id[args.id], args.profile)
            }
        elif args.cmd == "blockers":
            obj = unresolved_prereqs(graph, args.id)
        elif args.cmd == "deps":
            obj = upstream_dependencies(graph, args.id)[:args.limit]
        elif args.cmd == "impact":
            obj = downstream_reach(graph, args.id, not args.all_relations)[:args.limit]
        elif args.cmd == "path":
            obj = {
                "source": args.source,
                "target": args.target,
                "path": shortest_path(graph, args.source, args.target, args.type, args.semantic_only)
            }
        elif args.cmd == "cycles":
            cycles = find_cycles_scc(graph)
            obj = {"blocking_sccs": cycles, "count": len(cycles)}
        elif args.cmd == "next":
            obj = ranked_next(graph, args.profile, args.limit)
        elif args.cmd == "packet":
            pkt = generate_packet(graph, args.id, args.profile)
            if args.format == "md":
                print(format_packet_markdown(pkt))
                return PASS
            obj = pkt
        elif args.cmd == "stale":
            obj = sorted([
                n for n in graph.nodes
                if n.get("staleness_state") == "STALE" or "STALE_OPEN" in str(n.get("completion", {}).get("coordination_state"))
            ], key=lambda n: n["id"])[:args.limit]
        elif args.cmd == "diff":
            other = load_json(args.other)
            obj = {
                "full_semantic": True,
                "ignored_fields": args.ignore_field,
                "changes": semantic_diff(other, raw, set(args.ignore_field))
            }
        elif args.cmd == "validate-change":
            other = load_json(args.other)
            obj = validate_change(other, raw, args.ignore_field)
        elif args.cmd == "reconcile":
            obj = reconcile(graph)
        elif args.cmd in ("sources", "trace"):
            nid = getattr(args, "id", None)
            if nid:
                n = graph.by_id[nid]
                refs = [
                    {
                        "source_ref": r,
                        "source": graph.sources.get(r),
                        "claim_ids": [x for x in n.get("source_claim_ids", []) if str(x).startswith(f"{r}:")]
                    }
                    for r in n.get("source_refs", [])
                ]
                obj = {
                    "id": nid,
                    "sources": refs,
                    "source_details": n.get("source_details", []),
                    "provenance": n.get("provenance", []),
                    "dod_evidence": (n.get("completion") or {}).get("dod_evidence", [])
                }
            else:
                obj = graph.sources
        elif args.cmd == "verify-evidence":
            obj = verify_evidence(graph)
        elif args.cmd in ("critical-path",):
            obj = critical_path(graph)
        elif args.cmd in ("diagnostics", "lint"):
            obj = diagnose_graph(raw)
        elif args.cmd == "simulate":
            if args.mode == "complete" or args.complete:
                obj = simulate_completions(graph, args.complete or [], args.profile)
            else:
                obj = critical_path(graph)
        elif args.cmd == "explain-score":
            obj = {"id": args.id, **score_breakdown(graph, graph.by_id[args.id])}
        elif args.cmd == "history":
            obj = {
                "snapshot": raw.get("meta", {}).get("snapshot"),
                "lineage": raw.get("meta", {}).get("lineage", {}),
                "projection_run_id": raw.get("meta", {}).get("projection_run_id")
            }
        elif args.cmd == "coverage":
            from collections import Counter
            ve = verify_evidence(graph)
            canonical = sum(1 for n in graph.nodes if all(n.get(k) for k in ("canonical_system", "canonical_id", "canonical_revision")))
            claims = sum(1 for n in graph.nodes if n.get("source_claim_ids"))
            obj = {
                "source_recoverability": ve,
                "canonical_identity": {
                    "count": canonical,
                    "coverage": round(canonical / max(1, len(graph.nodes)), 4)
                },
                "anchored_claim_nodes": {
                    "count": claims,
                    "coverage": round(claims / max(1, len(graph.nodes)), 4)
                }
            }
        elif args.cmd == "doctor":
            obj = doctor_check(graph, VERSION)
        elif args.cmd == "intake":
            obj = handle_intake(graph, args)
        elif args.cmd == "export":
            if args.export_format == "html":
                generate_html_viewer(graph, args.output)
                obj = {"exported": args.output, "format": "html", "nodes": len(graph.nodes)}
            elif args.export_format == "json":
                atomic_write(args.output, json.dumps(stable_dict(graph.to_dict()), ensure_ascii=False, indent=2) + "\n", overwrite=True)
                obj = {"exported": args.output, "format": "json", "nodes": len(graph.nodes)}
            elif args.export_format == "md":
                from .adapters import MarkdownAdapter
                atomic_write(args.output, MarkdownAdapter.to_markdown(graph), overwrite=True)
                obj = {"exported": args.output, "format": "md", "nodes": len(graph.nodes)}
            elif args.export_format == "mermaid":
                from .adapters import MermaidAdapter
                atomic_write(args.output, MermaidAdapter.to_mermaid(graph), overwrite=True)
                obj = {"exported": args.output, "format": "mermaid", "nodes": len(graph.nodes)}
            elif args.export_format == "csv-nodes":
                from .adapters import CsvAdapter
                atomic_write(args.output, CsvAdapter.nodes_to_csv(graph), overwrite=True)
                obj = {"exported": args.output, "format": "csv-nodes", "nodes": len(graph.nodes)}
            elif args.export_format == "csv-edges":
                from .adapters import CsvAdapter
                atomic_write(args.output, CsvAdapter.edges_to_csv(graph), overwrite=True)
                obj = {"exported": args.output, "format": "csv-edges", "edges": len(graph.edges)}
        elif args.cmd == "add-node":
            from .mutations import add_node_to_graph
            new_graph_dict = add_node_to_graph(
                graph,
                node_id=args.id,
                title=args.title,
                cluster=args.cluster,
                priority=args.priority,
                horizon=args.horizon,
                criticality=args.criticality,
                summary=args.summary,
                depends_on=args.depends_on,
                tags=args.tag
            )
            if args.save:
                atomic_write(args.graph, json.dumps(stable_dict(new_graph_dict), ensure_ascii=False, indent=2) + "\n", overwrite=True)
            obj = {"status": "PASS", "action": "added_node", "node_id": args.id, "saved": bool(args.save)}
        elif args.cmd == "complete-node":
            from .mutations import complete_node_in_graph
            new_graph_dict = complete_node_in_graph(
                graph,
                node_id=args.id,
                evidence_summary=args.evidence,
                evidence_grade=args.grade
            )
            if args.save:
                atomic_write(args.graph, json.dumps(stable_dict(new_graph_dict), ensure_ascii=False, indent=2) + "\n", overwrite=True)
            obj = {"status": "PASS", "action": "completed_node", "node_id": args.id, "saved": bool(args.save)}
        elif args.cmd == "mutation-test":
            from .mutation_testing import MutationEngine
            tests = args.test_module or ["tests.test_algorithms", "tests.test_validation", "tests.test_graph_ops"]
            res = MutationEngine.run_mutation_test(
                target_file=args.target,
                test_modules=tests,
                max_mutants=args.max_mutants
            )
            obj = {
                "target": args.target,
                "total_mutants": res.total_mutants,
                "killed": res.killed,
                "survived": res.survived,
                "mutation_score_percent": res.score_percentage,
                "status": "PASS" if res.score_percentage >= 70.0 else "WARN",
                "details": res.details
            }
        elif args.cmd == "visualize":
            serve_visualizer(graph, port=args.port, open_browser=not args.no_browser)
            return PASS
        else:
            raise UsageError(f"Unsupported command: {args.cmd}")

        dump_formatted(obj, args.format)
        if isinstance(obj, dict) and obj.get("status") == "FAIL":
            return VALIDATION_FAIL
        return PASS

    except KeyError as exc:
        print(json.dumps({"status": "ERROR", "error": f"Unknown node/key: {exc}"}), file=sys.stderr)
        return RUNTIME_ERROR
    except (UsageError, GraphInvalid) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return RUNTIME_ERROR

if __name__ == "__main__":
    raise SystemExit(main())
