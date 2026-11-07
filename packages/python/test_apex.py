import unittest, math, random
from apex_sort import Apex
class TestApex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.a=Apex()
    def test_float(self):
        x=[float('nan'),-0.,0.,3.,float('-inf'),float('inf'),float('nan'),-8.,3.]
        ix=self.a.order_float64(x)
        self.assertEqual(ix,[4,7,1,2,3,8,5,0,6])
    def test_int(self):
        self.assertEqual(self.a.order_int64([7,-2,7,0,-2]),[1,4,3,0,2])
    def test_u64(self):
        self.assertEqual(self.a.order_uint64([2**64-1,0,7]),[1,2,0])
    def test_records(self):
        r=[{'v':2,'id':1},{'v':1,'id':2},{'v':2,'id':3}]
        self.assertEqual([v['id'] for v in self.a.sorted_records_by_float64(r,lambda x:x['v'])],[2,1,3])
    def test_random(self):
        rng=random.Random(123)
        for n in (0,1,2,33,120,999,10000):
            a=[rng.randint(-2000,2000) for _ in range(n)]
            self.assertEqual(self.a.order_int64(a), sorted(range(n),key=lambda i:(a[i],i)))
if __name__=='__main__':unittest.main()
