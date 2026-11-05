# Local CPU development environment

Install and verify the dependencies used by local numerical and fixture tests:

```sh
bash tools/bootstrap_local_cpu.sh
python3 -m pytest
```

The bootstrap is repeatable. It installs into the current user's default Python
environment, or into an already activated virtual environment. Set
`NGA_LOCAL_PYTHON=/absolute/path/to/python` to select another interpreter and use
that same interpreter to run tests. Direct dependencies are pinned in
`requirements-local-cpu.txt`; this is not a complete transitive release lock.

Required missing development dependencies should be installed and the failed
check retried immediately. Record reusable dependencies here rather than
repeatedly treating an import failure as an external blocker. Use `python -m pip`
and `python -m pytest` to avoid installing for a different interpreter.

`python3 -I` hides user-installed packages. For these local tests use ordinary
Python, or `python3 -P` with an explicit test path. If isolated mode is required,
install the requirements into a virtual environment and invoke its interpreter.

This environment supports CPU fixtures and analysis. Ascend runtime dependencies
belong in the versioned Docker image. Local fixture success does not qualify NPU
inference or training, and a container import failure must be repaired inside
its own build/runtime environment.
