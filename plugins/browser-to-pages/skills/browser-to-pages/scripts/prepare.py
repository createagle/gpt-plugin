#!/usr/bin/env python3
"""Convert Browser captures, cache image files and checkpoint Page import jobs."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.import-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []


class Tree(HTMLParser):
    VOID = {'img','br','hr','input','source','wbr','meta','link'}
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node(); self.stack = [self.root]
        self.feed(html); self.close()
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs); self.stack[-1].children.append(n)
        if tag not in self.VOID: self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID: self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]; return
    def handle_data(self, data): self.stack[-1].children.append(data)


def text(n):
    return n if isinstance(n, str) else ''.join(text(c) for c in n.children)


def inline_code(value):
    fence = '`' * max(1, max(map(len, re.findall(r'`+', value)), default=0)+1)
    pad = ' ' if value.startswith(('`',' ')) or value.endswith(('`',' ')) else ''
    return fence + pad + value + pad + fence


def code_block(value, language):
    if value.startswith(('npm ', 'npx ', 'mkdir ', 'cd ')): language = 'bash'
    language = language if re.fullmatch(r'[\w+.-]+', language or '') else 'text'
    fence = '`' * max(3, max(map(len, re.findall(r'`+', value)), default=0)+1)
    return fence + language + '\n' + value + ('' if value.endswith('\n') else '\n') + fence


def convert(n, base, assets, declarations):
    if isinstance(n, str): return re.sub(r'([\\`*\[\]_])', r'\\\1', n)
    tag = n.tag
    if tag in {'style','script'}: return ''
    if tag in {'iframe','video','audio','canvas','svg','math','picture','table','mark'}:
        raise ValueError(f'Needs documented Pages adaptation: <{tag}>')
    if tag == 'img':
        src = n.attrs.get('src','')
        match = next((i for i in declarations if i.get('src') == src), None)
        if not match and len(declarations) == 1: match = declarations[0]
        src = urljoin(base, match['src'] if match else src)
        if urlparse(src).scheme not in {'http','https'}: raise ValueError('Image needs Browser download')
        index = len(assets); assets.append({'src':src,'alt':n.attrs.get('alt','')})
        return '{{IMAGE' + str(index) + '}}'
    if tag == 'code': return inline_code(text(n))
    if tag == 'pre':
        c = next((c for c in n.children if isinstance(c, Node) and c.tag=='code'), n)
        m = re.search(r'language-([^\s]+)', c.attrs.get('class',''))
        return code_block(text(c), m.group(1) if m else 'text')
    if tag == 'br': return '  \n'
    if tag == 'hr': return '\n\n---\n\n'
    if tag == 'input':
        if n.attrs.get('type') != 'checkbox': raise ValueError('Form inside article')
        return '[x] ' if 'checked' in n.attrs else '[ ] '
    if tag in {'ul','ol'}:
        rows=[]; start=int(n.attrs.get('start',1))
        for i,li in enumerate(c for c in n.children if isinstance(c,Node) and c.tag=='li'):
            value=''.join(convert(c,base,assets,declarations) for c in li.children).strip()
            if not value: continue
            prefix=f'{start+i}. ' if tag=='ol' else '- '
            lines=value.splitlines()
            rows.append(prefix+lines[0]+''.join('\n'+' '*len(prefix)+line for line in lines[1:]))
        return '\n\n'+'\n'.join(rows)+'\n\n'
    value=''.join(convert(c,base,assets,declarations) for c in n.children)
    if tag in {'strong','b'}: return '**'+value+'**'
    if tag in {'em','i'}: return '*'+value+'*'
    if tag in {'del','s'}: return '~~'+value+'~~'
    if tag == 'a':
        href=n.attrs.get('href','')
        if urlparse(href).scheme in {'javascript','data'}: raise ValueError('Unsupported link scheme')
        target=urljoin(base,href)
        if re.search(r'[\s()]',target): target='<'+target+'>'
        return '['+value+']('+target+')' if href else value
    if re.fullmatch(r'h[1-6]',tag): return '\n\n'+'#'*int(tag[1])+' '+value.strip()+'\n\n'
    if tag=='blockquote': return '\n\n'+'\n'.join('> '+line for line in value.strip().splitlines())+'\n\n'
    if tag in {'p','div','section','article','figure','figcaption'}: return '\n\n'+value.strip()+'\n\n'
    if tag not in {'','span','li','small'}: raise ValueError(f'Needs manual adaptation: <{tag}>')
    return value


def image_type(b):
    if b.startswith(b'\x89PNG\r\n\x1a\n'): return '.png'
    if b.startswith(b'\xff\xd8\xff'): return '.jpg'
    if b[:6] in (b'GIF87a',b'GIF89a'): return '.gif'
    if b[:4]==b'RIFF' and b[8:12]==b'WEBP': return '.webp'
    raise ValueError('Response is not PNG/JPEG/GIF/WebP')


def prepare(capture_path, job_path, source_url=None, title=None, workers=8, cache_only=False):
    capture=json.loads(Path(capture_path).read_text())
    blocks=capture if isinstance(capture,list) else capture['blocks']
    source_url=source_url or (capture.get('source_url') if isinstance(capture,dict) else None)
    title=title or (capture.get('title') if isinstance(capture,dict) else None)
    if not source_url or not title: raise ValueError('Source URL and title required')
    raw_hash=digest(json.dumps(blocks,sort_keys=True).encode())
    old=json.loads(Path(job_path).read_text()) if Path(job_path).exists() else {}
    if old and (old['source_url']!=source_url or old['title']!=title): raise ValueError('Job belongs to another source')
    if old and old['source_hash']!=raw_hash and old.get('page_id'): raise ValueError('Source changed; reconcile managed Page')
    units=[]; assets=[]
    for p in blocks:
        if p.get('code'):
            units.append(code_block(p['code']['text'],p['code'].get('language','text'))); continue
        html='<'+p['tag'].lower()+'>'+p['html']+'</'+p['tag'].lower()+'>'
        value=convert(Tree(html).root,source_url,assets,p.get('images',[])).strip()
        if value: units.append(value)
    folder=Path(job_path).resolve().parent/'assets'; folder.mkdir(parents=True,exist_ok=True)
    def download(asset):
        key=digest(asset['src'].encode()); existing=sorted(folder.glob(key+'.*'))
        if existing:
            path=existing[0]; data=path.read_bytes(); image_type(data)
        else:
            if cache_only: raise ValueError('Missing cached image: '+asset['src'])
            req=Request(asset['src'].split('#')[0],headers={'User-Agent':'Mozilla/5.0','Referer':source_url})
            with urlopen(req,timeout=45) as response: data=response.read(10*1024*1024+1)
            if len(data)>10*1024*1024: raise ValueError('Image exceeds Pages 10 MiB limit')
            path=folder/(key+image_type(data))
            fd,temp=tempfile.mkstemp(dir=folder,prefix='.image-')
            try:
                with os.fdopen(fd,'wb') as f: f.write(data)
                os.replace(temp,path)
            finally:
                if os.path.exists(temp): os.unlink(temp)
        return {**asset,'path':str(path),'sha256':digest(data),'bytes':len(data)}
    unique=list(dict.fromkeys(a['src'] for a in assets)); lookup={a['src']:a for a in assets}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        files=dict(zip(unique,pool.map(download,(lookup[u] for u in unique))))
    assets=[{**files[a['src']],'alt':a['alt']} for a in assets]
    job={**old,'schema_version':1,'title':title,'source_url':source_url,'source_hash':raw_hash,
         'units':units,'images':assets,'uploads':old.get('uploads',{}),'state':old.get('state','prepared')}
    save(job_path,job); return job


def finalize(job):
    def replacement(m):
        image=job['images'][int(m[1])]; upload=job['uploads'].get(image['sha256'],{})
        if not upload.get('file_access_confirmed') or not upload.get('markdown'): raise ValueError('Attachment unconfirmed')
        if upload.get('page_id')!=job.get('page_id'): raise ValueError('Attachment belongs to another Page')
        return upload['markdown']
    return [re.sub(r'\{\{IMAGE(\d+)\}\}',replacement,unit) for unit in job['units']]


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare'); a.add_argument('--capture',required=True); a.add_argument('--job',required=True)
    a.add_argument('--source-url'); a.add_argument('--title'); a.add_argument('--workers',type=int,default=8)
    a.add_argument('--cache-only',action='store_true')
    a=sub.add_parser('checkpoint'); a.add_argument('--job',required=True); a.add_argument('--patch',required=True)
    a=sub.add_parser('show'); a.add_argument('--job',required=True)
    a=sub.add_parser('finalize'); a.add_argument('--job',required=True)
    args=p.parse_args()
    if args.command=='prepare':
        job=prepare(args.capture,args.job,args.source_url,args.title,args.workers,args.cache_only)
        print(json.dumps({'blocks':len(job['units']),'images':len(job['images']),'job':args.job})); return
    job=json.loads(Path(args.job).read_text())
    if args.command=='checkpoint':
        patch=json.loads(args.patch)
        if 'uploads' in patch: patch['uploads']={**job.get('uploads',{}),**patch['uploads']}
        job.update(patch); save(args.job,job)
    if args.command=='finalize': print(json.dumps(finalize(job),ensure_ascii=False)); return
    print(json.dumps(job,ensure_ascii=False))


if __name__=='__main__': main()
