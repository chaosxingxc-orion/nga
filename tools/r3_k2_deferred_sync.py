"""Build an opt-in K2 scalar-transfer candidate; never modify a running trainer.

Forward/backward calls and RNG order stay unchanged. Detached per-question loss
values transfer together; Python sums their float32 values in the original order.
No performance or numerical acceptance is inferred by generating this file.
"""
import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = '56bf1c3317ed8d9a75514a2c3c331f03117f9bb00e23ce29153d9c2ab7b3e78a'


def transform(raw):
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('original row-wise trainer source differs')
    text = raw.decode()
    start = text.index('    if arm == "k2":', text.index('def step_loss('))
    end = text.index('    raise ValueError(arm)', start)
    section = text[start:end]
    old = '        total = 0.0\n'
    assert section.count(old) == 1
    section = section.replace(old, '        detached_losses = []\n')
    old = '            total += float(lq.detach())\n'
    assert section.count(old) == 1
    section = section.replace(old, '            detached_losses.append(lq.detach())\n')
    old = '        return total, {"tokens": n_tok'
    assert section.count(old) == 1
    section = section.replace(old, '        total = sum(torch.stack(detached_losses).cpu().tolist()) if detached_losses else 0.0\n' + old)
    return (text[:start] + section + text[end:]).encode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = Path(args.source)
    if not source.is_absolute() or '..' in source.parts or any(p.is_symlink() for p in (source, *source.parents)):
        raise ValueError('absolute nonsymlink source required')
    result = transform(source.read_bytes())
    with Path(args.output).open('xb') as stream:
        stream.write(result)
    print(hashlib.sha256(result).hexdigest())
