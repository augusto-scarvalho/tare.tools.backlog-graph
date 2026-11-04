"""Declared source/claim coverage must not masquerade as checked content."""
import contextlib
import copy
import io
import json
from pathlib import Path

from graph_backlog.cli import main
from graph_backlog.core import WorkGraph
from graph_backlog.jsonutil import compute_revision_hash, load_json
from graph_backlog.validation import verify_evidence


def unobserved_graph():
    graph = load_json(Path(__file__).resolve().parents[1]/'fixtures/sample-backlog.json')
    graph['sources']['unread'] = {'kind': 'doc', 'title': 'Not fetched',
        'locator': 'missing-export.txt', 'recoverability': 'RECOVERABLE_REFERENCE'}
    for node in graph['nodes']:
        node['source_refs'] = ['unread']
        node['source_claim_ids'] = ['unread:unresolved-'+node['id']]
    graph['revision'] = compute_revision_hash(graph)
    return graph


def test_locator_coverage_does_not_claim_the_missing_bytes_were_checked():
    raw = unobserved_graph()
    before = copy.deepcopy(raw)
    report = verify_evidence(WorkGraph(raw))
    assert report['recoverable_source_nodes'] == len(raw['nodes'])
    assert report['verification_scope'] == 'DECLARED_SOURCE_METADATA_ONLY'
    assert report['content_verification'] == 'NOT_PERFORMED'
    assert raw == before


def test_public_coverage_discloses_unverified_claim_ids_without_admitting_them(tmp_path):
    raw = unobserved_graph()
    path = tmp_path/'graph.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    before = path.read_bytes()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = main(['--graph', str(path), 'coverage'])
    report = json.loads(output.getvalue())
    assert result == 0, report
    claims = report['anchored_claim_nodes']  # legacy field remains compatible
    assert claims['count'] == len(raw['nodes'])
    assert claims['verification_scope'] == 'DECLARED_CLAIM_IDS_ONLY'
    assert claims['anchor_verification'] == 'NOT_PERFORMED'
    assert report['source_recoverability']['content_verification'] == 'NOT_PERFORMED'
    assert path.read_bytes() == before
