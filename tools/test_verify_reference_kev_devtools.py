#!/usr/bin/env python3
"""Synthetic valid and corrupt artifact fixtures for the independent auditor."""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('verify_reference_kev_devtools.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / 'source'
        source.mkdir()
        self.records = [{'state': str(i), '_meta': {'id': 'collision' if i<2 else 'other', 'source': 'fixture', 'variant': 'clean'},
                         'questions': {'q': {'type': 'choice', 'criteria': {'a': None, 'b': None},
                                             'label': 'a' if i == 0 else 'b', 'src': 'fixture'}}}
                        for i in range(3)]
        (source / 'test.jsonl').write_text('\n'.join(json.dumps(r) for r in self.records))
        write(source / 'manifest.json', {'files': {'test.jsonl': {
            'sha256': m.digest(source / 'test.jsonl'), 'records': 3, 'questions': 3}}})
        base, checkpoint, code = self.root/'base', self.root/'checkpoint', self.root/'code'/'kev'
        for folder, names in [(base, ['config.json','tokenizer.json','.complete','model.safetensors']),
                              (checkpoint, ['head.pt','adapter_config.json','adapter_model.safetensors']),
                              (code, ['checkpoint.py','model.py','predictors.py','benchmark.py','metrics.py','api.py','suite.py']),
                              (self.root, ['reference_kev_devtools.py','verify_reference_kev_devtools.py','run.sh','launch.sh','LAUNCH_EXACT.sh','PREREGISTRATION.md'])]:
            folder.mkdir(parents=True, exist_ok=True)
            for name in names: (folder/name).write_text('synthetic dependency')
        write(self.root/'release.json', {'drop_ids':['collision']})
        self.config = {'out': str(self.root), 'checkpoint': 'fixture', 'runtime': {'fixture': '1'},
                       'files': {str(p): m.digest(p) for p in self.root.rglob('*') if p.is_file()},
                       'suites': [{'name': 'suite', 'path': str(source), 'records': 3,
                                   'questions': 3, 'release_questions': 1}]}
        self.config.update(release_spec=str(self.root/'release.json'),drop_ids=['collision'],base=str(base), checkpoint=str(checkpoint), kev_code=str(code.parent))
        self.config_path = self.root / 'config.json'
        write(self.config_path, self.config)
        self.stamp = m.object_digest(self.config)
        write(self.root / 'CONFIG_RECEIPT.json', {'stamp': self.stamp})
        write(self.root / 'ENVIRONMENT.json', {'runtime': {'fixture': '1'}, 'temperature': 2.})
        d = self.root / 'suite'
        write(d / 'EXPECTED.json', {'stamp': self.stamp, 'ids': [{'index':i,'id':r['_meta']['id'],'input_sha256':m.object_digest(r)} for i,r in enumerate(self.records)],
                                   'input_hashes': [m.object_digest(r) for r in self.records]})
        rows = []
        for i, record in enumerate(self.records):
            prediction = {'probabilities': {'q': {'a': .75, 'b': .25}},
                          'logits': {'q': {'a': math.log(3), 'b': 0.}}, 'inference_temperature': 2.}
            payload = {'index':i,'original_id':record['_meta']['id'],'stamp': self.stamp, 'input_sha256': m.object_digest(record),
                       'prediction': prediction, 'seconds': .1}
            write(d / 'records' / f'{i:06d}.json', {'payload': payload, 'sha256': m.object_digest(payload)})
            for j,row in enumerate(m.build_rows(record,prediction,2.)):
                row.update(record_index=i,question_index=j,input_sha256=m.object_digest(record));rows.append(row)
        write(d / 'rows.json', rows)
        native = {'full': m.metrics(rows), 'release': m.metrics(rows[2:])}
        raw = {'full': m.metrics(rows,2.), 'release': m.metrics(rows[2:],2.)}
        write(d/'report.json', {'stamp':self.stamp,'split':'test','reference_model':str(checkpoint),
              'records':3,'questions':3,'native_serving_temperature':2.,'native':native,'raw_temperature_one':raw,
              'drop_ids':['collision'],'excluded_record_indices':[0,1]})
        self.rebind()

    def rebind(self):
        d = self.root / 'suite'
        bindings = {'suite': {'report_sha256': m.digest(d / 'report.json'),
                              'rows_sha256': m.digest(d / 'rows.json')}}
        write(self.root / 'REFERENCE_COMPLETE.json', {'rc': 0, 'stamp': self.stamp, 'suites': bindings})
        write(self.root / 'report.json', {'stamp': self.stamp, 'run_of_record': True, 'suite_reports': bindings})

    def test_valid_collision(self):
        r=m.audit(self.config_path);self.assertEqual(r['suites']['suite']['full']['native']['n'],3)
        self.assertEqual(r['suites']['suite']['release']['native']['n'],1)
    def test_missing_collision_record(self):
        (self.root/'suite/records/000001.json').unlink()
        with self.assertRaisesRegex(ValueError,'Missing'):m.audit(self.config_path)
    def test_position_forged(self):
        p=self.root/'suite/records/000001.json';o=json.loads(p.read_text());o['payload']['index']=0;o['sha256']=m.object_digest(o['payload']);write(p,o)
        with self.assertRaisesRegex(ValueError,'position'):m.audit(self.config_path)
    def test_wrong_release_rehashed(self):
        p=self.root/'suite/report.json';o=json.loads(p.read_text());o['native']['release']['acc']=1.;write(p,o);self.rebind()
        with self.assertRaisesRegex(ValueError,'acc'):m.audit(self.config_path)
    def test_wrong_exclusion_rehashed(self):
        p=self.root/'suite/report.json';o=json.loads(p.read_text());o['excluded_record_indices']=[0];write(p,o);self.rebind()
        with self.assertRaisesRegex(ValueError,'Exclusion'):m.audit(self.config_path)

if __name__=='__main__':unittest.main()
