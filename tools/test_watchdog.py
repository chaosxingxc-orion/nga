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
os.environ["WATCHDOG_NO_NPU"] = "1"   # the CLI tests below must never ssh to a real host; the NPU tests pass their own probe
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


class Suppression(unittest.TestCase):
    REP = {"primary": "real-model", "splits": {"g": {"h": {"src": {
        "constant": {"flip": {"rate": 0.0, "n": 500}, "m": {"a": {"acc": 1.0, "n": 0}}},
        "uniform": {"flip": {"rate": 0.0, "n": 500}},
        "mock-x": {"flip": {"rate": 1.0, "n": 500}},
        "primary": {"flip": {"rate": 0.0, "n": 500}, "m": {"a": {"acc": 1.0, "n": 500}}},
        "empty_input": {"flip": {"rate": 0.0, "n": 500}},
        "question_only": {"flip": {"rate": 1.0, "n": 500}}}}}}}

    def items(self, rep=None, **kw):
        return wd.check_report(rep or self.REP, wd.make_cfg(**kw))

    def test_roles(self):
        its = self.items()
        flagged = {(i["kind"], i["path"].split(".")[5]) for i in its if not i["suppressed_by"] and i["kind"] != "low_sample_count"}
        self.assertEqual({r for _, r in flagged}, {"primary", "empty_input", "question_only"})
        supp = {i["suppressed_by"] for i in its if i["suppressed_by"]}
        self.assertEqual(supp, {"constant", "uniform", "mock-x"})

    def test_low_n_always_flagged_even_for_degenerate(self):
        its = [i for i in self.items() if i["kind"] == "low_sample_count"]
        self.assertEqual(len(its), 1)
        self.assertIsNone(its[0]["suppressed_by"])
        self.assertIn("constant", its[0]["path"])

    def test_no_suppress_shows_everything(self):
        self.assertFalse([i for i in self.items(no_suppress=True) if i["suppressed_by"]])

    def test_custom_roles(self):
        its = self.items(suppress_roles="empty_input", protect_roles="")
        self.assertEqual({i["suppressed_by"] for i in its if i["suppressed_by"]}, {"empty_input"})

    def test_mock_primary_is_suppressed_real_primary_is_not(self):
        rep = {"primary": "mock-name-driven", "decision_lines": {"B": [{"followed_rate": 0.0}]},
               "splits": {"primary": {"flip": {"rate": 0.0, "n": 99}}}}
        its = [i for i in self.items(rep) if i["kind"] == "exact_zero"]
        self.assertTrue(its and all(i["suppressed_by"] == "primary=mock-name-driven" for i in its))
        rep["primary"] = "qwen"
        self.assertFalse([i for i in self.items(rep) if i["suppressed_by"]])

    def test_summary_line_in_digest(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-1, "x"), marker="rc=0", report=self.REP)
        dg = t.digest()
        sm = dg["runs"][0]["suspicious_metrics"]
        self.assertEqual(set(sm["suppressed"]["by_role"]), {"constant", "mock-x", "uniform"})
        self.assertGreater(sm["suppressed"]["total"], 0)
        self.assertFalse([i for i in sm["items"] if i["kind"] != "low_sample_count" and "constant" in i["path"]])
        md = wd.render_md(dg, t.cfg())
        self.assertIn("suppressed", md)
        self.assertIn("constant x", md)


class Archived(unittest.TestCase):
    def test_old_log_only_run_is_archived_and_quiet(self):
        t = Tree()
        d = t.run("old", log="ERROR boom\n")
        os.utime(os.path.join(d, "run.log"), (NOW - 7 * 3600, NOW - 7 * 3600))
        d2 = t.run("recent", log="ERROR boom\n")
        os.utime(os.path.join(d2, "run.log"), (NOW - 5 * 3600, NOW - 5 * 3600))
        dg = t.digest(archive_seconds=6 * 3600)
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual((by["old"]["state"], by["old"]["escalation"]), ("archived", "none"))
        self.assertEqual((by["recent"]["state"], by["recent"]["escalation"]), ("stalled", "decide"))
        self.assertEqual(dg["exit_code"], 30)

    def test_heartbeat_file_or_marker_prevents_archiving(self):
        t = Tree()
        t.run("hb", heartbeat=hb_line(-100000, "x"))
        t.run("failed", log="x\n", marker="rc=1")
        d = t.run("oldfail", log="x\n", marker="rc=1")
        os.utime(os.path.join(d, "run.log"), (NOW - 100000, NOW - 100000))
        st = t.states()
        self.assertEqual((st["hb"], st["oldfail"]), ("stalled", "failed"))

    def test_only_archived_runs_exit_zero(self):
        t = Tree()
        d = t.run("old", log="x\n")
        os.utime(os.path.join(d, "run.log"), (NOW - 100000, NOW - 100000))
        self.assertEqual(t.digest()["exit_code"], 0)
        md = wd.render_md(t.digest(), t.cfg())
        self.assertIn("Archived", md)


class PriorityTruncation(unittest.TestCase):
    def tree(self):
        t = Tree()
        t.run("a_failed", heartbeat=hb_line(-1, "x"), marker="rc=9", log="ERROR the failure %s\n" % ("w" * 50))
        t.run("b_stalled", heartbeat=hb_line(-9999, "x"))
        rep = {"primary": "real", "splits": {"primary": {"flip": {"rate": 0.0, "n": 99}},
                                             "empty_input": {"flip": {"rate": 0.0, "n": 99}}}}
        t.run("c_donebad", heartbeat=hb_line(-1, "x"), marker="rc=0", report=rep)
        for i in range(12):
            t.run("d_run%02d" % i, heartbeat=hb_line(-1, "x"), log="ERROR distinct%s problem\n" % ("abcdefghijkl"[i] * 5))
        return t

    def test_tiny_cap_keeps_summary_and_failed_rows_drops_low_priority(self):
        t = self.tree()
        big = t.cfg(max_md_bytes=10 ** 6)
        dg = wd.build_digest(big, {}, NOW)
        md_full = wd.render_md(dg, big)
        self.assertIn("flags on", "flags on")
        self.assertIn("empty_input", md_full)
        cfg = t.cfg(max_md_bytes=1700)
        md = wd.render_md(dg, cfg)
        self.assertLessEqual(len(md.encode()), 1700)
        self.assertIn("# Watchdog digest", md)
        self.assertIn("worst=failed", md)
        self.assertIn("| a_failed | failed", md)
        self.assertIn("| b_stalled | stalled", md)
        self.assertIn("TRUNCATED", md)
        self.assertNotIn("empty_input", md)          # flags on other scorers dropped
        self.assertNotIn("distinctlllll", md)        # low-priority error signatures dropped
        note = [x for x in md.splitlines() if "TRUNCATED" in x][0]
        self.assertIn("flags on other scorers", note)
        self.assertRegex(note, r"dropped \d+ blocks, \d+ B")

    def test_order_primary_flags_outlive_other_flags_and_errors(self):
        t = self.tree()
        dg = wd.build_digest(t.cfg(max_md_bytes=10 ** 6), {}, NOW)
        sizes = []
        for cap in range(1200, 6000, 150):
            md = wd.render_md(dg, t.cfg(max_md_bytes=cap))
            self.assertLessEqual(len(md.encode()), cap)
            sizes.append(("(primary scorer)" in md, "(other scorer)" in md, "distinctaaaaa" in md))
        for hi, lo in ((0, 2), (0, 1)):   # whenever a lower tier survives, the primary-flag tier survived first
            self.assertFalse([s for s in sizes if s[lo] and not s[hi]])

    def test_default_cap_is_16000(self):
        self.assertEqual(wd.make_cfg().max_md_bytes, 16000)


class WhyNote(unittest.TestCase):
    def test_why_note_surfaces_for_failed_and_archived(self):
        t = Tree()
        d = t.run("f", heartbeat=hb_line(-1, "x"), marker="rc=1")
        json.dump({"note": "Stopped: scoring on slow fallback.", "other": 1}, open(os.path.join(d, "WHY_FAILED.json"), "w"))
        d2 = t.run("old", log="x\n")
        os.utime(os.path.join(d2, "run.log"), (NOW - 100000, NOW - 100000))
        json.dump({"reason": "ad hoc smoke, finished"}, open(os.path.join(d2, "WHY_STOPPED.json"), "w"))
        d3 = t.run("bad", heartbeat=hb_line(-1, "x"), marker="rc=1")
        open(os.path.join(d3, "WHY_FAILED.json"), "w").write("plain text, not json")
        dg = t.digest()
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual(by["f"]["why"]["note"], "Stopped: scoring on slow fallback.")
        self.assertEqual(by["bad"]["why"]["note"], "plain text, not json")
        md = wd.render_md(dg, t.cfg())
        self.assertIn("scoring on slow fallback", md)
        self.assertIn("ad hoc smoke, finished", md)
        long_note = "x" * 5000
        json.dump({"note": long_note}, open(os.path.join(d, "WHY_FAILED.json"), "w"))
        self.assertLessEqual(len(t.digest()["runs"][0]["why"]["note"]) + len(t.digest()["runs"][1]["why"]["note"]), 400)


