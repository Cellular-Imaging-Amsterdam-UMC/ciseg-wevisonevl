"""Conservative GPU profiles and safe whole-overview retry planning."""
import math

GIB=1024**3


def plan_resolution(shape,limit,free_bytes,total_bytes):
    """Use assigned device/MIG capacity and current free memory, not host GPU sum."""
    if total_bytes<22*GIB:
        raise RuntimeError('Automatic resolution requires a 24 GB GPU class or larger; 12 GB MIG devices are not supported.')
    profile=3072 if total_bytes<=32*GIB else 4096
    side=min(limit,profile)
    reserve=max(2*GIB,.15*total_bytes)
    # Conservative planning estimate, not a guarantee. Exact attention workspace
    # is bounded; mask count and decoder activations can still trigger retries.
    pixel_budget=(free_bytes-reserve-GIB)/768
    if pixel_budget<=0:
        raise RuntimeError('Insufficient free GPU memory after model loading and safety reserve. Free GPU memory or request a larger GPU/MIG profile.')
    aspect=min(shape)/max(shape)
    fit=math.sqrt(pixel_budget/aspect)
    if fit<side:
        side=max(128,int(fit)//128*128)
    return side,{'gpu_free_bytes':int(free_bytes),'gpu_total_bytes':int(total_bytes),
                 'gpu_profile_side':profile,'safety_reserve_bytes':int(reserve),
                 'planning_bytes_per_pixel':768,'configured_side_limit':limit,'selected_side_limit':side}


def choose_resolution(predictor,settings,shape):
    device=getattr(predictor,'cuda_device',None)
    if not settings.auto_resolution or not device:
        return settings.max_side,{'mode':'configured_limit','selected_side_limit':settings.max_side}
    import torch
    free,total=torch.cuda.mem_get_info(device)
    side,details=plan_resolution(shape,settings.max_side,free,total)
    return side,{'mode':'automatic_gpu_profile',**details}


def next_smaller_side(side):
    return max(128,int(side*.75)//128*128)
