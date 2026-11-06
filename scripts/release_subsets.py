"""Scientific helpers copied verbatim from the canonical analysis.

Only imports, module constants and historical command entry points are adapted
for the focused paper release. The source map records each retained definition.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import nnls
from release_coarse import NAMES, SIGNS, ALPHA, REDUNDANCY_TOL, one_sided_test, describe
BRANCHES = 30
MASKS = list(range(1, 8))
DISPLAY_ORDER = [7, 3, 5, 6, 1, 2, 4, 0]
AGGREGATED = ['scores', 'subset_coefficients', 'subset_prediction', 'subset_rmse', 'full_shares', 'profiles']

def members(mask):
    if not isinstance(mask, int) or not 0 <= mask <= 7:
        raise ValueError('Expected a three-bit inspiratory subset')
    return [j for j in range(3) if mask & (1 << j)]

def label(mask):
    return ' + '.join(NAMES[j] for j in members(mask)) if mask else 'None'

def make_directions(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != 5 or not np.isfinite(matrix).all():
        raise ValueError('Expected finite phase-by-five templates')
    if (matrix < 0).any():
        raise ValueError('Source activity must be nonnegative')
    if np.linalg.matrix_rank(matrix) != 5:
        raise ValueError('Closed coefficient-null interpretation requires full column rank')
    result = []
    for mask in MASKS:
        omitted = members(mask)
        retained = [j for j in range(5) if j not in omitted]
        a = matrix[:, retained]
        for j in omitted:
            coef, _ = nnls(a, matrix[:, j], maxiter=3000)
            residual = matrix[:, j] - a @ coef
            norm = np.linalg.norm(residual)
            own = float(residual @ matrix[:, j])
            tol = 1e-9 * max(1., np.linalg.norm(matrix)**2)
            if np.max(residual @ a) > tol or not np.isclose(own, norm**2, atol=tol, rtol=1e-8):
                raise AssertionError('Template NNLS optimality conditions failed')
            estimable = norm > REDUNDANCY_TOL * np.linalg.norm(matrix[:, j])
            w = residual/own if estimable else np.zeros(matrix.shape[0])
            result.append(dict(omitted_mask=mask, omitted=omitted,
                retained=retained, template=NAMES[j], template_index=j,
                estimable=bool(estimable), weights=w,
                relative_residual_norm=float(norm/np.linalg.norm(matrix[:, j])),
                retained_dot_max=float(np.max(residual @ a)),
                residual_norm_squared=float(norm**2), own_dot=own))
    assert len(result) == 12
    return result

def closed_pvalues(local):
    if set(local) != set(MASKS) or any(not 0 <= x <= 1 for x in local.values()):
        raise ValueError('All seven valid local p-values are required')
    return {d: max(p for s, p in local.items() if s & d == d) for d in MASKS}

def minimal_masks(values):
    values = set(values)
    return sorted([a for a in values if not any(b != a and b & a == b for b in values)],
                  key=lambda x: (x.bit_count(), x))

def logical_summary(rejected):
    rejected = set(rejected)
    allowed = [r for r in range(8) if all(r & d for d in rejected)]
    clauses = minimal_masks(rejected)
    smallest = minimal_masks(allowed)
    required = [NAMES[j] for j in range(3) if (1 << j) in rejected]
    if 7 not in rejected:
        wording = 'Inspiratory input not established'
    elif clauses == [7]:
        wording = 'At least one inspiratory source'
    else:
        wording = ' AND '.join(NAMES[members(d)[0]] if d.bit_count() == 1 else
                              '('+' OR '.join(NAMES[j] for j in members(d))+')'
                              for d in clauses)
    options = ' OR '.join(label(r) if r.bit_count() <= 1 else '('+label(r)+')' for r in smallest)
    return dict(minimal_requirement_masks=clauses, requirement=wording,
                individually_required=required, unexcluded_retained_masks=allowed,
                minimal_unexcluded_masks=smallest, minimal_options=options)

def analyze_record(old, matrix, directions):
    pair = np.asarray(old['profiles'], dtype=float)
    if pair.shape != (2, 100) or not np.isfinite(pair).all() or (pair < 0).any():
        raise ValueError('Invalid preserved conductance profiles')
    scores = pair @ np.array([d['weights'] for d in directions]).T
    np.testing.assert_allclose(scores[:, -3:], np.array(old['scores'])[:, :3], atol=1e-12, rtol=0)
    coefficients, predictions, errors = [], [], []
    for mask in range(8):
        keep = members(mask)+[3, 4]
        coef = np.zeros((2, 5))
        for si in range(2):
            coef[si, keep], _ = nnls(matrix[:, keep], pair[si], maxiter=3000)
        prediction = coef @ matrix.T
        coefficients.append(coef)
        predictions.append(prediction)
        errors.append(np.sqrt(np.mean((pair-prediction)**2, axis=1)))
    coefficients, predictions, errors = map(np.array, (coefficients, predictions, errors))
    np.testing.assert_allclose(coefficients[7], old['coefficients'], atol=1e-12, rtol=0)
    for a in range(8):
        for b in range(8):
            if a & b == a and np.any(errors[a] < errors[b]-1e-10):
                raise AssertionError('Adding an available source increased the optimum error')
    return dict(source_path=old['source_path'], cell=old['cell'], phenotype=old['phenotype'],
                mode=old['mode'], ti=old['ti'], scores=scores, profiles=pair,
                subset_coefficients=coefficients, subset_prediction=predictions,
                subset_rmse=errors, full_shares=np.array(old['shares']))

def aggregate(records, old_cells):
    by_path = {r['source_path']: r for r in records}
    cells = []
    for old in old_cells:
        weights = old['record_weights']
        np.testing.assert_allclose(sum(weights.values()), 1., atol=1e-12)
        row = {k: old[k] for k in ['cell', 'phenotype', 'modes', 'n_records', 'source_paths', 'record_weights']}
        for path in weights:
            assert by_path[path]['cell'] == old['cell']
            assert by_path[path]['phenotype'] == old['phenotype']
        for field in AGGREGATED:
            row[field] = sum(weight*np.array(by_path[path][field]) for path, weight in weights.items())
        np.testing.assert_allclose(row['full_shares'], old['shares'], atol=1e-12, rtol=0)
        cells.append(row)
    return cells

def summarize(cells, directions, coarse):
    panels, tests, elementary, fits, allocations, coarse_policy = [], [], [], [], [], []
    for target in NAMES:
        selected = [c for c in cells if c['phenotype'] == target]
        n = len(selected)
        scores = np.array([c['scores'] for c in selected])
        errors = np.array([c['subset_rmse'] for c in selected])
        shares = np.array([c['full_shares'] for c in selected])
        for si, sign in enumerate(SIGNS):
            local = {}
            for mask in MASKS:
                component_tests = []
                for k, d in enumerate(directions):
                    if d['omitted_mask'] == mask:
                        stat = dict(target=target, sign=sign, omitted_mask=mask,
                                    contrast=d['template'], **one_sided_test(scores[:, si, k]))
                        component_tests.append(stat)
                        elementary.append(stat)
                local[mask] = min(1., mask.bit_count()*min(r['p_raw'] for r in component_tests))
            old_family = next(r for r in coarse['families'] if r['target'] == target
                              and r['sign'] == sign and r['source'] == 'Inspiratory')
            np.testing.assert_allclose(local[7], old_family['p_family'], atol=1e-14, rtol=1e-10)
            closed = closed_pvalues(local)
            joint = {mask: min(1., BRANCHES*p) for mask, p in closed.items()}
            rejected = [d for d in MASKS if joint[d] < ALPHA]
            logic = logical_summary(rejected)
            for mask in MASKS:
                tests.append(dict(target=target, sign=sign, n_cells=n,
                    omitted_mask=mask, omitted_sources=label(mask),
                    retained_mask=7 ^ mask, retained_sources=label(7 ^ mask),
                    p_local=local[mask], p_closed=closed[mask], p_joint=joint[mask],
                    rejected=bool(mask in rejected)))
            for mask in DISPLAY_ORDER:
                delta = 100*(errors[:, mask, si]-errors[:, 7, si])
                direct_rejected = False if mask == 7 else (7 ^ mask) in rejected
                assert direct_rejected == (mask not in logic['unexcluded_retained_masks'])
                fits.append(dict(target=target, sign=sign, retained_mask=mask,
                    retained_sources=label(mask), excluded=direct_rejected,
                    minimal_unexcluded=bool(mask in logic['minimal_unexcluded_masks']),
                    p_joint=None if mask == 7 else joint[7 ^ mask],
                    mean_rmse_joint_peak_percent=float(100*errors[:, mask, si].mean()),
                    mean_added_rmse_pp=float(delta.mean()),
                    median_added_rmse_pp=float(np.median(delta)),
                    q25_added_rmse_pp=float(np.quantile(delta, .25)),
                    q75_added_rmse_pp=float(np.quantile(delta, .75))))
            family_total = shares[:, si, :3].sum(axis=1)
            valid = family_total > 1e-12
            ratios = shares[valid, si, :3] / family_total[valid, None]
            for j in range(3):
                winners = shares[:, si, j] - shares[:, si, [k for k in range(3) if k != j]].max(axis=1) > 1e-12
                allocations.append(dict(target=target, sign=sign, source=NAMES[j], n_cells=n,
                    n_defined_ratios=int(valid.sum()), zero_family_cells=int(np.sum(~valid)),
                    n_strictly_largest=int(winners.sum()),
                    share_statistics=describe(shares[:, si, j]),
                    within_family_statistics=describe(ratios[:, j]) if valid.any() else None))
            panels.append(dict(target=target, sign=sign, n_cells=n,
                family_p_joint=joint[7], family_supported=bool(7 in rejected),
                family_share_mean=float(family_total.mean()), **logic,
                mean_profile=np.mean([c['profiles'][si] for c in selected], axis=0),
                mean_subset_predictions=np.mean([c['subset_prediction'][:, si] for c in selected], axis=0)))
    for old in coarse['families']:
        if old['source'] == 'Inspiratory':
            p_joint = next(p['family_p_joint'] for p in panels
                           if p['target'] == old['target'] and p['sign'] == old['sign'])
        else:
            p_joint = min(1., BRANCHES*old['p_family'])
        coarse_policy.append(dict(target=old['target'], sign=old['sign'], source=old['source'],
            old_p_holm=old['p_holm'], old_supported=old['supported'],
            p_joint=p_joint, supported=bool(p_joint < ALPHA), share_mean=old['share_mean']))
    assert len(panels) == 10 and len(tests) == 70 and len(elementary) == 120 and len(fits) == 80
    return dict(panels=panels, tests=tests, elementary=elementary, alternatives=fits,
                allocations=allocations, coarse_policy=coarse_policy)
