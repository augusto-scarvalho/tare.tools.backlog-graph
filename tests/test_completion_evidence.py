from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph_backlog.core import WorkGraph
from graph_backlog.cli import main
from graph_backlog.jsonutil import UsageError, compute_revision_hash, load_json
from graph_backlog.mutations import (
    complete_node_in_graph, execute_graph_transaction, land_train_tasks,
)
from graph_backlog.validation import (
    validate_completion_evidence, validate_work_graph, verify_evidence,
)


FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'sample-backlog.json'


class CompletionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = load_json(FIXTURE)
        self.graph = WorkGraph(self.raw)

    def closed(self, node_id='TASK-02', grade='C'):
        after = copy.deepcopy(self.raw)
        node = next(n for n in after['nodes'] if n['id'] == node_id)
        node['completion'].update(
            status='DONE', dod_satisfied=True, evidence_grade=grade,
            evidence_grade_reason='Declared scope is limited to the recorded reference',
            dod_evidence=['artifact:synthetic-review'],
        )
        return after, node

    def assert_refused_without_write(self, after, diagnostic):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.json'
            path.write_text(json.dumps(self.raw), encoding='utf-8')
            original = path.read_bytes()
            with patch('graph_backlog.mutations.atomic_write') as write:
                with self.assertRaisesRegex(UsageError, diagnostic):
                    execute_graph_transaction(path, lambda graph: copy.deepcopy(after))
                write.assert_not_called()
            self.assertEqual(path.read_bytes(), original)

    def test_invalid_declarations_abort_before_write(self):
        cases = (
            ('grade_missing', 'COMPLETION_EVIDENCE_GRADE_REQUIRED'),
            ('reason_missing', 'COMPLETION_EVIDENCE_GRADE_REASON_REQUIRED'),
            ('provenance_missing', 'COMPLETION_PROVENANCE_REQUIRED'),
            ('invalid_grade', 'COMPLETION_EVIDENCE_GRADE_INVALID'),
            ('minimum', 'COMPLETION_EVIDENCE_GRADE_INSUFFICIENT'),
            ('empty_evidence', 'COMPLETION_DOD_EVIDENCE_REQUIRED'),
            ('blank_evidence', 'COMPLETION_DOD_EVIDENCE_REQUIRED'),
            ('unknown_source', 'COMPLETION_SOURCE_REF_INVALID'),
        )
        for case, diagnostic in cases:
            with self.subTest(case=case):
                after, node = self.closed()
                completion = node['completion']
                if case == 'grade_missing':
                    completion.pop('evidence_grade')
                elif case == 'reason_missing':
                    completion['evidence_grade_reason'] = '  '
                elif case == 'provenance_missing':
                    node['provenance'] = []
                    node['source_refs'] = []
                elif case == 'invalid_grade':
                    completion['evidence_grade'] = 'tests passed'
                elif case == 'minimum':
                    node['readiness']['minimum_evidence_grade'] = 'B'
                elif case == 'empty_evidence':
                    completion['dod_evidence'] = []
                elif case == 'blank_evidence':
                    completion['dod_evidence'] = ['  ']
                elif case == 'unknown_source':
                    node['source_refs'] = ['not-registered']
                self.assert_refused_without_write(after, diagnostic)

    def test_high_grades_require_recoverable_registered_source(self):
        for grade in ('A', 'B'):
            for locator, recoverability in (
                ('', 'CONTENT_ADDRESSED'),
                ('   ', 'EXACT_BYTES'),
                ('artifact:declared', 'UNRESOLVED_REFERENCE'),
            ):
                with self.subTest(grade=grade, locator=locator, recoverability=recoverability):
                    after, node = self.closed(grade=grade)
                    after['sources']['SRC-INIT'].update(
                        locator=locator, recoverability=recoverability,
                    )
                    self.assert_refused_without_write(
                        after, 'HIGH_GRADE_WITHOUT_RECOVERABLE_SOURCE',
                    )

    def test_explicit_grades_with_real_fixture_source(self):
        for grade in ('A', 'B', 'C', 'D'):
            with self.subTest(grade=grade):
                before = copy.deepcopy(self.raw)
                result = complete_node_in_graph(
                    self.graph, 'TASK-02', 'artifact:synthetic-review', grade,
                    'Explicitly declared reference scope', ['SRC-INIT'],
                )
                node = WorkGraph(result).by_id['TASK-02']
                self.assertEqual(node['completion']['evidence_grade'], grade)
                self.assertIn('SRC-INIT', node['completion']['dod_evidence'])
                self.assertIn('artifact:synthetic-review', node['provenance'])
                self.assertEqual(node['source_refs'], ['SRC-INIT'])
                self.assertEqual(result['sources'], self.raw['sources'])
                self.assertEqual(self.raw, before)
                self.assertEqual(validate_work_graph(result)['status'], 'PASS')

    def test_c_with_declared_provenance_does_not_need_recoverable_source(self):
        raw = copy.deepcopy(self.raw)
        node = WorkGraph(raw).by_id['TASK-02']
        node['source_refs'] = []
        node['provenance'] = []
        result = complete_node_in_graph(
            WorkGraph(raw), 'TASK-02', 'artifact:synthetic-review', 'C', 'Limited declaration',
        )
        closed = WorkGraph(result).by_id['TASK-02']
        self.assertEqual(closed['provenance'], ['artifact:synthetic-review'])
        self.assertEqual(closed['source_refs'], [])

    def test_owner_apis_never_inherit_grade(self):
        for operation in (
            lambda: complete_node_in_graph(self.graph, 'TASK-02', 'artifact:ref'),
            lambda: land_train_tasks(self.graph, 'TRAIN-1', ['TASK-02'], 'artifact:ref'),
        ):
            with self.assertRaisesRegex(UsageError, 'COMPLETION_EVIDENCE_GRADE_REQUIRED'):
                operation()

    def test_actionable_owner_requires_nonempty_evidence(self):
        for evidence in (None, '', '   '):
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(UsageError, 'COMPLETION_DOD_EVIDENCE_REQUIRED'):
                    complete_node_in_graph(self.graph, 'TASK-02', evidence, 'C', 'Reason')

    def test_unknown_source_is_not_created(self):
        before = copy.deepcopy(self.raw)
        with self.assertRaisesRegex(UsageError, 'COMPLETION_SOURCE_REF_INVALID'):
            complete_node_in_graph(
                self.graph, 'TASK-02', 'artifact:ref', 'C', 'Reason', ['missing'],
            )
        self.assertEqual(self.raw, before)

    def test_atomic_batch_aborts_when_one_target_fails(self):
        raw = copy.deepcopy(self.raw)
        WorkGraph(raw).by_id['TASK-03']['readiness']['minimum_evidence_grade'] = 'A'
        before = copy.deepcopy(raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            original = path.read_bytes()
            with patch('graph_backlog.mutations.atomic_write') as write:
                with self.assertRaisesRegex(UsageError, 'COMPLETION_EVIDENCE_GRADE_INSUFFICIENT'):
                    execute_graph_transaction(
                        path, lambda graph: land_train_tasks(
                            graph, 'TRAIN-1', ['TASK-02', 'TASK-03'], 'artifact:ref',
                            evidence_grade='C', evidence_grade_reason='Limited scope',
                        ),
                    )
                write.assert_not_called()
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(raw, before)

    def test_legacy_done_does_not_block_another_node(self):
        raw = copy.deepcopy(self.raw)
        WorkGraph(raw).by_id['TASK-01']['completion'].pop('evidence_grade')
        result = complete_node_in_graph(
            WorkGraph(raw), 'TASK-02', 'artifact:ref', 'C', 'Limited scope',
        )
        self.assertNotIn('evidence_grade', WorkGraph(result).by_id['TASK-01']['completion'])
        validate_completion_evidence(raw, result)
        self.assertEqual(validate_work_graph(result)['status'], 'PASS')

    def test_exact_legacy_replay_and_unrelated_edit(self):
        raw = copy.deepcopy(self.raw)
        WorkGraph(raw).by_id['TASK-01']['completion'].pop('evidence_grade')
        validate_completion_evidence(raw, copy.deepcopy(raw))
        after = copy.deepcopy(raw)
        WorkGraph(after).by_id['TASK-01']['title'] = 'Unrelated metadata edit'
        validate_completion_evidence(raw, after)

    def test_kind_change_does_not_escape_guard(self):
        after, node = self.closed()
        node['kind'] = 'group'
        node['completion'].pop('evidence_grade')
        self.assert_refused_without_write(after, 'COMPLETION_EVIDENCE_GRADE_REQUIRED')

    def test_existing_done_completion_revision_is_guarded(self):
        after, node = self.closed('TASK-01')
        node['completion'].pop('evidence_grade')
        self.assert_refused_without_write(after, 'COMPLETION_EVIDENCE_GRADE_REQUIRED')

    def test_replay_preserves_completion_timestamps_and_original_grade(self):
        raw = copy.deepcopy(self.raw)
        node = WorkGraph(raw).by_id['TASK-02']
        node['completion']['evidence_grade_original'] = 'D'
        node['completion']['custom_historical_field'] = 'preserved'
        result = complete_node_in_graph(WorkGraph(raw), 'TASK-02', 'artifact:ref', 'C', 'Reason')
        replay = complete_node_in_graph(WorkGraph(result), 'TASK-02', 'artifact:ref', 'C', 'Reason')
        self.assertEqual(result, replay)
        completion = WorkGraph(replay).by_id['TASK-02']['completion']
        self.assertEqual(completion['evidence_grade_original'], 'D')
        self.assertEqual(completion['custom_historical_field'], 'preserved')
        landed = land_train_tasks(
            WorkGraph(result), 'TRAIN-1', ['TASK-02'], 'artifact:ref',
            evidence_grade='C', evidence_grade_reason='Reason',
        )
        replay_landed = land_train_tasks(
            WorkGraph(landed), 'TRAIN-1', ['TASK-02'], 'artifact:ref',
            evidence_grade='C', evidence_grade_reason='Reason',
        )
        self.assertEqual(landed, replay_landed)

    def test_transaction_snapshots_in_place_callbacks(self):
        def mutate(graph):
            node = graph.by_id['TASK-02']
            node['completion'].update(status='DONE', dod_satisfied=True, evidence_grade=None)
            return graph.to_dict()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.json'
            path.write_text(json.dumps(self.raw), encoding='utf-8')
            original = path.read_bytes()
            with patch('graph_backlog.mutations.atomic_write') as write:
                with self.assertRaisesRegex(UsageError, 'COMPLETION_EVIDENCE_GRADE_REQUIRED'):
                    execute_graph_transaction(path, mutate)
                write.assert_not_called()
            self.assertEqual(path.read_bytes(), original)

    def test_nonactionable_and_unfinished_do_not_require_closure_grade(self):
        raw = copy.deepcopy(self.raw)
        node = WorkGraph(raw).by_id['TASK-02']
        node['kind'] = 'group'
        node['completion']['evidence_grade'] = None
        result = complete_node_in_graph(WorkGraph(raw), 'TASK-02')
        self.assertEqual(WorkGraph(result).by_id['TASK-02']['completion']['status'], 'DONE')
        raw['nodes'] = [raw['nodes'][1]]
        raw['edges'] = []
        node['kind'] = 'task'
        node['completion']['evidence_grade'] = None
        for status in ('NOT_DONE', 'PARTIAL'):
            node['completion']['status'] = status
            report = verify_evidence(WorkGraph(raw))
            self.assertFalse(any(i['issue'].startswith('COMPLETION_') for i in report['issues']))

    def test_report_exposes_legacy_gaps_without_writes(self):
        raw = copy.deepcopy(self.raw)
        WorkGraph(raw).by_id['TASK-01']['completion'].pop('evidence_grade')
        before = copy.deepcopy(raw)
        revision = compute_revision_hash(raw)
        with patch('graph_backlog.mutations.atomic_write') as write:
            report = verify_evidence(WorkGraph(raw))
            write.assert_not_called()
        issues = {i['issue'] for i in report['issues'] if i['id'] == 'TASK-01'}
        self.assertIn('COMPLETION_EVIDENCE_GRADE_REQUIRED', issues)
        self.assertIn('COMPLETION_EVIDENCE_GRADE_REASON_REQUIRED', issues)
        self.assertIn('COMPLETION_DOD_EVIDENCE_REQUIRED', issues)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['nodes'], 3)
        self.assertEqual(report['recoverable_source_nodes'], 3)
        self.assertEqual(report['coverage'], 1.0)
        self.assertEqual(raw, before)
        self.assertEqual(compute_revision_hash(raw), revision)

    def test_public_cli_rejects_missing_grade_then_persists_explicit_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.json'
            path.write_text(json.dumps(self.raw), encoding='utf-8')
            original = path.read_bytes()
            args = ['--graph', str(path), 'complete-node', 'TASK-02',
                    '--evidence', 'artifact:cli-review', '--save']
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)
            self.assertEqual(path.read_bytes(), original)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args + ['--grade', 'C', '--grade-reason', 'Manual fixture review']), 0)
            node = WorkGraph(load_json(path)).by_id['TASK-02']
            self.assertEqual(node['completion']['evidence_grade'], 'C')
            self.assertIn('artifact:cli-review', node['provenance'])

    def test_public_cli_land_alias_honors_explicit_source_and_grade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.json'
            path.write_text(json.dumps(self.raw), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--graph', str(path), 'land-train', '--train', 'TRAIN-CLI',
                    '--tasks', 'TASK-02', '--evidence', 'artifact:cli-review', '--grade', 'B',
                    '--grade-reason', 'Declared synthetic automated log', '--source-ref', 'SRC-INIT']), 0)
            node = WorkGraph(load_json(path)).by_id['TASK-02']
            self.assertEqual(node['completion']['landed_train'], 'TRAIN-CLI')
            self.assertEqual(node['completion']['evidence_grade'], 'B')
            self.assertEqual(node['source_refs'], ['SRC-INIT'])


if __name__ == '__main__':
    unittest.main()
