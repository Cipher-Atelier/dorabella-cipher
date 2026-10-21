"""Partitioned execution only; uses the unchanged frozen refinement function.
Launched after all initial Hartmeier controls exist, while the first worker batch
is processing Hauer controls. The partition has no numerical/seed effect.
For normal reproduction just run refine_conditional_v7.py after initial stage.
"""
import sys
import refine_conditional_v7 as runner
OriginalPool=runner.ThreadPoolExecutor
class HartOnly(OriginalPool):
    def map(self,func,iterable,*args,**kwargs):
        tasks=[c for c in iterable if c.get('kind')=='bigram' and c.get('source')=='hart_real']
        print('Hart-only partition jobs:',len(tasks),flush=True)
        return super().map(func,tasks,*args,**kwargs)
runner.ThreadPoolExecutor=HartOnly
if __name__=='__main__':
    sys.argv=['refine_conditional_v7.py','--workers','2'];runner.main()
