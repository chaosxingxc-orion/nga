"""Additional independent regressions; external processes are forbidden."""
import copy, fcntl, json, sys, unittest
from pathlib import Path
from unittest import mock
from tools import unified_resource_provider_v1 as P
from tools.test_unified_resource_provider_v1 import ProviderTests
from tools.test_unified_container_host_v1 import IMAGE
from tools import unified_resource_lease_v1 as U


def row(i=1, status='running', devices=None):
    return {'Id':f'{i:064x}', 'Name':f'/c{i}', 'State':{'Status':status,'Running':status in ('running','paused','restarting')},
            'HostConfig':{'Devices':devices or [],'Privileged':False,'DeviceCgroupRules':None,'DeviceRequests':None}, 'Mounts':[]}


def dev(path, target=None):
    return {'PathOnHost':path,'PathInContainer':target or path,'CgroupPermissions':'rwm'}


def inventory(rows):
    by_id={r['Id']:r for r in rows}
    def call(argv, **kw):
        if argv == ['/usr/bin/docker','ps','-aq','--no-trunc']: return '\n'.join(by_id)
        assert argv[:2] == ['/usr/bin/docker','inspect']
        return json.dumps([by_id[i] for i in argv[2:]])
    with mock.patch.object(P,'run',side_effect=call): result=P.Inventory()
    return result, []

class ExtraInventory(unittest.TestCase):
    def test_standard_profile_only_reserves_mapped_device(self):
        aux=['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci2']
        self.assertEqual(inventory([row(devices=[dev(x) for x in aux])])[0].busy,{2})
    def test_duplicate_names_rejected(self):
        a,b=row(1),row(2); b['Name']=a['Name']
        with self.assertRaises(ValueError): inventory([a,b])
    def test_unqualified_manager_profiles_are_broad(self):
        aux=['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci2']
        for maps in ([dev('/dev/davinci_manager')], [dev(x) for x in aux[:-1]],
                     [dev(x, '/bad' if x=='/dev/davinci_manager' else x) for x in aux],
                     [dev(x) for x in aux]+[dev('/dev/ascend0')]):
            self.assertEqual(inventory([row(devices=maps)])[0].busy,set(range(8)))
    def test_all_falsy_grants_and_state_types_rejected(self):
        for field in ('DeviceCgroupRules','DeviceRequests'):
            for val in ({},False,'',0):
                r=row(); r['HostConfig'][field]=val
                with self.subTest(field=field,val=val),self.assertRaises(ValueError): inventory([r])
        for state in ({'Status':'dead','Running':True},{'Status':'exited','Running':0},{'Status':'unknown','Running':False}):
            r=row(); r['State']=state
            with self.subTest(state=state),self.assertRaises(ValueError): inventory([r])
    def test_image_queries_are_cached_and_facade_is_read_only(self):
        class Cache:
            def inspect(self,name): return {'name':name}
        facade=P.DiagnosticFacade(Cache()); calls=[]
        def cmd(argv):
            calls.append(argv); return json.dumps([{'Id':IMAGE,'Config':{'Env':['PATH=/bin']}}])
        with mock.patch.object(P,'run',side_effect=cmd):
            self.assertEqual(facade.image_id(IMAGE),IMAGE); self.assertEqual(facade.image_id(IMAGE),IMAGE)
            self.assertEqual(facade.image_env(IMAGE),{'PATH':'/bin'})
        self.assertEqual(len(calls),1); self.assertEqual(facade.inspect('c'),{'name':'c'})
        self.assertFalse(hasattr(facade,'start')); self.assertFalse(hasattr(facade,'create'))

