"""Registered training entry point for an image integrator; no user code loading."""
import argparse
import json
from pathlib import Path
import training

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate configuration key: ' + key)
        result[key] = value
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    with Path(args.config).open() as f: config = json.load(f, object_pairs_hook=unique)
    if "recipe_id" in config:
        import family
        result = family.run(config, args.output)
    else:
        result = training.run(config, args.output)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__': main()
