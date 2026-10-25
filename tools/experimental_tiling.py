"""Research-only in-memory tile stitching. Not the production large-image pipeline."""
from itertools import product
import numpy as np


def starts(length,size,overlap):
    if size<32 or not 0<=overlap<size:raise ValueError('Invalid tile size or overlap')
    if length<=size:return [0]
    values=list(range(0,length-size+1,size-overlap))
    if values[-1]!=length-size:values.append(length-size)
    return values


def windows(shape,size=1024,overlap=256):
    return [(y,x,min(size,shape[0]-y),min(size,shape[1]-x)) for y,x in product(starts(shape[0],size,overlap),starts(shape[1],size,overlap))]


class InstanceStitcher:
    """Match only reciprocal unambiguous overlap instances, then resolve ownership by context."""
    def __init__(self,shape,threshold=.5,min_shared=8):
        if int(shape[0])*int(shape[1])>16_777_216:
            raise ValueError('Research stitcher is limited to 16 megapixels; production large-image streaming is not implemented')
        self.labels=np.zeros(shape,np.uint32);self.weight=np.zeros(shape,np.float32)
        self.covered=np.zeros(shape,bool);self.parents=[0];self.threshold=threshold;self.min_shared=min_shared
        self.matches=0;self.ambiguous=0
    def root(self,value):
        while self.parents[value]!=value:
            self.parents[value]=self.parents[self.parents[value]];value=self.parents[value]
        return value
    def add(self,tile,y,x):
        h,w=tile.shape;view=self.labels[y:y+h,x:x+w];known=self.covered[y:y+h,x:x+w]
        old=view.copy()
        for value in np.unique(old):
            if value:old[old==value]=self.root(int(value))
        ids=np.unique(tile);ids=ids[ids>0];mapping={}
        for value in ids:
            mapping[int(value)]=len(self.parents);self.parents.append(len(self.parents))
        if known.any() and ids.size:
            shared=known&(old>0)&(tile>0);pairs,counts=np.unique(np.stack([old[shared],tile[shared]],axis=1),axis=0,return_counts=True)
            old_ids,old_counts=np.unique(old[known],return_counts=True);new_ids,new_counts=np.unique(tile[known],return_counts=True)
            a=dict(zip(old_ids,old_counts));b=dict(zip(new_ids,new_counts));candidates=[]
            for (left,right),intersection in zip(pairs,counts):
                iou=intersection/(a[left]+b[right]-intersection)
                if intersection>=self.min_shared and iou>=self.threshold:candidates.append((int(left),int(right)))
            for left,right in candidates:
                if sum(l==left for l,r in candidates)==1 and sum(r==right for l,r in candidates)==1:
                    self.parents[mapping[right]]=self.root(left);self.matches+=1
                else:self.ambiguous+=1
        translated=np.zeros(tile.shape,np.uint32)
        for local,global_id in mapping.items():translated[tile==local]=self.root(global_id)
        yy=np.minimum(np.arange(h)+1,h-np.arange(h))[:,None]
        xx=np.minimum(np.arange(w)+1,w-np.arange(w))[None,:]
        weights=np.minimum(yy,xx).astype(np.float32)
        previous=self.weight[y:y+h,x:x+w];owns=(~known)|(weights>previous)
        view[owns]=translated[owns];previous[owns]=weights[owns];known[:]=True
    def finish(self):
        result=self.labels.copy()
        for value in np.unique(result):
            if value:result[self.labels==value]=self.root(int(value))
        ids=np.unique(result);ids=ids[ids>0];final=np.zeros_like(result)
        for number,value in enumerate(ids,1):final[result==value]=number
        return final,{'objects':len(ids),'matched_pairs':self.matches,'ambiguous_pairs':self.ambiguous}
