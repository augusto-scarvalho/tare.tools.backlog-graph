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
