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

if __name__ == "__main__": unittest.main()
