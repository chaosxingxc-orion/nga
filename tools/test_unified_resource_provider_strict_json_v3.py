import json
import unittest
from unittest import mock

from tools import unified_resource_provider_v1 as P
from tools.test_unified_resource_provider_v1 import ProviderTests


def row(state):
    return {'Id': '1'*64, 'Name': '/fixture', 'State': state,
            'HostConfig': {'Devices': [], 'Privileged': False, 'DeviceCgroupRules': None, 'DeviceRequests': None}, 'Mounts': []}


def inspect(raw):
    with mock.patch.object(P, 'run', side_effect=['1'*64, raw]):
        return P.Inventory()


class StrictDocker(unittest.TestCase):
    def test_recursive_duplicate_inventory_and_image(self):
        raw = json.dumps([row({'Status': 'running', 'Running': True})])
        for before, after in [
            ('"Devices": []', '"Devices": [{"PathOnHost":"/dev/davinci0"}], "Devices": []'),
            ('"Running": true', '"Running": true, "Running": true'),
            ('"Mounts": []', '"Mounts": [{"x": {"a": 1, "a": 2}}]')]:
            with self.subTest(before=before), self.assertRaises(ValueError): inspect(raw.replace(before, after))
        image = '[{"Id":"sha256:' + 'a'*64 + '","RepoDigests":null,"Config":{"Env":[],"Env":[]}}]'
        with mock.patch.object(P, 'run', return_value=image), self.assertRaises(ValueError):
            P.DiagnosticFacade(None).image_id('sha256:'+'a'*64)
        with self.assertRaises(ValueError): P.strict_json('{"outer":[{"a":1,"a":2}]}')

    def test_docker_state_variants(self):
        # Actual inspect-shaped states include OOMKilled on stopped containers;
        # OOMKilled is an independent historical fact, not a status indicator.
        for status, running, paused, restarting, dead, oom in [
            ('created', False, False, False, False, False),
            ('exited', False, False, False, False, True),
            ('running', True, False, False, False, False),
            ('paused', True, True, False, False, False),
            ('restarting', True, False, True, False, True),
            ('dead', False, False, False, True, False)]:
            state = dict(Status=status, Running=running, Paused=paused, Restarting=restarting, Dead=dead, OOMKilled=oom)
            with self.subTest(status=status): inspect(json.dumps([row(state)]))
        for state in [dict(Status='removing', Running=False, RemovalInProgress=True),
                      dict(Status='removing', Running=True, Paused=True, RemovalInProgress=True)]:
            r=row(state); r['HostConfig']['Devices']=[{'PathOnHost':'/dev/davinci0','PathInContainer':'/dev/davinci0'}]
            self.assertTrue(inspect(json.dumps([r])).conflict(0))
        for status, flag in [('exited','Paused'),('exited','Restarting'),('created','Dead'),('running','Dead'),('exited','RemovalInProgress')]:
            state=dict(Status=status, Running=status=='running'); state[flag]=True
            with self.subTest(status=status,flag=flag), self.assertRaises(ValueError): inspect(json.dumps([row(state)]))
        for flag in ('Running','Paused','Restarting','Dead','OOMKilled','RemovalInProgress'):
            for value in (0, 1, None, 'false'):
                state=dict(Status='exited', Running=False); state[flag]=value
                with self.subTest(flag=flag,value=value), self.assertRaises(ValueError): inspect(json.dumps([row(state)]))

    def test_image_digest_collection_and_exact_membership(self):
        ident='sha256:'+'a'*64; ref='registry.example:5000/ns/image@sha256:'+'d'*64
        def query(digests, requested=ref):
            raw=json.dumps([{'Id':ident,'RepoDigests':digests,'Config':{'Env':[]}}])
            with mock.patch.object(P,'run',return_value=raw): return P.DiagnosticFacade(None).image_id(requested)
        self.assertEqual(query([ref]),ident)
        self.assertEqual(query(None,ident),ident)
        for bad in (ref, {}, [None], ['prefix'+ref], [ref+'0'], ['UPPER/image@sha256:'+'d'*64], ['repo@sha256:short'], [ref, 'bad']):
            with self.subTest(bad=bad), self.assertRaises(ValueError): query(bad)
        with self.assertRaises(ValueError): query(['other/image@sha256:'+'d'*64])
        with self.assertRaises(ValueError): query(None)


class StrictLedger(ProviderTests):
    def test_duplicate_ledger_is_error(self):
        self.setup_provider(1)
        from pathlib import Path
        p=Path(self.alloc); raw=p.read_text(); p.write_text(raw.replace('{', '{"allocation": [],', 1))
        with self.assertRaisesRegex(ValueError,'duplicate JSON member'): self.obs()


if __name__ == '__main__':
    import subprocess
    import sys
    def guard(event, args):
        if event in ('subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.exec','socket.connect','socket.connect_ex','socket.bind'):
            raise RuntimeError('ESCAPE_GUARD '+event)
    sys.addaudithook(guard)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(StrictDocker), StrictLedger('test_duplicate_ledger_is_error')])
    with mock.patch.object(subprocess,'run',side_effect=RuntimeError('unsimulated run')), mock.patch.object(subprocess,'Popen',side_effect=RuntimeError('unsimulated Popen')):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