class Expected(unittest.TestCase):
    def mk(self, t, name, expected, note=True, **kw):
        d = t.run(name, **kw)
        body = {"note": "explained"} if note else {}
        if expected is not None:
            body["expected"] = expected
        json.dump(body, open(os.path.join(d, "WHY_FAILED.json"), "w"))
        return d

    def test_expected_true_downgrades_failed_marker_and_stalled_but_not_running_or_unknown(self):
        t = Tree()
        self.mk(t, "failed", True, heartbeat=hb_line(-1, "x"), marker="rc=1")
        self.mk(t, "stalled", True, heartbeat=hb_line(-9999, "x"))
        self.mk(t, "unknown", True, report={"a": 1})
        self.mk(t, "running", True, heartbeat=hb_line(-1, "x"), log="RuntimeError: x\n")
        dg = t.digest()
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual((by["failed"]["state"], by["failed"]["escalation"]), ("failed", "none"))
        self.assertTrue(by["failed"]["expected_applied"])
        self.assertEqual((by["stalled"]["state"], by["stalled"]["escalation"]), ("stalled", "none"))   # a written disposition, state unchanged
        self.assertTrue(by["stalled"]["expected_applied"])
        self.assertEqual(by["unknown"]["escalation"], "read")
        self.assertEqual(by["running"]["escalation"], "read")
        self.assertFalse(by["unknown"]["expected_applied"] or by["running"]["expected_applied"])
        self.assertEqual(dg["expected_downgrades"], {"count": 2, "runs": ["failed", "stalled"]})
        self.assertEqual(dg["expected_by_state"], {"failed": 1, "stalled": 1})
        self.assertEqual(dg["counts"]["stalled"], 1)                      # still counted
        self.assertEqual(dg["exit_code"], 40)                             # exit codes follow state
        md = wd.render_md(dg, t.cfg())
        self.assertIn("none expected=yes", md)
        self.assertEqual(md.count("expected=yes"), 2 + md.count("was decide"))
        self.assertIn("stalled 1", md.split("Dispositioned", 1)[1].splitlines()[0])

    def test_stalled_without_the_file_or_with_a_non_true_value_keeps_shouting_and_the_summary_audits_the_rest(self):
        t = Tree()
        t.run("bare", heartbeat=hb_line(-9999, "x"))
        self.mk(t, "false", False, heartbeat=hb_line(-9999, "x"))
        self.mk(t, "note", None, heartbeat=hb_line(-9999, "x"))
        self.mk(t, "yes1", True, heartbeat=hb_line(-9999, "x"))
        self.mk(t, "yes2", True, heartbeat=hb_line(-9999, "x"))
        dg = t.digest()
        by = {r["id"]: r["escalation"] for r in dg["runs"]}
        self.assertEqual(by, {"bare": "decide", "false": "decide", "note": "decide", "yes1": "none", "yes2": "none"})
        md = wd.render_md(dg, t.cfg())
        self.assertIn("Dispositioned", md.splitlines()[2])                # in the summary block, not buried
        self.assertIn("stalled 2", md.splitlines()[2])
        self.assertIn("worst=stalled", md.splitlines()[1])
        self.assertIn("stalled 5", md.splitlines()[1])                    # all five are still counted as stalled

    def test_an_explained_stop_ranks_below_an_unexplained_one_when_space_is_short(self):
        t = Tree()
        for i in range(6):
            t.run("a_unexplained%d" % i, heartbeat=hb_line(-9999, "x"))
            self.mk(t, "b_explained%d" % i, True, heartbeat=hb_line(-9999, "x"))
        dg = t.digest(max_md_bytes=10 ** 6)
        for cap in range(1100, 4000, 100):
            cfg = t.cfg(max_md_bytes=cap)
            md = wd.render_md(dg, cfg)
            un, ex = md.count("| a_unexplained"), md.count("| b_explained")
            self.assertTrue(ex == 0 or un == 6, (cap, un, ex))

    def test_note_alone_or_non_boolean_changes_nothing(self):
        t = Tree()
        self.mk(t, "note_only", None, heartbeat=hb_line(-1, "x"), marker="rc=1")
        self.mk(t, "false", False, heartbeat=hb_line(-1, "x"), marker="rc=1")
        self.mk(t, "string", "true", heartbeat=hb_line(-1, "x"), marker="rc=1")
        self.mk(t, "int", 1, heartbeat=hb_line(-1, "x"), marker="rc=1")
        d = t.run("prose", heartbeat=hb_line(-1, "x"), marker="rc=1")
        json.dump({"note": "this failure is expected and harmless, expected: true"}, open(os.path.join(d, "WHY_FAILED.json"), "w"))
        dg = t.digest()
        self.assertTrue(all(r["escalation"] == "decide" for r in dg["runs"]))
        self.assertEqual(dg["expected_downgrades"]["count"], 0)

    def test_expected_on_done_run_with_flags_and_on_archived(self):
        t = Tree()
        self.mk(t, "doneflag", True, heartbeat=hb_line(-1, "x"), marker="rc=0", report={"T1": {"n": 500, "rate": 1.0}})
        d = self.mk(t, "old", True, log="x\n")
        os.utime(os.path.join(d, "run.log"), (NOW - 100000, NOW - 100000))
        dg = t.digest()
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual(by["doneflag"]["escalation"], "none")
        self.assertEqual(by["doneflag"]["suspicious_metrics"]["total"], 1)   # the flag itself is still reported
        self.assertTrue(by["old"]["expected_applied"])
        self.assertEqual(dg["expected_downgrades"]["runs"], ["doneflag"])

    def test_marker_problem_unknown_is_not_downgraded(self):
        t = Tree()
        self.mk(t, "badmarker", True, heartbeat=hb_line(-1, "x"), marker="finished", marker_name="DONE")
        r = t.digest()["runs"][0]
        self.assertEqual((r["state"], r["escalation"]), ("unknown", "read"))


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
               "--watch", "--interval", "1", "--allow-fast-poll"]
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
        open(os.path.join(d, "WATCH.json"), "w").write('{"tier": "fast"}')
        out = os.path.join(t.tmp.name, "_out")
        p = subprocess.Popen([sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out,
                              "--watch", "--interval", "1", "--allow-fast-poll", "--fast-recheck", "1"], stdout=subprocess.DEVNULL)
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


def beats(period_s, n, end_offset=0):
    """n heartbeat lines, period_s apart, the last at end_offset seconds from NOW."""
    return "".join(hb_line(end_offset - period_s * (n - 1 - i), "alive rows: x=%d" % i) for i in range(n))


def watch_json(d, text):
    with open(os.path.join(d, "WATCH.json"), "w") as f:
        f.write(text)


