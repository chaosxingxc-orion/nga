import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('r0_report', Path(__file__).with_name('r3_r0_report.py'))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)


class R0Report(unittest.TestCase):
    def test_code_record_allows_bound_entry_but_rejects_omission_or_unbound_code(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'code').mkdir()
            science=root/'code/science.py';entry=root/'code/entry.py'
            science.write_text('X=1');entry.write_text('X=2')
            prep={'out':'/prep','files':{'/prep/code/science.py':R.sha(science)}}
            record=root/'SHA1SUMS'
            def write_record(paths, bound):
                record.write_text(''.join(R.hashlib.sha1(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in paths))
                (root/'plan.json').write_text(json.dumps({'files':{str(p):R.sha(p) for p in [record,*bound]}}))
            write_record([science,entry],[science,entry]);R.verify_code_record(root,prep)
            write_record([entry],[science,entry])
            with self.assertRaisesRegex(ValueError,'scientific source absent'):R.verify_code_record(root,prep)
            write_record([science,entry],[science])
            with self.assertRaisesRegex(ValueError,'not bound'):R.verify_code_record(root,prep)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name); self.out = self.run / 'instruct'; self.rd = self.out / 'trackt/readouts'; self.rd.mkdir(parents=True)
        self.model = {'path': '/pinned/instruct', 'base_path': '/pinned/instruct', 'sha256': 'a' * 64, 'kind': 'checkpoint', 'base_revision': 'rev'}
        self.prep = {'model': self.model, 'data': {'/data/manifest.json': 'manifest', '/data/T1.jsonl': 'data1', '/data/T2.jsonl': 'data2'}}
        self.scorer = {'record_grade': True, 'mode': 'rightpad', 'dtype': 'float32', 'token_budget': 16384, 'hf32': {'hf32': False}}
        self.header = {'model': self.model, 'stages': 't_score', 'track_t_config': 'r0', 'arm': 'K0', 'partitions': ['dev', 'calibration'],
                       'limit': 0, 'limit_groups': 0, 'dry_run_warnings': [], 'primary_input_mode': 'full', 'render': 'record_name',
                       'dtype': 'float32', 'scorer': self.scorer, 'prompt_version': 'v', 'prompt_format': 'f',
                       'track_t_sources': 'typed-decisions,openjev-synth,akhilaaa3', 'data_files': {'/data/T1.jsonl': 'data1', '/data/T2.jsonl': 'data2'}}
        self.receipt = {'schema': 'r3-scoring-receipt-v1', 'header': self.header, 'scientific_acceptance': False}
        self.rows = [{'key': 'a'}, {'key': 'b'}]
        self.calls = []
        def validate(rows, expected, key_fn):
            if len(rows) != len(expected) or {r['k'] for r in rows} != {key_fn(r) for r in expected}:
                raise ValueError('population mismatch')
            return sorted(rows, key=lambda r: r['k'])
        def build(by_role, records, config):
            self.calls.append((copy.deepcopy(by_role), records, config))
            return {'config': 'r0', 'decision_lines': {'all': {'B-2': [{'source': 'typed-decisions', 'level_type': kind, 'status': 'void'} for kind in ('boolean', 'nominal', 'ordinal')]}}}
        self.deps = {'prompt': SimpleNamespace(PROMPT_VERSION='v', PROMPT_FORMAT='f'),
                     'provenance_r3': SimpleNamespace(_scorer_problems=lambda x: [] if x == self.scorer else ['wrong'],
                          verify=lambda *a: {'manifests': {'one': {'scorer': self.scorer}}}),
                     'core_r3': SimpleNamespace(read_jsonl=lambda p: [json.loads(s) for s in Path(p).read_text().splitlines()]),
                     'track_t_r3': SimpleNamespace(CONFIG_R0={'name': 'r0'}, records_needed=lambda rows,c: rows,
                          make_readout=lambda row,scores: {'k': row['key'], 's': scores}, constant_and_uniform_rows=lambda *a: {'constant': [], 'uniform': []}, build_track_t=build),
                     'selection_evidence_r3': SimpleNamespace(validate_population=validate),
                     'common': SimpleNamespace(SOURCE_FILES=['fixture'], task_path=lambda root,task,source:'/data/'+task+'.jsonl',
                         load_records=lambda p: [self.rows[0 if 'T1' in p else 1]])}
        self.write(self.out / 'SCORING_RECEIPT.track_t_r0.json', self.receipt)
        self.write(self.out / 'RUN_IDENTITY.json', {'arm': 'K0', 'track_t_config': 'r0', 'prompt_version': 'v', 'model_path': self.model['path']})
        for role in R.ROLES:
            (self.rd / (role + '__task.jsonl')).write_text(''.join(json.dumps({'k': row['key'], 's': [.1,.2]}) + '\n' for row in self.rows))
        self.count = patch.object(R, 'EXPECTED_COUNT', 2); self.count.start(); self.addCleanup(self.count.stop)
    def write(self,p,v): p.write_text(json.dumps(v))

    def test_rebuild_preserves_producer_header_and_uses_full_r0(self):
        report,statuses = R.rebuild(self.run, self.prep, self.deps)
        self.assertEqual(report['header'], self.header)
        self.assertEqual(set(statuses), {'boolean','nominal','ordinal'})
        self.assertFalse(report['scientific_acceptance'])
        self.assertEqual(report['cpu_rebuild']['per_role'], dict.fromkeys(R.ROLES, 2))
        self.assertEqual(self.calls[0][2], {'name':'r0'})
        self.assertFalse((self.run/'R0RESCORE_COMPLETE.json').exists())

    def test_test_partition_r3_partial_or_wrong_model_refused_before_metrics(self):
        changes = [('partitions',['test']), ('track_t_config','r3'), ('limit_groups',1), ('arm','K1'),
                   ('model',dict(self.model,sha256='b'*64)), ('data_files',{}), ('scorer',{}), ('stages','t_score,report')]
        for key,value in changes:
            receipt=copy.deepcopy(self.receipt);receipt['header'][key]=value
            self.write(self.out/'SCORING_RECEIPT.track_t_r0.json',receipt)
            with self.subTest(key=key), self.assertRaises(ValueError):R.rebuild(self.run,self.prep,self.deps)
        self.assertEqual(self.calls,[])

    def test_missing_duplicate_and_extra_role_refused_before_metrics(self):
        p=self.rd/'primary__task.jsonl';original=p.read_text()
        for value in ('',original+original):
            p.write_text(value)
            with self.assertRaisesRegex(ValueError,'population'):R.rebuild(self.run,self.prep,self.deps)
        p.write_text(original);(self.rd/'foreign__task.jsonl').write_text(original)
        with self.assertRaisesRegex(ValueError,'unexpected readout role'):R.rebuild(self.run,self.prep,self.deps)
        self.assertEqual(self.calls,[])

    def test_provenance_failure_and_descriptor_mismatch_propagate(self):
        def refuse(*a):raise ValueError('unstamped rows')
        self.deps['provenance_r3'].verify=refuse
        with self.assertRaisesRegex(ValueError,'unstamped'):R.rebuild(self.run,self.prep,self.deps)
        self.deps['provenance_r3'].verify=lambda *a:{'manifests':{'one':{'scorer':dict(self.scorer,token_budget=1)}}}
        with self.assertRaisesRegex(ValueError,'descriptors differ'):R.rebuild(self.run,self.prep,self.deps)
        self.assertEqual(self.calls,[])

    def test_invalid_gating_population_refused(self):
        self.deps['track_t_r3'].build_track_t=lambda *a:{'config':'r0','decision_lines':{'all':{'B-2':[]}}}
        with self.assertRaisesRegex(ValueError,'gating population'):R.rebuild(self.run,self.prep,self.deps)

    def test_execution_binds_real_mounts_and_guarded_release(self):
        prep = copy.deepcopy(self.prep); prep.update(out=str(self.run/'prepared'),files={},data={},model_files={},image_sha256='image')
        files,mounts = {},[]
        for name in ('code','r0_code','r1_code'):
            source=self.run/'mounted'/name;source.mkdir(parents=True)
            f=source/'module.py';f.write_text('X=1\n');files[str(f)]=R.sha(f)
            prep['files'][str(Path(prep['out'])/name/'module.py')]=R.sha(f)
            mounts.append({'source':str(source),'destination':'/mnt/cephfs/xingchao/experiments/jev/'+('r3_code' if name=='code' else name),'readonly':True})
        spec={'evaluation_profile':'track_t_r0','model':prep['model']['path'],'image_sha256':'image','files':files,'code_mounts':mounts}
        sp=self.run/'plan.json';self.write(sp,spec)
        execution={'schema':'r3-engineering-posttrain-execution-v1','out':str(self.run),'scientific_acceptance':False,'test_read':False,
                   'spec':str(sp),'spec_sha256':R.sha(sp),'tools':{},'chip':1,'run':'r3_runs/r0'}
        ep=self.run/'execution.json';self.write(ep,execution)
        attempt=self.run/'attempts/1';attempt.mkdir(parents=True)
        end={'exit_code':0,'attempt':1};self.write(self.run/'ENGINEERING_EVAL_EXIT.json',end);self.write(attempt/'EXIT.json',end)
        self.write(attempt/'LAUNCH_RECEIPT.json',{'id':'actual-container'})
        release={'exit_code':0,'container_id':'actual-container','chip':1,'run':'r3_runs/r0'};self.write(attempt/'RELEASE.json',release)
        R.verify_execution(self.run,R.sha(ep),prep)
        self.write(attempt/'RELEASE.json',dict(release,chip=2))
        with self.assertRaisesRegex(ValueError,'release evidence'):R.verify_execution(self.run,R.sha(ep),prep)
        self.write(attempt/'RELEASE.json',release)
        prep['files'][next(iter(prep['files']))]='bad'
        with self.assertRaisesRegex(ValueError,'scientific code differs'):R.verify_execution(self.run,R.sha(ep),prep)


if __name__ == '__main__':unittest.main()
