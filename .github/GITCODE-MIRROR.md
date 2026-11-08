# GitHub / GitCode collaboration

> Repository split, 2026-11-08: this pair now owns Jev-class model research.
> Architecture work continues in [Agent Hub Alpha](https://github.com/chaosxingxc-orion/agent-hub-alpha)
> and [its GitCode counterpart](https://gitcode.com/xingchao_ml/agent-hub-alpha).
> Old architecture Issue/MR links below are historical. The synchronization
> mechanism remains scoped to NGA; it does not mirror the projects into each other.

## Current collaboration entry points

| Purpose | GitHub | GitCode |
| --- | --- | --- |
| Current expert implementation | [PR #2](https://github.com/chaosxingxc-orion/nga/pull/2) | [MR #2](https://gitcode.com/xingchao_ml/nga/merge_requests/2) |
| Earlier implementation and architecture replies | [PR #3](https://github.com/chaosxingxc-orion/nga/pull/3) | [MR #1](https://gitcode.com/xingchao_ml/nga/merge_requests/1) |
| Architecture discussion | [Issue #1](https://github.com/chaosxingxc-orion/nga/issues/1) | [Issue #1](https://gitcode.com/xingchao_ml/nga/issues/1) |

Use ordinary comments on either linked object. The counterpart will retain your
name and source link. The two expert requests remain drafts on GitHub until
maintainers finish their review; synchronization is not implementation acceptance.

GitHub `chaosxingxc-orion/nga` is the final integration repository. Both teams can
develop, open requests and discuss changes on their own platform. GitCode
`xingchao_ml/nga` is no longer a destructive mirror.

## Code and request ownership

- GitHub `main`, `github/**` branches and `v*` tags synchronize to GitCode with
  ordinary fast-forward / new-tag pushes only. Divergence fails visibly.
- No branch or tag is automatically deleted. Existing tags are never replaced.
- GitCode MRs import original commit IDs into GitHub `gitcode/mr-N`.
  GitHub-native PRs project to GitCode `github/pr-N`. These namespaces are
  bridge-owned; developers work on source branches or forks.
- Counterpart requests start as drafts. The bridge never merges or approves them.
  Final integration is on GitHub. A GitCode receipt reports GitHub status/head;
  it does not falsely mark a GitCode request as merged.
- Source rebases stop at the non-fast-forward check. Resolve deliberately while
  preserving previous review history; do not enable unconditional force pushes.
- MR #2 includes MR #1. Use #2 for current integration review; retain #1's
  discussion and avoid independently squash-merging both requests.

## Discussions

Source titles/descriptions/status are maintained in generated counterparts.
Ordinary comments synchronize both ways with author, timestamp and source link.
Edits update copies; deletions do not propagate. GitHub inline comments retain
path/position/commit as ordinary GitCode comments. Review summaries never become
approvals. Reserved `nga-bridge` markers prevent bounce loops and support recovery
after interrupted writes. Do not remove markers or hand-edit generated bodies;
write a new ordinary comment. Never put credentials in a discussion.

## Automation

Workflow: `.github/workflows/sync-gitcode.yml`. GitHub events trigger runs.
GitCode changes are discovered by a five-minute scheduled reconciliation.
GitHub can delay schedules: this is eventual sync, not a five-minute SLA.
Use Run workflow for immediate catch-up. Runs are serialized; failures are
visible in Actions and later runs retry from current platform state.
Notification delivery follows GitHub user settings.

The owner selected polling because no public webhook receiver is available.
`repository_dispatch: gitcode-collaboration` is reserved for a later authenticated
receiver; no GitCode webhook is configured. The receiver must validate provider
credentials and repository/event scope, deduplicate deliveries, then authenticate
separately to GitHub.

Existing `GITCODE_TOKEN` needs repository/code/discussion access. GitHub uses its
per-run token with contents/issues/PR write and the repository setting permitting
workflow-created PRs. Secrets are available only to trusted-main synchronization.
Imported refs are fetched into temporary bare repositories: never checked out,
executed or used as workflow scripts.

## Recovery and limits

Inspect failed runs, correct expired credentials or divergent refs, then rerun.
GitHub's per-run token cannot introduce historical workflow-file changes. For
such an initial import, a maintainer with workflow permission must first push the
verified source SHA to the reserved counterpart branch, then rerun reconciliation.
This was required for the initial MR #1/#2 imports. Subsequent ordinary updates
use the existing automated token; no personal credential was stored in Actions.
Do not start a competing reverse full mirror. Labels, assignees, milestones,
approval votes, attachments, releases and LFS objects are outside this bridge.
Closed states are reported; closing a request never authorizes an automatic merge
or deletion on the other platform.
