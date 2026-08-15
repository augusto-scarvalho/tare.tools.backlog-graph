from __future__ import annotations
import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

from .core import WorkGraph

class MarkdownAdapter:
    """Import and export work graphs from/to structured Markdown tasklists."""
    
    @staticmethod
    def from_markdown(text: str, default_cluster: str = "general") -> dict[str, Any]:
        nodes = []
        edges = []
        
        # Regex to match tasks: - [x] TASK-01: Title (depends: TASK-00) #tag [P0]
        pattern = re.compile(r"^\s*-\s*\[([ xX])\]\s*(?:([A-Za-z0-9_\-]+):\s*)?([^(\n#]+)(?:\((?:depends|blocks|after):\s*([^)]+)\))?(?:#([A-Za-z0-9_,\-]+))?(?:\[([A-Za-z0-9]+)\])?", re.MULTILINE)
        
        for i, match in enumerate(pattern.finditer(text)):
            checked, task_id, title, deps, tags_str, priority = match.groups()
            task_id = task_id.strip() if task_id else f"TASK-{i+1:02d}"
            title = title.strip() if title else f"Task {task_id}"
            is_done = checked.lower() == "x"
            priority = priority.strip() if priority else "P1"
            tags = [t.strip() for t in tags_str.split(",")] if tags_str else []
            
            node = {
                "id": task_id,
                "title": title,
                "kind": "task",
                "cluster": default_cluster,
                "horizon": "H1",
                "work_status": "PROPOSED",
                "admission_state": "ADMITTED",
                "epistemic_status": "CERTAIN",
                "bounded_contexts": [default_cluster],
                "priority": priority,
                "criticality": "MEDIUM",
                "authority_required": "none",
                "evidence_required": [],
                "confidence": {"score": 1.0},
                "summary": title,
                "exit_criteria": [f"Complete {title}"],
                "source_refs": [],
                "source_details": [],
                "provenance": [],
                "source_claim_ids": [],
                "unlock_score": 1,
                "tags": tags,
                "metrics": {},
                "notes": [],
                "items": [],
                "canonical_system": "markdown",
                "canonical_id": task_id,
                "canonical_revision": "r1",
                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "projection_run_id": "import-md",
                "staleness_state": "FRESH",
                "readiness": {"operational_identity_required": False},
                "completion": {
                    "status": "DONE" if is_done else "NOT_DONE",
                    "dod_satisfied": is_done,
                    "evidence_grade": "C" if is_done else None,
                    "materialization_scope": "local"
                }
            }
            nodes.append(node)
            
            if deps:
                for dep in re.split(r"[,;\s]+", deps.strip()):
                    dep_id = dep.strip()
                    if dep_id:
                        edges.append({
                            "from": dep_id,
                            "to": task_id,
                            "type": "UNLOCKS",
                            "semantic": True,
                            "source_refs": [],
                            "source_details": [],
                            "confidence": {"score": 1.0},
                            "notes": ["Imported from markdown dependency declaration"],
                            "requirements": {}
                        })
                        
        return {
            "meta": {
                "schema": "work-graph-poc/0.5",
                "title": "Imported Markdown Backlog",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "snapshot": "md-import"
            },
            "sources": {},
            "nodes": nodes,
            "edges": edges
        }

    @staticmethod
    def to_markdown(graph: WorkGraph) -> str:
        lines = [f"# {graph.meta.get('title', 'Work Graph Backlog')}", ""]
        clusters: dict[str, list[dict[str, Any]]] = {}
        for n in graph.nodes:
            c = n.get("cluster", "general")
            clusters.setdefault(c, []).append(n)
            
        for cluster, nodes in sorted(clusters.items()):
            lines.append(f"## Cluster: {cluster}")
            for n in nodes:
                st = graph.status_of(n)
                checked = "x" if st == "DONE" else " "
                prereqs = [e["from"] for e in graph.in_edges.get(n["id"], []) if e.get("semantic", True)]
                dep_str = f" (depends: {', '.join(prereqs)})" if prereqs else ""
                tag_str = f" #{','.join(n.get('tags', []))}" if n.get("tags") else ""
                prio_str = f" [{n.get('priority', 'P1')}]"
                lines.append(f"- [{checked}] {n['id']}: {n.get('title', '')}{dep_str}{tag_str}{prio_str}")
            lines.append("")
        return "\n".join(lines)


