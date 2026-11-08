# RC1 shared-prefix DEV192 option

This is the reviewed opt-in CPU entrypoint, frozen configuration, descriptor,
five numerical source files and four receipts. Review accepted the implementation
and synthetic CPU control-flow checks; external execution binding and deployment
remain pending. Rightpad is the default. This package does not launch a job.
The historical status text inside the frozen descriptor predates implementation
acceptance and is retained to preserve its hash.

From a fresh checkout, run this CPU-only synthetic configuration and dispatch
check with a new output directory (it reads no model or dataset):

```bash
opt="$PWD/docker/engineering-base/scoped_options/shared_prefix_dev192"
out="$(mktemp -d)/check"
CALLS="${out}.calls.json" /usr/bin/python3 -B -P "$opt/cpu_fixture_check.py" \
  "$opt/scoped_runner.py" --config "$opt/config.json" --output "$out" \
  --descriptor-sha256 3f1a5481a8ac5e6be11d2d0412de039c12322f8d9928804c21f0e0a4207256c0 \
  --budget-bytes 8589934592 --allowance-bytes 2147483648 \
  --per-row-extra 16777216 --max-rows 8 --scorer-layout shared_prefix \
  --scorer-option "$opt/option.json"
cat "$out/report.json"
```

An exit of 0 and status complete verify configuration, package hashes and
synthetic shared-prefix dispatch. Fixture scores and timing are synthetic and
are not numerical, equivalence, performance or device evidence.

The actual entrypoint is `scoped_runner.py` with the same arguments after
replacing the fixture invocation with `python3 -B -P "$opt/scoped_runner.py"`.
This is an interface description, not a ready host launcher. Before any real
execution the execution owner must bind host 175 physical chip 4 to logical 0,
the fixed RC1 image
`sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d`,
the exact model, unmerged seed 2 terminal 3116 adapter, DEV source and
accepted receipt provenance specified in the descriptor, plus the matching
source/import environment and a durable launcher. Use host
`/usr/bin/python3.12 -B -P` for host helpers; inside the fixed Ascend image
use `python3 -B -P` with CANN PYTHONPATH preserved. The code checks package
source and receipt hashes relative to the entrypoint. Descriptor absolute
paths are frozen provenance authorities, not rewritten checkout paths; bind
the accepted originals at those paths wherever provenance consumers require
them, or supply an independently reviewed relocation. Paths alone do not
establish asset identity. No full host launch is supplied or authorized here.

Scope is Qwen3.5-9B Base, DEV rows 33–96 and three transforms (192 conditions),
FP32/HF32 off, one chip, cap 8; results are not of record. No TEST, other
model, training, global default or automatic NPU adoption is implied.
The wrapper SHA256 is
`a7c571e5d459505a2ddf72c5520e7f235a6bae3410005fe792c94e2f334e3729`;
the descriptor canonical SHA256 is the value in the command above.
