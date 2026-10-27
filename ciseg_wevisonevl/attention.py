"""Exact full-image attention with bounded query workspace for the pinned VLM."""


def bounded_attention(module,query,key,value,attention_mask=None,dropout=0.,scaling=None,is_causal=None,**kwargs):
    """Every query sees all keys; splitting queries does not split image context."""
    import torch
    if dropout or module.training:
        raise ValueError('Bounded attention supports inference only')
    groups=query.shape[1]//key.shape[1]
    if groups>1:
        key=key.repeat_interleave(groups,dim=1)
        value=value.repeat_interleave(groups,dim=1)
    causal=(is_causal if is_causal is not None else getattr(module,'is_causal',True))
    causal=causal and query.shape[-2]>1 and attention_mask is None
    outputs=[]
    for start in range(0,query.shape[-2],512):
        stop=min(start+512,query.shape[-2])
        mask=attention_mask
        if mask is not None and mask.shape[-2]!=1:
            mask=mask[...,start:stop,:]
        elif causal:
            # Match SDPA's upper-left causal semantics; cached generation supplies
            # its explicit offset mask, or has a single non-causal query token.
            mask=torch.arange(key.shape[-2],device=query.device)[None,:]<=torch.arange(start,stop,device=query.device)[:,None]
        part=torch.nn.functional.scaled_dot_product_attention(
            query[...,start:stop,:],key,value,attn_mask=mask,dropout_p=0.,is_causal=False,scale=scaling)
        outputs.append(part)
    return torch.cat(outputs,dim=-2).transpose(1,2).contiguous(),None


def install_bounded_attention(model):
    """Bound the pinned vision and language attention workspaces, with full keys."""
    from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS
    from transformers.models.qwen3_vl.modeling_qwen3_vl import Qwen3VLVisionAttention,Qwen3VLTextAttention
    ALL_ATTENTION_FUNCTIONS.register('ciseg_bounded_sdpa',bounded_attention)
    count=0
    for module in model.modules():
        if isinstance(module,(Qwen3VLVisionAttention,Qwen3VLTextAttention)):
            module.config._attn_implementation='ciseg_bounded_sdpa'
            count+=1
    if not count:
        raise RuntimeError('Pinned Qwen3-VL vision attention modules were not found')
    return count
