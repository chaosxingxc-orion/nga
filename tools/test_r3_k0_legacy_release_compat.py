import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import r3_k0_legacy_release_compat as C


class PureTests(unittest.TestCase):
    def test_unknown_member_fails_before_io(self):
        with self.assertRaisesRegex(ValueError, 'only two'):
            C.replay('/absent', '/absent', 'primary_s2')

    def test_exact_does_not_accept_boolean_integer_alias(self):
        with self.assertRaises(ValueError):
            C.exact({'chip':1}, {'chip':True}, 'alias')


@unittest.skipUnless(os.environ.get('NGA_K0_FIXTURES'), 'requires pinned original local evidence')
class OriginalTests(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ['NGA_K0_FIXTURES'])
        self.config = root/'production-dev-qualification-20261103-v5/CONFIG.json'
        self.capture = root/'member-runtime-capture-20261103-v1/k0_base/CAPTURE.json'
        cfg = C.E.loaded(self.config, C.CONFIG_SHA)
        cap = C.E.loaded(self.capture, C.CAPTURE_SHA['k0_base'])
        pins = C.E.ORIGINALS['k0_base']
        execution = C.E.loaded(cfg['members']['k0_base']['execution'], pins['execution'])
        a = Path(execution['out'])/'attempts/1'
        ref = cap['evaluation_observations']['container']
        self.kw = dict(execution=execution, claim=C.E.loaded(a/'CLAIM.json',pins['claim']),
                       release=C.E.loaded(a/'RELEASE.json',pins['release']),claim_pin=pins['claim'],
                       release_path=a/'RELEASE.json',actual=C.E.loaded(ref['path'],ref['sha256'])[0])
        self.root = root

    def verify(self, **kw):
        return C.verify(self.config,self.capture,'k0_base',**kw)

    def test_both_originals_pass_without_writing_historical_evidence(self):
        for member in C.CAPTURE_SHA:
            result = C.replay(self.config,self.root/f'member-runtime-capture-20261103-v1/{member}/CAPTURE.json',member)
            self.assertFalse(result['active'])
            self.assertFalse(result['scientific_acceptance'])
            self.assertFalse(result['derived_release_persisted'])

    def test_caller_mutations_rejected(self):
        mutations = [
            lambda k:k['execution'].update(chip=7),
            lambda k:k['claim'].update(run='third-party'),
            lambda k:k['release'].update(container_id='foreign'),
            lambda k:k.update(claim_pin='0'*64),
            lambda k:k.update(release_path=Path('/foreign/RELEASE.json')),
            lambda k:k['actual'].update(Id='foreign'),
            lambda k:k['execution'].update(tools={}),
            lambda k:k['actual']['Config'].update(Cmd=['foreign-producer']),
            lambda k:k['release'].update(claim_sha256=k['claim_pin']),
            lambda k:k['claim'].update(successor_precondition={}),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                kw=copy.deepcopy(self.kw);mutate(kw)
                with self.assertRaises(ValueError):self.verify(**kw)

    def test_unpinned_config_capture_and_partial_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'changed.json'
            for original in (self.config,self.capture):
                doc=json.loads(original.read_text())
                if original==self.config:
                    doc['immutable_files']={}
                    p.write_text(json.dumps(doc))
                    with self.assertRaises(ValueError):
                        C.verify(p,self.capture,'k0_base',**self.kw)
                else:
                    doc['evaluation_observations'].pop('image')
                    p.write_text(json.dumps(doc))
                    with self.assertRaises(ValueError):
                        C.verify(self.config,p,'k0_base',**self.kw)

    def test_wrong_original_capture_rejected(self):
        with self.assertRaises(ValueError):
            C.verify(self.config,self.root/'member-runtime-capture-20261103-v1/k0_instruct/CAPTURE.json','k0_base',**self.kw)


if __name__=='__main__':unittest.main()
