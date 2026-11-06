#!/usr/bin/env python3
"""Reproduce the paper's inference from saved or reconstructed conductances.

This command does not reconstruct conductances or redigitize source templates.
It writes only to the selected output directory and checks all three alignment
scenarios against the frozen coarse/subset results. The final circuit uses the
subset analysis's joint policy; the intermediate coarse Holm policy is retained
solely to reproduce the historical computation exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy

import release_coarse as coarse
import release_subsets as subsets
from release_cell_influence import panel_tests
from release_templates import CorrectedBasis, TI, NAMES

ROOT = Path(__file__).resolve().parents[1]
CONDUCTANCES = Path('data/extended_dataset/conductance_reversal_bounded_ee_minus20/records.json')
TIMING = Path('data/extended_dataset/connectomics_source_support/timing_evidence.json')
BASIS = Path('data/model_analyses/postI_figure_registration/results.json')
COARSE = Path('data/model_analyses/coarse_connection_contrasts')
SUBSETS = Path('data/model_analyses/inspiratory_subset_contrasts')
INFLUENCE = Path('data/model_analyses/cell_influence_uncertainty/summary.json')
EXPECTED_COUNTS = dict(zip(NAMES, (17, 41, 8, 54, 30)))
RTOL = 1e-8
ATOL = 1e-10


def read(root, path):
    return json.loads((root / path).read_text())


def compare(actual, expected, label):
    """Check frozen fields, allowing numerical roundoff but no decision drift."""
    if isinstance(actual, np.ndarray):
        actual = actual.tolist()
    if isinstance(actual, np.generic):
        actual = actual.item()
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or not set(expected).issubset(actual):
            raise AssertionError(f'{label}: missing frozen fields')
        for key, value in expected.items():
            compare(actual[key], value, f'{label}.{key}')
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f'{label}: length differs')
        # Most of the archive consists of rectangular numerical arrays.
        try:
            a, b = np.asarray(actual), np.asarray(expected)
            numeric = a.dtype.kind in 'iuf' and b.dtype.kind in 'iuf'
        except (TypeError, ValueError):
            numeric = False
        if numeric:
            np.testing.assert_allclose(a, b, atol=ATOL, rtol=RTOL, err_msg=label)
        else:
            for index, (a, b) in enumerate(zip(actual, expected)):
                compare(a, b, f'{label}[{index}]')
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise AssertionError(f'{label}: {actual!r} != {expected!r}')
    elif isinstance(expected, (int, float)):
        if not np.isclose(actual, expected, atol=ATOL, rtol=RTOL):
            raise AssertionError(f'{label}: {actual!r} != {expected!r}')
    elif actual != expected:
        raise AssertionError(f'{label}: values differ')


def keyed_compare(actual, expected, key, label):
    a, b = {r[key]: r for r in actual}, {r[key]: r for r in expected}
    if len(a) != len(actual) or len(b) != len(expected) or a.keys() != b.keys():
        raise AssertionError(f'{label}: duplicate or mismatched identifiers')
    for identifier in b:
        compare(a[identifier], b[identifier], f'{label}:{identifier}')


def omission_table(summary):
    rows = [dict(target=r['target'], sign=r['sign'], omitted_mask=r['omitted_mask'],
                 p_joint=r['p_joint'], rejected=r['rejected']) for r in summary['tests']]
    rows += [dict(target=r['target'], sign=r['sign'],
                  omitted_mask={'post-I': 8, 'aug-E': 16}[r['source']],
                  p_joint=r['p_joint'], rejected=r['supported'])
             for r in summary['coarse_policy'] if r['source'] != 'Inspiratory']
    if len(rows) != 90 or len({(r['target'], r['sign'], r['omitted_mask']) for r in rows}) != 90:
        raise AssertionError('Expected 90 distinct omission hypotheses')
    return rows


def deletion_check(coarse_cells, subset_cells, coarse_directions, subset_directions):
    """Delete whole cells from the saved fixed-template scores; keep all branches."""
    directions = [dict(d, family='Inspiratory') for d in subset_directions]
    directions += [dict(d, omitted_mask=0) for d in coarse_directions[3:]]
    by_cell = {r['cell']: r for r in coarse_cells}
    cells = [dict(cell=r['cell'], phenotype=r['phenotype'],
                  scores=np.concatenate((r['scores'], np.asarray(by_cell[r['cell']]['scores'])[:, 3:]), axis=1))
             for r in subset_cells]
    summary, deletions = [], []
    for target in NAMES:
        selected = [r for r in cells if r['phenotype'] == target]
        for si, sign in enumerate(coarse.SIGNS):
            scores = np.asarray([r['scores'][si] for r in selected])
            full, _ = panel_tests(scores, directions)
            changes = {r['test']: [] for r in full}
            for index, cell in enumerate(selected):
                deleted, _ = panel_tests(np.delete(scores, index, axis=0), directions)
                for original, reduced in zip(full, deleted):
                    if original['test'] != reduced['test']:
                        raise AssertionError('Cell deletion changed hypothesis order')
                    row = dict(target=target, sign=sign, cell=cell['cell'],
                        test=original['test'], kind=original['kind'], source=original['source'],
                        omitted_mask=original['omitted_mask'], full_p_joint=original['p_joint'],
                        deleted_p_joint=reduced['p_joint'], full_supported=original['supported'],
                        deleted_supported=reduced['supported'])
                    deletions.append(row)
                    changes[original['test']].append(row)
            for original in full:
                values = changes[original['test']]
                losses = [r['cell'] for r in values if r['full_supported'] and not r['deleted_supported']]
                gains = [r['cell'] for r in values if not r['full_supported'] and r['deleted_supported']]
                summary.append(dict(target=target, sign=sign, n_cells=len(selected), **original,
                    n_deletions_losing_support=len(losses), n_deletions_gaining_support=len(gains),
                    deleted_p_min=min(r['deleted_p_joint'] for r in values),
                    deleted_p_max=max(r['deleted_p_joint'] for r in values),
                    loss_cells=losses, gain_cells=gains))
    return summary, deletions


def protect_inputs(root, out, inputs):
    """Reject every planned write that could replace a protected input."""
    protected = {p.resolve() for p in inputs}
    identities = {(p.stat().st_dev, p.stat().st_ino) for p in protected if p.exists()}
    outputs = [out / name for name in ('cell_deletion_summary.json', 'cell_deletions.json',
                                      'cell_deletions.csv', 'verification.json')]
    for scenario, _ in coarse.SCENARIOS:
        outputs.append(out / scenario / 'omission_tests.csv')
        outputs.extend(out / scenario / folder / f'{name}.json'
                       for folder in ('coarse', 'subsets')
                       for name in ('records', 'cells', 'contrasts', 'summary'))
    for path in outputs:
        resolved = path.resolve()
        shared_file = resolved.exists() and (resolved.stat().st_dev, resolved.stat().st_ino) in identities
        if resolved in protected or shared_file or resolved.is_relative_to((root / 'data').resolve()):
            raise ValueError(f'Output would overwrite a protected input: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT,
                        help='Release root containing data/ (default: this release).')
    parser.add_argument('--output-dir', type=Path,
                        help='New results directory (default: DATA_ROOT/output/reproduced).')
    parser.add_argument('--conductances', type=Path,
                        help='Reconstructed 168-record JSON list; default uses packaged frozen conductances.')
    args = parser.parse_args()
    root = args.data_root.resolve()
    out = (args.output_dir or root / 'output/reproduced').resolve()
    if out == root or out.is_relative_to(root / 'data') or (root / 'data').is_relative_to(out):
        parser.error('Output must be separate from the frozen data directory.')
    paths = [CONDUCTANCES, TIMING, BASIS, INFLUENCE]
    paths += [folder / f'{name}.json' for folder in (COARSE, SUBSETS)
              for name in ('records', 'cells', 'contrasts', 'summary')]
    conductances = (args.conductances or root / CONDUCTANCES).resolve()
    try:
        protect_inputs(root, out, [root / p for p in paths] + [conductances])
    except ValueError as error:
        parser.error(str(error))
    hashes = {str(p): coarse.sha(root / p) for p in paths}
    supplied_hash = coarse.sha(conductances)
    supplied = json.loads(conductances.read_text())
    if not isinstance(supplied, list):
        raise ValueError('Conductances input must be a JSON list of recording objects')
    rows = [r for r in supplied if r['status'] == 'ok' and r['phase_coordinate'] == 'two_part']
    if args.conductances and len(rows) != len(supplied):
        raise ValueError('Reconstructed input must contain only the selected successful two-part recordings')
    timing = {r['source_path']: r for r in read(root, TIMING)['records']}
    frozen_coarse = {name: read(root, COARSE / f'{name}.json')
                     for name in ('records', 'cells', 'contrasts', 'summary')}
    frozen_subsets = {name: read(root, SUBSETS / f'{name}.json')
                      for name in ('records', 'cells', 'contrasts', 'summary')}
    if len(rows) != 168 or len({r['source_path'] for r in rows}) != 168:
        raise AssertionError('Expected 168 distinct selected recordings')
    basis = CorrectedBasis(root / BASIS)
    results = {}
    for scenario, landmark in coarse.SCENARIOS:
        cache, records = {}, []
        for row in rows:
            ev = timing[row['source_path']]
            if ev['source_sha256'] != row['source_sha256']:
                raise AssertionError('Timing and conductance source hashes differ')
            if any(row['chosen_epoch'][key] != value for key, value in ev['chosen_epoch'].items()):
                raise AssertionError('Timing and conductance epochs differ')
            ti = float(ev['operational_ie_phase_by_landmark'][landmark])
            if landmark == 'fall50':
                np.testing.assert_allclose(ti, TI, atol=1e-14, rtol=0)
                ti = TI
            if ti not in cache:
                matrix = basis.matrix(ti)
                cache[ti] = matrix, coarse.make_contrasts(matrix), subsets.make_directions(matrix)
            matrix, coarse_directions, _ = cache[ti]
            records.append(coarse.fit_record(row, matrix, coarse_directions, ti))
        cells = coarse.collapse_cells(records)
        if {name: sum(c['phenotype'] == name for c in cells) for name in NAMES} != EXPECTED_COUNTS:
            raise AssertionError('Cell cohort or phenotype counts changed')
        coarse_summary = coarse.summarize(cells)
        coarse_archive = [dict(ti=ti, matrix=a, directions=d) for ti, (a, d, _) in sorted(cache.items())]
        keyed_compare(records, frozen_coarse['records'][scenario], 'source_path', scenario + '.coarse.records')
        keyed_compare(cells, frozen_coarse['cells'][scenario], 'cell', scenario + '.coarse.cells')
        compare(coarse_archive, frozen_coarse['contrasts'][scenario], scenario + '.coarse.contrasts')
        compare(coarse_summary, frozen_coarse['summary'][scenario], scenario + '.coarse.summary')
        subset_records = [subsets.analyze_record(r, cache[r['ti']][0], cache[r['ti']][2]) for r in records]
        subset_cells = subsets.aggregate(subset_records, cells)
        subset_summary = subsets.summarize(subset_cells, next(iter(cache.values()))[2], coarse_summary)
        subset_archive = [dict(ti=ti, directions=d, source_matrix_rank=int(np.linalg.matrix_rank(a)),
                               source_matrix_condition=float(np.linalg.cond(a)))
                          for ti, (a, _, d) in sorted(cache.items())]
        keyed_compare(subset_records, frozen_subsets['records'][scenario], 'source_path', scenario + '.subset.records')
        keyed_compare(subset_cells, frozen_subsets['cells'][scenario], 'cell', scenario + '.subset.cells')
        compare(subset_archive, frozen_subsets['contrasts'][scenario], scenario + '.subset.contrasts')
        compare(subset_summary, frozen_subsets['summary'][scenario], scenario + '.subset.summary')
        tests = omission_table(subset_summary)
        compare(tests, omission_table(frozen_subsets['summary'][scenario]), scenario + '.90_omissions')
        for folder, values in [('coarse', dict(records=records, cells=cells, contrasts=coarse_archive, summary=coarse_summary)),
                               ('subsets', dict(records=subset_records, cells=subset_cells, contrasts=subset_archive, summary=subset_summary))]:
            for name, value in values.items():
                if name in ('records', 'cells'):
                    value = [{k: v for k, v in row.items() if k != 'subset_prediction'} for row in value]
                coarse.save(out / scenario / folder / f'{name}.json', value)
        coarse.csv_save(out / scenario / 'omission_tests.csv', tests)
        results[scenario] = dict(cells=len(cells), recordings=len(records), unique_tests=len(tests),
            rejected_subsets=sum(r['rejected'] for r in subset_summary['tests']),
            supported_coarse=sum(r['supported'] for r in subset_summary['coarse_policy']),
            individually_required=sum(len(r['individually_required']) for r in subset_summary['panels']),
            frozen_arrays_and_decisions_match=True)
        print(f'{scenario}: reproduced 168 recordings, 150 cells and 90 omission tests.', flush=True)

    # These inputs are frozen cell scores, after verification against the fresh fit.
    primary = 'fixed_fall50'
    influence, deletions = deletion_check(frozen_coarse['cells'][primary], frozen_subsets['cells'][primary],
        frozen_coarse['contrasts'][primary][0]['directions'], frozen_subsets['contrasts'][primary][0]['directions'])
    expected = read(root, INFLUENCE)['hypotheses']
    expected_index = {(r['target'], r['sign'], r['test']): r for r in expected}
    for row in influence:
        saved = expected_index[row['target'], row['sign'], row['test']]
        compare(row, {key: saved[key] for key in row}, 'cell_deletion:' + str((row['target'], row['sign'], row['test'])))
    if len(influence) != 100 or len(deletions) != 3000 or len(expected_index) != 100:
        raise AssertionError('Cell-deletion audit dimensions changed')
    # 100 displayed summaries include the 10 all-inspiratory tests twice.
    coarse.save(out / 'cell_deletion_summary.json', influence)
    coarse.save(out / 'cell_deletions.json', deletions)
    coarse.csv_save(out / 'cell_deletions.csv', deletions)
    if hashes != {str(p): coarse.sha(root / p) for p in paths}:
        raise AssertionError('A frozen input changed during reproduction')
    if supplied_hash != coarse.sha(conductances):
        raise AssertionError('The conductances input changed during reproduction')
    sensitivity = {}
    first = omission_table(frozen_subsets['summary'][primary])
    for scenario, _ in coarse.SCENARIOS[1:]:
        other = omission_table(frozen_subsets['summary'][scenario])
        changes = sum(a['rejected'] != b['rejected'] for a, b in zip(first, other))
        if changes:
            raise AssertionError('Published timing sensitivity decisions changed')
        sensitivity[scenario] = dict(changed_omission_decisions=changes)
    coarse.save(out / 'verification.json', dict(inputs_sha256=hashes, inputs_unchanged=True,
        conductances_input=dict(kind='provided' if args.conductances else 'packaged',
            path=str(conductances.relative_to(root)) if conductances.is_relative_to(root) else conductances.name,
            sha256=supplied_hash, unchanged=True),
        numpy=np.__version__, scipy=scipy.__version__, numeric_tolerance=dict(rtol=RTOL, atol=ATOL),
        scenarios=results, timing_sensitivity=sensitivity,
        cell_deletion=dict(displayed_hypotheses=100, unique_primary_hypotheses=90,
                           deletion_test_rows=3000, frozen_summary_matches=True),
        note='Whole-cell influence only; no raw-record or cycle-jackknife reconstruction.'))
    print(f'Cell deletion: all 100 displayed summaries match; wrote {out}', flush=True)


if __name__ == '__main__':
    main()
