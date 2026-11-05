import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import unified_container_log_follower_v1 as follower
from tools import unified_service_supervisor_v1 as supervisor


class ClosureTest(unittest.TestCase):
    def test_pipeline_change_rejects_supervisor_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool_dir = root / 'tools'
            tool_dir.mkdir()
            for source in follower.PIN_PATHS:
                target = root / source.relative_to(follower.REPO)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            old_here, old_registry = supervisor.HERE, supervisor.REGISTRY
            try:
                supervisor.HERE = tool_dir
                supervisor.REGISTRY = {'unified_container_log_follower_v1': (tool_dir / 'unified_container_log_follower_v1.py', 'serve')}
                paths = [root / p.relative_to(follower.REPO) for p in follower.PIN_PATHS]
                capture = root / 'capture.json'
                capture.write_text(json.dumps({'code_pins': {str(p): supervisor.digest(p) for p in paths}}))
                pin = lambda p: {'path': str(p), 'sha256': supervisor.digest(p)}
                config = root / 'supervisor.json'
                config.write_text(json.dumps({'schema':'unified-service-supervisor-v1', 'service':'unified_container_log_follower_v1',
                    'entry':pin(paths[0]), 'python':pin(Path('/usr/bin/true').resolve()), 'service_config':pin(capture),
                    'supervisor':pin(Path(supervisor.__file__).resolve()), 'state_dir':str(root/'state'),
                    'heartbeat_seconds':10, 'max_retries':2, 'retry_backoff_seconds':1}))
                config_hash = supervisor.digest(config)
                supervisor.load(str(config), config_hash)
                pipeline = tool_dir / 'unified_cpu_pipeline_v1.py'
                pipeline.write_bytes(pipeline.read_bytes() + b'\n# tamper\n')
                with self.assertRaisesRegex(ValueError, 'capture closure changed'):
                    supervisor.load(str(config), config_hash)
            finally:
                supervisor.HERE, supervisor.REGISTRY = old_here, old_registry


if __name__ == '__main__':
    unittest.main()
