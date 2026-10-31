"""Real split/threshold/metric regression for selection-only Track T aggregation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track_t_r3 as T
import common as RC
import split as S


def keys(prefix, count, predicate):
    found = []
    for i in range(100000):
        value = prefix + str(i)
        if predicate(value):
            found.append(value)
            if len(found) == count:
                return found
    raise AssertionError('fixture split search exhausted')


def fixture():
    # A carve-out row is GROUP70 train but can be QUESTION70 heldout. This is
    # precisely the population that previously leaked into question70.report.
    train_report = keys('train-report-', 40, lambda g:
        S.GROUP70.assign({'group_id': g}) == S.TRAIN and T.in_carveout(g) and T.half_of(g) == 'report')
    held_selection = keys('held-selection-', 4, lambda g:
        S.GROUP70.assign({'group_id': g}) == S.HELDOUT and T.half_of(g) == 'selection')
    held_report = keys('held-report-', 4, lambda g:
        S.GROUP70.assign({'group_id': g}) == S.HELDOUT and T.half_of(g) == 'report')
    q = keys('question-', 1, lambda q: S.QUESTION70.assign({'qname': q}) == S.HELDOUT)[0]
    records = []
    for group in train_report + held_selection + held_report:
        for variant in RC.T1_VARIANTS:
            records.append({'source': 'akhilaaa3-hard', 'group_id': group, 'task': 'T1',
                'qname': q, 'input': 'input ' + group, 'task_definition': 'choose', 'question': q,
                'levels': [{'id': 'a', 'name': 'A', 'definition': 'a'},
                           {'id': 'b', 'name': 'B', 'definition': 'b'}],
                'level_type': 'nominal', 'candidate_set': 'exclusive', 'variant': variant, 'gold': 'a'})
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'fixture.jsonl'
        p.write_text(''.join(json.dumps(r) + '\n' for r in records))
        records = RC.load_records(str(p))
    rows = [T.make_readout(r, [2., -1.] if r['variant'] != 'letters' else [1., 0.]) for r in records]
    return records, {role: list(rows) for role in T.ROLES}


class SelectionBoundary(unittest.TestCase):
    def test_report_training_rows_fit_tau_but_never_reach_metric_aggregation(self):
        records, roles = fixture()
        full = T.build_track_t(roles, records)
        self.assertTrue(full['question70']['report'])
        original = T.CELL_METRICS[T.CONFIG_R3['tie_rule']]
        seen = []
        def metrics(decided, fitted):
            self.assertTrue(all(T.half_of(d.row['group_id']) == 'selection' for d in decided))
            seen.extend(decided)
            return original(decided, fitted)
        with patch.dict(T.CELL_METRICS, {T.CONFIG_R3['tie_rule']: metrics}):
            selected = T.build_track_t(roles, records, selection_only=True)
        self.assertTrue(seen)
        self.assertNotIn('report', selected['cells'])
        self.assertNotIn('report', selected['question70'])
        self.assertNotIn('report', selected['decision_lines'])
        self.assertEqual(selected['cells']['selection'], full['cells']['selection'])
        self.assertEqual(selected['question70']['selection'], full['question70']['selection'])
        self.assertEqual(selected['selection'], full['selection'])
        for role in T.ROLES:
            self.assertEqual(selected['tau_fit'][role]['carveout_rows'], 160)
            self.assertEqual(selected['tau_fit'][role]['fitted'], full['tau_fit'][role]['fitted'])

    def test_consumer_prefilter_preserves_selection_values_and_fitting(self):
        records, roles = fixture()
        full = T.build_track_t(roles, records)
        filtered = {role: [r for r in rows if S.GROUP70.assign(r) == S.TRAIN or
                          T.half_of(r['group_id']) == 'selection'] for role, rows in roles.items()}
        selected = T.build_track_t(filtered, records, selection_only=True)
        self.assertEqual(selected['cells']['selection'], full['cells']['selection'])
        self.assertEqual(selected['question70']['selection'], full['question70']['selection'])
        for role in T.ROLES:
            self.assertEqual(selected['tau_fit'][role]['fitted'], full['tau_fit'][role]['fitted'])
        with self.assertRaises(ValueError):
            T.build_track_t(roles, records, T.CONFIG_R0, selection_only=True)


if __name__ == '__main__':
    unittest.main()
