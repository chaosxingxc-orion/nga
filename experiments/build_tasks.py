#!/usr/bin/env python3
"""Build T1–T3 (no-label invariance / discrimination tasks) from the local dataset mirrors.

Usage:  python3 -I experiments/build_tasks.py [--out DIR] [--max-inputs N]
Writes <out>/T1_level_names/*.jsonl, <out>/T2_definition_swap/*.jsonl, <out>/T3_question_set/*.jsonl
and <out>/manifest.json.  Only reads the mirrors; never imports from them.
"""
import argparse, collections, hashlib, io, json, os, random, string
import pyarrow.parquet as pq

R = '/mnt/cephfs/xingchao/datasets/jev'
rng = random.Random(20261028)

def rows(p, cols=None):
    return pq.read_table(p, columns=cols).to_pylist()

# ------------------------------------------------------------------ sources ---
def src_typed_decisions():
    """1,200 inputs x 5 questions. questions: {name: {type, instructions, criteria}}; gold: {name: {label,...}}"""
    out = []
    for r in rows(R + '/LocalLLaMA__typed-decisions/all/train-00000-of-00001.parquet',
                  ['id', 'workflow', 'state', 'questions', 'gold']):
        qs, gold = json.loads(r['questions']), json.loads(r['gold'])
        for qn, q in qs.items():
            crit = q.get('criteria')
            if crit is None:                  # noul without written criteria: boolean with the statement itself
                crit = {'true': 'The statement holds for this record.', 'false': 'The statement does not hold for this record.'}
            if q['type'] == 'score':          # list of level definitions, ordinal 0..K-1
                levels = [{'id': str(i), 'name': str(i), 'definition': d} for i, d in enumerate(crit)]
                ltype = 'ordinal'
            elif q['type'] == 'choice':
                levels = [{'id': k, 'name': k, 'definition': v} for k, v in crit.items()]
                ltype = 'nominal'
            else:                              # noul
                levels = [{'id': k, 'name': k, 'definition': v} for k, v in crit.items()]
                ltype = 'boolean'
            out.append(dict(source='typed-decisions', group_id=r['id'], input=r['state'],
                            task_definition=f'Workflow: {r["workflow"]}. Answer the question about the record using only the criteria given.',
                            question=q['instructions'], qname=qn, levels=levels, level_type=ltype,
                            candidate_set='exclusive', gold=str(gold.get(qn, {}).get('label'))))
    return out

def src_akhilaaa3():
    out = []
    for split in ('medium', 'hard'):
        with io.open(f'{R}/akhilaaa3__decision-bench/data/{split}.jsonl', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                qs = json.loads(r['questions']) if isinstance(r['questions'], str) else r['questions']
                ans = json.loads(r['answers']) if isinstance(r['answers'], str) else r['answers']
                for qn, q in qs.items():
                    crit = q.get('criteria')
                    if q['type'] == 'score' and isinstance(crit, list):
                        levels = [{'id': str(i), 'name': str(i), 'definition': d} for i, d in enumerate(crit)]; ltype = 'ordinal'
                    elif isinstance(crit, dict):
                        levels = [{'id': k, 'name': k, 'definition': v} for k, v in crit.items()]
                        ltype = 'boolean' if q['type'] == 'noul' else 'nominal'
                    else:
                        continue
                    out.append(dict(source=f'akhilaaa3-{split}', group_id=r['id'], input=r['state'],
                                    task_definition=f'Family: {r["family"]}. Decide using only the stated criteria.',
                                    question=q['instructions'], qname=qn, levels=levels, level_type=ltype,
                                    candidate_set='exclusive', gold=str(ans.get(qn))))
    return out

def src_openjev_synth_score():
    """Open-Jev v1.1 synthetic 'score' rows: ordinal 'Exactly k of N requirements' levels, code labels."""
    out = []
    p = R + '/ZefanCai__Open-Jev-v1.1/data/community-hard-mix-v2-redistributable/train-00000-of-00001.parquet'
    for r in rows(p, ['id', 'group_id', 'kind', 'question', 'options', 'state_json', 'target', 'source']):
        if r['kind'] != 'score' or not r['source'].startswith('community-diversity-v2'):
            continue
        levels = [{'id': str(i), 'name': str(i), 'definition': o} for i, o in enumerate(r['options'])]
        gold = str(max(range(len(r['target'])), key=lambda i: r['target'][i]))
        out.append(dict(source='openjev-synth', group_id=r['group_id'], input=r['state_json'],
                        task_definition='Apply the visible numbered requirements under the stated evidence policy.',
                        question=r['question'], qname='score', levels=levels, level_type='ordinal',
                        candidate_set='exclusive', gold=gold))
    return out

# ----------------------------------------------------------------- variants ---
def rand_token(k=6):
    return ''.join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(k))