class MermaidAdapter:
    """Export work graph into standard Mermaid flowchart syntax."""
    
    @staticmethod
    def to_mermaid(graph: WorkGraph, orientation: str = "TD") -> str:
        lines = [f"flowchart {orientation}"]
        
        # Subgraphs by cluster
        clusters: dict[str, list[dict[str, Any]]] = {}
        for n in graph.nodes:
            c = n.get("cluster", "general")
            clusters.setdefault(c, []).append(n)
            
        for cluster_name, nodes in sorted(clusters.items()):
            safe_cluster = re.sub(r"[^A-Za-z0-9_]", "_", cluster_name)
            lines.append(f"    subgraph {safe_cluster}[\"{cluster_name}\"]")
            for n in nodes:
                st = graph.status_of(n)
                nid = n["id"]
                safe_id = re.sub(r"[^A-Za-z0-9_]", "_", nid)
                title = n.get("title", nid).replace('"', "'")
                # Styling shapes: [ ] default, ([ ]) rounded for done
                if st == "DONE":
                    lines.append(f"        {safe_id}([\"{nid}: {title}\"])")
                else:
                    lines.append(f"        {safe_id}[\"{nid}: {title}\"]")
            lines.append("    end")
            
        # Edges
        for e in graph.edges:
            src = re.sub(r"[^A-Za-z0-9_]", "_", e.get("from", ""))
            dst = re.sub(r"[^A-Za-z0-9_]", "_", e.get("to", ""))
            rel = e.get("type", "UNLOCKS")
            if src and dst:
                if rel == "UNLOCKS":
                    lines.append(f"    {src} -->|unlocks| {dst}")
                elif rel == "DEPENDS_ON":
                    lines.append(f"    {dst} -->|required by| {src}")
                elif rel == "ENABLES":
                    lines.append(f"    {src} -.->|enables| {dst}")
                else:
                    lines.append(f"    {src} ---|{rel}| {dst}")
                    
        # Classes for visual status
        lines.extend([
            "",
            "    classDef done fill:#10b98122,stroke:#10b981,stroke-width:2px,color:#d1fae5;",
            "    classDef ready fill:#06b6d422,stroke:#06b6d4,stroke-width:2px,color:#cffafe;",
            "    classDef blocked fill:#f43f5e22,stroke:#f43f5e,stroke-width:1px,color:#ffe4e6;"
        ])
        
        from .algorithms import unresolved_prereqs
        for n in graph.nodes:
            nid = re.sub(r"[^A-Za-z0-9_]", "_", n["id"])
            st = graph.status_of(n)
            if st == "DONE":
                lines.append(f"    class {nid} done;")
            elif not unresolved_prereqs(graph, n["id"]):
                lines.append(f"    class {nid} ready;")
            else:
                lines.append(f"    class {nid} blocked;")
                
        return "\n".join(lines)


class CsvAdapter:
    """Export work graph nodes and edges to CSV."""
    
    @staticmethod
    def nodes_to_csv(graph: WorkGraph) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "title", "status", "cluster", "priority", "horizon", "criticality", "unlock_score", "summary"])
        for n in graph.nodes:
            writer.writerow([
                n.get("id"),
                n.get("title"),
                graph.status_of(n),
                n.get("cluster"),
                n.get("priority"),
                n.get("horizon"),
                n.get("criticality"),
                n.get("unlock_score"),
                n.get("summary")
            ])
        return buf.getvalue()

    @staticmethod
    def edges_to_csv(graph: WorkGraph) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["from", "to", "type", "semantic"])
        for e in graph.edges:
            writer.writerow([e.get("from"), e.get("to"), e.get("type"), e.get("semantic", True)])
        return buf.getvalue()


