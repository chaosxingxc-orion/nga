"""CPU reconstruction of final Track K fields using frozen metric primitives.

No scoring, ticket issuance or authorization. The caller provides an existing
ticket; model/readout provenance is verified inside the source snapshot. Dataset hashes are
checked against both the task manifest and the producing report.
"""
import json
import hashlib
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


ARMS = ('K0', 'K1', 'K2', 'K1-QO', 'K1-PT')


def validate_header(header, *, prompt, expected_arm=None, expected_model=None,
                    expected_adapter=None, expected_sha256=None):
    """Validate actual producer protocol before reading data or publishing.

    Identity is checked against execution arguments when supplied. This does not
    prove training eligibility or review authorship. The returned protocol names
    QO's dropped input explicitly rather than labelling it full-input scoring.
    """
    arm = header.get('arm')
    require(arm in ARMS and (expected_arm is None or arm == expected_arm), 'final header arm differs')
    mode = 'drop' if arm == 'K1-QO' else 'full'
    require(header.get('primary_input_mode') == mode, 'final primary input mode differs')
    require(header.get('stages') == 'k' and header.get('partitions') in
            (['calibration', 'test'], ['test', 'calibration']), 'final header stage/partitions differ')
    require(type(header.get('limit')) is int and header['limit'] == 0
            and type(header.get('limit_groups')) is int and header['limit_groups'] == 0
            and header.get('dry_run_warnings') == [], 'final header partial/diagnostic scope')
    require(header.get('dtype') == 'float32' and header.get('render') == 'record_name',
            'final header dtype/render differs')
    require(header.get('prompt_version') == prompt.PROMPT_VERSION
            and header.get('prompt_format') == prompt.PROMPT_FORMAT, 'final prompt differs')
    model = header.get('model', {})
    require(model.get('kind') == ('checkpoint' if arm == 'K0' else 'lora-adapter-unmerged'),
            'final model kind differs')
    require(all(isinstance(model.get(k), str) and Path(model[k]).is_absolute()
                for k in ('path', 'base_path')), 'final model paths differ')
    if arm == 'K0': require(model['path'] == model['base_path'], 'K0 model/base differs')
    if arm in ('K1-QO', 'K1-PT'):
        wanted = 'Qwen__Qwen3.5-0.8B-Base' if arm == 'K1-QO' else 'Qwen__Qwen3.5-0.8B'
        require(Path(model['base_path']).name == wanted, 'final control base differs')
    if expected_sha256 is not None:
        require(model.get('sha256') == expected_sha256, 'final model SHA differs')
    if expected_model is not None:
        require(model['base_path'] == expected_model
                and model['path'] == (expected_adapter or expected_model), 'final model execution identity differs')
    scorer = header.get('scorer', {})
    require(isinstance(scorer, dict) and scorer.get('record_grade') is True
            and scorer.get('mode') == 'rightpad' and scorer.get('dtype') == 'float32'
            and scorer.get('token_budget') == 16384 and isinstance(scorer.get('hf32'), dict)
            and scorer['hf32'].get('hf32') is False
            and scorer.get('render') == 'record_name' and scorer.get('dedup') is True,
            'final scorer protocol differs')
    require(scorer.get('model_path') == model['base_path'] and 'adapter' in scorer
            and scorer['adapter'] == (None if arm == 'K0' else model['path']),
            'final scorer model/adapter differs')
    return {'mode':'rightpad', 'dtype':'float32', 'hf32':False, 'token_budget':16384,
            'headline':'kev_argmax_first', 'input_mode':mode, 'render':'record_name'}


def rebuild_suite(C, E, D, V, *, train, calibration, clean, variants, readouts, arm, suite):
    """Reconstruct every numerical field of one final suite and calibration."""
    require(arm in ARMS, 'unregistered final arm')
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