class ExtraObservation(ProviderTests):
    def test_terminal_freshness_includes_final_validation(self):
        self.setup_provider(1); now=[10]; count=[0]; real=P.validate_config
        def validate(config):
            result=real(config); count[0]+=1
            if count[0]==2: now[0]=50
            return result
        with mock.patch.object(P.time,'monotonic',side_effect=lambda:now[0]), mock.patch.object(P.time,'time',side_effect=lambda:100+now[0]), mock.patch.object(P,'validate_config',side_effect=validate):
            snap,receipt=self.obs()
        self.assertFalse(receipt['fresh']); self.assertEqual(snap['resources']['0'],'unknown')
    def test_wrong_host_skips_diagnostics(self):
        self.setup_provider(1); U.claim(self.c,self.q)
        with mock.patch.object(P,'host_check',side_effect=ValueError('wrong host')), mock.patch.object(P,'Inventory') as inventory_mock, mock.patch.object(P,'DiagnosticFacade') as facade:
            snap,receipt=P.observe(self.pc,self.g)
        inventory_mock.assert_not_called(); facade.assert_not_called(); self.assertEqual(snap['resources']['0'],'busy')
    def test_publication_rechecks_source_exact_pair_ledger_and_age(self):
        for mutation in ('source','snapshot','ledger','late'):
            with self.subTest(mutation=mutation):
                self.setUp(); self.setup_provider(1); snap,receipt=self.obs(); dest=self.root/'published'
                if mutation=='source': receipt['source_pins'][0]['sha256']='0'*64
                if mutation=='snapshot': snap['resources']['0']='busy'
                if mutation=='ledger': Path(self.alloc).write_bytes(Path(self.alloc).read_bytes()+b' ')
                if mutation=='late': receipt['monotonic_start']-=31
                with self.assertRaises((ValueError,OSError)): P.publish(self.pc,self.g,snap,receipt,dest)
                self.assertFalse(dest.exists())
        self.setUp(); self.setup_provider(1); snap,receipt=self.obs(); dest=self.root/'published'
        result=P.publish(self.pc,self.g,snap,receipt,dest)
        self.assertTrue((dest/'snapshot.json').is_file()); self.assertEqual(result['snapshot']['sha256'],P.pin(dest/'snapshot.json')['sha256'])
    def test_publication_checks_age_after_pin_verification(self):
        self.setup_provider(1); snap,receipt=self.obs(); dest=self.root/'late'; real=P.check_raw_pin; called=[0]
        def slow(ref):
            real(ref); called[0]+=1
        with mock.patch.object(P,'check_raw_pin',side_effect=slow), mock.patch.object(P.time,'monotonic',side_effect=lambda: receipt['monotonic_start']+31):
            with self.assertRaisesRegex(ValueError,'expired'): P.publish(self.pc,self.g,snap,receipt,dest)
        self.assertGreater(called[0],2); self.assertFalse(dest.exists())
    def test_owner_device_failure_prevents_diagnostic(self):
        self.setup_provider(1); h=U.ref(self.pc['host_configs'][0]); U.claim(self.c,self.q)
        with mock.patch.object(P,'host_check'), mock.patch.object(P,'Inventory',return_value=self.q), mock.patch.object(P,'device_query',side_effect=ValueError('probe')), mock.patch.object(P,'DiagnosticFacade') as facade:
            snap,receipt=P.observe(self.pc,self.g)
        facade.return_value.image_id.assert_not_called(); self.assertEqual(snap['resources']['0'],'busy'); self.assertIn('uncertain',receipt['owners'][self.c['lease_id']])
    def test_lock_contention_fails_without_waiting(self):
        self.setup_provider(1)
        with open(self.alloc+'.lock') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.obs()

if __name__=='__main__':
    names=[(cls,n) for cls in (ExtraInventory,ExtraObservation) for n in cls.__dict__ if n.startswith('test_')]
    with mock.patch.object(P.subprocess,'run',side_effect=AssertionError('external process forbidden')), mock.patch.object(P.subprocess,'Popen',side_effect=AssertionError('external process forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cls(n) for cls,n in names))
    sys.exit(not result.wasSuccessful())