class GitHubIssuesAdapter:
    """Import and export work graphs from/to GitHub Issues payloads."""
    
    @staticmethod
    def from_issues(
        issues_data: list[dict[str, Any]] | dict[str, Any],
        id_prefix: str = "GH-",
        default_cluster: str = "general"
    ) -> dict[str, Any]:
        if isinstance(issues_data, dict):
            if "items" in issues_data:
                issues_data = issues_data["items"]
            else:
                issues_data = [issues_data]
                
        nodes = []
        edges = []
        node_ids = set()
        
        depends_patterns = [
            re.compile(r"(?:depends\s+on|blocked\s+by|prerequisites?|requires?)\s*[:]?\s*([#\d\s,]+)", re.IGNORECASE),
            re.compile(r"^\s*-\s*\[[ xX]\]\s*#(\d+)", re.MULTILINE),
        ]
        blocks_patterns = [
            re.compile(r"(?:blocks|unlocks)\s*[:]?\s*([#\d\s,]+)", re.IGNORECASE),
        ]
        
        # Pass 1: Nodes
        for item in issues_data:
            num = item.get("number") or item.get("id")
            if num is None:
                continue
            task_id = f"{id_prefix}{num}"
            node_ids.add(task_id)
            title = (item.get("title") or f"Issue #{num}").strip()
            body = item.get("body") or ""
            state = (item.get("state") or "open").lower()
            is_done = state in ("closed", "done")
            
            raw_labels = item.get("labels") or []
            cluster = default_cluster
            priority = "P1"
            horizon = "H1"
            tags = []
            
            for lab in raw_labels:
                name = lab.get("name") if isinstance(lab, dict) else str(lab)
                if not name:
                    continue
                low = name.lower()
                
                if low in ("p0", "priority:p0", "priority:critical", "critical", "urgent"):
                    priority = "P0"
                elif low in ("p1", "priority:p1", "priority:high", "high"):
                    priority = "P1"
                elif low in ("p2", "priority:p2", "priority:medium", "medium"):
                    priority = "P2"
                elif low in ("p3", "priority:p3", "priority:low", "low"):
                    priority = "P3"
                    
                if low in ("h0", "horizon:h0", "now"):
                    horizon = "H0"
                elif low in ("h1", "horizon:h1", "next"):
                    horizon = "H1"
                elif low in ("h2", "horizon:h2", "later"):
                    horizon = "H2"
                elif low in ("h3", "horizon:h3", "future"):
                    horizon = "H3"
                    
                if ":" in name or "/" in name:
                    parts = re.split(r"[:/]", name, maxsplit=1)
                    prefix = parts[0].strip().lower()
                    val = parts[1].strip()
                    if prefix in ("cluster", "area", "module", "team", "domain", "scope"):
                        cluster = val.lower()
                    elif prefix in ("priority", "prio"):
                        if val.upper() in ("P0", "P1", "P2", "P3"):
                            priority = val.upper()
                    elif prefix in ("horizon", "h"):
                        if val.upper() in ("H0", "H1", "H2", "H3"):
                            horizon = val.upper()
                else:
                    tags.append(name)
                    
            criteria = []
            for line in body.splitlines():
                cl_m = re.match(r"^\s*-\s*\[([ xX])\]\s*(.+)", line)
                if cl_m and not cl_m.group(2).strip().startswith("#"):
                    criteria.append(cl_m.group(2).strip())
            if not criteria:
                criteria = [f"Resolve GitHub Issue #{num}"]
                
            node = {
                "id": task_id,
                "title": title,
                "kind": "task",
                "cluster": cluster,
                "horizon": horizon,
                "work_status": "COMMITTED" if state == "open" else "PROPOSED",
                "admission_state": "ADMITTED",
                "epistemic_status": "CERTAIN",
                "bounded_contexts": [cluster],
                "priority": priority,
                "criticality": "HIGH" if priority == "P0" else "MEDIUM",
                "authority_required": "none",
                "evidence_required": [],
                "confidence": {"score": 1.0},
                "summary": body[:200].replace("\r", " ").replace("\n", " ").strip() or title,
                "exit_criteria": criteria,
                "source_refs": [],
                "source_details": [],
                "provenance": [{"source": "github_issues", "issue_number": num}],
                "source_claim_ids": [],
                "unlock_score": 1,
                "tags": tags,
                "metrics": {},
                "notes": [],
                "items": [],
                "canonical_system": "github",
                "canonical_id": str(num),
                "canonical_revision": "r1",
                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "projection_run_id": "import-github",
                "staleness_state": "FRESH",
                "readiness": {"operational_identity_required": False},
                "completion": {
                    "status": "DONE" if is_done else "NOT_DONE",
                    "dod_satisfied": is_done,
                    "evidence_grade": "A" if is_done else None,
                    "materialization_scope": "repo"
                }
            }
            nodes.append(node)

        # Pass 2: Dependencies
        for item in issues_data:
            num = item.get("number") or item.get("id")
            if num is None:
                continue
            task_id = f"{id_prefix}{num}"
            body = item.get("body") or ""
            
            for p in depends_patterns:
                for match in p.finditer(body):
                    raw_deps = match.group(1)
                    found_nums = re.findall(r"#?(\d+)", raw_deps)
                    for fn in found_nums:
                        edges.append({
                            "from": f"{id_prefix}{fn}",
                            "to": task_id,
                            "type": "UNLOCKS",
                            "semantic": True,
                            "confidence": {"score": 1.0},
                            "notes": ["Imported from GitHub Issue dependency"],
                            "requirements": {},
                            "source_details": [],
                            "source_refs": []
                        })
                        
            for p in blocks_patterns:
                for match in p.finditer(body):
                    raw_blocks = match.group(1)
                    found_nums = re.findall(r"#?(\d+)", raw_blocks)
                    for fn in found_nums:
                        edges.append({
                            "from": task_id,
                            "to": f"{id_prefix}{fn}",
                            "type": "UNLOCKS",
                            "semantic": True,
                            "confidence": {"score": 1.0},
                            "notes": ["Imported from GitHub Issue blocking relation"],
                            "requirements": {},
                            "source_details": [],
                            "source_refs": []
                        })
                        
        seen_edges = set()
        clean_edges = []
        for e in edges:
            k = (e["from"], e["to"])
            if k not in seen_edges and e["from"] in node_ids and e["to"] in node_ids and e["from"] != e["to"]:
                seen_edges.add(k)
                clean_edges.append(e)
                
        return {
            "meta": {
                "schema": "work-graph-poc/0.5",
                "title": "GitHub Issues Graph Backlog",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "snapshot": "github-import"
            },
            "sources": {},
            "nodes": nodes,
            "edges": clean_edges
        }


