"""Exclusive, per-attempt trace files for CPU qualification evidence."""
from pathlib import Path
import re


def write_trace(directory, attempt, step, preclip, postclip, save):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', attempt):
        raise ValueError('invalid attempt')
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise ValueError('invalid step')
    path = Path(directory) / f'gradients-{step:06d}-{attempt}.pt'
    # Exclusive creation ensures a retry cannot destroy earlier evidence.
    with path.open('xb') as stream:
        save({'preclip': preclip, 'postclip': postclip}, stream)
    return path