class Tiers(unittest.TestCase):
    def test_defaults_as_specified(self):
        cfg = wd.make_cfg(root=["/nonexistent"])
        self.assertEqual(cfg.interval, 600.0)
        self.assertEqual(cfg.tiers, {"fast": {"recheck_s": 600.0, "stall_s": 600.0},
                                     "medium": {"recheck_s": 1200.0, "stall_s": 1800.0},
                                     "slow": {"recheck_s": 3600.0, "stall_s": 7200.0}})

    def test_sub_600_refused_in_watch_and_override(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-5, "x"))
        out = os.path.join(t.tmp.name, "_out")
        base = [sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out]
        r = subprocess.run(base + ["--watch", "--interval", "120"], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 2)
        self.assertIn("floor", r.stderr)
        self.assertIn("--allow-fast-poll", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(out, "digest.json")))
        # one-shot is unaffected by --interval
        r = subprocess.run(base + ["--interval", "5"], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(r.returncode, 2)
        # override lets the watcher start
        p = subprocess.Popen(base + ["--watch", "--interval", "1", "--allow-fast-poll"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.time() + 10
            while time.time() < deadline and not os.path.exists(os.path.join(out, "digest.json")):
                time.sleep(0.1)
            self.assertTrue(os.path.exists(os.path.join(out, "digest.json")))
            self.assertIsNone(p.poll())
        finally:
            p.terminate()
            p.wait(10)

    def test_each_tier_threshold_applied(self):
        t = Tree()
        for tier in wd.TIER_NAMES:
            for age, tag in ((-500, "ok"), (-1000, "mid"), (-5000, "old"), (-9000, "vold")):
                d = t.run("%s_%s" % (tier, tag), heartbeat=hb_line(age, "alive"))
                watch_json(d, json.dumps({"tier": tier}))
        st = t.states()
        want = {"fast": {"ok": "running", "mid": "stalled", "old": "stalled", "vold": "stalled"},      # 600 s
                "medium": {"ok": "running", "mid": "running", "old": "stalled", "vold": "stalled"},    # 1800 s
                "slow": {"ok": "running", "mid": "running", "old": "running", "vold": "stalled"}}      # 7200 s
        for tier, row in want.items():
            for tag, state in row.items():
                self.assertEqual(st["%s_%s" % (tier, tag)], state, "%s %s" % (tier, tag))

    def test_flag_overrides_tier_defaults(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-1000, "alive"))
        watch_json(d, '{"tier": "fast"}')
        self.assertEqual(t.states()["r"], "stalled")
        self.assertEqual(t.states(fast_stall=1500.0)["r"], "running")

    def test_ten_minute_heartbeat_is_not_stalled(self):
        """The bug being fixed: a job that beats every 10 minutes was flagged stalled by the fixed 300 s threshold."""
        t = Tree()
        t.run("slowbeat", heartbeat=beats(600, 8, end_offset=-540))     # last beat 9 min ago
        t.run("latebeat", heartbeat=beats(600, 8, end_offset=-3600))    # silent for 1 h: 6 periods > 5x
        dg = t.digest()
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual(by["slowbeat"]["state"], "running")
        self.assertEqual(by["latebeat"]["state"], "stalled")
        self.assertEqual(by["slowbeat"]["tier"]["name"], "auto")
        self.assertEqual(by["slowbeat"]["tier"]["stall_s"], 3000.0)
        self.assertIn("heartbeat period", by["slowbeat"]["tier"]["source"])
        # the old global default (300 s) would have said stalled
        self.assertEqual(t.states(stall_seconds=300.0)["slowbeat"], "stalled")

    def test_inference_floor_and_few_heartbeats(self):
        t = Tree()
        t.run("quick", heartbeat=beats(30, 10, end_offset=-100))        # 5 x 30 s = 150 s, floored to 600 s
        t.run("one", heartbeat=hb_line(-1000, "alive"))                 # no gap at all: medium
        by = {r["id"]: r for r in t.digest()["runs"]}
        self.assertEqual(by["quick"]["tier"]["stall_s"], 600.0)
        self.assertEqual(by["quick"]["state"], "running")
        self.assertEqual(by["one"]["tier"]["name"], "medium")
        self.assertIn("default", by["one"]["tier"]["source"])
        self.assertEqual(by["one"]["tier"]["stall_s"], 1800.0)

    def test_single_two_hour_gap_is_not_stalled(self):
        t = Tree()
        t.run("one_gap", heartbeat=hb_line(-7200 - 3000, "alive") + hb_line(-3000, "alive"))   # 1 gap of 2 h, silent 50 min
        t.run("two_gaps", heartbeat=hb_line(-9000, "a") + hb_line(-7200, "a") + hb_line(-3600, "a"))   # gaps 30 min, 60 min
        t.run("one_gap_dead", heartbeat=hb_line(-7200 - 40000, "alive") + hb_line(-40000, "alive"))    # silent 11 h > 10 h
        by = {r["id"]: r for r in t.digest()["runs"]}
        self.assertEqual(by["one_gap"]["state"], "running")
        self.assertEqual(by["one_gap"]["tier"]["stall_s"], 36000.0)
        self.assertIn("max of 1 gap", by["one_gap"]["tier"]["source"])
        self.assertEqual(by["two_gaps"]["tier"]["stall_s"], 18000.0)
        self.assertIn("max of 2 gaps", by["two_gaps"]["tier"]["source"])
        self.assertEqual(by["one_gap_dead"]["state"], "stalled")

    def test_inference_ignores_duplicate_and_disordered_timestamps(self):
        # unique sorted timestamps 0,600,1200,1500,1800,2400 -> gaps 600,600,300,300,600 -> median 600
        samples = [{"ts": x} for x in (0, 0, 600, 600, 1200, 1800, 1500, 2400)]
        self.assertEqual(wd.infer_period(samples), (600, 5, "median"))
        # thin evidence uses the MAX gap, not the median
        self.assertEqual(wd.infer_period([{"ts": x} for x in (0, 0, 0, 0, 600, 1800)]), (1200, 2, "max"))
        self.assertEqual(wd.infer_period([{"ts": x} for x in (0, 7200)]), (7200, 1, "max"))
        self.assertEqual(wd.infer_period([{"ts": 5}, {"ts": 5}])[0], None)

    def test_watch_file_beats_inference_and_invalid_errors(self):
        t = Tree()
        d = t.run("r", heartbeat=beats(600, 8, end_offset=-2500))       # inference would give 3000 s: running
        self.assertEqual(t.states()["r"], "running")
        watch_json(d, '{"tier": "fast"}')                               # explicit fast (600 s): stalled
        r = t.digest()["runs"][0]
        self.assertEqual((r["state"], r["tier"]["name"], r["tier"]["source"]), ("stalled", "fast", "WATCH.json"))
        for bad in ('{"tier": "Slow"}', '{"tier": "hourly"}', '{"tier": 3}', '{"tier": null}', '[1]', '{not json'):
            watch_json(d, bad)
            r = t.digest()["runs"][0]
            self.assertEqual(r["state"], "unknown", bad)
            self.assertIn("WATCH.json", r["state_reason"], bad)
        watch_json(d, '{"note": "no tier key"}')                        # no tier key: not an error, falls through
        self.assertEqual(t.digest()["runs"][0]["tier"]["name"], "auto")

    def test_row_shows_tier_and_times(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-10, "alive rows: x=1"))
        watch_json(d, '{"tier": "slow"}')
        cfg = t.cfg()
        dg = wd.build_digest(cfg, {}, NOW)
        md = wd.render_md(dg, cfg)
        row = [ln for ln in md.splitlines() if ln.startswith("| r |")][0]
        self.assertIn("slow/file 08:00>09:00", row)
        self.assertEqual(dg["runs"][0]["watch"]["recheck_s"], 3600.0)


class DueScheduling(unittest.TestCase):
    def _tree(self, tier):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-10, "alive rows: x=1"))
        watch_json(d, json.dumps({"tier": tier}))
        return t, d

    def test_not_due_run_is_skipped_and_due_run_is_read(self):
        t, d = self._tree("slow")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        dg = wd.build_digest(cfg, {}, NOW, sched)
        self.assertEqual(dg["runs"][0]["progress"]["done"], 1)
        with open(os.path.join(d, "heartbeat.log"), "a") as f:           # new progress, but no marker
            f.write(hb_line(3500, "alive rows: x=99"))
        for tick in (600, 1200, 3000):                                  # ticks every 10 min, run is due hourly
            dg = wd.build_digest(cfg, {}, NOW + tick, sched)
            self.assertEqual(dg["runs"][0]["progress"]["done"], 99, "progress must track the run on every tick")
            self.assertEqual(dg["runs"][0]["watch"]["last_eval_utc"], wd.iso(NOW), "tick %d fully re-read a not-due run" % tick)
        dg = wd.build_digest(cfg, {}, NOW + 3600, sched)
        self.assertEqual(dg["runs"][0]["progress"]["done"], 99)
        self.assertEqual(dg["runs"][0]["watch"]["last_eval_utc"], wd.iso(NOW + 3600))
        self.assertEqual(dg["runs"][0]["watch"]["next_eval_utc"], wd.iso(NOW + 7200))

    def test_skipped_run_is_not_parsed(self):
        t, d = self._tree("slow")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        calls = []
        orig = wd.evaluate_run
        wd.evaluate_run = lambda *a, **k: calls.append(1) or orig(*a, **k)
        try:
            for tick in range(0, 3600, 600):
                wd.build_digest(cfg, {}, NOW + tick, sched)
            self.assertEqual(len(calls), 1)
            wd.build_digest(cfg, {}, NOW + 3600, sched)
            self.assertEqual(len(calls), 2)
        finally:
            wd.evaluate_run = orig

    def test_cached_age_keeps_growing(self):
        t, d = self._tree("slow")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        wd.build_digest(cfg, {}, NOW, sched)
        dg = wd.build_digest(cfg, {}, NOW + 1200, sched)
        self.assertEqual(dg["runs"][0]["age_s"], 1210)

    def test_failed_and_stalled_use_fast_cadence_despite_slow_tier(self):
        t = Tree()
        d1 = t.run("bad", heartbeat=hb_line(-10, "alive"), marker="rc=1")
        d2 = t.run("hung", heartbeat=hb_line(-20000, "alive"))
        d3 = t.run("ok", heartbeat=hb_line(-10, "alive"))
        for d in (d1, d2, d3):
            watch_json(d, '{"tier": "slow"}')
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        dg = wd.build_digest(cfg, {}, NOW, sched)
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual(by["bad"]["watch"]["recheck_s"], 600.0)
        self.assertEqual(by["hung"]["watch"]["recheck_s"], 600.0)
        self.assertEqual(by["ok"]["watch"]["recheck_s"], 3600.0)
        os.unlink(os.path.join(d1, "FAILED"))
        open(os.path.join(d1, "DONE"), "w").write("rc=0\n")
        with open(os.path.join(d2, "heartbeat.log"), "a") as f:
            f.write(hb_line(590, "alive"))
        dg = wd.build_digest(cfg, {}, NOW + 600, sched)
        by = {r["id"]: r for r in dg["runs"]}
        self.assertEqual(by["bad"]["state"], "done")                    # re-read at +10 min
        self.assertEqual(by["hung"]["state"], "running")
        self.assertEqual(by["ok"]["watch"]["last_eval_utc"], wd.iso(NOW))   # still cached

    def test_new_marker_makes_a_not_due_slow_run_due(self):
        t, d = self._tree("slow")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        calls = []
        orig = wd.evaluate_run
        wd.evaluate_run = lambda *a, **k: calls.append(1) or orig(*a, **k)
        try:
            wd.build_digest(cfg, {}, NOW, sched)
            wd.build_digest(cfg, {}, NOW + 600, sched)
            self.assertEqual(len(calls), 1)                              # not due, no marker: skipped
            open(os.path.join(d, "DONE"), "w").write("rc=0\n")
            dg = wd.build_digest(cfg, {}, NOW + 1200, sched)             # next tick, far before the hour
            self.assertEqual((len(calls), dg["runs"][0]["state"]), (2, "done"))
            self.assertEqual(dg["runs"][0]["watch"]["last_eval_utc"], wd.iso(NOW + 1200))
            wd.build_digest(cfg, {}, NOW + 1800, sched)                  # marker already seen: back to not-due
            self.assertEqual(len(calls), 2)
        finally:
            wd.evaluate_run = orig

    def test_marker_present_at_first_read_does_not_retrigger(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-10, "alive"), marker="rc=1")
        watch_json(d, '{"tier": "slow"}')
        os.unlink(os.path.join(d, "FAILED"))
        open(os.path.join(d, "DONE"), "w").write("rc=0\n")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        wd.build_digest(cfg, {}, NOW, sched)
        self.assertEqual(sched[d]["markers"], frozenset({"DONE"}))
        self.assertTrue(wd.marker_set(d, cfg) <= sched[d]["markers"])

    def test_vanished_run_is_forgotten(self):
        t, d = self._tree("fast")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        wd.build_digest(cfg, {}, NOW, sched)
        self.assertEqual(len(sched), 1)
        import shutil
        shutil.rmtree(d)
        wd.build_digest(cfg, {}, NOW + 600, sched)
        self.assertEqual(sched, {})

    def test_digest_rewritten_every_tick_even_when_nothing_is_due(self):
        t, d = self._tree("slow")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        wd.run_once(cfg, {}, NOW, sched)
        first = json.load(open(os.path.join(cfg.out_dir, "digest.json")))["generated_utc"]
        wd.run_once(cfg, {}, NOW + 600, sched)
        second = json.load(open(os.path.join(cfg.out_dir, "digest.json")))["generated_utc"]
        self.assertEqual((first, second), (wd.iso(NOW), wd.iso(NOW + 600)))



def rows_line(offset_s, alive, total, **counters):
    return hb_line(offset_s, "alive_shards=%d/%d rows: %s" % (alive, total, " ".join("%s=%d" % kv for kv in counters.items())))


