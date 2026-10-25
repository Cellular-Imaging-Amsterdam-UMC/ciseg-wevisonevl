"""Compare stitched instance IDs with the independent organoid consensus IDs."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
import zarr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import write_json
from tools.experimental_tiling import starts


def metrics(truth,prediction):
    gt=np.unique(truth);gt=gt[gt>0];pr=np.unique(prediction);pr=pr[pr>0]
    iou=np.zeros((len(gt),len(pr)),float)
    for i,g in enumerate(gt):
        mask=truth==g
        candidates,counts=np.unique(prediction[mask],return_counts=True)
        for p,intersection in zip(candidates,counts):
            if not p:continue
            j=int(np.searchsorted(pr,p));iou[i,j]=intersection/(int(mask.sum())+int(np.count_nonzero(prediction==p))-intersection)
    a,b=linear_sum_assignment(-iou);tp=int(np.sum(iou[a,b]>=.5))
    fg_gt=truth>0;fg_pr=prediction>0;intersection=int((fg_gt&fg_pr).sum())
    return {'reference_instances':len(gt),'predicted_instances':len(pr),'matched_instances_iou_05':tp,
            'instance_f1_iou_05':2*tp/(len(gt)+len(pr)) if len(gt)+len(pr) else 1.,
            'foreground_dice':2*intersection/(int(fg_gt.sum())+int(fg_pr.sum())) if fg_gt.any() or fg_pr.any() else 1.}


if __name__=='__main__':
    reference=np.load(ROOT/'publicdata/ome-zarr/organoids_im10_reference.npy',allow_pickle=False)
    folder=ROOT/'test-results/tiling-research';rows=json.loads((folder/'benchmark.json').read_text())
    baseline=ROOT/'test-results/published-gallery/organoids_im10/organoids/2048/organoids_im10__wevisonevl.ome.zarr'
    root=zarr.open_group(str(baseline),mode='r');labels=root['labels/wevisone_organoids/0'][0,0,0]
    report=[{'mode':'whole image','model_view_max_side':1024,**metrics(reference,labels)}]
    for row in rows:
        if row['status']!='complete':report.append(row);continue
        labels=np.load(folder/f"tiles-{row['tile_size']}.npz",allow_pickle=False)['labels']
        overlaps=[]
        for length in reference.shape:
            positions=starts(length,row['tile_size'],row['overlap'])
            overlaps.extend(row['tile_size']-(b-a) for a,b in zip(positions,positions[1:]))
        report.append({**row,**metrics(reference,labels),'actual_axis_overlap_range_px':[min(overlaps),max(overlaps)]})
    write_json(folder/'evaluation.json',report)
    print(json.dumps(report,indent=2))
