"""Exercise actual host start orchestration without spawning hardware work."""
import contextlib
import io
import json
import socket
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_config_panel_host as H


class HostStartEnvironment(unittest.TestCase):
    def test_start_with_configured_bytecode_flag_reaches_popen(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = dict(out=str(root), host_name=socket.gethostname(),
                     host_python='/usr/bin/python3.12',
                     host_environment={'PYTHONDONTWRITEBYTECODE': '1',
                                       'NGA_START_TEST': 'configured'})
            argv = ['host.py', 'start', '--plan', '/fixture/PLAN.json',
                    '--sha256', 'a' * 64, '--review', '/fixture/REVIEW.json',
                    '--review-sha256', 'b' * 64, '--attempt', '1']
            with patch.object(H.sys, 'argv', argv), \
                 patch.object(H, 'verify', return_value=d), \
                 patch.object(H, 'approval') as approval, \
                 patch.object(H, 'previous') as previous, \
                 patch.object(H.subprocess, 'Popen', return_value=types.SimpleNamespace(pid=12345)) as spawn, \
                 patch.dict(H.os.environ, {'PYTHONDONTWRITEBYTECODE': '0', 'NGA_START_TEST': 'inherited'}), \
                 contextlib.redirect_stdout(io.StringIO()):
                H.main()
            approval.assert_called_once()
            previous.assert_called_once()
            spawn.assert_called_once()
            command, options = spawn.call_args.args[0], spawn.call_args.kwargs
            self.assertEqual(options['env']['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertEqual(options['env']['NGA_START_TEST'], 'configured')
            self.assertTrue(options['start_new_session'])
            self.assertEqual(options['stdin'], H.subprocess.DEVNULL)
            self.assertIn('supervise', command)
            h = root / 'host_attempts/1'
            self.assertEqual(json.loads((h/'SERVICE.json').read_text()), {'pid': 12345, 'command': command})
            self.assertEqual(json.loads((h/'START_INTENT.json').read_text())['command'], command)
            self.assertEqual(json.loads((h/'RELAUNCH.json').read_text())['command'], command)
            self.assertFalse((h/'CLAIM.json').exists())
            self.assertFalse((h/'EXIT.json').exists())


if __name__ == '__main__':
    unittest.main()