class LinearAdapter:
    """Import work graphs from Linear CSV or JSON export payloads."""
    
    @staticmethod
    def from_csv(csv_text: str, default_cluster: str = "general") -> dict[str, Any]:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        nodes = []
        edges = []
        node_ids = set()
        pending_edges = []
        
        prio_map = {"Urgent": "P0", "High": "P1", "Medium": "P2", "Low": "P3", "None": "P2", "1": "P0", "2": "P1", "3": "P2", "4": "P3", "0": "P2"}
        
        for row in reader:
            task_id = (row.get("ID") or row.get("Identifier") or row.get("Issue ID") or "").strip()
            if not task_id:
                continue
            node_ids.add(task_id)
            title = (row.get("Title") or f"Issue {task_id}").strip()
            description = (row.get("Description") or "").strip()
            status_raw = (row.get("Status") or row.get("State") or "Todo").strip().lower()
            
            is_done = status_raw in ("done", "completed", "closed")
            is_partial = status_raw in ("in progress", "started", "in review")
            is_canceled = status_raw in ("canceled", "cancelled", "duplicate")
            status_val = "DONE" if is_done else ("SUPERSEDED" if is_canceled else ("PARTIAL" if is_partial else "NOT_DONE"))
            
            priority_raw = (row.get("Priority") or "Medium").strip()
            priority = prio_map.get(priority_raw, "P1")
            
            cluster = (row.get("Project") or row.get("Team") or default_cluster).strip().lower() or default_cluster
            
            labels_raw = (row.get("Labels") or "").strip()
            tags = [t.strip() for t in labels_raw.split(",") if t.strip()]
            
            blocked_by = (row.get("Blocked by") or row.get("Blocked By") or "").strip()
            if blocked_by:
                for b in re.split(r"[,;\s]+", blocked_by):
                    if b.strip():
                        pending_edges.append((b.strip(), task_id))
                        
            blocking = (row.get("Blocking") or row.get("Blocks") or "").strip()
            if blocking:
                for bl in re.split(r"[,;\s]+", blocking):
                    if bl.strip():
                        pending_edges.append((task_id, bl.strip()))
                        
            for match in re.finditer(r"(?:depends\s+on|blocked\s+by)\s*[:]?\s*([A-Za-z0-9_\-,\s]+)", description, re.IGNORECASE):
                for dep in re.split(r"[,;\s]+", match.group(1)):
                    if dep.strip():
                        pending_edges.append((dep.strip(), task_id))
                        
            node = {
                "id": task_id,
                "title": title,
                "kind": "task",
                "cluster": cluster,
                "horizon": "H1",
                "work_status": "COMMITTED" if status_val != "DONE" else "PROPOSED",
                "admission_state": "ADMITTED",
                "epistemic_status": "CERTAIN",
                "bounded_contexts": [cluster],
                "priority": priority,
                "criticality": "HIGH" if priority == "P0" else "MEDIUM",
                "authority_required": "none",
                "evidence_required": [],
                "confidence": {"score": 1.0},
                "summary": description[:200].replace("\r", " ").replace("\n", " ").strip() or title,
                "exit_criteria": [f"Complete {title}"],
                "source_refs": [],
                "source_details": [],
                "provenance": [{"source": "linear", "id": task_id}],
                "source_claim_ids": [],
                "unlock_score": 1,
                "tags": tags,
                "metrics": {},
                "notes": [],
                "items": [],
                "canonical_system": "linear",
                "canonical_id": task_id,
                "canonical_revision": "r1",
                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "projection_run_id": "import-linear",
                "staleness_state": "FRESH",
                "readiness": {"operational_identity_required": False},
                "completion": {
                    "status": status_val,
                    "dod_satisfied": is_done,
                    "evidence_grade": "A" if is_done else None,
                    "materialization_scope": "linear"
                }
            }
            nodes.append(node)
            
        seen_edges = set()
        for src, dst in pending_edges:
            k = (src, dst)
            if k not in seen_edges and src in node_ids and dst in node_ids and src != dst:
                seen_edges.add(k)
                edges.append({
                    "from": src,
                    "to": dst,
                    "type": "UNLOCKS",
                    "semantic": True,
                    "confidence": {"score": 1.0},
                    "notes": ["Imported from Linear relations"],
                    "requirements": {},
                    "source_details": [],
                    "source_refs": []
                })
                
        return {
            "meta": {
                "schema": "work-graph-poc/0.5",
                "title": "Linear Work Graph Backlog",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "snapshot": "linear-import"
            },
            "sources": {},
            "nodes": nodes,
            "edges": edges
        }

    @staticmethod
    def from_json(json_data: list[dict[str, Any]] | dict[str, Any], default_cluster: str = "general") -> dict[str, Any]:
        if isinstance(json_data, dict):
            if "data" in json_data and "issues" in json_data["data"]:
                json_data = json_data["data"]["issues"].get("nodes", [])
            elif "issues" in json_data:
                json_data = json_data["issues"]
            else:
                json_data = [json_data]
                
        nodes = []
        edges = []
        node_ids = set()
        pending_edges = []
        prio_map = {1: "P0", 2: "P1", 3: "P2", 4: "P3", 0: "P2"}
        
        for item in json_data:
            task_id = item.get("identifier") or item.get("id")
            if not task_id:
                continue
            task_id = str(task_id).strip()
            node_ids.add(task_id)
            title = (item.get("title") or f"Issue {task_id}").strip()
            desc = (item.get("description") or "").strip()
            
            state_obj = item.get("state")
            if isinstance(state_obj, dict):
                st_type = state_obj.get("type", "").lower()
                st_name = state_obj.get("name", "").lower()
            else:
                st_type = str(state_obj or "").lower()
                st_name = st_type
                
            is_done = st_type in ("completed", "done", "closed") or st_name in ("done", "completed")
            is_partial = st_type in ("started", "in_progress") or st_name in ("in progress", "in review")
            is_canceled = st_type in ("canceled", "cancelled")
            status_val = "DONE" if is_done else ("SUPERSEDED" if is_canceled else ("PARTIAL" if is_partial else "NOT_DONE"))
            
            p_val = item.get("priority", 2)
            priority = prio_map.get(p_val, "P1") if isinstance(p_val, int) else "P1"
            
            proj_obj = item.get("project")
            cluster = (proj_obj.get("name") if isinstance(proj_obj, dict) else str(proj_obj or default_cluster)).strip().lower() or default_cluster
            
            relations = item.get("relations") or []
            if isinstance(relations, dict) and "nodes" in relations:
                relations = relations["nodes"]
            for rel in relations:
                r_type = rel.get("type", "").lower()
                rel_issue = rel.get("relatedIssue") or {}
                rel_id = rel_issue.get("identifier") or rel_issue.get("id")
                if rel_id:
                    if r_type == "blocks":
                        pending_edges.append((task_id, str(rel_id).strip()))
                    elif r_type in ("blocked_by", "depends_on"):
                        pending_edges.append((str(rel_id).strip(), task_id))
                        
            node = {
                "id": task_id,
                "title": title,
                "kind": "task",
                "cluster": cluster,
                "horizon": "H1",
                "work_status": "COMMITTED" if status_val != "DONE" else "PROPOSED",
                "admission_state": "ADMITTED",
                "epistemic_status": "CERTAIN",
                "bounded_contexts": [cluster],
                "priority": priority,
                "criticality": "HIGH" if priority == "P0" else "MEDIUM",
                "authority_required": "none",
                "evidence_required": [],
                "confidence": {"score": 1.0},
                "summary": desc[:200].replace("\r", " ").replace("\n", " ").strip() or title,
                "exit_criteria": [f"Complete {title}"],
                "source_refs": [],
                "source_details": [],
                "provenance": [{"source": "linear", "id": task_id}],
                "source_claim_ids": [],
                "unlock_score": 1,
                "tags": [],
                "metrics": {},
                "notes": [],
                "items": [],
                "canonical_system": "linear",
                "canonical_id": task_id,
                "canonical_revision": "r1",
                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "projection_run_id": "import-linear",
                "staleness_state": "FRESH",
                "readiness": {"operational_identity_required": False},
                "completion": {
                    "status": status_val,
                    "dod_satisfied": is_done,
                    "evidence_grade": "A" if is_done else None,
                    "materialization_scope": "linear"
                }
            }
            nodes.append(node)
            
        seen_edges = set()
        for src, dst in pending_edges:
            k = (src, dst)
            if k not in seen_edges and src in node_ids and dst in node_ids and src != dst:
                seen_edges.add(k)
                edges.append({
                    "from": src,
                    "to": dst,
                    "type": "UNLOCKS",
                    "semantic": True,
                    "confidence": {"score": 1.0},
                    "notes": ["Imported from Linear JSON relations"],
                    "requirements": {},
                    "source_details": [],
                    "source_refs": []
                })
                
        return {
            "meta": {
                "schema": "work-graph-poc/0.5",
                "title": "Linear Work Graph Backlog",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "snapshot": "linear-json-import"
            },
            "sources": {},
            "nodes": nodes,
            "edges": edges
        }