class ProgressAndFlat(unittest.TestCase):
    def test_progress_is_the_sum_of_row_counters_and_advances_across_reads(self):
        t = Tree()
        d = t.run("r", heartbeat=rows_line(-120, 6, 6, hf=100, uniform=50))
        watch_json(d, '{"tier": "slow"}')
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        seen = []
        for k, tick in enumerate((0, 600, 1200)):                       # run advances; run is only fully read hourly
            with open(os.path.join(d, "heartbeat.log"), "a") as f:
                f.write(rows_line(tick - 60, 6, 6, hf=100 + 60 * (k + 1), uniform=50 + 30 * (k + 1)))
            dg = wd.build_digest(cfg, {}, NOW + tick, sched)
            seen.append(dg["runs"][0]["progress"]["done"])
        self.assertEqual(seen, [240, 330, 420])

    def test_empty_rows_line_is_zero_not_a_fraction(self):
        s = wd.parse_heartbeat_line(hb_line(0, "alive_shards=6/6 rows: ").strip())
        self.assertEqual(s["done"], 0)
        self.assertIsNone(s["total"])
        self.assertEqual(s["fields"], {"alive_shards": 6, "shards_total": 6})

    def test_rate_comes_from_two_observations_not_from_the_total(self):
        t = Tree()
        # the live bug: an empty first rows: line was read as '6/6 done', so the first rate was 1726/min beside a total of 1732
        t.run("r", heartbeat=rows_line(-180, 6, 6) + rows_line(-120, 6, 6, hf=1732) + rows_line(-60, 6, 6, hf=2800))
        p = t.digest()["runs"][0]["progress"]
        self.assertEqual(p["done"], 2800)
        self.assertEqual(p["rate_per_min"], 1400.0)                     # (2800 - 0) over 120 s, not 1732/min
        t2 = Tree()
        t2.run("r", heartbeat=rows_line(-120, 1, 6, hf=8685) + rows_line(-60, 1, 6, hf=8685))
        self.assertEqual(t2.digest()["runs"][0]["progress"]["rate_per_min"], 0.0)

    def _flat_hb(self, n_flat, step=60):
        return rows_line(-(n_flat + 1) * step, 6, 6, hf=10) + "".join(rows_line(-i * step, 6, 6, hf=500) for i in range(n_flat, -1, -1))

    def test_fresh_heartbeat_flat_progress_flagged_after_two_reads_not_one(self):
        t = Tree()
        d = t.run("r", heartbeat=self._flat_hb(25))                    # flat for 25 min under a fast tier (flag at 2 x 10 min)
        watch_json(d, '{"tier": "fast"}')
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        dg = wd.build_digest(cfg, {}, NOW, sched)
        r = dg["runs"][0]
        self.assertEqual(r["state"], "running")
        self.assertEqual(r["escalation"], "none")                       # one flat read: not flagged
        self.assertFalse(r["progress_flat"]["confirmed"])
        r = wd.build_digest(cfg, {}, NOW + 600, sched)["runs"][0]       # second consecutive full read, still flat
        self.assertEqual(r["state"], "running")
        self.assertEqual(r["escalation"], "read")
        self.assertTrue(r["progress_flat"]["confirmed"])
        self.assertIn("PROGRESS FLAT", r["escalation_reason"])
        md = wd.render_md(wd.build_digest(cfg, {}, NOW + 600, sched), cfg)   # a cached tick still shows it
        self.assertIn("PROGRESS FLAT", md)

    def test_flat_read_counter_resets_when_progress_moves(self):
        t = Tree()
        d = t.run("r", heartbeat=self._flat_hb(25))
        watch_json(d, '{"tier": "fast"}')
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        wd.build_digest(cfg, {}, NOW, sched)
        with open(os.path.join(d, "heartbeat.log"), "a") as f:
            f.write(rows_line(5, 6, 6, hf=900))
        r = wd.build_digest(cfg, {}, NOW + 600, sched)["runs"][0]
        self.assertIsNone(r["progress_flat"])
        self.assertEqual(r["escalation"], "none")

    def test_short_flat_stretch_and_long_tier_do_not_cry_wolf(self):
        t = Tree()
        t.run("short", heartbeat=self._flat_hb(8))                     # 8 min flat, below 2 x fast stall
        d = t.run("slowtier", heartbeat=self._flat_hb(25))             # 25 min flat is normal for a slow tier (flag at 4 h)
        watch_json(d, '{"tier": "slow"}')
        t.run("two", heartbeat=rows_line(-60, 6, 6, hf=5) + rows_line(-30, 6, 6, hf=5))   # only 2 samples: never flat
        watch_json(os.path.join(t.root, "short"), '{"tier": "fast"}')
        for r in t.digest()["runs"]:
            self.assertEqual(r["escalation"], "none", r["id"])
            self.assertIsNone(r["progress_flat"], r["id"])

    def test_one_shot_flags_on_heartbeat_history_alone(self):
        t = Tree()
        d = t.run("r", heartbeat=self._flat_hb(25))
        watch_json(d, '{"tier": "fast"}')
        r = t.digest()["runs"][0]
        self.assertEqual((r["state"], r["escalation"]), ("running", "read"))

    def test_dead_heartbeat_is_still_stalled_not_flat(self):
        t = Tree()
        d = t.run("r", heartbeat=self._flat_hb(25).replace(wd.iso(NOW), wd.iso(NOW - 5000)), log="x\n")
        watch_json(d, '{"tier": "fast"}')
        r = t.digest()["runs"][0]
        self.assertEqual(r["state"], "stalled")
        self.assertIsNone(r["progress_flat"])

    def test_finished_shards_are_told_from_lost_shards(self):
        t = Tree()
        d = t.run("r", heartbeat=rows_line(-60, 1, 6, hf=5) + rows_line(-30, 1, 6, hf=6))
        os.makedirs(os.path.join(d, "logs"))
        for i in range(6):                                             # shards 0-4 finished, shard 5 alive
            with open(os.path.join(d, "logs", "shard%d.log" % i), "w") as f:
                f.write("work\n" + ("shard %d/6 done; merge with --report-only\n" % i if i < 5 else ""))
        r = t.digest()["runs"][0]
        self.assertEqual((r["shards"]["finished"], r["shards"]["lost"]), (5, 0))
        self.assertFalse([n for n in r["notes"] if n.startswith("shards:")])
        os.unlink(os.path.join(d, "logs", "shard3.log"))                # now the count does not match: say so, do not guess
        with open(os.path.join(d, "logs", "shard3.log"), "w") as f:
            f.write("Traceback\n")                                     # shard 3 died without a done line
        r = t.digest()["runs"][0]
        self.assertEqual(r["shards"]["lost"], 1)
        self.assertTrue([n for n in r["notes"] if "neither alive nor finished" in n])

    def test_shards_not_determinable_without_matching_logs(self):
        t = Tree()
        t.run("r", heartbeat=rows_line(-60, 1, 6, hf=5) + rows_line(-30, 1, 6, hf=6))
        r = t.digest()["runs"][0]
        self.assertIsNone(r["shards"]["lost"])
        self.assertIn("not determinable", r["shards"]["note"])
        self.assertFalse([n for n in r["notes"] if n.startswith("shards:")])



def steady_hb(n, step, rate_per_step, start_count=0):
    """n rows: lines, step seconds apart, the last at NOW, advancing rate_per_step rows per line."""
    return "".join(rows_line(-(n - 1 - i) * step, 6, 6, hf=start_count + rate_per_step * i) for i in range(n))


class DeclaredTotal(unittest.TestCase):
    def test_undeclared_total_stays_unknown_no_estimate(self):
        t = Tree()
        t.run("r", heartbeat=steady_hb(40, 60, 100))
        p = t.digest()["runs"][0]["progress"]
        self.assertIsNone(p["total"])
        self.assertIsNone(p["left_s"])
        self.assertIsNone(p["eta_utc"])
        self.assertIn("total unknown", p["note"])

    def test_declared_total_gives_fraction_and_a_range(self):
        t = Tree()
        d = t.run("r", heartbeat=steady_hb(61, 60, 100))               # 6000 rows in 1 h, 100/min
        watch_json(d, '{"tier": "slow", "total": 24000}')
        r = t.digest()["runs"][0]
        p = r["progress"]
        self.assertEqual((p["done"], p["total"], p["percent"], p["total_source"]), (6000, 24000, 25.0, "WATCH.json"))
        lo, hi = p["left_s"]
        base = 18000 / (100 / 60.0)                                     # 10800 s at a constant rate
        w = 1.0 + 0.75
        self.assertAlmostEqual(lo, base / w, delta=5)                   # widened both ways, more when early
        self.assertAlmostEqual(hi, base * w, delta=5)
        self.assertEqual(p["eta_quality"], "range")
        self.assertEqual(r["escalation"], "none")
        cfg = t.cfg()
        row = [ln for ln in wd.render_md(wd.build_digest(cfg, {}, NOW), cfg).splitlines() if ln.startswith("| r |")][0]
        self.assertIn("6000/24000 25%", row)
        self.assertIn("left", row)

    def test_range_is_narrower_late_and_rate_changes_widen_it(self):
        t = Tree()
        # fast early, slow now: the two rates disagree, so the range spans both
        lines = [(-(49 - i) * 60, 300 * i if i < 30 else 300 * 29 + 20 * (i - 29)) for i in range(50)]
        d = t.run("r", heartbeat="".join(rows_line(o, 6, 6, hf=c) for o, c in lines))
        watch_json(d, '{"tier": "slow", "total": 20000}')
        p = t.digest()["runs"][0]["progress"]
        self.assertGreater(p["left_s"][1] / float(p["left_s"][0]), 4)  # wide: recent and average rates differ a lot
        self.assertEqual(wd.fmt_left(7200, 14400), "~2-4h")
        self.assertEqual(wd.fmt_left(2400, 7200), "~40m-2h")
        self.assertEqual(wd.fmt_left(36000, 36000), "~10h")

    def test_few_minutes_of_data_is_labelled_rough(self):
        t = Tree()
        d = t.run("r", heartbeat=steady_hb(4, 60, 100))
        watch_json(d, '{"tier": "slow", "total": 90000}')
        r = t.digest()["runs"][0]
        self.assertEqual(r["progress"]["eta_quality"], "rough")
        cfg = t.cfg()
        row = [ln for ln in wd.render_md(wd.build_digest(cfg, {}, NOW), cfg).splitlines() if ln.startswith("| r |")][0]
        self.assertIn("rough", row)

    def test_total_exceeded_is_flagged(self):
        t = Tree()
        d = t.run("r", heartbeat=steady_hb(30, 60, 100))               # 2900 rows
        watch_json(d, '{"tier": "slow", "total": 2000}')
        r = t.digest()["runs"][0]
        self.assertEqual((r["state"], r["escalation"]), ("running", "read"))
        self.assertIn("TOTAL EXCEEDED", r["escalation_reason"])
        cfg = t.cfg()
        self.assertIn(">100%", wd.render_md(wd.build_digest(cfg, {}, NOW), cfg))
        d2 = t.run("fin", heartbeat=steady_hb(30, 60, 100), marker="rc=0")
        watch_json(d2, '{"tier": "slow", "total": 2000}')
        by = {x["id"]: x for x in t.digest()["runs"]}
        self.assertIn("TOTAL EXCEEDED", by["fin"]["escalation_reason"])  # a finished run that overshot is also wrong

    def test_unreachable_total_is_flagged_only_on_the_optimistic_bound(self):
        t = Tree()
        d = t.run("hopeless", heartbeat=steady_hb(61, 60, 1))           # 1 row/min, 10 million to go
        watch_json(d, '{"tier": "slow", "total": 10000000}')
        d2 = t.run("fine", heartbeat=steady_hb(61, 60, 100))
        watch_json(d2, '{"tier": "slow", "total": 40000}')
        by = {x["id"]: x for x in t.digest()["runs"]}
        self.assertIn("TOTAL UNREACHABLE", by["hopeless"]["escalation_reason"])
        self.assertEqual(by["fine"]["escalation"], "none")

    def test_no_anomaly_without_a_declaration(self):
        t = Tree()
        t.run("r", heartbeat=steady_hb(61, 60, 1))
        r = t.digest()["runs"][0]
        self.assertEqual(r["escalation"], "none")
        self.assertIsNone(r["total_anomaly"])

    def test_invalid_total_errors_naming_the_file(self):
        t = Tree()
        d = t.run("r", heartbeat=steady_hb(10, 60, 1))
        for bad in ('{"total": "5000"}', '{"total": 0}', '{"total": -3}', '{"total": 12.5}', '{"total": true}', '{"total": null}'):
            watch_json(d, bad)
            r = t.digest()["runs"][0]
            self.assertEqual(r["state"], "unknown", bad)
            self.assertIn("WATCH.json", r["state_reason"], bad)
            self.assertIn("total", r["state_reason"], bad)

    def test_declared_total_wins_and_cached_ticks_keep_the_estimate_current(self):
        t = Tree()
        d = t.run("r", heartbeat=steady_hb(61, 60, 100))
        watch_json(d, '{"tier": "slow", "total": 24000}')
        with open(os.path.join(d, "total.txt"), "w") as f:
            f.write("999999")
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        p0 = wd.build_digest(cfg, {}, NOW, sched)["runs"][0]["progress"]
        self.assertEqual(p0["total"], 24000)
        with open(os.path.join(d, "heartbeat.log"), "a") as f:
            f.write(rows_line(600, 6, 6, hf=7000))
        r = wd.build_digest(cfg, {}, NOW + 600, sched)["runs"][0]
        self.assertEqual((r["progress"]["done"], r["progress"]["total"]), (7000, 24000))
        self.assertEqual(r["watch"]["last_eval_utc"], wd.iso(NOW))      # estimate refreshed without a full read


