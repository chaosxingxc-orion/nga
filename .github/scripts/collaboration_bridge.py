"""NGA collaboration bridge. Never merge, approve, delete, or execute imported code."""
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

GH = 'https://api.github.com/repos/chaosxingxc-orion/nga'
GC = 'https://api.gitcode.com/api/v5/repos/xingchao_ml/nga'
GH_GIT = 'https://github.com/chaosxingxc-orion/nga.git'
GC_GIT = 'https://gitcode.com/xingchao_ml/nga.git'
MARK = '<!-- nga-bridge:'


def number(value):
    if not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError('Invalid object number')
    return int(value)


def managed_branch(value):
    return bool(re.fullmatch(r'(gitcode/mr-|github/pr-)[1-9][0-9]*', value))


def marker(key):
    return f'{MARK}{key} -->'


def matches_title(obj, title):
    actual = obj.get('title') or ''
    if obj.get('draft') and actual.startswith('[WIP]'):
        actual = actual[5:]
    return actual == title


def origin_body(key, obj, url):
    status = 'merged' if obj.get('merged_at') else obj.get('state', 'open')
    return (f'{marker(key)}\nSource: {url}\nSource status: {status}\n'
            f'Source head: {obj.get("head", {}).get("sha", "n/a")}\n\n'
            'Synchronized review copy. Final integration is on GitHub; '
            'copied reviews are attributed discussion, not approval.\n\n' + (obj.get('body') or ''))


def comment_changes(source, target, platform, context, url):
    existing = {(x.get('body') or '').split('\n')[0]: x for x in target}
    changes = []
    for c in source:
        body = c.get('body') or ''
        if not body.strip() or body.startswith(MARK):
            continue
        tag = marker(f'{platform}:{context}:comment:{c["id"]}')
        author = c.get('user', {}).get('login', 'unknown')
        link = c.get('html_url') or url
        location = ''
        if c.get('path'):
            location = (f'\nOriginal location: `{c["path"]}`; line/position '
                        f'{c.get("line") or c.get("position") or c.get("original_line")}; '
                        f'commit `{c.get("commit_id") or c.get("original_commit_id") or "see source"}`.\n')
        text = f'{tag}\nFrom {platform} · {author} · {c.get("created_at", "")} · [source]({link}){location}\n\n{body}'
        old = existing.get(tag)
        if not old or old.get('body') != text:
            changes.append((old['id'] if old else None, text))
    return changes


