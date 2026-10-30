# GitCode mirror

The canonical repository is [GitHub](https://github.com/chaosxingxc-orion/nga).
[GitCode](https://gitcode.com/xingchao_ml/nga) is a one-way mirror. Make changes on
GitHub; changes made directly on GitCode can be replaced by synchronization.

## Synchronization contract

- GitHub pushes, branch/tag creation and deletion trigger the
  [Sync GitCode mirror workflow](https://github.com/chaosxingxc-orion/nga/actions/workflows/sync-gitcode.yml).
  A manual trigger is also available. A schedule at minutes 7, 22, 37 and 52 provides
  catch-up for missed events and transient failures.
- All branches, tags and reachable Git history are copied. Source ref rewrites and
  deletions are reflected on GitCode. Provider-internal refs are excluded.
- Runs are serialized. Each run fetches the latest source refs, applies changes
  with explicit destination leases and an atomic push, then checks exact ref
  equality against both repositories. A moving source or transient failure is
  retried up to three times. An unsupported atomic push fails rather than silently
  falling back to a partial update.
- This is event-driven eventual synchronization, not a zero-latency or bounded-time
  guarantee. Runner availability, network conditions, platform policies and token
  expiry affect delivery. A green run records the exact verified `main` commit;
  later source changes require another run.
- The scope is Git content. Issues, pull requests, repository settings, secrets,
  release attachments and external experiment/model data are not copied. No Git
  LFS objects were present at setup; add and verify LFS transfer before introducing
  LFS-managed data. Git submodule contents are separate repositories.

## Credential and first setup

1. In GitCode, create a personal access token with the permissions needed to push
   `xingchao_ml/nga`. Use the narrowest available repository access and an expiry
   compatible with the intended operation. See the
   [official PAT guide](https://docs.gitcode.com/docs/help/home/user_center/security_management/user_pat/).
2. Save it as **`GITCODE_TOKEN`** under GitHub repository Settings → Secrets and
   variables → Actions → Repository secrets. Do not put the token in chat, source
   files, remote URLs or command-line arguments.
3. Run the workflow manually and check its result. A GitCode branch protection rule
   may reject the initial replacement or later rewrites; inspect the rejection and
   adjust only the mirror repository's relevant rule if needed.

The initial GitCode repository contained only `README.md` (`# nga`) at commit
`bf926147db12bb78aade8fe4fc04221f730009ab`. Before replacing that initialization,
the setup workspace retained it at `refs/backup/gitcode-initial-main` and in
`.git/gitcode-initial-main.bundle`. These local recovery copies are not mirrored.

The workflow reads the GitCode token only from the encrypted GitHub secret and
passes it to Git through a host-specific temporary credential prompt helper. It
does not embed credentials in Git configuration. GitHub access is read-only, the
checkout action is pinned to a commit, and no pull-request trigger uses the secret.

## Operation and recovery

- Check the workflow's result and summary for the verified commit. A failed run is
  visible in GitHub Actions; personal notification delivery depends on the user's
  GitHub notification settings. The schedule provides another attempt, not an
  independent availability monitor.
- For expired or exposed credentials, revoke the old GitCode token, update the
  existing `GITCODE_TOKEN` secret and rerun the workflow.
- For authentication or branch-protection failures, fix that cause and rerun.
  Do not create a competing reverse mirror to work around a failure.
- To compare the current branch/tag tips independently:

  ```sh
  git ls-remote --refs https://github.com/chaosxingxc-orion/nga.git 'refs/heads/*' 'refs/tags/*'
  git ls-remote --refs https://gitcode.com/xingchao_ml/nga.git 'refs/heads/*' 'refs/tags/*'
  ```

- To pause synchronization, disable the workflow in GitHub Actions. This does not
  delete GitCode content. Public-repository scheduled workflows may be disabled
  after inactivity, so review workflow status when resuming work.

References: [Git push leases and atomic updates](https://git-scm.com/docs/git-push),
[GitHub workflow events and scheduling limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
