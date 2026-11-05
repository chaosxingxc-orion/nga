"""Isolated fixed-path CPU bridge test; never mounts or writes host stage paths."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def namespace():
    # The private mount namespace gives the subprocess its own empty /model,
    # /data and /run. Host directories used for Python and source are read-only
    # in practice: all fixture writes go to the temporary chroot.
    root = Path(sys.argv[-1])
    subprocess.run(['mount', '--make-rprivate', '/'], check=True)
    for name in ('usr', 'lib', 'lib64', 'bin', 'etc', 'home', 'dev', 'proc', 'sys'):
        src = Path('/') / name
        if src.is_symlink():
            (root / name).symlink_to(os.readlink(src))
        elif src.exists():
            (root / name).mkdir()
            subprocess.run(['mount', '--rbind', str(src), str(root / name)], check=True)
    for name in ('model', 'data', 'run/nga/output', 'run/nga/export', 'run/nga/score', 'tmp'):
        (root / name).mkdir(parents=True, exist_ok=True)
    os.chroot(root)
    os.chdir(str(HERE))
    os.execv(sys.executable, [sys.executable, '-B', '-P', str(Path(__file__).resolve()), '--inside'])


def inside():
    sys.path.insert(0, str(HERE))
    import test_panel_bridge as bridge
    from test_panel_bridge import A, FrozenModel, Tokenizer, put

    case = bridge.Bridge('test_three_type_parity_and_completed_reuse')
    temporary_directory = tempfile.TemporaryDirectory
    with mock.patch.object(bridge.tempfile, 'TemporaryDirectory',
                           side_effect=lambda: temporary_directory(dir='/data')):
        case.setUp()
    try:
        model = Path('/model/Qwen__Qwen3.5-0.8B-Base')
        shutil.copytree(case.modelroot / model.name, model)
        case.cfg['model']['path'] = str(model)
        case.out = Path('/run/nga/output/result')
        case.cfg['output'] = str(case.out)
        put(case.cfgpath, case.cfg)
        original_load = A.load

        def loader(path, name):
            module = original_load(path, name)
            if name == 'nga_native_inference':
                module.load_tokenizer = lambda config: Tokenizer()
                module.load_model = lambda config: FrozenModel(case.vectors)
            return module

        # Admission checks the real MODEL_ROOTS. An equally valid inventory
        # under an unregistered parent must fail before creating output.
        rejected = Path('/data') / model.name
        shutil.copytree(model, rejected)
        bad = dict(case.cfg, model=dict(case.cfg['model'], path=str(rejected)), output='/run/nga/output/rejected')
        with mock.patch.object(A, 'load', side_effect=loader):
            with case.assertRaisesRegex(ValueError, 'unregistered model mirror'):
                case.invoke(bad, case.root / 'bad.json')
            case.assertFalse(Path(bad['output']).exists())
            case.invoke(case.cfg, case.cfgpath)
            subprocess.run(['mount', '--bind', str(case.out), str(case.out)], check=True)
            subprocess.run(['mount', '-o', 'remount,bind,ro', str(case.out)], check=True)
            export = dict(schema='nga-unified-config-v1', adapter='native-panel-export-v2', runtime='cpu',
                          source=str(case.out), owner_sha256=bridge.sha(case.out / 'OWNER.json'),
                          source_config=str(case.cfgpath), source_config_sha256=bridge.sha(case.cfgpath),
                          panel_manifest=str(case.mp), panel_manifest_sha256=bridge.sha(case.mp),
                          output='/run/nga/export/result')
            case.invoke(export, case.root / 'export-config.json')
            subprocess.run(['mount', '--bind', export['output'], export['output']], check=True)
            subprocess.run(['mount', '-o', 'remount,bind,ro', export['output']], check=True)
            actual = case.score(Path('/run/nga/export/result/manifest.json'), Path('/run/nga/score/result'))
            baseline = case.score(case.baseline(), case.root / 'baseline-score')
            case.assertEqual(actual, baseline)
            case.assertEqual((Path('/run/nga/score/result/summary.json')).read_bytes(),
                             (case.root / 'baseline-score/summary.json').read_bytes())
        print('fixed stage path bridge and model admission passed')
    finally:
        case.tearDown()


class StagePaths(unittest.TestCase):
    def test_private_namespace_bridge(self):
        with tempfile.TemporaryDirectory(prefix='nga-stage-chroot-') as tmp:
            result = subprocess.run(['unshare', '--user', '--map-root-user', '--mount', sys.executable,
                                     '-B', '-P', str(Path(__file__).resolve()), '--namespace', tmp],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('fixed stage path bridge and model admission passed', result.stdout)


if __name__ == '__main__':
    if '--namespace' in sys.argv:
        namespace()
    elif '--inside' in sys.argv:
        inside()
    else:
        unittest.main(verbosity=2)