def name_sets(levels):
    K = len(levels)
    sets = {'digits': [str(i + 1) for i in range(K)],
            'letters': [(string.ascii_lowercase[i] if i < 26 else 'z' + str(i)) for i in range(K)],
            'original': [l['name'] for l in levels],
            'random': [rand_token() for _ in range(K)]}
    return sets

def t1(rec):
    """Same input, same definitions, four name sets.  Invariance expected."""
    if len(rec['levels']) > 26:
        return
    for variant, names in name_sets(rec['levels']).items():
        lv = [dict(l, name=n) for l, n in zip(rec['levels'], names)]
        yield dict(rec, task='T1', variant=variant, levels=lv)

def t2(rec):
    """Discrimination: (a) swap definitions of two adjacent levels (names fixed) -> gold moves accordingly;
       (b) reverse level order (ordinal only) -> distribution must reverse."""
    lv = rec['levels']; K = len(lv)
    if K < 2:
        return
    yield dict(rec, task='T2', variant='base')
    i = rng.randrange(K - 1)
    sw = [dict(l) for l in lv]
    sw[i]['definition'], sw[i + 1]['definition'] = lv[i + 1]['definition'], lv[i]['definition']
    g = rec['gold']; gm = {lv[i]['id']: lv[i + 1]['id'], lv[i + 1]['id']: lv[i]['id']}
    yield dict(rec, task='T2', variant=f'swap_{i}_{i+1}', levels=sw, gold=gm.get(g, g), swap=[lv[i]['id'], lv[i + 1]['id']])
    if rec['level_type'] == 'ordinal':
        rv = [dict(l, name=lv[K - 1 - j]['name'], id=lv[K - 1 - j]['id']) for j, l in enumerate(lv)]
        # definitions keep their meaning; names/ids now run K-1..0, so gold id is unchanged but position reversed
        yield dict(rec, task='T2', variant='reversed', levels=rv)

def t3(by_input):
    """typed-decisions only: for each (input, target question) render with 1 / 3 / 5 questions in the prefix,
       target question always included; also a shuffled 5.  Invariance expected on the target readout."""
    for gid, recs in by_input.items():
        if len(recs) < 5:
            continue
        for tgt in recs:
            others = [r for r in recs if r is not tgt]
            for n in (0, 2, 4):
                ctx = rng.sample(others, n)
                yield dict(tgt, task='T3', variant=f'prefix_{n+1}q', prefix_questions=[c['question'] for c in ctx] + [tgt['question']])
            sh = others[:]; rng.shuffle(sh)
            yield dict(tgt, task='T3', variant='prefix_5q_shuffled', prefix_questions=[c['question'] for c in sh] + [tgt['question']])

# --------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/cephfs/xingchao/experiments/jev')
    ap.add_argument('--max-inputs', type=int, default=0, help='cap inputs per source (0 = all)')
    a = ap.parse_args()
    srcs = {'typed-decisions': src_typed_decisions(), 'akhilaaa3': src_akhilaaa3(), 'openjev-synth': src_openjev_synth_score()}
    if a.max_inputs:
        for k, v in srcs.items():
            keep = set(list(dict.fromkeys(r['group_id'] for r in v))[:a.max_inputs])
            srcs[k] = [r for r in v if r['group_id'] in keep]
    manifest = {'built': '2026-10-28', 'sources': {k: len(v) for k, v in srcs.items()}, 'tasks': {}}
    def write(task, name, it):
        d = os.path.join(a.out, task); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name + '.jsonl'); n = 0; h = hashlib.sha256()
        with io.open(p, 'w', encoding='utf-8') as f:
            for rec in it:
                line = json.dumps(rec, ensure_ascii=False); f.write(line + '\n'); h.update(line.encode()); n += 1
        manifest['tasks'].setdefault(task, {})[name] = {'records': n, 'sha256': h.hexdigest()}
        print(f'{task}/{name}: {n}')
    for k, v in srcs.items():
        write('T1_level_names', k, (x for r in v for x in t1(r)))
        write('T2_definition_swap', k, (x for r in v for x in t2(r)))
    by_input = collections.defaultdict(list)
    for r in srcs['typed-decisions']:
        by_input[r['group_id']].append(r)
    write('T3_question_set', 'typed-decisions', t3(by_input))
    io.open(os.path.join(a.out, 'manifest.json'), 'w', encoding='utf-8').write(json.dumps(manifest, indent=1, ensure_ascii=False))
    io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifest.json'), 'w', encoding='utf-8').write(json.dumps(manifest, indent=1, ensure_ascii=False))

if __name__ == '__main__':
    main()
