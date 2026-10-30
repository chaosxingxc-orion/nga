"""Exercise the mirror against disposable local Git repositories."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("sync_gitcode", Path(__file__).with_name("sync_gitcode.py"))
mirror = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mirror)


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="nga-mirror-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = str(self.root / "source")
        self.target = str(self.root / "target.git")
        mirror.git("init", "--initial-branch=main", self.source)
        mirror.git("init", "--bare", "--initial-branch=main", self.target)
        self.commit("first")

    def commit(self, text):
        Path(self.source, "README.md").write_text(text, encoding="utf-8")
        mirror.git("add", "README.md", cwd=self.source)
        mirror.git("-c", "user.name=Mirror Test", "-c", "user.email=test@example.invalid",
                   "commit", "-m", text, cwd=self.source)
        return mirror.git("rev-parse", "HEAD", cwd=self.source)

    def sync(self):
        return mirror.sync_once(self.source, self.target)

    def assert_equal_refs(self):
        self.assertEqual(mirror.remote_refs(self.source), mirror.remote_refs(self.target))

    def test_full_history_branches_and_annotated_tags(self):
        self.commit("second")
        mirror.git("branch", "feature", cwd=self.source)
        mirror.git("-c", "user.name=Mirror Test", "-c", "user.email=test@example.invalid",
                   "tag", "-a", "v1", "-m", "Version one", cwd=self.source)
        mirror.git("update-ref", "refs/pull/1/head", "HEAD", cwd=self.source)
        refs, changes = self.sync()
        self.assertEqual(3, len(refs))
        self.assertEqual(3, changes)
        self.assert_equal_refs()
        self.assertEqual("2", mirror.git("rev-list", "--count", "main", cwd=self.target))
        self.assertEqual("tag", mirror.git("cat-file", "-t", "v1", cwd=self.target))
        self.assertEqual("", mirror.git("for-each-ref", "refs/pull/", cwd=self.target))

    def test_repeated_sync_is_a_noop(self):
        self.sync()
        refs, changes = self.sync()
        self.assertEqual(0, changes)
        self.assertEqual(mirror.remote_refs(self.target), refs)

    def test_updates_force_updates_and_deletions(self):
        first = mirror.git("rev-parse", "HEAD", cwd=self.source)
        mirror.git("branch", "obsolete", cwd=self.source)
        mirror.git("tag", "old", cwd=self.source)
        self.sync()
        self.commit("new content")
        mirror.git("branch", "new-feature", cwd=self.source)
        mirror.git("branch", "-D", "obsolete", cwd=self.source)
        mirror.git("tag", "-d", "old", cwd=self.source)
        self.sync()
        self.assert_equal_refs()
        self.assertEqual("new content", mirror.git("show", "main:README.md", cwd=self.target))
        mirror.git("update-ref", "refs/heads/main", first, cwd=self.source)
        self.sync()
        self.assert_equal_refs()

    def test_initial_destination_commit_is_replaced(self):
        other = str(self.root / "bootstrap")
        mirror.git("init", "--initial-branch=main", other)
        mirror.git("-c", "user.name=Mirror Test", "-c", "user.email=test@example.invalid",
                   "commit", "--allow-empty", "-m", "Initial commit", cwd=other)
        mirror.git("push", self.target, "main", cwd=other)
        self.sync()
        self.assert_equal_refs()

    def test_concurrent_destination_change_rejects_entire_push(self):
        first = mirror.git("rev-parse", "HEAD", cwd=self.source)
        self.sync()
        second = self.commit("second")
        mirror.git("push", self.target, "main", cwd=self.source)
        before = mirror.remote_refs(self.target)
        self.commit("third")
        mirror.git("branch", "new-feature", cwd=self.source)
        leases, refspecs = mirror.push_arguments(mirror.remote_refs(self.source), before)
        # An independent writer changes main after we have observed the target.
        mirror.git("update-ref", "refs/heads/main", first, second, cwd=self.target)
        with self.assertRaises(subprocess.CalledProcessError):
            mirror.git("push", "--atomic", *leases, self.target, *refspecs, cwd=self.source)
        self.assertEqual({"refs/heads/main": first}, mirror.remote_refs(self.target))

    def test_missing_source_main_does_not_delete_destination(self):
        self.sync()
        before = mirror.remote_refs(self.target)
        mirror.git("branch", "-m", "main", "renamed", cwd=self.source)
        with self.assertRaisesRegex(RuntimeError, "Source main is missing"):
            self.sync()
        self.assertEqual(before, mirror.remote_refs(self.target))


if __name__ == "__main__":
    unittest.main()
