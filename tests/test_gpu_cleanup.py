from contextlib import nullcontext
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from ciseg_wevisonevl.inference import Predictor
from ciseg_wevisonevl.settings import Settings


@pytest.mark.parametrize('fails',[False,True])
def test_unused_gpu_cache_is_released_after_success_and_failure(monkeypatch,fails):
    predictor=Predictor.__new__(Predictor)
    predictor.settings=Settings()
    predictor.cuda_device='cuda:0'
    snapshots=iter([{'allocated_bytes':10,'reserved_bytes':10},
                    {'allocated_bytes':10,'reserved_bytes':20},
                    {'allocated_bytes':10,'reserved_bytes':10}])
    predictor.gpu_memory=lambda:next(snapshots)
    calls=[]
    monkeypatch.setattr(torch.cuda,'device',lambda device:nullcontext())
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:calls.append('sync'))
    monkeypatch.setattr(torch.cuda,'empty_cache',lambda:calls.append('release'))
    def predict(image,text):
        if fails:raise RuntimeError('Deliberate prediction failure')
        return SimpleNamespace(masks=[np.ones((2,2),np.float32)])
    predictor._predict=predict
    if fails:
        with pytest.raises(RuntimeError,match='Deliberate'):predictor.predict(None,'test')
    else:
        assert isinstance(predictor.predict(None,'test').masks[0],np.ndarray)
    assert calls==['sync','release']
    assert predictor.last_gpu_memory['after_cleanup']=={'allocated_bytes':10,'reserved_bytes':10}


def test_cpu_prediction_does_not_initialize_cuda(monkeypatch):
    predictor=Predictor.__new__(Predictor)
    predictor.settings=Settings(device='cpu')
    predictor.cuda_device=None
    predictor._predict=lambda *args:'result'
    monkeypatch.setattr(torch.cuda,'empty_cache',lambda:pytest.fail('CPU prediction touched CUDA'))
    assert predictor.predict(None,'test')=='result'
    assert predictor.last_gpu_memory['after_cleanup'] is None