class UniformCost(unittest.TestCase):
    def _run(self, t, flag):
        d = t.run("r", heartbeat=steady_hb(61, 60, 100))
        body = {"tier": "slow", "total": 24000}
        if flag is not None:
            body["uniform_cost"] = flag
        watch_json(d, json.dumps(body))
        return d

    def test_false_suppresses_the_range_but_keeps_fraction_and_rate(self):
        t = Tree()
        self._run(t, False)
        r = t.digest()["runs"][0]
        p = r["progress"]
        self.assertEqual((p["done"], p["total"], p["percent"]), (6000, 24000, 25.0))
        self.assertEqual(p["rate_per_min"], 100.0)
        self.assertEqual(p["eta_quality"], "suppressed")
        for k in ("left_s", "eta_utc", "eta_lo_utc", "eta_hi_utc"):     # nothing half-computed anywhere
            self.assertIsNone(p[k], k)
        self.assertFalse(p["uniform_cost"])
        cfg = t.cfg()
        row = [ln for ln in wd.render_md(wd.build_digest(cfg, {}, NOW), cfg).splitlines() if ln.startswith("| r |")][0]
        self.assertIn("6000/24000 25%", row)
        self.assertIn("100/min", row)
        self.assertIn("no ETA", row)
        self.assertNotIn("left", row)

    def test_false_also_disables_the_unreachable_flag_but_not_the_exceeded_flag(self):
        t = Tree()
        d = t.run("hopeless", heartbeat=steady_hb(61, 60, 1))
        watch_json(d, '{"tier": "slow", "total": 10000000, "uniform_cost": false}')
        d2 = t.run("over", heartbeat=steady_hb(61, 60, 100))
        watch_json(d2, '{"tier": "slow", "total": 1000, "uniform_cost": false}')
        by = {x["id"]: x for x in t.digest()["runs"]}
        self.assertEqual(by["hopeless"]["escalation"], "none")
        self.assertIsNone(by["hopeless"]["total_anomaly"])
        self.assertIn("TOTAL EXCEEDED", by["over"]["escalation_reason"])   # a row count over the declaration is not about cost

    def test_absent_and_true_behave_exactly_as_before(self):
        outs = []
        for flag in (None, True):
            t = Tree()
            self._run(t, flag)
            p = t.digest()["runs"][0]["progress"]
            p = dict(p)
            p.pop("uniform_cost")
            outs.append(p)
            self.assertEqual(p["eta_quality"], "range")
            self.assertTrue(p["left_s"])
        self.assertEqual(outs[0], outs[1])

    def test_invalid_flag_errors_naming_the_file(self):
        t = Tree()
        d = t.run("r", heartbeat=steady_hb(10, 60, 1))
        for bad in ('{"uniform_cost": "no"}', '{"uniform_cost": 0}', '{"uniform_cost": null}'):
            watch_json(d, bad)
            r = t.digest()["runs"][0]
            self.assertEqual(r["state"], "unknown", bad)
            self.assertIn("uniform_cost", r["state_reason"], bad)
            self.assertIn("WATCH.json", r["state_reason"], bad)

    def test_flag_survives_cached_ticks_and_legend_states_the_assumption(self):
        t = Tree()
        d = self._run(t, False)
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        wd.build_digest(cfg, {}, NOW, sched)
        with open(os.path.join(d, "heartbeat.log"), "a") as f:
            f.write(rows_line(600, 6, 6, hf=7000))
        dg = wd.build_digest(cfg, {}, NOW + 600, sched)
        r = dg["runs"][0]
        self.assertEqual(r["watch"]["last_eval_utc"], wd.iso(NOW))      # cached tick
        self.assertEqual((r["progress"]["done"], r["progress"]["eta_quality"], r["progress"]["left_s"]), (7000, "suppressed", None))
        md = wd.render_md(dg, cfg)
        self.assertIn("UNIFORM cost per row", md)
        self.assertIn("wrong when work per row varies", md)

# ----------------------------------------------------------------------------- throughput and NPU utilisation
def smi_text(chips, procs=()):
    """npu-smi info in its real shape: TWO lines per chip, then the process table. chips: [(npu, aicore, hbm_used_mb)]."""
    out = ["+---------------------------+---------------+----------------------------------------------------------------------+",
           "| NPU   Name                | Health        | Power(W)             Temp(C)                 Hugepages-Usage(page)   |",
           "| Chip                      | Bus-Id        | AICore(%)            Memory-Usage(MB)        HBM-Usage(MB)           |",
           "+===========================+===============+======================================================================+"]
    for n, ai, hbm in chips:
        out.append("| %-5d 910B3               | OK            | 184.4                58                      0    / 0                |" % n)
        out.append("| 0                         | 0000:C%d:00.0  | %-20d 0    / 0                %-5d/ 65536            |" % (n, ai, hbm))
        out.append("+===========================+===============+======================================================================+")
    out.append("| NPU     Chip              | Process id    | Process name       | Process memory(MB)    | Process id in container |")
    for n, pid, mem in procs:
        out.append("| %-7d 0                 | %-13d | python3            | %-21d | NA                      |" % (n, pid, mem))
    return "\n".join(out) + "\n"


def procmem_text(npu, procs):
    body = "".join("\tProcess id:%d Process name:python3           Process memory(MB):%d\n" % p for p in procs) or "\tNo process in device.\n"
    return "\tNPU ID                         : %d\n\tChip Count                     : 1\n\n%s\tChip ID                        : 0\n" % (npu, body)


def hb_perf(offset, tok=32062, q=3.41, chips=1, k=1, gib=20.0, done=20, total=3116):
    return hb_line(offset, "step done=%d total=%d loss=1.2 step_s=1.58 tok_s_chip_w20=%d q_s_chip_w20=%.2f chips=%d procs_on_chip=%d reserved_gib=%.1f" % (
        done, total, tok, q, chips, k, gib))


def perf_json(path, win_tok=1000.0, win_q=10.0, base=(1000.0, 10.0), utc_off=-20, chips=1, k=1):
    o = {"utc": wd.iso(NOW + utc_off), "step": 200, "total_steps": 3116, "chips": chips, "procs_on_chip": k, "window_steps": 20,
         "reserved_gib_peak": 20.5,
         "window": {"tok_s_proc": win_tok, "q_s_proc": win_q, "step_s_mean": 2.0, "tok_s_chip_equiv": win_tok * k, "q_s_chip_equiv": win_q * k},
         "baseline": ({"steps": [20, 120], "n_steps": 101, "tok_s_proc": base[0], "q_s_proc": base[1], "step_s_mean": 2.0} if base else None),
         "ratio_to_baseline": None}
    with open(path, "w") as f:
        json.dump(o, f)


class ThroughputParsing(unittest.TestCase):
    def test_per_chip_and_host_fields_keep_their_scope(self):
        a = wd.parse_perf_fields("step done=20 tok_s_chip_w20=32062 q_s_chip_w20=3.41 chips=1 procs_on_chip=2 reserved_gib=20.0 step_s=1.58")
        self.assertEqual((a["scope"], a["tok_s"], a["ex_s"], a["ex_unit"], a["window"], a["chips"], a["procs_on_chip"], a["reserved_gib"]),
                         ("chip", 32062.0, 3.41, "q", 20, 1, 2, 20.0))
        h = wd.parse_perf_fields("x:y done=64 total=80 ex_s_host_nochip_w20=0.55 tok_s_host_nochip_w20=128 chips=0")
        self.assertEqual((h["scope"], h["tok_s"], h["ex_s"], h["ex_unit"], h["chips"]), ("host", 128.0, 0.55, "ex", 0))
        self.assertIsNone(wd.parse_perf_fields("alive pid=78 log_lines=0"))
        self.assertIsNone(wd.parse_perf_fields("alive_shards=6/6 rows: a=5"))

    def test_heartbeat_progress_is_unchanged_by_the_new_fields(self):
        s = wd.parse_heartbeat_line(hb_perf(0).strip())
        self.assertEqual((s["done"], s["total"]), (20, 3116))
        s = wd.parse_heartbeat_line("2026-10-30T03:03:53Z HEARTBEAT decision-v7/dev clean 6/6 ex_s_host_nochip_w20=3454.71 tok_s_host_nochip_w20=1085642 chips=0")
        self.assertEqual((s["done"], s["total"], s["perf"]["scope"], s["perf"]["tok_s"]), (6, 6, "host", 1085642.0))

    def test_progress_log_median_of_step_lines(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-30, "alive pid=1"))
        with open(os.path.join(d, "progress.log"), "w") as f:
            for i, tok in enumerate((400, 594, 332, 538, 456)):
                f.write(hb_line(-100 + i, "step %d/100 epoch 0 loss 0.8 lr 1e-4 gnorm 1 step_s 5.0 tok/s/chip %d q/s/chip 1.95 chips 1 reserved_gib 6.6" % (i + 1, tok)).replace("\n", "\n"))
        p = t.digest()["runs"][0]["perf"]
        self.assertEqual((p["scope"], p["tok_s"], p["chips"], p["sources"], p["baseline"]), ("chip", 456.0, 1, ["progress.log"], "undeclared"))


