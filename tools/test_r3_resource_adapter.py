#!/usr/bin/env python3
import importlib.util
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("r3_resource_adapter", Path(__file__).with_name("r3_resource_adapter.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class AdapterTests(unittest.TestCase):
    def test_legacy_reclaim_requires_bound_terminal_and_unchanged_owner(self):
        marker = self.root / 'DONE'; marker.write_text('rc=0 utc=fixture\n')
        entry = json.loads(self.alloc.read_text())['allocation'][0]
        a = self.args(chip=2, container='legacy', container_id='cid', marker=str(marker),
                      marker_sha256=m.sha_bytes(marker.read_bytes()),
                      entry_sha256=m.sha_bytes(json.dumps(entry, sort_keys=True).encode()))
        d = {'Id':'cid','Config':{'Cmd':[str(self.root)]},
             'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci2'}]},
             'State':{'Status':'exited','ExitCode':0}}
        with mock.patch.object(m, 'docker_inspect', return_value=d), mock.patch.object(m, 'live_chip_conflict', return_value=False):
            a.entry_sha256='wrong'
            with self.assertRaises(RuntimeError): m.reclaim_legacy(a)
            self.assertFalse(Path(a.proof).exists())
            a.entry_sha256=m.sha_bytes(json.dumps(entry,sort_keys=True).encode())
            d['Config']['Cmd']=[]
            with self.assertRaises(RuntimeError): m.reclaim_legacy(a)
            d['Config']['Cmd']=[str(self.root)]
            m.reclaim_legacy(a)
        after=json.loads(self.alloc.read_text())
        self.assertEqual(after['allocation'],[])
        self.assertEqual([x['chip'] for x in after['free']],[1,2,4])
        self.assertFalse(json.loads(Path(a.proof).read_text())['scientific_acceptance'])

    def test_release_refuses_changed_container_before_ledger_mutation(self):
        claim=self.root/'claim.json';claim.write_text(json.dumps({'schema':'r3-resource-claim-v1','run':'r3_runs/test','chip':1}))
        args=self.args(container='run',container_id='expected-id',claim=str(claim))
        actual={'Id':'other-id','State':{'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False}}
        before=self.alloc.read_bytes()
        with mock.patch.object(m,'docker_inspect',return_value=actual),mock.patch.object(m,'live_chip_conflict',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'container generation differs'):m.release(args)
        self.assertEqual(self.alloc.read_bytes(),before);self.assertFalse(Path(args.proof).exists())

    def test_docker_uncertainty_is_not_absence(self):
        for message in ('Error: No such object: c', 'error: no such object: c'):
            with mock.patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', message)):
                self.assertIsNone(m.docker_inspect('c'))
        with mock.patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'Cannot connect to Docker daemon')):
            with self.assertRaises(RuntimeError):
                m.docker_inspect('c')

    def test_inventory_disappearance_blocks_release(self):
        with mock.patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'container-id', '')):
            with mock.patch.object(m, 'docker_inspect', return_value=None):
                with self.assertRaises(RuntimeError):
                    m.live_chip_conflict(1, 'ours')

    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name); self.alloc = self.root / "CHIP-ALLOCATION.json"
        self.alloc.write_text(json.dumps({"allocation": [{"chip": 2, "run": "other"}], "free": [{"chip": 1}, {"chip": 4}]}) + "\n")

    def args(self, **kw):
        d = dict(alloc=str(self.alloc), run="r3_runs/test", chip=1, owner="test", purpose="test", proof=str(self.root / "proof.json"))
        d.update(kw); return type("Args", (), d)()

    def test_claim_uses_explicit_free_and_records_before_after(self):
        self.assertIsNone(m.claim(self.args()))
        d = json.loads(self.alloc.read_text())
        self.assertEqual([x["chip"] for x in d["free"]], [4]); self.assertEqual([x["chip"] for x in d["allocation"]], [1, 2])
        p = json.loads((self.root / "proof.json").read_text())
        self.assertEqual(p["schema"], "r3-resource-claim-v1"); self.assertEqual(p["allocation_before"]["free"], [{"chip": 1}, {"chip": 4}])

    def test_claim_refuses_chip_not_in_free_without_mutation(self):
        before = self.alloc.read_bytes()
        with self.assertRaises(RuntimeError): m.claim(self.args(chip=2))
        self.assertEqual(self.alloc.read_bytes(), before)

    def test_claim_and_release_refuse_symlinked_allocation_path(self):
        alias = self.root / "allocation-alias.json"
        alias.symlink_to(self.alloc)
        with self.assertRaises(RuntimeError): m.claim(self.args(alloc=str(alias)))
        with self.assertRaises(RuntimeError): m.release(self.args(alloc=str(alias), container="ctr",
                                                                  claim=str(self.root / "missing-claim.json"),
                                                                  proof=str(self.root / "release.json")))

    def test_claim_recovers_after_allocation_replace_before_proof(self):
        before_raw = self.alloc.read_bytes(); before = json.loads(before_raw)
        now = m.utc(); entry = {"chip": 1, "owner": "test", "run": "r3_runs/test",
                                "purpose": "test", "claimed_utc": now,
                                "release_when": "retained container exited and guarded release proof written"}
        after = dict(before); after["free"] = [e for e in before["free"] if e["chip"] != 1]
        after["allocation"] = sorted(before["allocation"] + [entry], key=lambda e: e["chip"])
        after["updated_utc"], after["updated_by"] = now, "r3_resource_adapter claim"
        proof = self.root / "proof.json"
        intent = proof.with_suffix(proof.suffix + ".intent")
        m.write_atomic(intent, {"schema": "r3-resource-claim-intent-v1", "run": "r3_runs/test", "chip": 1,
                                 "allocation_before_sha256": m.sha_bytes(before_raw), "allocation_before": before,
                                 "allocation_after": after, "entry": entry, "proof": str(proof.resolve())})
        m.write_atomic(self.alloc, after)
        m.claim(self.args())
        recovered = json.loads(proof.read_text())
        self.assertEqual(recovered["schema"], "r3-resource-claim-v1")
        self.assertFalse(intent.exists())

    def test_release_requires_exited_retained_container_and_preserves_other_owner(self):
        m.claim(self.args())
        claim = self.root / "proof.json"; release = self.root / "release.json"
        d = {"Id": "cid", "Name": "/ctr", "HostConfig": {"AutoRemove": False, "Devices": [{"PathOnHost": "/dev/davinci1"}]}, "State": {"Status": "exited", "ExitCode": 0, "StartedAt": "s", "FinishedAt": "f"}}
        fake = type("P", (), {"returncode": 0, "stdout": ""})()
        with mock.patch.object(m, "docker_inspect", side_effect=[d, None]), mock.patch.object(m.subprocess, "run", return_value=fake):
            self.assertIsNone(m.release(self.args(container="ctr", claim=str(claim), proof=str(release))))
        now = json.loads(self.alloc.read_text())
        self.assertEqual([x["chip"] for x in now["free"]], [1, 4]); self.assertEqual([x["chip"] for x in now["allocation"]], [2])
        self.assertFalse(json.loads(release.read_text())["scientific_acceptance"])

    def test_release_refuses_running_container(self):
        m.claim(self.args())
        d = {"Id": "cid", "HostConfig": {"AutoRemove": False}, "State": {"Status": "running"}}
        with mock.patch.object(m, "docker_inspect", return_value=d), self.assertRaises(RuntimeError):
            m.release(self.args(container="ctr", claim=str(self.root / "proof.json"), proof=str(self.root / "release.json")))

    def test_bound_release_recovers_each_write_boundary_and_rejects_wrong_generation(self):
        for crash_after_ledger in (False, True):
            with self.subTest(crash_after_ledger=crash_after_ledger), tempfile.TemporaryDirectory() as tmp:
                alloc=Path(tmp)/'allocation.json'
                alloc.write_text(json.dumps({'allocation':[], 'free':[{'chip':1}]}))
                claim=Path(tmp)/'claim.json';proof=Path(tmp)/'release.json'
                m.claim(self.args(alloc=str(alloc),proof=str(claim)))
                a=self.args(alloc=str(alloc),container='ctr',container_id='cid',claim=str(claim),proof=str(proof))
                actual={'Id':'cid','HostConfig':{'AutoRemove':False},'State':{'Status':'exited','ExitCode':0}}
                write=m.write_atomic
                def interrupted(path,doc):
                    if Path(path)==(proof if crash_after_ledger else alloc):
                        raise OSError('simulated crash')
                    return write(path,doc)
                with mock.patch.object(m,'docker_inspect',return_value=actual), mock.patch.object(m,'live_chip_conflict',return_value=False):
                    with mock.patch.object(m,'write_atomic',side_effect=interrupted):
                        with self.assertRaisesRegex(OSError,'simulated crash'):m.release(a)
                    intent=proof.with_suffix('.json.intent'); saved=intent.read_bytes()
                    forged=json.loads(saved);forged['container_id']='wrong';intent.write_text(json.dumps(forged))
                    ledger=alloc.read_bytes()
                    with self.assertRaisesRegex(RuntimeError,'intent container generation'):m.release(a)
                    self.assertEqual(alloc.read_bytes(),ledger);self.assertFalse(proof.exists())
                    intent.write_bytes(saved);m.release(a)
                    self.assertEqual(json.loads(proof.read_text())['container_id'],'cid')
                    self.assertEqual(json.loads(alloc.read_text())['allocation'],[])
                    self.assertFalse(intent.exists())
                    m.release(a)  # idempotent proof recovery
                    forged=json.loads(proof.read_text());forged['container_id']='wrong';proof.write_text(json.dumps(forged))
                    ledger=alloc.read_bytes()
                    with self.assertRaisesRegex(RuntimeError,'proof container generation'):m.release(a)
                    self.assertEqual(alloc.read_bytes(),ledger)

if __name__ == "__main__": unittest.main()
