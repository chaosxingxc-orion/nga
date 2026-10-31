"""CPU reconstruction of final Track K fields using frozen metric primitives.

No scoring, ticket issuance or authorization. The caller provides an existing
ticket and verifies model/readout provenance separately. Dataset hashes are
checked against both the task manifest and the producing report.
"""
import json
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rebuild_suite(C, E, D, V, *, train, calibration, clean, variants, readouts, arm, suite):
    """Reconstruct every numerical field of one final suite and calibration."""
    require(arm in ('K0', 'K1', 'K2'), 'unregistered final arm')
    require(suite in C.SUITES, 'unregistered final suite')
    require(len(clean) == {'decision-v7':1200, 'transfer-v4':656}[suite], 'final population count differs')
    require(bool(train) and bool(calibration) and bool(variants), 'missing reference population')
    require(set(readouts) == {'calibration', 'clean', 'variants', 'question_only', 'empty_input'},
            'readout kinds differ')
    populations = dict(calibration=calibration, clean=clean, variants=variants,
                       question_only=clean, empty_input=clean)
    ordered = {kind:E.validate_population(readouts[kind], rows, C.kev_key)
               for kind,rows in populations.items()}
    scores = {kind:[row['s'] for row in rows] for kind,rows in ordered.items()}
    const = D.fit_constant(train)
    fitted = V.fit_operator(calibration, scores['calibration'])
    all_scores = {C.kev_key(row):s for kind in ('clean','variants')
                  for row,s in zip(populations[kind],scores[kind])}
    require(len(all_scores) == len(clean)+len(variants), 'clean/variant keys overlap')
    op = lambda row,s:V.operator_decision(fitted,row,s)[0]

    def partition(rows, values, is_calibration=False):
        arms = {}
        if not is_calibration:
            cs, tiers = D.score_constant(const,rows)
            arms = {'constant':{**C.headline(rows,cs),'tier_usage':tiers},
                    'uniform':C.headline(rows,D.score_uniform(rows)),
                    **{kind:C.headline(rows,scores[kind]) for kind in ('question_only','empty_input')}}
        return {'n':len(rows), 'headline':C.headline(rows,values),
                'near_tie_census':C.near_tie_census(values,gold=[C.gold_index(r) for r in rows],
                    keys=[C.kev_key(r) for r in rows],option_ids=[C.level_ids(r) for r in rows]),
                'duplicate_option_audit':C.duplicate_option_audit(rows),
                'gold_position_distribution':C.gold_position_distribution(rows), 'arms':arms,
                'n_variants':{kind:0 if is_calibration else sum(v['variant']==kind for v in variants)
                              for kind in C.KEV_VARIANTS}}
    test = partition(clean,scores['clean'])
    test['secondary'] = {
        'permutation':V.permutation_metrics(V.build_permutation_pairs(clean,variants),all_scores,op,arm),
        'nota':V.nota_metrics(V.build_nota_units(clean,variants),all_scores),
        'operator':V.operator_column(clean,scores['clean'],fitted,suite+'/test')}
    return {'test':test,'calibration':partition(calibration,scores['calibration'],True),
            'operator_fit':{'partition':'decision-v7/calibration','n':len(calibration),'fitted':fitted.summary()}}


def verify(ticket, run_dir, *, kev_dir, report=None):
    """Rebuild from raw rows; fail if any reported numerical field differs."""
    import core_r3 as C
    import selection_evidence_r3 as E
    import degenerate_r3 as D
    import variants_r3 as V
    import prechecks_r3 as PC
    import testlock_r3 as TL
    require(isinstance(ticket,TL.TestTicket) and ticket.split=='test', 'existing final ticket required')
    if report is None:
        report = json.loads((Path(run_dir)/'TEST-PRODUCER-REPORT.json').read_text())
    header=report['header']
    require(header['model']['sha256']==ticket.identity['sha256'], 'metric report model differs')
    populations={};paths=[]
    for kind,suite,split,variant in (
            ('train','decision-v7','train',False),('calibration','decision-v7','calibration',False),
            ('clean',ticket.suite,'test',False),('variants',ticket.suite,'test',True)):
        rows,path=C.load_partition(suite,split,variants=variant,ticket=ticket if split=='test' else None,
                                   kev_dir=str(kev_dir))
        populations[kind]=rows;paths.append(path)
    PC.check_kev_manifest(paths,kev_dir=str(kev_dir))
    for path in paths:
        require(header.get('data_files',{}).get(path)==C.sha256_file(path), 'producer dataset hash differs: '+path)
    readouts={kind:C.read_jsonl(C.k_readout_path(str(run_dir),ticket.suite,'test',kind))
              for kind in ('clean','variants','question_only','empty_input')}
    readouts['calibration']=C.read_jsonl(C.k_readout_path(str(run_dir),'decision-v7','calibration','clean'))
    rebuilt=rebuild_suite(C,E,D,V,**populations,readouts=readouts,arm=header['arm'],suite=ticket.suite)
    block=report['track_k']
    for key in ('partition','n','fitted'):
        require(block['operator_fit'].get(key)==rebuilt['operator_fit'][key], 'operator fit differs: '+key)
    for label,values in ((ticket.suite+'/test',rebuilt['test']),('decision-v7/calibration',rebuilt['calibration'])):
        actual=block['partitions'][label]
        # Only human-readable annotations may be additional to rebuilt fields.
        require(set(actual)-set(values) <= {'secondary_note'}, 'unverified partition fields: '+label)
        for key,value in values.items():
            require(actual.get(key)==value, 'reconstructed metric differs: '+label+'/'+key)
    return {'suite':ticket.suite,'verified_fields':sorted(rebuilt['test']),
            'scope':'full Track K numerical fields; metric primitives shared with producer'}