class ThroughputInDigest(unittest.TestCase):
    def _row(self, t, **kw):
        cfg = t.cfg(**kw)
        md = wd.render_md(wd.build_digest(cfg, {}, NOW), cfg)
        return [ln for ln in md.splitlines() if ln.startswith("| r |")][0]

    def test_running_row_shows_per_chip_rates_chip_count_and_reserved(self):
        t = Tree()
        t.run("r", heartbeat=hb_perf(-60, done=10) + hb_perf(-30, done=20))
        row = self._row(t)
        for frag in ("32062 tok/s/chip", "3.41 q/s/chip", "x1", "20.0GiB", "base?"):
            self.assertIn(frag, row)
        p = t.digest()["runs"][0]["perf"]
        self.assertEqual((p["scope"], p["chips"], p["baseline"], p["ratio"], p["regressed"]), ("chip", 1, "undeclared", None, False))

    def test_host_rates_of_a_cpu_run_are_never_shown_per_chip(self):
        t = Tree()
        t.run("r", heartbeat=hb_line(-60, "trackT:x done=32 total=80 ex_s_host_nochip_w20=0.55 tok_s_host_nochip_w20=128 chips=0") +
              hb_line(-30, "trackT:x done=64 total=80 ex_s_host_nochip_w20=0.59 tok_s_host_nochip_w20=130 chips=0"))
        row = self._row(t)
        self.assertIn("host 130 tok/s, 0.59 ex/s (chips=0)", row)
        self.assertNotIn("/chip", row)
        p = t.digest()["runs"][0]["perf"]
        self.assertEqual((p["scope"], p["chips"]), ("host", 0))

    def test_children_are_found_and_processes_sharing_a_chip_count_once(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-30, "alive pid=78 log_lines=0"))
        for i in range(2):
            c = os.path.join(d, "res", "p%d" % i)
            os.makedirs(c)
            with open(os.path.join(c, "heartbeat.log"), "w") as f:
                f.write(hb_perf(-30, tok=4000 + 1000 * i, chips=1, k=2, gib=23.0))
        p = t.digest()["runs"][0]["perf"]
        self.assertEqual((p["n_procs"], p["chips"], p["procs_on_chip"], p["tok_s"]), (2, 1, 2, 4500.0))
        self.assertIn("x1/2p", self._row(t))
        d2 = t.run("q", heartbeat=hb_line(-30, "alive pid=78"))
        for i in range(4):
            c = os.path.join(d2, "res", "p%d" % i)
            os.makedirs(c)
            with open(os.path.join(c, "heartbeat.log"), "w") as f:
                f.write(hb_perf(-30))
        self.assertEqual(next(r for r in t.digest()["runs"] if r["id"] == "q")["perf"]["chips"], 4)

    def test_finished_rows_carry_perf_only_in_json(self):
        t = Tree()
        t.run("r", heartbeat=hb_perf(-60) + hb_perf(-30), marker="rc=0 utc=2027-01-15T08:00:00Z")
        dg = t.digest()
        self.assertEqual(dg["runs"][0]["perf"]["tok_s"], 32062.0)


class ThroughputRegression(unittest.TestCase):
    def _t(self, win_tok, base=(1000.0, 10.0), marker=None, utc_off=-20, win_q=None):
        t = Tree()
        d = t.run("r", heartbeat=hb_perf(-60, done=10) + hb_perf(-30, done=20), marker=marker)
        perf_json(os.path.join(d, "perf.json"), win_tok=win_tok, win_q=win_q if win_q is not None else win_tok / 100.0, base=base, utc_off=utc_off)
        return t

    def test_below_seven_tenths_of_the_declared_baseline_escalates_like_a_stall(self):
        t = self._t(600.0)
        r = t.digest()["runs"][0]
        self.assertEqual((r["state"], r["escalation"], r["perf_regression"]), ("running", "decide", True))
        self.assertIn("THROUGHPUT REGRESSION 0.60x", r["escalation_reason"])
        self.assertAlmostEqual(r["perf"]["ratio"], 0.6)
        self.assertEqual(r["pointers"][0]["path"], os.path.join(r["path"], "perf.json"))
        cfg = t.cfg()
        md = wd.render_md(wd.build_digest(cfg, {}, NOW), cfg)
        row = [ln for ln in md.splitlines() if ln.startswith("| r |")][0]
        self.assertIn("r=0.60", row)
        self.assertIn("THROUGHPUT REGRESSION", row)

    def test_at_or_above_the_threshold_is_not_flagged(self):
        for w in (700.0, 950.0, 1400.0):
            r = self._t(w).digest()["runs"][0]
            self.assertEqual((r["escalation"], r["perf_regression"]), ("none", False), w)

    def test_no_declared_baseline_is_stated_not_invented(self):
        t = self._t(10.0, base=None)
        r = t.digest()["runs"][0]
        self.assertEqual((r["escalation"], r["perf"]["baseline"], r["perf"]["ratio"]), ("none", "undeclared", None))
        cfg = t.cfg()
        self.assertIn("base?", wd.render_md(wd.build_digest(cfg, {}, NOW), cfg))

    def test_only_a_running_run_is_flagged(self):
        r = self._t(300.0, marker="rc=0 utc=2027-01-15T08:00:00Z").digest()["runs"][0]
        self.assertEqual((r["state"], r["escalation"], r["perf_regression"]), ("done", "none", False))
        self.assertAlmostEqual(r["perf"]["ratio"], 0.3)

    def test_a_stale_perf_json_is_not_flagged(self):
        r = self._t(300.0, utc_off=-5000).digest()["runs"][0]
        self.assertEqual((r["escalation"], r["perf"]["ratio_stale"], r["perf_regression"]), ("none", True, False))

    def test_ratio_key_and_threshold_are_options(self):
        t = self._t(900.0, win_q=5.0)                  # tokens 0.9x, questions 0.5x
        self.assertEqual(t.digest()["runs"][0]["escalation"], "none")
        self.assertEqual(t.digest(perf_ratio_key="q_s")["runs"][0]["escalation"], "decide")
        self.assertEqual(t.digest(perf_regress_ratio=0.95)["runs"][0]["escalation"], "decide")

    def test_worst_process_decides(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-30, "alive pid=78"))
        for i, w in enumerate((1000.0, 500.0)):
            c = os.path.join(d, "res", "p%d" % i)
            os.makedirs(c)
            with open(os.path.join(c, "heartbeat.log"), "w") as f:
                f.write(hb_perf(-30))
            perf_json(os.path.join(c, "perf.json"), win_tok=w)
        r = t.digest()["runs"][0]
        self.assertEqual((r["escalation"], r["perf"]["ratio_dir"]), ("decide", os.path.join("res", "p1")))
        self.assertEqual(r["pointers"][0]["path"], os.path.join(d, "res", "p1", "perf.json"))

    def test_eval_shaped_perf_json_on_cpu_is_host(self):
        t = Tree()
        d = t.run("r", heartbeat=hb_line(-30, "alive"))
        with open(os.path.join(d, "perf.json"), "w") as f:
            json.dump({"utc": wd.iso(NOW - 10), "chips": 0, "device": "cpu", "examples_per_s_per_chip": None, "tokens_per_s_per_chip": None,
                       "examples_per_s_total_for_reference": 0.55, "tokens_per_s_total_for_reference": 127.5, "window_calls": 20}, f)
        p = t.digest()["runs"][0]["perf"]
        self.assertEqual((p["scope"], p["tok_s"], p["ex_s"], p["chips"]), ("host", 127.5, 0.55, 0))
        with open(os.path.join(d, "perf.json"), "w") as f:
            json.dump({"utc": wd.iso(NOW - 10), "chips": 2, "examples_per_s_per_chip": 4.0, "tokens_per_s_per_chip": 900.0}, f)
        p = t.digest()["runs"][0]["perf"]
        self.assertEqual((p["scope"], p["tok_s"], p["ex_s"], p["chips"]), ("chip", 900.0, 4.0, 2))

    def test_cached_tick_follows_the_rate_but_keeps_the_escalation_of_the_last_full_read(self):
        t = self._t(600.0)
        cfg = t.cfg(interval=600.0, watch=True)
        sched = {}
        self.assertEqual(wd.build_digest(cfg, {}, NOW, sched)["runs"][0]["escalation"], "decide")
        d = os.path.join(t.root, "r")
        perf_json(os.path.join(d, "perf.json"), win_tok=990.0, utc_off=300)
        r = wd.build_digest(cfg, {}, NOW + 300, sched)["runs"][0]
        self.assertEqual(r["watch"]["last_eval_utc"], wd.iso(NOW))      # cached
        self.assertAlmostEqual(r["perf"]["ratio"], 0.99)                # the rate follows
        self.assertEqual(r["escalation"], "decide")                     # the escalation waits for the next full read


NPU_REAL = """\
+---------------------------+---------------+----------------------------------------------------------------------+
| NPU   Name                | Health        | Power(W)             Temp(C)                 Hugepages-Usage(page)   |
| Chip                      | Bus-Id        | AICore(%)            Memory-Usage(MB)        HBM-Usage(MB)           |
+===========================+===============+======================================================================+
| 0     910B3               | OK            | 184.4                58                      0    / 0                |
| 0                         | 0000:C1:00.0  | 55                   0    / 0                16209/ 65536            |
+===========================+===============+======================================================================+
| 4     910B3               | OK            | 101.3                43                      0    / 0                |
| 0                         | 0000:01:00.0  | 0                    0    / 0                3455 / 65536            |
+===========================+===============+======================================================================+
| NPU     Chip              | Process id    | Process name       | Process memory(MB)    | Process id in container |
+===========================+===============+======================================================================+
| 0       0                 | 1176824       | python3            | 12810                 | NA                      |
+===========================+===============+======================================================================+
| No running processes found in NPU 4                                                                              |
+===========================+===============+======================================================================+
"""


def raw_probe(chips, procmem=None, ps=None, procs=(), t=NOW, snaps=1):
    """What probe_npu returns, built from (npu, aicore_list, hbm) tuples; `snaps` identical snapshots unless aicore is a list."""
    samples = []
    for k in range(snaps):
        samples.append(wd.parse_npu_smi(smi_text([(n, a[k] if isinstance(a, list) else a, h) for n, a, h in chips], procs)))
    return {"ok": True, "samples": samples, "procmem": procmem or {}, "ps": ps or {}, "t": t}


