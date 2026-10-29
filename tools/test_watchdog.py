"""Tests for tools/watchdog.py. Standard library only. Run: python3 -P tools/test_watchdog.py"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -P removes the script dir from sys.path
import watchdog as wd  # noqa: E402

warnings.simplefilter("ignore", ResourceWarning)
NOW = 1_800_000_000.0
PFLAG = ["-P"] if sys.version_info >= (3, 11) else []
HERE = os.path.dirname(os.path.abspath(__file__))


def hb_line(offset_s, body):
    return "%s %s\n" % (wd.iso(NOW + offset_s), body)


class Tree:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def run(self, name, heartbeat=None, marker=None, log=None, report=None, marker_name=None):
        d = os.path.join(self.root, name)
        os.makedirs(d)
        if heartbeat is not None:
            with open(os.path.join(d, "heartbeat.log"), "w") as f:
                f.write(heartbeat)
        if log is not None:
            with open(os.path.join(d, "run.log"), "w") as f:
                f.write(log)
        if marker is not None:
            with open(os.path.join(d, marker_name or ("DONE" if marker.startswith("rc=0") else "FAILED")), "w") as f:
                f.write(marker)
        if report is not None:
            with open(os.path.join(d, "report.json"), "w") as f:
                json.dump(report, f)
        return d

    def cfg(self, **kw):
        kw.setdefault("root", [self.root])
        kw.setdefault("out_dir", os.path.join(self.tmp.name, "_out"))
        return wd.make_cfg(**kw)

    def digest(self, now=NOW, **kw):
        return wd.build_digest(self.cfg(**kw), {}, now)

    def states(self, **kw):
        return {r["id"]: r["state"] for r in self.digest(**kw)["runs"]}


class Classification(unittest.TestCase):
    def test_all_states(self):
        t = Tree()
        t.run("a_done", heartbeat=hb_line(-50, "alive rows: x=5"), marker="rc=0 utc=2027-01-15T08:00:00Z")
        t.run("b_failed", heartbeat=hb_line(-50, "alive"), marker="rc=3 utc=x")
        t.run("c_running", heartbeat=hb_line(-100, "alive rows: x=5"))
        t.run("d_stalled", heartbeat=hb_line(-4000, "alive"), log="x\n")
        t.run("e_unknown", report={"a": 1})
        st = t.states(stall_seconds=300)
        self.assertEqual(st, {"a_done": "done", "b_failed": "failed", "c_running": "running",
                              "d_stalled": "stalled", "e_unknown": "unknown"})

    def test_stall_threshold_is_a_parameter(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-1000, "alive"))
        self.assertEqual(t.states(stall_seconds=300)["r"], "stalled")
        self.assertEqual(t.states(stall_seconds=2000)["r"], "running")

    def test_marker_beats_a_fresh_heartbeat(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-1, "alive"), marker="rc=1")
        self.assertEqual(t.states()["r"], "failed")

    def test_marker_problems_are_unknown_with_a_reason(self):
        t = Tree()
        t.run("noexit", heartbeat=hb_line(-1, "x"), marker="finished", marker_name="DONE")
        t.run("conflict", heartbeat=hb_line(-1, "x"), marker="rc=1", marker_name="DONE")
        t.run("failed0", heartbeat=hb_line(-1, "x"), marker="rc=0", marker_name="FAILED")
        dg = t.digest()
        for r in dg["runs"]:
            self.assertEqual(r["state"], "unknown", r["id"])
            self.assertTrue(r["state_reason"])

    def test_mtime_fallback_without_heartbeat_file(self):
        t = Tree()
        d = t.run("r", log="hello\n")
        os.utime(os.path.join(d, "run.log"), (NOW - 10, NOW - 10))
        r = t.digest()["runs"][0]
        self.assertEqual(r["state"], "running")
        self.assertIn("mtime", r["heartbeat_source"])
        os.utime(os.path.join(d, "run.log"), (NOW - 9999, NOW - 9999))
        self.assertEqual(t.digest()["runs"][0]["state"], "stalled")

    def test_future_heartbeat_is_unknown(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(+5000, "x"))
        self.assertEqual(t.states()["r"], "unknown")

    def test_escalation_rule(self):
        t = Tree()
        t.run("failed", heartbeat=hb_line(-1, "x"), marker="rc=1")
        t.run("stalled", heartbeat=hb_line(-9999, "x"))
        t.run("clean", heartbeat=hb_line(-1, "x"), marker="rc=0")
        t.run("doneflag", heartbeat=hb_line(-1, "x"), marker="rc=0", report={"cell": {"rate": 1.0, "n": 500}})
        t.run("runerr", heartbeat=hb_line(-1, "x"), log="RuntimeError: boom\n")
        e = {r["id"]: r["escalation"] for r in t.digest()["runs"]}
        self.assertEqual(e, {"failed": "decide", "stalled": "decide", "clean": "none", "doneflag": "decide", "runerr": "read"})

    def test_discovery_does_not_descend_into_runs_or_skipped_dirs(self):
        t = Tree()
        d = t.run("run1", heartbeat=hb_line(-1, "x"))
        os.makedirs(os.path.join(d, "sub"))
        open(os.path.join(d, "sub", "x.log"), "w").write("e\n")
        os.makedirs(os.path.join(t.root, "data"))
        open(os.path.join(t.root, "data", "big.jsonl"), "w").write("{}\n")
        os.makedirs(os.path.join(t.root, "_out"))
        self.assertEqual(list(t.states()), ["run1"])


class Progress(unittest.TestCase):
    def test_rate_eta_and_percent(self):
        t = Tree()
        hb = "".join(hb_line(-600 + 60 * i, "progress %d/200" % (i * 10)) for i in range(11))
        t.run("r", heartbeat=hb)
        p = t.digest(window_seconds=900)["runs"][0]["progress"]
        self.assertEqual((p["done"], p["total"], p["percent"]), (100, 200, 50.0))
        self.assertAlmostEqual(p["rate_per_min"], 10.0)
        self.assertEqual(p["eta_utc"], wd.iso(NOW + 600))

    def test_total_unknown_is_stated_not_guessed(self):
        t = Tree()
        hb = "".join(hb_line(-300 + 60 * i, "alive_shards=8 rows: a=%d b=%d" % (i, i)) for i in range(6))
        t.run("r", heartbeat=hb)
        p = t.digest()["runs"][0]["progress"]
        self.assertEqual(p["done"], 10)
        self.assertIsNone(p["total"])
        self.assertIsNone(p["eta_utc"])
        self.assertIn("total unknown", p["note"])

    def test_counter_reset_uses_only_the_new_segment(self):
        t = Tree()
        hb = hb_line(-300, "done=900 total=1000") + hb_line(-240, "done=10 total=1000") + hb_line(-180, "done=40 total=1000")
        t.run("r", heartbeat=hb)
        p = t.digest()["runs"][0]["progress"]
        self.assertAlmostEqual(p["rate_per_min"], 30.0)


class Signatures(unittest.TestCase):
    def test_similar_lines_group(self):
        n = wd.normalize
        a = n("2026-10-29 07:28:21,653 ERROR [pid 3961] failed to open /mnt/x/run7/shard3.log at line 120 addr 0x7f3a2c001000")
        b = n("2026-10-29 09:00:00,111 ERROR [pid 77] failed to open /home/u/other/shard9.log at line 5 addr 0xdeadbeef")
        self.assertEqual(a, b)
        self.assertEqual(n("shard3 exited rc=1 after 12.5s"), n("shard4 exited rc=137 after 400s"))
        self.assertEqual(n("File \"/a/b/c.py\", line 42, in f"), n("File \"/x/y.py\", line 7, in f"))

    def test_different_lines_stay_apart(self):
        n = wd.normalize
        self.assertNotEqual(n("RuntimeError: out of memory"), n("RuntimeError: device lost"))
        self.assertNotEqual(n("EZ9999: Inner Error!"), n("EZ1001: Inner Error!"))
        self.assertNotEqual(n("failed to open file"), n("failed to close file"))

    def test_clustering_counts_pointers_and_cap(self):
        t = Tree()
        lines = ["%s step %d ok\n" % (wd.iso(NOW - 1000 + i), i) for i in range(5)]
        lines.append("2027-01-15T08:00:01Z ERROR shard3 failed at /a/b.py:10 (pid 99)\n")
        lines.append("progress\n")
        lines.append("2027-01-15T08:05:00Z ERROR shard4 failed at /c/d.py:20 (pid 100)\n")
        for i in range(6):
            lines.append("2027-01-15T08:06:00Z WARNING distinct%s thing happened\n" % ("xyzuvw"[i] * 3))
        lines.append("Traceback (most recent call last):\n" + '  File "/a.py", line 3, in f\n' * 30 + "ValueError: bad value 12\n")
        t.run("r", heartbeat=hb_line(-1, "x"), log="".join(lines))
        r = t.digest(max_signatures=3, exemplar_width=40)["runs"][0]
        e = r["errors"]
        self.assertEqual(len(e["signatures"]), 3)
        self.assertGreater(e["omitted_signatures"], 0)
        top = e["signatures"][0]
        self.assertEqual(top["count"], 2)
        self.assertEqual(top["severity"], "error")
        self.assertEqual(top["first_utc"], "2027-01-15T08:00:01Z")
        self.assertEqual(top["last_utc"], "2027-01-15T08:05:00Z")
        ex = top["exemplar"]
        self.assertEqual(ex["line"], 6)
        self.assertLessEqual(ex["line_start"], 6)
        self.assertGreaterEqual(ex["line_end"], 6)
        self.assertTrue(ex["log"].endswith("run.log"))
        self.assertLessEqual(len(ex["text"]), 40)
        blob = json.dumps(r["errors"])
        self.assertLess(blob.count("File "), 2)   # no traceback frames

    def test_ansi_and_progress_bars(self):
        t = Tree()
        log = "\x1b[36m(W pid=5)\x1b[0m ERROR boom 1\n\x1b[36m(W pid=9)\x1b[0m ERROR boom 2\nLoading 10%\rLoading 90%\rdone\n"
        t.run("r", heartbeat=hb_line(-1, "x"), log=log)
        e = t.digest()["runs"][0]["errors"]
        self.assertEqual(len(e["signatures"]), 1)
        self.assertEqual(e["signatures"][0]["count"], 2)

    def test_credentials_are_redacted_in_exemplars(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-1, "x"), log="ERROR connect via https://user:hunter2@proxy:80/ token=abc123 failed\n")
        blob = json.dumps(t.digest()["runs"][0]["errors"])
        self.assertNotIn("hunter2", blob)
        self.assertNotIn("abc123", blob)

    def test_warning_vs_error_and_ignore(self):
        t = Tree()
        log = ("UserWarning: Failed to create processor\nRuntimeError: x\n0 errors found\nall good, errors=0\n")
        t.run("r", heartbeat=hb_line(-1, "x"), log=log)
        e = t.digest()["runs"][0]["errors"]
        self.assertEqual((e["error_lines"], e["warning_lines"]), (1, 1))

    def test_secrets_are_not_a_concern_of_signatures_but_incremental_scan_is_stable(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-1, "x"), log="ERROR a\n")
        cfg, states = t.cfg(), {}
        wd.build_digest(cfg, states, NOW)
        with open(os.path.join(d, "run.log"), "a") as f:
            f.write("ERROR a\nERROR b\n")
        r = wd.build_digest(cfg, states, NOW)["runs"][0]
        self.assertEqual(r["errors"]["error_lines"], 3)


class Suspicious(unittest.TestCase):
    def kinds(self, obj, **kw):
        cfg = wd.make_cfg(**kw)
        return {(i["kind"], i["path"]) for i in wd.check_report(obj, cfg)}

    def test_exact_zero_and_one(self):
        k = self.kinds({"T1": {"n": 500, "rate": 0.0}, "T2": {"n": 500, "acc": 1.0}, "T3": {"n": 500, "rate": 0.4}})
        self.assertIn(("exact_zero", "$.T1.rate"), k)
        self.assertIn(("exact_one", "$.T2.acc"), k)
        self.assertNotIn(("exact_zero", "$.T3.rate"), k)
        self.assertFalse([x for x in k if x[1] == "$.T3.rate"])

    def test_integer_one_under_a_rate_key_counts_but_counts_do_not(self):
        k = self.kinds({"cell": {"n": 1, "rate": 1}, "other": {"n": 0, "failures": 1}})
        self.assertIn(("exact_one", "$.cell.rate"), k)
        self.assertFalse([x for x in k if x[0] in ("exact_one", "exact_zero") and "n" == x[1].split(".")[-1]])

    def test_identical_metric_across_every_cell(self):
        table = {"A": {"n": 100, "acc": 0.73}, "B": {"n": 90, "acc": 0.73}, "C": {"n": 80, "acc": 0.73}}
        k = self.kinds(table)
        self.assertIn(("identical_across_cells", "$[*].acc"), k)
        varied = {"A": {"n": 100, "acc": 0.73}, "B": {"n": 90, "acc": 0.71}, "C": {"n": 80, "acc": 0.73}}
        self.assertFalse([x for x in self.kinds(varied) if x[0] == "identical_across_cells"])

    def test_identical_in_list_of_rows_and_flat_dict(self):
        k = self.kinds({"rows": [{"id": i, "followed_rate": 0.5, "n": 100} for i in range(4)]})
        self.assertTrue([x for x in k if x[0] == "identical_across_cells" and x[1].startswith("$.rows[*]")])
        k2 = self.kinds({"flip": {"a|b": 0.2, "a|c": 0.2, "b|c": 0.2}})
        self.assertIn(("identical_across_cells", "$.flip"), k2)

    def test_two_cells_are_not_a_table(self):
        self.assertFalse([x for x in self.kinds({"A": {"acc": 0.7}, "B": {"acc": 0.7}}) if x[0] == "identical_across_cells"])

    def test_tiny_sample(self):
        k = self.kinds({"T1": {"n": 4, "rate": 0.5}, "T2": {"n": 400, "rate": 0.5}}, min_n=30)
        self.assertIn(("low_sample_count", "$.T1.n"), k)
        self.assertNotIn(("low_sample_count", "$.T2.n"), k)
        k = self.kinds({"T1": {"n": 4, "rate": 0.5}}, min_n=3)
        self.assertFalse([x for x in k if x[0] == "low_sample_count"])

    def test_nan_and_clean_report(self):
        self.assertTrue([x for x in self.kinds({"a": {"rate": float("nan")}}) if x[0] == "non_finite"])
        clean = {"A": {"n": 200, "acc": 0.61}, "B": {"n": 300, "acc": 0.72}, "C": {"n": 250, "acc": 0.55}}
        self.assertEqual(self.kinds(clean), set())

    def test_end_to_end_flag_in_digest_and_markdown(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-1, "x"), marker="rc=0", report={"T1": {"n": 500, "rate": 1.0}})
        dg = t.digest()
        sm = dg["runs"][0]["suspicious_metrics"]
        self.assertEqual(sm["by_kind"], {"exact_one": 1})
        self.assertEqual(sm["items"][0]["path"], "$.T1.rate")
        md = wd.render_md(dg, t.cfg())
        self.assertIn("suspicious_metrics", md)
        self.assertIn("$.T1.rate", md)

    def test_unreadable_report_is_noted(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-1, "x"))
        open(os.path.join(d, "report.json"), "w").write("{not json")
        self.assertTrue(t.digest()["runs"][0]["notes"])


class DigestOutput(unittest.TestCase):
    def test_size_cap_is_hard_and_explicit(self):
        t = Tree()
        for i in range(60):
            t.run("run%02d" % i, heartbeat=hb_line(-9999, "x"), log="ERROR something %d went wrong\n" % i)
        cfg = t.cfg(max_md_bytes=2500)
        md = wd.render_md(wd.build_digest(cfg, {}, NOW), cfg)
        self.assertLessEqual(len(md.encode()), 2500)
        self.assertIn("TRUNCATED", md)
        cfg2 = t.cfg(max_md_bytes=10 ** 6)
        md2 = wd.render_md(wd.build_digest(cfg2, {}, NOW), cfg2)
        self.assertNotIn("TRUNCATED", md2)

    def test_tiny_cap_still_holds(self):
        self.assertLessEqual(len(wd.enforce_cap("x\n" * 1000, 150).encode()), 150)

    def test_atomic_write_under_concurrent_reader(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "digest.json")
            wd.atomic_write(p, json.dumps({"v": 0, "pad": ""}))
            stop, bad, reads = threading.Event(), [], [0]

            def reader():
                while not stop.is_set():
                    try:
                        with open(p) as f:
                            obj = json.loads(f.read())
                        assert obj["pad"] == "x" * obj["v"] * 1000
                        reads[0] += 1
                    except Exception as e:  # noqa: BLE001
                        bad.append(repr(e))

            th = [threading.Thread(target=reader) for _ in range(3)]
            for x in th:
                x.start()
            for i in range(1, 150):
                wd.atomic_write(p, json.dumps({"v": i, "pad": "x" * i * 1000}))
            stop.set()
            for x in th:
                x.join()
            self.assertEqual(bad, [])
            self.assertGreater(reads[0], 10)
            self.assertEqual([f for f in os.listdir(d) if f.endswith(".tmp")], [])

    def test_concurrent_invocations_leave_consistent_output(self):
        t = Tree()
        t.run("r", heartbeat="%s x\n" % wd.iso(time.time() - 9999), log="ERROR x\n")
        out = os.path.join(t.tmp.name, "_out")
        cmd = [sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out]
        procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE) for _ in range(6)]
        codes = [p.wait() for p in procs]
        self.assertEqual(set(codes), {30})
        dg = json.load(open(os.path.join(out, "digest.json")))
        md = open(os.path.join(out, "digest.md")).read()
        self.assertIn(dg["generated_utc"], md.splitlines()[0])
        self.assertEqual([f for f in os.listdir(out) if f.endswith(".tmp")], [])

    def test_second_watcher_refuses(self):
        t = Tree()
        t.run("r", heartbeat="%s x\n" % wd.iso(time.time()))
        out = os.path.join(t.tmp.name, "_out")
        cmd = [sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out,
               "--watch", "--interval", "1"]
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.time() + 10
            while time.time() < deadline and not os.path.exists(os.path.join(out, "digest.json")):
                time.sleep(0.1)
            p2 = subprocess.run(cmd, capture_output=True, timeout=20)
            self.assertEqual(p2.returncode, 3)
        finally:
            p1.terminate()
            p1.wait(10)

    def test_watch_rewrites_in_place(self):
        t = Tree()
        d = t.run("r", heartbeat="%s x\n" % wd.iso(time.time()))
        out = os.path.join(t.tmp.name, "_out")
        p = subprocess.Popen([sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out,
                              "--watch", "--interval", "1"], stdout=subprocess.DEVNULL)
        try:
            deadline = time.time() + 10
            while time.time() < deadline and not os.path.exists(os.path.join(out, "digest.json")):
                time.sleep(0.1)
            first = json.load(open(os.path.join(out, "digest.json")))["runs"][0]["state"]
            open(os.path.join(d, "DONE"), "w").write("rc=0\n")
            deadline = time.time() + 15
            second = first
            while time.time() < deadline and second == first:
                time.sleep(0.3)
                second = json.load(open(os.path.join(out, "digest.json")))["runs"][0]["state"]
            self.assertEqual((first, second), ("running", "done"))
        finally:
            p.terminate()
            p.wait(10)


class ExitCode(unittest.TestCase):
    def code(self, setup):
        t = Tree()
        setup(t)
        return t.digest()["exit_code"]

    def test_worst_state_wins(self):
        def done(t):
            t.run("a", heartbeat=hb_line(-1, "x"), marker="rc=0")

        def run(t):
            done(t)
            t.run("b", heartbeat=hb_line(-1, "x"))

        def unk(t):
            run(t)
            t.run("c", report={"x": {"n": 100, "rate": 0.5}})

        def stalled(t):
            unk(t)
            t.run("d", heartbeat=hb_line(-9999, "x"))

        def failed(t):
            stalled(t)
            t.run("e", heartbeat=hb_line(-1, "x"), marker="rc=2")

        codes = [self.code(f) for f in (done, run, unk, stalled, failed)]
        self.assertEqual(codes, [0, 10, 20, 30, 40])
        self.assertEqual(sorted(codes), codes)

    def test_cli_exit_code_and_no_runs(self):
        t = Tree()
        t.run("a", heartbeat="%s x\n" % wd.iso(time.time()), marker="rc=7")
        out = os.path.join(t.tmp.name, "_o")
        r = subprocess.run([sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out],
                           capture_output=True)
        self.assertEqual(r.returncode, 40)
        t2 = Tree()
        r = subprocess.run([sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t2.root,
                            "--out-dir", os.path.join(t2.tmp.name, "_o")], capture_output=True)
        self.assertEqual(r.returncode, wd.EXIT_NO_RUNS)

    def test_clean_done_run_with_flag_is_not_exit_zero_silently(self):
        t = Tree()
        t.run("a", heartbeat=hb_line(-1, "x"), marker="rc=0", report={"T1": {"n": 500, "rate": 1.0}})
        dg = t.digest()
        self.assertEqual(dg["runs"][0]["escalation"], "decide")


if __name__ == "__main__":
    unittest.main(verbosity=1)
