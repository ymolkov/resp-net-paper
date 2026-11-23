#!/usr/bin/env python3
"""Verify the paper-only release inventory, cohort, documentation, and scope."""
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT/path).read_text())


def main():
    manifest=read('release-manifest.json')
    seen=set()
    for row in manifest['files']:
        rel=Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel) in seen:
            raise ValueError(f'Invalid release path: {rel}')
        path=ROOT/rel
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing/nonportable file: {rel}')
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
            raise ValueError(f'Release checksum mismatch: {rel}')
        seen.add(str(rel))
    ignored_parts={'.git','.venv','__pycache__'}
    actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()
            and not any(x in ignored_parts for x in p.relative_to(ROOT).parts)
            and not str(p.relative_to(ROOT)).startswith(('output/reproduced/','output/playwright/'))
            and p.name!='release-manifest.json'}
    workflow='.github/workflows/pages.yml'
    if workflow in actual:
        path=ROOT/workflow
        if path.is_symlink() or path.read_bytes()!=(ROOT/'docs/pages-workflow.yml.example').read_bytes():
            raise ValueError('Active Pages workflow differs from the verified template')
        actual.remove(workflow)
    if actual!=seen:
        raise ValueError(f'Unexpected release files: {sorted(actual-seen)}; missing: {sorted(seen-actual)}')
    with (ROOT/'data/manuscript_reporting/records.csv').open() as stream:
        rows=list(csv.DictReader(stream))
    ids={r['source_path'] for r in rows}
    assert len(rows)==len(ids)==168 and len({r['cell'] for r in rows})==150
    assert sum(r['mode']=='CC' for r in rows)==150
    assert sum(r['mode']=='VC' for r in rows)==18
    raw=read('data/extended_dataset/raw_archive_manifest.json')['files']
    assert len(raw)==168 and {r['archive_relative_path'] for r in raw}==ids
    raw_root=ROOT/'data/extended_dataset/raw_archive'
    assert {str(p.relative_to(raw_root)) for p in raw_root.rglob('*') if p.is_file()}==ids
    source_hashes={r['source_path']:r['source_sha256'] for r in rows}
    for r in raw:
        p=ROOT/r['path']
        assert digest(p)==r['sha256']==source_hashes[r['archive_relative_path']]
        assert 0<r['numeric_prefix_bytes']<=r['size_bytes']==p.stat().st_size
        assert r['size_bytes']-r['numeric_prefix_bytes']==r['excluded_suffix_bytes']
    for file,key in [('current_inventory/recordings.jsonl',None),
                     ('full_qc/run_config.json','configs'),('full_qc/records.json',None),
                     ('conductance_reversal_bounded_ee_minus20/records.json',None),
                     ('connectomics_source_support/timing_evidence.json','records')]:
        path=ROOT/'data/extended_dataset'/file
        data=[json.loads(x) for x in path.read_text().splitlines()] if file.endswith('.jsonl') else json.loads(path.read_text())
        if key:data=data[key]
        assert len(data)==168 and {r['source_path'] for r in data}==ids,file
    for folder in ('coarse_connection_contrasts','inspiratory_subset_contrasts'):
        records=read(f'data/model_analyses/{folder}/records.json')
        cells=read(f'data/model_analyses/{folder}/cells.json')
        assert set(records)==set(cells)=={'fixed_fall50','nerve_fall40','nerve_fall60'}
        for scenario in records:
            assert len(records[scenario])==168 and {r['source_path'] for r in records[scenario]}==ids
            assert len(cells[scenario])==150
    forbidden=('.openai/','models/','docs/sources/','literature_review/','paper/paper.tex','AGENTS.md')
    assert not [p for p in seen if any(p.startswith(x) for x in forbidden)]
    assert not [p for p in seen if '.openai' in Path(p).parts]
    for path in ROOT.rglob('*.md'):
        if any(x in ignored_parts for x in path.relative_to(ROOT).parts):continue
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if re.match(r'\w+://',target) or target.startswith('#'):continue
            if not (path.parent/target.split('#')[0]).exists():
                raise ValueError(f'Broken documentation link: {path.relative_to(ROOT)} -> {target}')
    print(f'Verified {len(seen)} release files, exactly 168 recordings / 150 cells, parse scopes, and documentation links.')


if __name__=='__main__':
    main()
