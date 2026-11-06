# RC1 async TEST source preservation

This directory preserves the accepted RC1 async TEST production Python source, byte for byte, in its candidate-relative layout. `SOURCE-PINS.json` records the source hashes and the two local acceptance records. The earlier source-delta review was conditional; the later binding acceptance covers the finite integration and permits activation, while explicitly excluding scientific acceptance. This copy is source preservation, not a new release version or a deployment claim.

The original production paths, external modules, fixed RC1 configuration and source/data bindings remain explicit in the code. This directory alone is not a runnable deployment; it does not include those dependencies, configurations, generated inputs or results. In particular, existing pinned configurations refer to their original absolute paths and do not automatically use this copy.

For an existing CPU fixture, from the repository root in the original environment run:

```sh
python3 -P .local/releases/engineering-base-rc1/tasks/execution/test-final-host-overlap/fixture/test_overlap.py
```

This fixture imports the original local candidate, whose reviewed source bytes are recorded in `SOURCE-PINS.json`; it does not import this preserved copy. It needs the original `.local` task fixtures and fixed host-stage dependencies and writes fixture evidence under its task directory. Those local paths and generated inputs are not repository artifacts. The fixture simulates device operations and checks overlap and refusal behavior; it is not a live NPU or scientific test. Its prior result and source pins are in `.local/releases/engineering-base-rc1/tasks/execution/test-final-host-overlap/RESULT.json`. Verify the preserved hashes against the candidate before using that fixture as evidence for this copy.