class GitLabAdapter:
    """Import work graphs from GitLab Issues JSON payloads."""
    
    @staticmethod
    def from_issues(
        issues_data: list[dict[str, Any]] | dict[str, Any],
        id_prefix: str = "GL-",
        default_cluster: str = "general"
    ) -> dict[str, Any]:
        if isinstance(issues_data, dict):
            issues_data = [issues_data]
            
        nodes = []
        edges = []
        node_ids = set()
        pending_edges = []
        
        for item in issues_data:
            iid = item.get("iid") or item.get("id")
            if iid is None:
                continue
            task_id = f"{id_prefix}{iid}"
            node_ids.add(task_id)
            title = (item.get("title") or f"Issue #{iid}").strip()
            desc = item.get("description") or ""
            state = (item.get("state") or "opened").lower()
            is_done = state in ("closed", "done")
            
            raw_labels = item.get("labels") or []
            cluster = default_cluster
            priority = "P1"
            horizon = "H1"
            tags = []
            
            for lab in raw_labels:
                name = lab.get("name") if isinstance(lab, dict) else str(lab)
                if not name:
                    continue
                low = name.lower()
                if "::" in name:
                    prefix, val = name.split("::", 1)
                    prefix_l = prefix.strip().lower()
                    val_l = val.strip().lower()
                    if prefix_l in ("cluster", "area", "module", "team", "scope"):
                        cluster = val_l
                    elif prefix_l in ("priority", "prio"):
                        priority = val.strip().upper()
                    elif prefix_l in ("horizon", "h"):
                        horizon = val.strip().upper()
                else:
                    if low in ("p0", "critical", "urgent"):
                        priority = "P0"
                    elif low in ("p1", "high"):
                        priority = "P1"
                    elif low in ("p2", "medium"):
                        priority = "P2"
                    elif low in ("p3", "low"):
                        priority = "P3"
                    tags.append(name)
                    
            for match in re.finditer(r"(?:/depends_on|depends\s+on|blocked\s+by)\s*[:]?\s*([#\d\s,]+)", desc, re.IGNORECASE):
                for fn in re.findall(r"#?(\d+)", match.group(1)):
                    pending_edges.append((f"{id_prefix}{fn}", task_id))
                    
            for match in re.finditer(r"(?:/blocks|blocks|unlocks)\s*[:]?\s*([#\d\s,]+)", desc, re.IGNORECASE):
                for fn in re.findall(r"#?(\d+)", match.group(1)):
                    pending_edges.append((task_id, f"{id_prefix}{fn}"))
                    
            links = item.get("issue_links") or []
            for link in links:
                l_type = link.get("link_type", "").lower()
                target_iid = link.get("target_issue", {}).get("iid") or link.get("iid")
                if target_iid:
                    if l_type == "blocks":
                        pending_edges.append((task_id, f"{id_prefix}{target_iid}"))
                    elif l_type == "is_blocked_by":
                        pending_edges.append((f"{id_prefix}{target_iid}", task_id))
                        
            node = {
                "id": task_id,
                "title": title,
                "kind": "task",
                "cluster": cluster,
                "horizon": horizon,
                "work_status": "COMMITTED" if state == "opened" else "PROPOSED",
                "admission_state": "ADMITTED",
                "epistemic_status": "CERTAIN",
                "bounded_contexts": [cluster],
                "priority": priority,
                "criticality": "HIGH" if priority == "P0" else "MEDIUM",
                "authority_required": "none",
                "evidence_required": [],
                "confidence": {"score": 1.0},
                "summary": desc[:200].replace("\r", " ").replace("\n", " ").strip() or title,
                "exit_criteria": [f"Resolve GitLab Issue #{iid}"],
                "source_refs": [],
                "source_details": [],
                "provenance": [{"source": "gitlab", "iid": iid}],
                "source_claim_ids": [],
                "unlock_score": 1,
                "tags": tags,
                "metrics": {},
                "notes": [],
                "items": [],
                "canonical_system": "gitlab",
                "canonical_id": str(iid),
                "canonical_revision": "r1",
                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "projection_run_id": "import-gitlab",
                "staleness_state": "FRESH",
                "readiness": {"operational_identity_required": False},
                "completion": {
                    "status": "DONE" if is_done else "NOT_DONE",
                    "dod_satisfied": is_done,
                    "evidence_grade": "A" if is_done else None,
                    "materialization_scope": "gitlab"
                }
            }
            nodes.append(node)
            
        seen_edges = set()
        for src, dst in pending_edges:
            k = (src, dst)
            if k not in seen_edges and src in node_ids and dst in node_ids and src != dst:
                seen_edges.add(k)
                edges.append({
                    "from": src,
                    "to": dst,
                    "type": "UNLOCKS",
                    "semantic": True,
                    "confidence": {"score": 1.0},
                    "notes": ["Imported from GitLab relations"],
                    "requirements": {},
                    "source_details": [],
                    "source_refs": []
                })
                
        return {
            "meta": {
                "schema": "work-graph-poc/0.5",
                "title": "GitLab Issues Graph Backlog",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "snapshot": "gitlab-import"
            },
            "sources": {},
            "nodes": nodes,
            "edges": edges
        }