def verify(ticket, run_dir, *, kev_dir, report=None, provenance_verifier=None):
    """Rebuild from raw rows; fail if any reported numerical field differs."""
    import core_r3 as C
    import selection_evidence_r3 as E
    import degenerate_r3 as D
    import variants_r3 as V
    import prechecks_r3 as PC
    import testlock_r3 as TL
    import prompt as P
    require(isinstance(ticket,TL.TestTicket) and ticket.split=='test', 'existing final ticket required')
    if report is None:
        report = json.loads((Path(run_dir)/'TEST-PRODUCER-REPORT.json').read_text())
    header=report['header']
    validate_header(header, prompt=P, expected_sha256=ticket.identity['sha256'])
    require(all(header['model'].get(k) == ticket.identity.get(k)
                for k in ('path','sha256','kind','base_path','base_revision')), 'metric report model differs')
    # Bind exactly the files consumed below before loading their contents.
    # A ticket and validated producer header are required before this boundary.
    source_paths = [C.partition_path(s, split, variant, str(kev_dir)) for s, split, variant in (
        ('decision-v7','train',False), ('decision-v7','calibration',False),
        (ticket.suite,'test',False), (ticket.suite,'test',True))]
    source_paths += [C.k_readout_path(str(run_dir),ticket.suite,'test',kind)
                     for kind in ('clean','variants','question_only','empty_input')]
    source_paths += [C.k_readout_path(str(run_dir),'decision-v7','calibration','clean'),
                     str(Path(kev_dir)/'manifest.json')]
    def snapshot():
        result = {}
        for name in source_paths:
            path = Path(name)
            require(path.is_absolute() and '..' not in path.parts
                    and not any(p.is_symlink() for p in (path,*path.parents)), 'unsafe metric source')
            result[name] = C.sha256_file(name)
        return result
    before = snapshot()
    headline = report['track_k']['partitions'][ticket.suite+'/test']['headline']
    source_verification = (provenance_verifier or TL.verify_test_result)(
        ticket, headline['n'], headline['kev_rule_accuracy'], str(run_dir), kev_dir=str(kev_dir))
    require(snapshot() == before, 'metric sources changed during provenance verification')
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
    clean_ordered=E.validate_population(readouts['clean'],populations['clean'],C.kev_key)
    correct=[int(C.argmax_first(row['s'])==C.gold_index(source))
             for row,source in zip(clean_ordered,populations['clean'])]
    vector={'dataset_sha256':header['data_files'][C.partition_path(ticket.suite,'test',False,str(kev_dir))],
            'keys':[C.kev_key(row) for row in populations['clean']], 'correct':correct,
            'n':len(correct),'tie_count':sum(C.is_tie(row['s']) for row in clean_ordered)}
    require(sum(correct)/len(correct)==rebuilt['test']['headline']['kev_rule_accuracy'],
            'paired vector headline differs')
    import r3_reference_metrics as RM
    panels = {}
    for suite, split, rows, saved, readout_path in (
        (ticket.suite,'test',populations['clean'],clean_ordered,
         C.k_readout_path(str(run_dir),ticket.suite,'test','clean')),
        ('decision-v7','calibration',populations['calibration'],
         E.validate_population(readouts['calibration'],populations['calibration'],C.kev_key),
         C.k_readout_path(str(run_dir),'decision-v7','calibration','clean'))):
        require(len(rows) == (1148 if split == 'calibration' else
                             {'decision-v7':1200,'transfer-v4':656}[suite]), 'supplement population differs')
        scores = [x['s'] for x in saved]; gold = [C.gold_index(x) for x in rows]
        values = RM.summarize(scores,gold)
        headline = report['track_k']['partitions'][suite+'/'+split]['headline']
        require(values['accuracy'] == headline['kev_rule_accuracy']
                and values['tie_count'] == headline['tie_count']
                and values['n'] == headline['n'], 'supplement headline differs')
        data_path = C.partition_path(suite,split,False,str(kev_dir))
        binding = {'keys':[C.kev_key(x) for x in rows], 'option_ids':[C.level_ids(x) for x in rows],
                   'gold':gold,'scores':scores}
        panels[suite+'/'+split] = {'metrics':values,'dataset_sha256':before[data_path],
            'readout_sha256':before[readout_path],
            'ordered_inputs_sha256':hashlib.sha256(json.dumps(binding,sort_keys=True,
                separators=(',',':'),allow_nan=False).encode()).hexdigest()}
    require(snapshot() == before, 'metric sources changed during reconstruction')
    supplement = {'schema':'r3-source-reference-metrics-v1', 'suite':ticket.suite,
        'specification_sha256':RM.SPECIFICATION_SHA256,'panels':panels,'source_sha256':before,
        'producer_report_sha256':hashlib.sha256(json.dumps(report,sort_keys=True,
            separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        'scientific_acceptance':False,'publication_authorized':False,
        'scope':'source-rebuilt supplementary T1 fields; existing admission remains external'}
    return {'suite':ticket.suite,'paired_vector':vector,'verified_fields':sorted(rebuilt['test']),
            'source_verification':source_verification,
            'reference_metrics':supplement,
            'scope':'full Track K numerical fields; metric primitives shared with producer'}
