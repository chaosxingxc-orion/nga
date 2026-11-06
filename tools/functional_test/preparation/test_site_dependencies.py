"""Configured subprocess suite supersedes stale chips-4 K0 callback fixture."""
import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parent/'test_callbacks_subprocess.py'
s=importlib.util.spec_from_file_location('callbacks_fixture',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
CallbackCLI=m.CallbackCLI
if __name__=='__main__':unittest.main(verbosity=2)
