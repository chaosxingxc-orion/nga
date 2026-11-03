import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import copy
import io
import urllib.error

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).with_name('collaboration_bridge.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class Tests(unittest.TestCase):
    def test_gitcode_draft_title_does_not_create_an_update_loop(self):
        self.assertTrue(b.matches_title({'title': '[WIP]generated', 'draft': True}, 'generated'))
        self.assertTrue(b.matches_title({'title': 'generated'}, 'generated'))
        self.assertFalse(b.matches_title({'title': 'changed', 'draft': True}, 'generated'))

    def test_api_and_pagination(self):
        api = b.API(b.GH, 'test-not-a-token')
        response = io.BytesIO(b'{"ok":true}')
        with patch.object(b.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            self.assertEqual({'ok': True}, api.call('/issues', 'POST', {'title': 'test'}))
        with self.assertRaises(ValueError):
            api.call('https://foreign.example')
        with patch.object(api, 'call', side_effect=[[{}] * 100, [{'last': 1}]]):
            self.assertEqual(101, len(api.pages('/issues?state=all')))
        with patch.object(api, 'call', return_value={}):
            with self.assertRaises(RuntimeError):
                api.pages('/issues')
        with patch.object(b.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = urllib.error.HTTPError('url', 403, 'denied', {}, None)
            with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
                api.call('/issues')

    def test_transfer_rechecks_head_and_never_forces(self):
        sha = 'a' * 40
        with patch.object(b, 'git', side_effect=['', '', sha, '']) as git:
            b.transfer(b.GC_GIT, b.GH_GIT, 'refs/merge-requests/1/head', 'gitcode/mr-1', sha)
            self.assertEqual(('push', b.GH_GIT, sha + ':refs/heads/gitcode/mr-1'), git.call_args.args)
        with patch.object(b, 'git', side_effect=['', '', 'b'*40]):
            with self.assertRaisesRegex(RuntimeError, 'Source head changed'):
                b.transfer(b.GC_GIT, b.GH_GIT, 'ref', 'gitcode/mr-1', sha)
        with self.assertRaises(ValueError):
            b.transfer('src', 'dst', 'ref', 'main', sha)

    def test_end_to_end_reconciliation_both_directions(self):
        gh, gc = FakeAPI('gh'), FakeAPI('gc')
        with patch.object(b, 'transfer') as transfer:
            b.reconcile(gh, gc)
            self.assertEqual(2, transfer.call_count)
            self.assertEqual(2, len(gh.pulls))
            self.assertEqual(2, len(gc.pulls))
            before = (copy.deepcopy(gh.comments), copy.deepcopy(gc.comments))
            b.reconcile(gh, gc)
            self.assertEqual(before, (gh.comments, gc.comments))
            self.assertEqual(2, transfer.call_count)
            gc.pulls[0]['body'] = 'edited description'
            gc.comments['pulls/1'][0]['body'] = 'edited discussion'
            gh.pulls[0]['title'] = 'edited title'
            gc.issues[0]['title'] = 'edited issue'
            b.reconcile(gh, gc)
            self.assertIn('edited description', gh.pulls[1]['body'])
            self.assertTrue(any('edited discussion' in x['body'] for x in gh.comments['issues/10']))

    def test_failed_import_continues_other_work_and_fails_run(self):
        gh, gc = FakeAPI('gh'), FakeAPI('gc')
        with patch.object(b, 'transfer', side_effect=RuntimeError('divergent')):
            with self.assertRaisesRegex(RuntimeError, 'divergent'):
                b.reconcile(gh, gc)
        self.assertEqual(2, len(gh.issues))

    def test_comment_idempotence_edit_and_loop(self):
        src = [{'id': 7, 'body': 'hello', 'user': {'login': 'expert'}}]
        target = []
        changes = b.comment_changes(src, target, 'gc', 'pulls/2', 'https://gitcode.com/xingchao_ml/nga/pull/2')
        self.assertEqual(len(changes), 1)
        target = [{'id': 9, 'body': changes[0][1]}]
        self.assertEqual([], b.comment_changes(src, target, 'gc', 'pulls/2', 'https://gitcode.com/xingchao_ml/nga/pull/2'))
        src[0]['body'] = 'edited'
        self.assertEqual(9, b.comment_changes(src, target, 'gc', 'pulls/2', 'https://gitcode.com/xingchao_ml/nga/pull/2')[0][0])
        self.assertEqual([], b.comment_changes(target, [], 'gh', 'issues/3', 'url'))

    def test_source_ids_do_not_collide(self):
        src = [{'id': 7, 'body': 'text'}]
        a = b.comment_changes(src, [], 'gc', 'pulls/1', 'url')[0][1]
        c = b.comment_changes(src, [], 'gc', 'issues/1', 'url')[0][1]
        self.assertNotEqual(a, c)

    def test_inline_keeps_location(self):
        src = [{'id': 8, 'body': 'fix', 'path': 'a.py', 'line': 42, 'commit_id': 'abc'}]
        body = b.comment_changes(src, [], 'gh-review', 'pulls/1', 'url')[0][1]
        self.assertIn('a.py', body)
        self.assertIn('42', body)
        self.assertIn('abc', body)

    def test_invalid_branch_id(self):
        with self.assertRaises(ValueError):
            b.number('1; echo bad')

    def test_ref_policy(self):
        self.assertTrue(b.managed_branch('gitcode/mr-2'))
        self.assertTrue(b.managed_branch('github/pr-3'))
        self.assertFalse(b.managed_branch('main'))
        self.assertFalse(b.managed_branch('gitcode/mr-2/../../main'))


class FakeAPI:
    def __init__(self, platform):
        self.platform = platform
        self.pulls = [self.obj(1, 'native-feature')]
        self.issues = [self.obj(1)]
        family = 'issues' if platform == 'gh' else 'pulls'
        self.comments = {family + '/1': [{'id': 1, 'body': 'native comment', 'user': {'login': platform}}]}

    def obj(self, n, head=None):
        obj = {'number': n, 'title': 'title', 'body': 'source text', 'state': 'open', 'html_url': 'https://example.invalid/' + str(n)}
        if head:
            obj['head'] = {'ref': head, 'sha': 'a' * 40}
        return obj

    def pages(self, path):
        path = path.split('?')[0].strip('/')
        if path == 'pulls':
            return copy.deepcopy(self.pulls)
        if path == 'issues':
            return copy.deepcopy(self.issues)
        if path.endswith('/reviews'):
            return [{'id': 99, 'body': 'review summary'}]
        if path.endswith('/comments'):
            return copy.deepcopy(self.comments.get(path[:-9], []))
        raise AssertionError(path)

    def call(self, path, method='GET', data=None):
        bits = path.strip('/').split('/')
        if method == 'GET':
            objects = self.pulls if bits[0] == 'pulls' else self.issues
            return copy.deepcopy(next(x for x in objects if x['number'] == int(bits[1])))
        if method == 'POST' and bits[-1] == 'comments':
            key = '/'.join(bits[:-1])
            items = self.comments.setdefault(key, [])
            item = {'id': 100 + sum(len(x) for x in self.comments.values()), **data}
            items.append(item)
            return copy.deepcopy(item)
        if method == 'PATCH' and bits[1] == 'comments':
            for items in self.comments.values():
                for item in items:
                    if item['id'] == int(bits[2]):
                        item.update(data)
                        return copy.deepcopy(item)
            raise AssertionError(path)
        objects = self.pulls if bits[0] == 'pulls' else self.issues
        if method == 'POST':
            obj = self.obj(10 + len(objects) - 1, data.get('head'))
            obj.update({k:v for k,v in data.items() if k != 'head'})
            objects.append(obj)
            return copy.deepcopy(obj)
        obj = next(x for x in objects if x['number'] == int(bits[1]))
        obj.update(data)
        return copy.deepcopy(obj)


if __name__ == '__main__':
    unittest.main()
