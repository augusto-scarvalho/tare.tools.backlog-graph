from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Sequence

from .jsonutil import canonical_json


EVIDENCE_CLASSES = (
    "E0_NON_EXECUTABLE",
    "E1_LOCAL_BEHAVIOR",
    "E2_OPERATIONAL",
    "E3_CRITICAL",
)
CLASS_RANK = {name: rank for rank, name in enumerate(EVIDENCE_CLASSES)}
MANIFEST_PATH = "policies/delivery-evidence.json"
GRAPH_GAPS = {
    "READY": None,
    "READY_TRUNCATED": "specgraph_output_truncated",
    "STALE": "specgraph_evidence_stale",
    "UNAVAILABLE": "specgraph_unavailable",
    "NOT_MAPPED": "specgraph_repository_not_mapped",
    "NOT_RUN": "specgraph_not_run",
}
NON_EXECUTABLE_SUFFIXES = {".gif", ".ico", ".jpeg", ".jpg", ".md", ".png", ".rst", ".svg", ".txt", ".webp"}
NON_EXECUTABLE_NAMES = {"copying", "license", "notice"}
FIXED_E3_PATTERNS = (
    MANIFEST_PATH,
    "src/graph_backlog/delivery_evidence.py",
    "src/graph_backlog/jsonutil.py",
    "src/graph_backlog/ledger.py",
    "src/graph_backlog/mutations.py",
)


class EvidencePolicyError(ValueError):
    """Raised when a pilot manifest or requested path is invalid."""


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidencePolicyError(f"Cannot load evidence manifest {path}: {exc}") from exc
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("surfaces"), list):
        raise EvidencePolicyError("Evidence manifest must use schema_version 1 and define surfaces")
    for surface in manifest["surfaces"]:
        if surface.get("class") not in CLASS_RANK or not surface.get("paths"):
            raise EvidencePolicyError("Every surface needs a valid class and at least one path")
    return manifest


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/").removeprefix("./")
    pure = PurePosixPath(normalized)
    if not normalized or pure.is_absolute() or PureWindowsPath(value).drive or ".." in pure.parts:
        raise EvidencePolicyError(f"Path must be repository-relative: {value}")
    return pure.as_posix()


def _matches(path: str, pattern: str) -> bool:
    path = path.casefold()
    pattern = pattern.casefold()
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def _default_class(path: str) -> str:
    folded = path.casefold()
    pure = PurePosixPath(folded)
    if folded.startswith(".github/workflows/"):
        return "E2_OPERATIONAL"
    if pure.suffix in NON_EXECUTABLE_SUFFIXES or pure.name in NON_EXECUTABLE_NAMES:
        return "E0_NON_EXECUTABLE"
    return "E1_LOCAL_BEHAVIOR"


def classify_delivery(
    candidate_manifest_path: Path,
    changed_paths: Sequence[str],
    declared_class: str,
    *,
    graph_status: str = "NOT_RUN",
    parent_manifest_path: Path | None = None,
) -> dict[str, Any]:
    if declared_class not in CLASS_RANK:
        raise EvidencePolicyError(f"Unknown evidence class: {declared_class}")
    if graph_status not in GRAPH_GAPS:
        raise EvidencePolicyError(f"Unknown graph status: {graph_status}")
    paths = sorted({normalize_path(path) for path in changed_paths})
    if not paths:
        raise EvidencePolicyError("At least one changed path is required")

    candidate_manifest = load_manifest(candidate_manifest_path)
    candidate_bytes = candidate_manifest_path.read_bytes()
    if parent_manifest_path is None:
        policy_manifest = candidate_manifest
        manifest_basis = "bootstrap_candidate"
    else:
        policy_manifest = load_manifest(parent_manifest_path)
        manifest_basis = "parent"

    selections: list[dict[str, Any]] = []
    effective_class = "E0_NON_EXECUTABLE"
    for path in paths:
        matches: list[dict[str, str]] = []
        if path == MANIFEST_PATH:
            matches.append({"rule": "builtin_manifest_authority", "class": "E3_CRITICAL"})
        if any(_matches(path, pattern) for pattern in FIXED_E3_PATTERNS):
            matches.append({"rule": "builtin_named_e3_floor", "class": "E3_CRITICAL"})
        for surface in policy_manifest["surfaces"]:
            for pattern in surface["paths"]:
                if _matches(path, pattern):
                    matches.append({"rule": surface["id"], "class": surface["class"]})
                    break
        if not matches:
            matches.append({"rule": "unmapped_path_floor", "class": _default_class(path)})
        path_class = max((item["class"] for item in matches), key=CLASS_RANK.__getitem__)
        effective_class = max((effective_class, path_class), key=CLASS_RANK.__getitem__)
        selections.append({"path": path, "effective_class": path_class, "rules": matches})

    would_hold = CLASS_RANK[declared_class] < CLASS_RANK[effective_class]
    gaps = [gap for gap in (GRAPH_GAPS[graph_status],) if gap]
    return {
        "schema_version": 1,
        "repository": candidate_manifest["repository"],
        "policy": candidate_manifest["policy"],
        "mode": "OBSERVE",
        "admission_enforced": False,
        "declared_class": declared_class,
        "effective_class": effective_class,
        "would_hold": would_hold,
        "delivery_state": "HELD" if would_hold else "PREPARED",
        "manifest_basis": manifest_basis,
        "candidate_manifest_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "graph_evidence": {"status": graph_status, "admission_authority": False},
        "evidence_gaps": gaps,
        "paths": selections,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify delivery evidence in P1 observation mode")
    parser.add_argument("--manifest", type=Path, default=Path(MANIFEST_PATH))
    parser.add_argument("--parent-manifest", type=Path)
    parser.add_argument("--declared", required=True, choices=EVIDENCE_CLASSES)
    parser.add_argument("--path", action="append", required=True, dest="paths")
    parser.add_argument("--graph-status", choices=tuple(GRAPH_GAPS), default="NOT_RUN")
    args = parser.parse_args(argv)
    try:
        receipt = classify_delivery(
            args.manifest,
            args.paths,
            args.declared,
            graph_status=args.graph_status,
            parent_manifest_path=args.parent_manifest,
        )
    except EvidencePolicyError as exc:
        parser.error(str(exc))
    print(canonical_json(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
