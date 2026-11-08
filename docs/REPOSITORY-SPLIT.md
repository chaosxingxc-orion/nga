# Repository split — 2026-11-08

The owner requested that NGA retain Jev-class model research and move framework/architecture work to Agent Hub Alpha, with matching GitHub and GitCode repositories.

- Model research: https://github.com/chaosxingxc-orion/nga and https://gitcode.com/xingchao_ml/nga
- Architecture research: https://github.com/chaosxingxc-orion/agent-hub-alpha and https://gitcode.com/xingchao_ml/agent-hub-alpha

The import is based on NGA `fad91b05b70805a7f4b3910c6f355dc79c700d95`, which integrated GitCode MR #4 (`25ab91e`) and its MR #2 ancestor with scoped acceptance. Destination commit `2e47d938e6a663afc02de34760e4e47341898a19` preserves code blobs and executable modes. See the [source manifest](https://github.com/chaosxingxc-orion/agent-hub-alpha/blob/main/docs/migration/nga-source-manifest.json). Original commits and discussions remain in NGA history; this is not a history rewrite.

Moved roots: achitecture design/, design/, agent-festival/, impl-2026-10-31/, impl-2026-11-01/, replies/.

Retained model dependencies: survey/, proposal/, experiments/, tools/, wiki/, configs/, docker/, tests/, experiment onboarding and local-review records. KEV/BEV and other named variants are part of Jev-class research. Existing preregistrations, training files and server jobs are unaffected.

Both projects keep their own synchronization infrastructure. GitHub is the integration endpoint; GitCode is polled periodically and receives attributed discussions and safe branch updates. There is no cross-project full mirror. Old architecture Issue #1 and MRs stay as historical evidence; new discussion continues at [Agent Hub Alpha Issue #1](https://github.com/chaosxingxc-orion/agent-hub-alpha/issues/1).

Start new framework branches from Agent Hub Alpha main. Do not merge old NGA main into it; port only intended architecture-path changes with source commit references.