class API:
    def __init__(self, base, token):
        self.base, self.token = base, token

    def call(self, path, method='GET', data=None):
        if not path.startswith('/') or '://' in path:
            raise ValueError('API path must remain in the configured repository')
        raw = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.base + path, data=raw, method=method,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json',
                     'Content-Type': 'application/json', 'User-Agent': 'nga-collaboration-bridge'})
        # Do not follow redirects carrying a credential to another origin.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=45) as response:
                content = response.read()
                result = json.loads(content) if content else None
                if isinstance(result, dict) and result.get('error'):
                    raise RuntimeError(f'API rejected {method} {path}')
                return result
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'API {method} {path}: HTTP {exc.code}') from None

    def pages(self, path):
        result = []
        for page in range(1, 1001):
            data = self.call(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            if not isinstance(data, list):
                raise RuntimeError('Expected paginated list')
            result.extend(data)
            if len(data) < 100:
                return result
        raise RuntimeError('Pagination limit exceeded')


def git(*args, cwd):
    result = subprocess.run(['git', '-c', 'credential.helper=', *args], cwd=cwd,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Git operation failed (no force updates permitted): ' + result.stderr[-1500:])
    return result.stdout.strip()


def transfer(source, target, ref, branch, sha):
    if not managed_branch(branch) or not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid bridge ref')
    with tempfile.TemporaryDirectory(prefix='nga-bridge-') as tmp:
        git('init', '--bare', '.', cwd=tmp)
        git('fetch', '--no-tags', source, ref, cwd=tmp)
        actual = git('rev-parse', 'FETCH_HEAD', cwd=tmp)
        if actual != sha:
            raise RuntimeError('Source head changed during import; retry next reconciliation')
        git('push', target, f'{sha}:refs/heads/{branch}', cwd=tmp)


def upsert_comments(api, family, n, changes):
    for ident, body in changes:
        if ident is None:
            api.call(f'/{family}/{n}/comments', 'POST', {'body': body})
        else:
            api.call(f'/{family}/comments/{ident}', 'PATCH', {'body': body})


def sync_discussion(gh, gc, gnum, cnum, family):
    gc_path = f'{family}/{cnum}'
    gh_path = f'issues/{gnum}'
    curl = f'https://gitcode.com/xingchao_ml/nga/{"pull" if family == "pulls" else "issues"}/{cnum}'
    gurl = f'https://github.com/chaosxingxc-orion/nga/{"pull" if family == "pulls" else "issues"}/{gnum}'
    cc = gc.pages(f'/{gc_path}/comments')
    hc = gh.pages(f'/{gh_path}/comments')
    upsert_comments(gh, 'issues', gnum, comment_changes(cc, hc, 'gc', gc_path, curl))
    upsert_comments(gc, family, cnum, comment_changes(hc, cc, 'gh', gh_path, gurl))
    if family == 'pulls':
        cc = gc.pages(f'/{gc_path}/comments')
        reviews = gh.pages(f'/pulls/{gnum}/comments')
        upsert_comments(gc, family, cnum, comment_changes(reviews, cc, 'gh-review', f'pulls/{gnum}', gurl))
        cc = gc.pages(f'/{gc_path}/comments')
        reviews = gh.pages(f'/pulls/{gnum}/reviews')
        upsert_comments(gc, family, cnum, comment_changes(reviews, cc, 'gh-review-summary', f'pulls/{gnum}', gurl))
    # Status is an attributed receipt, never an approval or automatic merge.
    current = gh.call(f'/{"pulls" if family == "pulls" else "issues"}/{gnum}')
    state = 'merged' if current.get('merged_at') else current.get('state')
    tag = marker(f'link:github:{family}:{gnum}')
    receipt = f'{tag}\nGitHub collaboration: {gurl}\nStatus: {state}\nHead: {current.get("head", {}).get("sha", "n/a")}\nFinal integration is on GitHub. This message does not approve or merge the GitCode request.'
    existing = next((c for c in gc.pages(f'/{gc_path}/comments') if (c.get('body') or '').startswith(tag)), None)
    if not existing or existing.get('body') != receipt:
        upsert_comments(gc, family, cnum, [(existing['id'] if existing else None, receipt)])


def reconcile(gh, gc):
    hp = gh.pages('/pulls?state=all')
    cp = gc.pages('/pulls?state=all')
    failures = []
    for source, objects, targets in [('gc', cp, hp), ('gh', hp, cp)]:
        for obj in objects:
            # Counterpart branches never become new source requests.
            head = obj.get('head', {}).get('ref', '')
            if managed_branch(head):
                continue
            n = number(obj['number'])
            key = f'{source}:pull:{n}'
            dest = next((x for x in targets if (x.get('body') or '').startswith(marker(key))), None)
            if obj.get('state') != 'open' and dest is None:
                continue
            try:
                source_url = obj['html_url']
                body = origin_body(key, obj, source_url)
                title = f'[{"GitCode MR" if source == "gc" else "GitHub PR"} #{n}] {obj["title"]}'[:250]
                api = gh if source == 'gc' else gc
                branch = f'gitcode/mr-{n}' if source == 'gc' else f'github/pr-{n}'
                sha = obj['head']['sha']
                if dest is None or (dest.get('state') == 'open' and dest.get('head', {}).get('sha') != sha):
                    transfer(GC_GIT if source == 'gc' else GH_GIT, GH_GIT if source == 'gc' else GC_GIT,
                             f'refs/merge-requests/{n}/head' if source == 'gc' else f'refs/pull/{n}/head', branch, sha)
                if dest is None:
                    dest = api.call('/pulls', 'POST', {'title': title, 'body': body, 'head': branch, 'base': 'main', 'draft': True})
                    targets.append(dest)
                elif dest.get('body') != body or not matches_title(dest, title):
                    api.call(f'/pulls/{number(dest["number"])}', 'PATCH', {'title': title, 'body': body})
                gn, cn = (number(dest['number']), n) if source == 'gc' else (n, number(dest['number']))
                sync_discussion(gh, gc, gn, cn, 'pulls')
                print(f'Linked GitCode MR {cn} and GitHub PR {gn}; source {sha}')
            except Exception as exc:
                failures.append(f'{key}: {exc}')
    hi = [x for x in gh.pages('/issues?state=all') if 'pull_request' not in x]
    ci = gc.pages('/issues?state=all')
    for source, objects, targets in [('gc', ci, hi), ('gh', hi, ci)]:
        for obj in objects:
            if (obj.get('body') or '').startswith(MARK):
                continue
            n = number(obj['number'])
            key = f'{source}:issue:{n}'
            dest = next((x for x in targets if (x.get('body') or '').startswith(marker(key))), None)
            if obj.get('state') != 'open' and dest is None:
                continue
            try:
                body = origin_body(key, obj, obj['html_url'])
                title = f'[{"GitCode" if source == "gc" else "GitHub"} Issue #{n}] {obj["title"]}'[:250]
                api = gh if source == 'gc' else gc
                if dest is None:
                    dest = api.call('/issues', 'POST', {'title': title, 'body': body})
                    targets.append(dest)
                elif dest.get('body') != body or dest.get('title') != title:
                    api.call(f'/issues/{number(dest["number"])}', 'PATCH', {'title': title, 'body': body})
                gn, cn = (number(dest['number']), n) if source == 'gc' else (n, number(dest['number']))
                sync_discussion(gh, gc, gn, cn, 'issues')
                print(f'Linked GitCode Issue {cn} and GitHub Issue {gn}')
            except Exception as exc:
                failures.append(f'{key}: {exc}')
    if failures:
        raise RuntimeError('\n'.join(failures))


if __name__ == '__main__':
    reconcile(API(GH, os.environ['GH_TOKEN']), API(GC, os.environ['GITCODE_TOKEN']))
