"""Dependency-free checks for the committed GitHub Pages site and its published assets."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote,urlsplit


class Document(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[];self.images=[]
    def handle_starttag(self,tag,attributes):
        attrs=dict(attributes)
        if 'id' in attrs:self.ids.append(attrs['id'])
        for name in ['href','src']:
            if attrs.get(name):self.links.append(attrs[name])
        if tag=='img':self.images.append(attrs)


def check(root):
    root=root.resolve();documents={};errors=[]
    for file in root.glob('*.html'):
        parser=Document();parser.feed(file.read_text(encoding='utf-8'));documents[file]=parser
        if len(parser.ids)!=len(set(parser.ids)):errors.append(f'Duplicate id: {file.name}')
        if any(not i.get('alt') for i in parser.images):errors.append(f'Image missing alt text: {file.name}')
        text=file.read_text(encoding='utf-8')
        if 'data-theme="dark"' not in text or 'data-theme-toggle' not in text:errors.append('Missing default Dark theme or theme button: '+file.name)
        if '<html lang="en"' not in text:errors.append('Public page must use English: '+file.name)
    for file,parser in documents.items():
        for link in parser.links:
            url=urlsplit(link)
            if url.scheme or url.netloc:continue
            target=(file.parent/unquote(url.path)).resolve() if url.path else file
            if not target.is_relative_to(root):errors.append(f'Link escapes published docs: {file.name}: {link}')
            elif not target.exists():errors.append(f'Missing file: {file.name}: {link}')
            elif url.fragment and target in documents and unquote(url.fragment) not in documents[target].ids:errors.append(f'Missing anchor: {file.name}: {link}')
    data=json.loads((root/'assets/examples.json').read_text(encoding='utf-8'))
    selection_path=root.parent/'gallery_selection.json'
    if selection_path.exists():
        selected=json.loads(selection_path.read_text(encoding='utf-8'))
        expected={e['name'] for e in selected['examples']}
        if {e['name'] for e in data['examples']}!=expected:errors.append('Gallery does not match reviewed selection')
        expected_labels={e['name']:set(e['labels']) for e in selected['examples']}
        for example in data['examples']:
            if {label['name'] for label in example['labels']}!=expected_labels.get(example['name']):errors.append('Unreviewed label set: '+example['name'])
    for sample in data['examples']:
        if sample.get('reference'):
            for path in sample['reference'].values():
                if not (root/path).is_file():errors.append('Missing dataset reference asset: '+path)
        if data.get('curated') and sample['category']=='EM' and sample['z_planes']>1:errors.append('EM Z projection in curated examples')
        if not (root/sample['input']).is_file():errors.append('Missing source preview: '+sample['name'])
        for label in sample['labels']:
            if data.get('curated') and (label['status']!='complete' or label.get('first_frame_objects',0)==0):errors.append('Unselected/empty result in curated examples: '+sample['name'])
            for key in ['overlay','download']:
                if label.get(key) and not (root/label[key]).is_file():errors.append('Missing result asset: '+str(label[key]))
            if label['status'] in ['complete','partial'] and (not label['overlay'] or not label['download']):errors.append('Successful result without real assets: '+sample['name'])
            if label['status']=='failed' and label.get('overlay'):errors.append('Failed prediction shown as successful mask: '+sample['name'])
    for file in root.rglob('*'):
        if file.is_file() and file.suffix in ['.html','.md','.json','.js','.css']:
            text=file.read_text(encoding='utf-8')
            if re.search(r'\b[A-Z]:[\\/]',text):errors.append('Local workstation path in public content: '+str(file.relative_to(root)))
            if re.search(r'gh[pousr]_[A-Za-z0-9]{20,}',text):errors.append('Credential-like value in '+str(file.relative_to(root)))
    if errors:raise SystemExit('\n'.join(errors))
    print(json.dumps({'html_pages':len(documents),'examples':len(data['examples']),'results':data['summary'],'status':'passed'}))


if __name__=='__main__':check(Path(sys.argv[1] if len(sys.argv)>1 else 'docs'))
