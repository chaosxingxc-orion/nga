#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import os

spec=importlib.util.spec_from_file_location('finish',Path(__file__).with_name('reference_finish.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class TerminalTests(unittest.TestCase):
    def test_wrapper_conflict_staleness_and_substring_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m.atomic(r/'REFERENCE_COMPLETE.json',{'rc':0})
            self.assertEqual(m.wrapper_state(r),'pending')
            (r/'DONE').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
            self.assertEqual(m.wrapper_state(r),'ready')
            (r/'FAILED').write_text('rc=1')
            with self.assertRaises(ValueError):m.wrapper_state(r)
            (r/'FAILED').unlink();(r/'DONE').write_text('bad rc=0 utc=garbage')
            with self.assertRaises(ValueError):m.wrapper_state(r)
            (r/'DONE').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
            os.utime(r/'DONE',ns=(1,1))
            with self.assertRaises(ValueError):m.wrapper_state(r)

    def test_missing_success_failure_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'terminal.json'
            self.assertEqual(m.terminal_state(p),'pending')
            m.atomic(p,{'rc':0});self.assertEqual(m.terminal_state(p),'ready')
            for obj in [{'rc':1},{'rc':False},{'status':'success'},{'rc':'0'}]:
                m.atomic(p,obj)
                with self.assertRaises(ValueError):m.terminal_state(p)
            p.write_text('incomplete')
            with self.assertRaises(ValueError):m.terminal_state(p)

    def test_real_subprocess_chain_and_failed_audit_blocks_comparison(self):
        for fail in [False, True]:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);run=root/'run';run.mkdir();out=root/'finish';out.mkdir()
                config=root/'config.json';config.write_text(json.dumps({'out':str(run)}))
                m.atomic(run/'REFERENCE_COMPLETE.json',{'rc':0});(run/'DONE').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
                audit=root/'audit.py';compare=root/'compare.py'
                audit.write_text('import sys,json\nfrom pathlib import Path\n'+
                    ('raise SystemExit(1)\n' if fail else 'Path(sys.argv[sys.argv.index("--out")+1]).write_text(json.dumps({"status":"test"}))\n'))
                compare.write_text('import sys\nfrom pathlib import Path\nPath(sys.argv[sys.argv.index("--out")+1]).write_text("{}")\n')
                plan={'out':str(out),'config':str(config),'auditor':str(audit),'comparison':str(compare),
                      'upstream':str(root),'files':{str(p):m.digest(p) for p in [config,audit,compare]}}
                pp=root/'plan.json';pp.write_text(json.dumps(plan))
                result=subprocess.run([sys.executable,'-P',str(Path(m.__file__)),'--plan',str(pp)],capture_output=True,timeout=10)
                terminal=json.loads((out/'FINISH_COMPLETE.json').read_text())
                self.assertEqual(result.returncode==0,not fail)
                self.assertEqual(terminal['rc'],1 if fail else 0)
                self.assertEqual((out/'PUBLISHED_COMPARISON.json').exists(),not fail)


if __name__=='__main__':unittest.main()
