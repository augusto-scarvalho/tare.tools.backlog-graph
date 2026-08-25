from __future__ import annotations

from .core import WorkGraph, load_default_policy, load_default_taxonomy
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
    doctor_check
)
from .diff import semantic_diff, validate_change
from .packet import generate_packet, format_packet_markdown
from .grounding import WorkGroundingReport, encode_work_grounding, ground_work_item
from .ledger import GraphLedger
from .simulation import simulate_completions
from .visualizer import generate_html_viewer, serve_visualizer
from .adapters import (
    MarkdownAdapter,
    MermaidAdapter,
    CsvAdapter,
    GitHubIssuesAdapter,
    LinearAdapter,
    GitLabAdapter,
    JiraAdapter
)

__version__ = "1.1.0"

__all__ = [
    "WorkGraph",
    "load_default_policy",
    "load_default_taxonomy",
    "readiness",
    "unresolved_prereqs",
    "compute_frontier",
    "find_cycles_scc",
    "score_breakdown",
    "ranked_next",
    "downstream_reach",
    "upstream_dependencies",
    "shortest_path",
    "critical_path",
    "validate_work_graph",
    "verify_evidence",
    "reconcile",
    "doctor_check",
    "semantic_diff",
    "validate_change",
    "generate_packet",
    "format_packet_markdown",
    "WorkGroundingReport",
    "encode_work_grounding",
    "ground_work_item",
    "GraphLedger",
    "simulate_completions",
    "generate_html_viewer",
    "serve_visualizer",
    "MarkdownAdapter",
    "MermaidAdapter",
    "CsvAdapter",
    "GitHubIssuesAdapter",
    "LinearAdapter",
    "GitLabAdapter",
    "JiraAdapter",
    "__version__",
]
