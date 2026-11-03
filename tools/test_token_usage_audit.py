import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest

from tools import token_usage_audit as A


class AuditTests(unittest.TestCase):
    def test_timezone_and_precision(self):
        self.assertEqual(A.instant('2026-11-03T03:10:00Z'),
                         A.instant('2026-11-03T03:10:00.000Z'))
        self.assertEqual(A.instant('2026-11-03T04:10:00+01:00'),
                         A.instant('2026-11-03T03:10:00Z'))
        with self.assertRaises(ValueError):
            A.instant('2026-11-03T03:10:00')

    def test_actual_parser_owns_dedup_scope_and_cache_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'nga';project.mkdir();codex=root/'codex';codex.mkdir()
            claude=root/'claude';out=root/'out';rollout=root/'rollout.jsonl'
            usage={'input_tokens':100,'cached_input_tokens':80,'output_tokens':10,
                   'reasoning_output_tokens':4,'total_tokens':110}
            def record(ordinal,typ,payload,stamp='2026-11-03T03:10:00Z'):
                return {'ordinal':ordinal,'type':typ,'payload':payload,'timestamp':stamp}
            def own(ordinal,rid='r',thread='child',stamp='2026-11-03T03:10:00Z'):
                return record(ordinal,'token_usage_record',
                              {'thread_id':thread,'response_id':rid,'usage':usage},stamp)
            rows=[record(0,'session_meta',{'subagent_history_start_ordinal':10}),
                  own(1,'inherited','parent'),
                  record(10,'event_msg',{'type':'token_count','info':{
                      'total_token_usage':{'total_tokens':999999}}}),
                  own(11),own(12),own(13,'foreign','parent'),
                  own(14,'late',stamp='2026-11-03T03:10:00.001Z')]
            rollout.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with sqlite3.connect(codex/'state_5.sqlite') as db:
                db.execute('CREATE TABLE threads(id,rollout_path,cwd,tokens_used,agent_path,title,thread_source,created_at)')
                created=A.instant('2026-11-03T03:09:00Z').timestamp()
                db.execute('INSERT INTO threads VALUES(?,?,?,?,?,?,?,?)',
                           ('child',str(rollout),str(project),999999,'/root/check','check','test',created))
                db.execute('INSERT INTO threads VALUES(?,?,?,?,?,?,?,?)',
                           ('outside',str(root/'must-not-read'),'/other',1,None,'other','test',created))
            with sqlite3.connect(codex/'goals_1.sqlite') as db:
                db.execute('CREATE TABLE thread_goals(thread_id,tokens_used,time_used_seconds,status,created_at_ms,updated_at_ms)')
            croot=claude/'projects'/str(project).replace('/','-');croot.mkdir(parents=True)
            cu={'input_tokens':5,'cache_read_input_tokens':70,'cache_creation_input_tokens':20,
                'output_tokens':10,'output_tokens_details':{'thinking_tokens':4}}
            row={'type':'assistant','cwd':str(project),'timestamp':'2026-11-03T04:10:00+01:00',
                 'message':{'id':'m','model':'fixture','usage':cu}}
            outside=dict(row,cwd='/other',message=dict(row['message'],id='outside'))
            late=dict(row,timestamp='2026-11-03T03:10:01Z',message=dict(row['message'],id='late'))
            (croot/'session.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in [row,row,outside,late]))
            args=types.SimpleNamespace(project=str(project),codex=str(codex),claude=str(claude),
                                       cutoff='2026-11-03T03:10:00.000Z',output=str(out))
            with contextlib.redirect_stdout(io.StringIO()):
                A.run(args)
            s=json.loads((out/'summary.json').read_text())
            self.assertEqual(s['codex']['totals']['total_tokens'],110)
            self.assertEqual(s['codex']['totals']['noncached_input_plus_output'],30)
            self.assertEqual(s['codex']['totals']['reasoning_output_tokens'],4)
            self.assertEqual(s['codex']['threads_scanned'],1)
            self.assertEqual(s['codex']['dedup_diagnostics']['duplicate_response_id'],1)
            self.assertEqual(s['codex']['dedup_diagnostics']['inherited_usage_excluded'],1)
            self.assertEqual(s['claude']['totals']['total_tokens'],105)
            self.assertEqual(s['claude']['totals']['noncached_input_plus_output'],35)
            self.assertEqual(s['claude']['totals']['uncached_input_tokens'],5)
            self.assertEqual(s['claude']['stream_rows_dropped'],1)
            self.assertEqual(s['claude']['out_of_project_rows_excluded'],1)
            self.assertEqual(len((out/'responses.jsonl').read_text().splitlines()),2)


if __name__=='__main__':
    unittest.main()