class NpuParsing(unittest.TestCase):
    def test_two_lines_per_chip_and_the_process_table(self):
        s = wd.parse_npu_smi(NPU_REAL)
        self.assertEqual([(c["npu"], c["aicore_pct"], c["hbm_used_mb"], c["hbm_total_mb"], c["health"], c["power_w"], c["temp_c"]) for c in s["chips"]],
                         [(0, 55, 16209, 65536, "OK", 184.4, 58), (4, 0, 3455, 65536, "OK", 101.3, 43)])
        self.assertEqual(s["chips"][0]["bus_id"], "0000:C1:00.0")
        self.assertEqual([(p["npu"], p["pid"], p["name"], p["mem_mb"]) for p in s["procs"]], [(0, 1176824, "python3", 12810)])

    def test_proc_mem_has_no_space_after_the_colons(self):
        txt = procmem_text(1, [(1479047, 3936), (1479561, 31)])
        self.assertEqual([(p["pid"], p["mem_mb"]) for p in wd.parse_proc_mem(txt)], [(1479047, 3936), (1479561, 31)])
        self.assertEqual(wd.parse_proc_mem(procmem_text(4, [])), [])

    def test_claim_walks_up_to_the_most_specific_run_directory(self):
        by = {"/x/runs/a": "a", "/x/runs/a/res/p0": "p0run", "/x/runs": "parent"}
        self.assertEqual(wd.claim_runs("python3 -P t.py --out /x/runs/a/res/p0 --seed 2", by), {"p0run"})
        self.assertEqual(wd.claim_runs("python3 /x/runs/a/ckpt/step_10/m.pt", by), {"a"})
        self.assertEqual(wd.claim_runs("python3 /x/runs/ab/foo", by), {"parent"})
        self.assertEqual(wd.claim_runs("python3 /elsewhere/foo", by), set())


class NpuAnalysis(unittest.TestCase):
    def cfg(self, **kw):
        kw.setdefault("interval", 600.0)
        kw.setdefault("out_dir", tempfile.mkdtemp(prefix="wdnpu_"))
        return wd.make_cfg(**kw)

    def runs(self, n_running=1):
        return [{"id": "run%d" % i, "path": "/x/run%d" % i, "state": "running"} for i in range(n_running)]

    def test_unclaimed_chip_beside_running_work_is_flagged_decide(self):
        raw = raw_probe([(0, 80, 20000), (1, 0, 3450)], procmem={0: [{"pid": 11, "name": "python3", "mem_mb": 9000}], 1: []},
                        ps={11: "python3 t.py --out /x/run0"}, procs=[(0, 11, 9000)])
        n = wd.analyse_npu(raw, self.runs(), [], self.cfg(), {})
        st = {c["npu"]: c["state"] for c in n["chips"]}
        self.assertEqual(st, {0: "busy", 1: "unclaimed"})
        self.assertEqual(n["chips"][0]["claimed_by"], ["run0"])
        self.assertEqual((n["escalation"], [f["kind"] for f in n["flags"]], n["unclaimed"]), ("decide", ["unclaimed_while_work"], [1]))

    def test_queued_work_alone_counts(self):
        raw = raw_probe([(1, 0, 3450)], procmem={1: []})
        n = wd.analyse_npu(raw, [], ["q1"], self.cfg(), {})
        self.assertEqual((n["escalation"], n["flags"][0]["kind"], n["queued_runs"]), ("decide", "unclaimed_while_work", 1))

    def test_nothing_running_or_queued_is_a_read_level_unused_flag(self):
        n = wd.analyse_npu(raw_probe([(1, 0, 3450)], procmem={1: []}), [], [], self.cfg(), {})
        self.assertEqual((n["escalation"], n["flags"][0]["kind"]), ("read", "unclaimed_no_work"))

    def test_a_claimed_chip_at_zero_aicore_is_never_unclaimed_and_one_sample_never_flags(self):
        # a container loading weights: a resident process (31 MB is enough) or HBM above the baseline, 0 % AICore
        for kw in (dict(procmem={2: [{"pid": 5, "name": "python3", "mem_mb": 31}]}), dict(procs=[(2, 5, 31)]), {}):
            hbm = 12000 if not kw else 3500
            n = wd.analyse_npu(raw_probe([(2, 0, hbm)], **kw), self.runs(), [], self.cfg(), {})
            c = n["chips"][0]
            self.assertTrue(c["claimed"], kw)
            self.assertEqual((c["state"], n["flags"], n["escalation"]), ("quiet", [], "none"), kw)

    def test_hbm_above_baseline_alone_claims_a_chip(self):
        n = wd.analyse_npu(raw_probe([(2, 0, 9000)]), self.runs(), [], self.cfg(), {})
        self.assertEqual(n["chips"][0]["state"], "quiet")
        self.assertEqual(n["chips"][0]["processes"], [])

    def test_sustained_near_zero_on_a_claimed_chip_is_flagged_with_its_duration(self):
        cfg = self.cfg()
        hist = {}
        pm = {2: [{"pid": 5, "name": "python3", "mem_mb": 9000}]}
        states = []
        for i in range(4):                                       # four passes, 10 min apart, always 0 %
            n = wd.analyse_npu(raw_probe([(2, [0, 0, 0], 9000)], procmem=pm, t=NOW + 600 * i, snaps=3), self.runs(), [], cfg, hist)
            states.append(n["chips"][0]["state"])
        self.assertEqual(states, ["quiet", "quiet", "wedged?", "wedged?"])   # 3 passes spanning 1200 s are needed; one sample never flags
        c = n["chips"][0]
        self.assertEqual((c["quiet_passes"], c["quiet_s"]), (4, 1800))
        self.assertEqual((n["escalation"], n["flags"][0]["kind"]), ("read", "possibly_wedged"))
        self.assertIn("30m", n["flags"][0]["text"])

    def test_one_busy_pass_or_a_gap_resets_the_streak(self):
        cfg = self.cfg()
        hist = {}
        pm = {2: [{"pid": 5, "name": "python3", "mem_mb": 9000}]}
        for i, a in enumerate((0, 0, 60, 0, 0)):
            n = wd.analyse_npu(raw_probe([(2, a, 9000)], procmem=pm, t=NOW + 600 * i), self.runs(), [], cfg, hist)
        self.assertEqual((n["chips"][0]["state"], n["chips"][0]["quiet_passes"]), ("quiet", 2))
        hist = {}
        for i, off in enumerate((0, 600, 1200, 1200 + 7200)):          # two-hour hole: the watchdog was not looking
            n = wd.analyse_npu(raw_probe([(2, 0, 9000)], procmem=pm, t=NOW + off), self.runs(), [], cfg, hist)
        self.assertEqual((n["chips"][0]["state"], n["chips"][0]["quiet_passes"]), ("quiet", 1))

    def test_claimed_and_low_is_informational_not_an_escalation(self):
        # a launch-bound job runs healthy at 9-22 % AICore
        raw = raw_probe([(0, 9, 20000), (1, 22, 20000), (2, 80, 20000)], procs=[(0, 1, 9000), (1, 2, 9000), (2, 3, 9000)])
        n = wd.analyse_npu(raw, self.runs(), [], self.cfg(), {})
        self.assertEqual([c["state"] for c in n["chips"]], ["low", "low", "busy"])
        self.assertEqual((n["escalation"], [(f["kind"], f["escalation"]) for f in n["flags"]]), ("none", [("claimed_low_info", "none")]))

    def test_history_is_persisted_between_one_shot_passes(self):
        cfg = self.cfg(root=[tempfile.mkdtemp(prefix="wdroot_")])
        states = {}
        raw = {"ok": True}
        orig = wd.probe_npu
        try:
            for i in range(2):
                wd.probe_npu = lambda c, i=i: raw_probe([(2, 0, 9000)], t=NOW + 600 * i)
                dg = {"runs": [], "queued": []}
                n = wd.npu_pass(cfg, dg, states)
                states.clear()                                  # a new process each time: only the file carries the history
            self.assertEqual(n["chips"][0]["passes_seen"], 2)
        finally:
            wd.probe_npu = orig

    def test_probe_failure_is_reported_not_raised(self):
        n = wd.analyse_npu({"ok": False, "reason": "ssh failed"}, [], [], self.cfg(), {})
        self.assertEqual((n["available"], n["reason"], n["flags"]), (False, "ssh failed", []))


