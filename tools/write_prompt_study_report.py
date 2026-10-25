"""Publish an English, image-free audit of prompt comparisons and explicit selection."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT


if __name__=='__main__':
    sources=[ROOT/'test-results/prompt-study-v2/summary.json',ROOT/'test-results/em-prompt-study-v2/summary.json',ROOT/'test-results/em-extra-prompt-study-v2/summary.json']
    results={}
    for path in sources:results.update(json.loads(path.read_text()))
    selection=json.loads((ROOT/'gallery_selection.json').read_text())
    chosen={s['selected_prompt_study'] for s in selection['examples'] if s.get('selected_prompt_study')}
    lines=['# Prompt comparison and gallery selection','',
           'The main gallery is a positively selected demonstration set, **not a representative accuracy benchmark**. Unconvincing candidates and EM Z projections are excluded. Raw comparisons remain local; this page preserves their audit without rejected overlays.','',
           '## Protocol','',
           '- Official segmentation API and trained target-description template; no rewritten freeform system instruction.',
           '- Pinned 4B weights, temperature 0, threshold 0.5, decoder batch 1 and a 4096-token budget.',
           '- Four descriptions per fixed fluorescence/DAB view; three per native 2D EM patch.',
           '- Fixed recorded normalization per view. No color threshold or manual annotation was substituted for a VLM mask.',
           '- 28 fluorescence/DAB and 24 EM candidates: **52 tested prompts**. EM exploration retrieved 33 paired patches; 8 native fields were tested.',
           '- Selected combinations were rerun through the workflow with native labels and calibrated CSVs.',
           '- The two retained EM patches share an acquisition and were selected after comparison; their scores are not held-out generalization estimates.','',
           '## Selected changes','',
           '| Example | Retained description / result | Selection rationale |','| --- | --- | --- |']
    for sample in selection['examples']:
        if not sample.get('selected_prompt_study'):continue
        case=results[sample['selected_prompt_study']]
        value=f"{case['text']} — {case.get('objects',0)} predicted objects"
        if 'foreground_dice' in case:value+=f", foreground Dice {case['foreground_dice']:.3f}"
        lines.append(f"| `{sample['name']}` | {value} | {sample['review']} |")
    lines+=['','## Interpretation','',
            'Concrete visible appearance helped. The green vessel profile changed from a near-whole-field mask to a local structure. The plant query names green bundles and excludes the outer ring. A native 192 × 192 Ki67 ROI makes brown nuclei distinguishable from blue negatives. The fiber example is explicitly network-level, not complete individual axon tracing.','',
            'Full-field DAB and most red-process/spine candidates were not convincing enough to retain. Technical completion or a nonempty mask was never sufficient. No manual references were supplied for fluorescence/DAB, so these improvements are qualitative.','',
            'EM used native single-frame micrographs without projection. Paired CEM-MitoLab references support foreground Dice near 0.965 and 0.936. These scores do not establish perfect instance identity or broad EM accuracy.','',
            'Repeatability check: all six selected study inputs matched the workflow RGB inputs exactly. Five rerun binary masks were identical; the neurofilament mask differed at 30 of 1,048,576 pixels (0.0029%). Temperature 0 did not guarantee bit-identical masks in every rerun. The gallery contains the final workflow outputs.','',
            '## All tested candidates','',
            '| Study view | Target description | Objects | Foreground fraction | Foreground Dice, if annotated | Selected |',
            '| --- | --- | ---: | ---: | ---: | --- |']
    for key,case in results.items():
        dice=f"{case['foreground_dice']:.3f}" if 'foreground_dice' in case else '—'
        text=case['text'].replace('|','/')
        lines.append(f"| `{case['sample']}` | {text} | {case.get('objects','—')} | {case.get('coverage',0):.3f} | {dice} | {'Yes' if key in chosen else 'No'} |")
    lines+=['','## References','',
            '- [Official pixel-level cookbook](https://github.com/Tencent/WeVisOne-VL/blob/main/tutorials/03_segmentation_matting_pipeline.ipynb)',
            '- [Official task prompt builder](https://github.com/Tencent/WeVisOne-VL/blob/main/wevisone_vl/prompts.py)',
            '- [CEM-MitoLab, EMPIAR-11037](https://www.ebi.ac.uk/empiar/EMPIAR-11037/)',
            '- [CEM/MitoNet data publication](https://doi.org/10.1016/j.cels.2022.12.006)',
            '- [QuPath Ki67 source images](https://zenodo.org/records/18302140)','']
    (ROOT/'docs/prompt-study.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print('Wrote audit for',len(results),'prompt candidates')
