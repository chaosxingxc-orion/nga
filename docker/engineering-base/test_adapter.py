import json, pathlib, subprocess
p=pathlib.Path(__file__).parent
assert json.loads(subprocess.check_output(['python3','-m','json.tool',str(p/'schema.json')]))
print('schema-json-ok')
