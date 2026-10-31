import importlib.util
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('resume',Path(__file__).with_name('r3_resume_contract.py'))
R=importlib.util.module_from_spec(s);s.loader.exec_module(R)


class ResumeContract(unittest.TestCase):
    def test_invalid_measurements_and_incomplete_controls_cannot_pass(self):
        controls={name:{'loss':1.,'weight_relative_l2':1.}
                  for name in ('zero_moments','no_update')}
        for value in (float('nan'),float('inf'),-1.,True,1.7e308):
            with self.subTest(value=value), self.assertRaises(ValueError):
                R.judge(value,0.,0.,0.,controls)
        with self.assertRaisesRegex(ValueError,'both registered'):
            R.judge(0.,0.,0.,0.,{'zero_moments':controls['zero_moments']})
        controls['no_update']['loss']=float('inf')
        with self.assertRaisesRegex(ValueError,'finite'):
            R.judge(0.,0.,0.,0.,controls)

    def test_floor_is_independent_of_resume_and_controls_must_discriminate(self):
        controls={'zero_moments':{'loss':.04,'weight_relative_l2':.001},
                  'no_update':{'loss':.001,'weight_relative_l2':.04}}
        good=R.judge(.01,.01,.014,.014,controls)
        self.assertTrue(good['pass'])
        bad=R.judge(.01,.01,.5,.5,controls)
        self.assertFalse(bad['pass']);self.assertEqual(good['bars'],bad['bars'])
        controls['no_update']={'loss':0.,'weight_relative_l2':0.}
        self.assertFalse(R.judge(.01,.01,0.,0.,controls)['pass'])

    def test_command_preserves_full_schedule_and_recipe(self):
        original=['python3','-P','/workspace/train_r3.py','--out','old','--total-steps','3116',
                  '--grad-ckpt','--micro-tokens','12000','--seed','2']
        cmd=R.command({'command':original},Path('/fresh'),10)
        self.assertEqual(cmd[cmd.index('--total-steps')+1],'3116')
        self.assertEqual(cmd[cmd.index('--out')+1],'/fresh')
        self.assertEqual(cmd[-2:],['--stop-after','10'])
        self.assertEqual(original[original.index('--out')+1],'old')


if __name__=='__main__':unittest.main()
