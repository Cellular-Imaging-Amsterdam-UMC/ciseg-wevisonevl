import numpy as np
import pytest
from tools.experimental_tiling import windows,InstanceStitcher


def test_tile_layout_covers_odd_edges():
    covered=np.zeros((133,197),bool)
    for y,x,h,w in windows(covered.shape,64,16):covered[y:y+h,x:x+w]=True
    assert covered.all()


def test_research_prototype_rejects_unbounded_allocation():
    with pytest.raises(ValueError,match='production large-image streaming is not implemented'):
        InstanceStitcher((10000,10000))


def test_same_object_across_four_tiles_has_one_final_id():
    truth=np.zeros((160,160),np.uint32);truth[40:130,40:130]=1
    stitched=InstanceStitcher(truth.shape)
    for index,(y,x,h,w) in enumerate(windows(truth.shape,96,32)):
        crop=(truth[y:y+h,x:x+w]>0).astype(np.uint32)*(index+1)
        stitched.add(crop,y,x)
    result,stats=stitched.finish()
    np.testing.assert_array_equal(result,truth)
    assert stats['objects']==1 and stats['matched_pairs']>0


def test_neighboring_objects_are_not_merged_by_touching_edges():
    truth=np.zeros((100,160),np.uint32);truth[15:70,40:80]=1;truth[15:70,80:120]=2
    stitched=InstanceStitcher(truth.shape)
    for y,x,h,w in windows(truth.shape,96,32):stitched.add(truth[y:y+h,x:x+w],y,x)
    result,stats=stitched.finish()
    assert stats['objects']==2
    assert result[30,70]!=result[30,90]


def test_ambiguous_split_is_flagged_instead_of_fusing_neighbors():
    stitched=InstanceStitcher((40,80),threshold=.45)
    old=np.zeros((40,60),np.uint32);old[5:35,20:60]=1;stitched.add(old,0,0)
    new=np.zeros((40,60),np.uint32);new[5:35,:20]=1;new[5:35,20:40]=2
    stitched.add(new,0,20)
    result,stats=stitched.finish()
    assert stats['ambiguous_pairs']==2 and stats['matched_pairs']==0
