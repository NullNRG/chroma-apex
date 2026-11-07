import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'examples'))
from decoder_engine import ApexSampler,TorchSampler,TorchFastSampler,CONFIGS,create_model,run_decode

for name in CONFIGS:
    model=create_model(name)
    output={}
    for method,sampler in [('apex',ApexSampler(strategy=0)),('reference',ApexSampler(strategy=1)),('torch',TorchSampler()),('torch_fast',TorchFastSampler())]:
        output[method]=run_decode(model,sampler,16,seed=98765,top_k=40,top_p=.95,temp=.8)
    assert output['apex']['token_ids']==output['reference']['token_ids']==output['torch']['token_ids']==output['torch_fast']['token_ids'],name
    assert all(output[x]['tokens_per_second']>0 for x in output),name
    print('PASS',name,'tokens',len(output['apex']['token_ids']))