class NpuProbeAndRender(unittest.TestCase):
    def bin_dir(self, ssh_rc=None):
        d = tempfile.mkdtemp(prefix="wdbin_")
        smi = ("#!/bin/sh\ncase \"$*\" in\n"
               "  'info -l') printf '\\tNPU ID : 0\\n\\tNPU ID : 1\\n';;\n"
               "  'info -t proc-mem -i 0') printf '\\tNPU ID : 0\\n\\n\\tProcess id:77 Process name:python3 Process memory(MB):9000\\n\\tChip ID : 0\\n';;\n"
               "  'info -t proc-mem -i 1') printf '\\tNPU ID : 1\\n\\n\\tNo process in device.\\n\\tChip ID : 0\\n';;\n"
               "  'info') cat %s;;\nesac\n")
        fx = os.path.join(d, "smi.txt")
        with open(fx, "w") as f:
            f.write(smi_text([(0, 70, 20000), (1, 0, 3450)], [(0, 77, 9000)]))
        for name, body in (("npu-smi", smi % fx), ("ps", "#!/bin/sh\necho '77 python3 train.py --out %s/runs/a'\n" % d)):
            with open(os.path.join(d, name), "w") as f:
                f.write(body)
            os.chmod(os.path.join(d, name), 0o755)
        if ssh_rc is not None:
            with open(os.path.join(d, "ssh"), "w") as f:
                f.write("#!/bin/sh\necho 'ssh: connect to host npu port 22: No route to host' >&2\nexit %d\n" % ssh_rc)
            os.chmod(os.path.join(d, "ssh"), 0o755)
        return d

    def run_with_path(self, d, fn):
        old = os.environ["PATH"]
        os.environ["PATH"] = d + os.pathsep + old
        try:
            return fn()
        finally:
            os.environ["PATH"] = old

    def test_local_probe_end_to_end_with_a_fake_npu_smi(self):
        d = self.bin_dir()
        cfg = wd.make_cfg(npu_host="local", npu_samples=2, npu_sample_gap=0.0)
        raw = self.run_with_path(d, lambda: wd.probe_npu(cfg))
        self.assertTrue(raw["ok"], raw)
        self.assertEqual((len(raw["samples"]), sorted(raw["procmem"]), raw["procmem"][1], raw["ps"][77].split()[0]), (2, [0, 1], [], "python3"))
        n = wd.analyse_npu(raw, [{"id": "a", "path": d + "/runs/a", "state": "running"}], [], cfg, {})
        self.assertEqual([(c["npu"], c["state"], c["claimed_by"]) for c in n["chips"]], [(0, "busy", ["a"]), (1, "unclaimed", [])])

    def test_ssh_failure_is_non_fatal_and_the_rest_of_the_digest_is_intact(self):
        d = self.bin_dir(ssh_rc=255)
        t = Tree()
        t.run("a_failed", heartbeat=hb_line(-50, "alive"), marker="rc=3 utc=x")
        cfg = t.cfg(npu_host="npu", no_npu=False)
        dg, md = self.run_with_path(d, lambda: wd.run_once(cfg, {}, NOW, npu=True))
        self.assertFalse(dg["npu"]["available"])
        self.assertIn("ssh/npu-smi failed (rc 255)", dg["npu"]["reason"])
        self.assertIn("npu n/a", md)
        self.assertIn("NPU utilisation unavailable", md)
        self.assertIn("| a_failed | failed", md)
        self.assertEqual(dg["exit_code"], 40)

    def test_timeout_and_unparseable_output_are_reasons(self):
        d = self.bin_dir()
        with open(os.path.join(d, "npu-smi"), "w") as f:
            f.write("#!/bin/sh\nsleep 5\n")
        cfg = wd.make_cfg(npu_host="local", npu_timeout=0.5, npu_samples=1)
        self.assertIn("timed out", self.run_with_path(d, lambda: wd.probe_npu(cfg))["reason"])
        with open(os.path.join(d, "npu-smi"), "w") as f:
            f.write("#!/bin/sh\necho 'npu-smi: command went wrong'\n")
        raw = self.run_with_path(d, lambda: wd.probe_npu(wd.make_cfg(npu_host="local", npu_samples=1)))
        self.assertFalse(raw["ok"])
        self.assertIn("no chips parsed", raw["reason"])

    def test_no_npu_flag_and_environment_variable_disable_the_probe(self):
        t = Tree()
        t.run("a", heartbeat=hb_line(-50, "alive"), marker="rc=0")
        dg, md = wd.run_once(t.cfg(no_npu=True), {}, NOW, npu=True)
        self.assertNotIn("npu", dg)
        self.assertNotIn("npu", md.splitlines()[1])
        self.assertTrue(wd.make_cfg().no_npu)                     # the test module sets WATCHDOG_NO_NPU=1
        old = os.environ.pop("WATCHDOG_NO_NPU")
        try:
            self.assertFalse(wd.make_cfg().no_npu)
            os.environ["WATCHDOG_NO_NPU"] = "0"
            self.assertFalse(wd.make_cfg().no_npu)
        finally:
            os.environ["WATCHDOG_NO_NPU"] = old

    def test_cli_one_shot_writes_the_npu_block(self):
        d = self.bin_dir()
        t = Tree()
        t.run("a_run", heartbeat=hb_line(-30, "alive"))
        out = os.path.join(t.tmp.name, "o")
        env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"])
        env.pop("WATCHDOG_NO_NPU")
        r = subprocess.run([sys.executable] + PFLAG + [os.path.join(HERE, "watchdog.py"), "--root", t.root, "--out-dir", out, "--npu-host", "local",
                                                       "--npu-samples", "1"], capture_output=True, text=True, timeout=60, env=env)
        self.assertIn(r.returncode, (0, 10, 20, 30), r.stderr)
        with open(os.path.join(out, "digest.json")) as f:
            dg = json.load(f)
        self.assertTrue(dg["npu"]["available"])
        self.assertEqual(dg["npu"]["unclaimed"], [1])
        self.assertIn("UNCLAIMED 1", open(os.path.join(out, "digest.md")).read().splitlines()[1])

    def test_queued_directory_counts_as_work_and_is_listed(self):
        t = Tree()
        q = os.path.join(t.root, "waiting")
        os.makedirs(q)
        open(os.path.join(q, "QUEUED"), "w").close()
        s = os.path.join(t.root, "started")
        os.makedirs(s)
        open(os.path.join(s, "QUEUED"), "w").close()
        with open(os.path.join(s, "heartbeat.log"), "w") as f:
            f.write(hb_line(-30, "alive"))
        dg = t.digest()
        self.assertEqual(dg["queued"], ["waiting"])                 # a heartbeat means it started
        self.assertEqual([r["id"] for r in dg["runs"]], ["started"])

    def _dg(self, t, flags=True):
        cfg = t.cfg()
        dg = wd.build_digest(cfg, {}, NOW)
        raw = raw_probe([(0, 80, 20000), (1, 0, 3450), (2, 0, 3450)] if flags else [(0, 80, 20000)],
                        procmem={0: [{"pid": 1, "name": "python3", "mem_mb": 9000}]}, procs=[(0, 1, 9000)])
        dg["npu"] = wd.analyse_npu(raw, dg["runs"], dg["queued"], cfg, {})
        return cfg, dg

    def test_digest_md_carries_fragment_flag_line_and_table(self):
        t = Tree()
        t.run("a_run", heartbeat=hb_line(-60, "alive") + hb_line(-30, "alive"))
        cfg, dg = self._dg(t)
        md = wd.render_md(dg, cfg)
        self.assertIn("| npu UNCLAIMED 1,2 (1 run, 0 queued) of 3", md.splitlines()[1])
        self.assertIn("## Host utilisation", md)
        self.assertIn("- [decide] NPU UNCLAIMED", md)
        self.assertIn("| 1 | 0% | 3.4/64 | unclaimed | - |", md)
        self.assertEqual(dg["npu"]["escalation"], "decide")

    def test_host_block_outranks_warnings_and_ordinary_error_signatures_but_not_failed_run_errors(self):
        t = Tree()
        t.run("a_failed", heartbeat=hb_line(-50, "alive"), marker="rc=3 utc=x", log="Traceback\nValueError: boom\n")
        for i in range(8):
            t.run("e%02d" % i, heartbeat=hb_line(-60, "alive") + hb_line(-30, "alive"), log="RuntimeError: distinct%s problem\n" % ("abcdefgh"[i] * 6))
            t.run("w%02d" % i, heartbeat=hb_line(-60, "alive") + hb_line(-30, "alive"), log="UserWarning: distinct%s thing\n" % ("ijklmnop"[i] * 6))
        seen = []
        for cap in range(2400, 12000, 100):
            cfg, dg = self._dg(t)
            cfg.max_md_bytes = cap
            md = wd.render_md(dg, cfg)
            self.assertLessEqual(len(md.encode()), cap)
            self.assertIn("worst=failed", md)
            self.assertIn("| a_failed | failed", md)
            if "| chip |" in md:
                self.assertIn("ValueError: boom", md)     # the failed run's own error signature (priority 2) outlives the chip table
            seen.append(("RuntimeError: distinct" in md, "| chip |" in md, "WARN x" in md))
        for err, host, warn in seen:
            self.assertFalse(warn and not host)       # a warning never survives without the chip table
            self.assertFalse(err and not host)        # nor does an ordinary run's error signature
        self.assertTrue(any(h for _, h, _ in seen) and any(not h for _, h, _ in seen))

    def test_the_chip_table_fits_at_the_default_cap_when_signatures_are_clustered(self):
        t = Tree()
        for i in range(40):                                      # the same benign warning in 40 run directories, plus status rows
            d = t.run("r%02d" % i, heartbeat=hb_line(-60, "alive") + hb_line(-30, "alive"),
                      log="[W1030 04:01:%02d.084 NPUCachingAllocator.cpp:204] Warning: The current CANN and HDK(driver) versions require processing for 32 padding size\n" % i)
        cfg, dg = self._dg(t)
        self.assertEqual(cfg.max_md_bytes, 16000)
        md = wd.render_md(dg, cfg)
        self.assertEqual(md.count("32 padding size"), 1)
        self.assertIn("WARN x40 in 40 runs", md)
        self.assertIn("| chip |", md)
        self.assertNotIn("TRUNCATED", md)


class SignatureClusters(unittest.TestCase):
    LINE = "[W1030 04:01:%02d.084 NPUCachingAllocator.cpp:204] Warning: The current CANN and HDK(driver) versions require processing for 32 padding size\n"

    def test_identical_signatures_are_one_entry_across_runs(self):
        t = Tree()
        for i in range(5):
            t.run("run%d" % i, heartbeat=hb_line(-1, "alive"), log="started\n" + self.LINE % (10 + i) + self.LINE % (20 + i))
        t.run("other", heartbeat=hb_line(-1, "alive"), log="ValueError: something else\n")
        dg = t.digest()
        cl = dg["signature_clusters"]
        self.assertEqual([c["severity"] for c in cl], ["error", "warning"])          # errors first
        w = cl[1]
        self.assertEqual((w["count"], w["n_runs"], len(w["runs"]), w["runs_omitted"]), (10, 5, 5, 0))
        self.assertEqual(sorted(x["id"] for x in w["runs"]), ["run%d" % i for i in range(5)])
        self.assertTrue(all(x["log"].endswith("run.log") and x["line_end"] >= x["line_start"] for x in w["runs"]))
        md = wd.render_md(dg, t.cfg())
        self.assertEqual(md.count("32 padding size"), 1)                              # one entry, not five
        self.assertIn("WARN x10 in 5 runs", md)
        self.assertIn("(+2 more runs: pointers in digest.json signature_clusters)", md)     # three pointers shown
        self.assertIn("ERR x1 in 1 run ", md)
        for r in dg["runs"]:
            if r["id"] != "other":
                self.assertEqual(r["errors"]["signatures"][0]["count"], 2)             # per-run detail is unchanged

    def test_run_list_is_bounded_but_counted(self):
        t = Tree()
        for i in range(wd.CLUSTER_MAX_RUNS + 7):
            t.run("r%03d" % i, heartbeat=hb_line(-1, "alive"), log="ValueError: same everywhere\n")
        c = t.digest()["signature_clusters"][0]
        self.assertEqual((c["n_runs"], len(c["runs"]), c["runs_omitted"], c["count"]), (wd.CLUSTER_MAX_RUNS + 7, wd.CLUSTER_MAX_RUNS, 7, wd.CLUSTER_MAX_RUNS + 7))

    def test_distinct_signatures_stay_distinct_and_failed_run_errors_keep_priority_two(self):
        t = Tree()
        t.run("a_failed", heartbeat=hb_line(-1, "alive"), marker="rc=1", log="ValueError: boom in failed\n")
        for i in range(3):
            t.run("b%d" % i, heartbeat=hb_line(-1, "alive"), log="ValueError: boom in ok run %s\n" % ("xyz"[i] * 3))
        cfg = t.cfg()
        blocks = wd.build_blocks(wd.build_digest(cfg, {}, NOW), cfg)
        prios = {b[3][0].split('"')[1]: b[0] for b in blocks if b[2] == "error signatures"}
        self.assertEqual(prios["ValueError: boom in failed"], 2)
        self.assertEqual({v for k, v in prios.items() if "ok run" in k}, {4})
        host_free = [b for b in blocks if b[2] == "warning signatures"]
        self.assertEqual(host_free, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
