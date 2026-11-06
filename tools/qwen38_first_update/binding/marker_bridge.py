"""Convert a phase marker to the existing controller's EXIT.json format.

Called by a future reviewed observer only after it has verified retained container
identity and terminal exit code. This script performs no allocation or launch.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path


def bridge(marker, output, observed_code):
    raw = Path(marker).read_text(encoding='ascii').strip()
    if not raw.isascii() or not raw.isdecimal() or int(raw) > 255:
        raise ValueError('invalid phase exit marker')
    if int(raw) != observed_code:
        raise ValueError('phase marker differs from retained container exit')
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    fd, temp = tempfile.mkstemp(prefix='.exit-', dir=output.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'exit_code': observed_code}, f)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        # No replacement of existing evidence, including on a concurrent call.
        os.link(temp, output)
    finally:
        os.unlink(temp)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--marker', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--observed-exit', required=True, type=int)
    a = p.parse_args()
    bridge(a.marker, a.output, a.observed_exit)
