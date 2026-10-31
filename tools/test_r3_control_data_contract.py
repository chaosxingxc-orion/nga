import copy
from types import SimpleNamespace
import unittest
import r3_control_data_contract as C

class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.B,cls.P=C.modules();cls.rows=cls.B.read_rows(str(C.TRAIN),20)
    def test_real_augmentation_and_drop_preserve_every_noninput_field(self):
        result=C.check(self.rows,self.B,self.P)
        self.assertEqual([r['base_questions'] for r in result],[20,20])
        self.assertTrue(all(r['examples_checked']>=20 for r in result))
    def test_input_leak_rejected(self):
        fake=SimpleNamespace(epoch_units=lambda rows,seed,epoch,aug,prompt,drop:self.B.epoch_units(rows,seed,epoch,aug,prompt,False))
        with self.assertRaisesRegex(ValueError,'state not removed'):C.check(self.rows,fake,self.P)
    def test_question_removed_along_with_state_rejected(self):
        def bad(*args):
            units=self.B.epoch_units(*args)
            if args[-1]:units[0][0]['prompt']=units[0][0]['prompt'].replace('Question: ','Deleted: ')
            return units
        with self.assertRaisesRegex(ValueError,'question, options or task'):C.check(self.rows,SimpleNamespace(epoch_units=bad),self.P)
    def test_nontraining_population_refused(self):
        rows=copy.deepcopy(self.rows);rows[0]['split']='test'
        with self.assertRaisesRegex(ValueError,'training split'):C.check(rows,self.B,self.P)
    def test_config_architectures_match_without_weights(self):
        self.assertTrue(C.architecture()['equal'])

if __name__=='__main__':unittest.main()
