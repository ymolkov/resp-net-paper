"""Scientific helpers copied verbatim from the canonical analysis.

Only imports, module constants and historical command entry points are adapted
for the focused paper release. The source map records each retained definition.
"""
from __future__ import annotations
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import nnls
from scipy.stats import shapiro, skew, t
from release_templates import CorrectedBasis, TI, NAMES, holm
SIGNS = ['E', 'I']
FAMILIES = [('Inspiratory', (0, 1, 2)), ('post-I', (3,)), ('aug-E', (4,))]
SCENARIOS = [('fixed_fall50', 'fall50'), ('nerve_fall60', 'fall60'), ('nerve_fall40', 'fall40')]
ALPHA = .05
REDUNDANCY_TOL = 1e-10
FIELDS = ['profiles', 'scores', 'shares', 'coefficients', 'prediction', 'rmse_joint_peak', 'relative_residual_energy']

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, obj):
    def convert(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(type(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, default=convert, allow_nan=False, indent=2) + '\n')

def csv_save(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def make_contrasts(matrix):
    """Template-only separating directions for each coarse absence null."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != 5 or not np.isfinite(matrix).all():
        raise ValueError('Expected a finite phase-by-five source matrix')
    if (matrix < 0).any():
        raise ValueError('Activity templates must be nonnegative')
    directions = []
    for family, omitted in FAMILIES:
        retained = [j for j in range(5) if j not in omitted]
        a = matrix[:, retained]
        for j in omitted:
            target = matrix[:, j]
            coef, _ = nnls(a, target, maxiter=3000)
            residual = target - a @ coef
            norm = np.linalg.norm(residual)
            scale = max(np.linalg.norm(target), np.finfo(float).tiny)
            estimable = norm > REDUNDANCY_TOL * scale
            own = float(residual @ target)
            cross = residual @ a
            tol = 1e-9 * max(1., np.linalg.norm(matrix)**2)
            if np.max(cross) > tol or not np.isclose(own, norm**2, atol=tol, rtol=1e-8):
                raise AssertionError('NNLS separating-direction identity failed')
            weights = residual / own if estimable else np.zeros(len(target))
            directions.append(dict(family=family, template=NAMES[j], source_index=j,
                omitted=list(omitted), retained=retained, estimable=bool(estimable),
                template_approximation_coefficients=coef,
                relative_residual_norm=float(norm / scale),
                retained_dot_max=float(np.max(cross)), own_dot=own,
                residual_norm_squared=float(norm**2), weights=weights))
    return directions

def one_sided_test(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all() or len(values) < 2:
        raise ValueError('Expected at least two finite cell scores')
    n = len(values)
    mean, sd = float(values.mean()), float(values.std(ddof=1))
    se = sd / np.sqrt(n)
    usable = sd > np.finfo(float).eps * max(1., float(np.max(np.abs(values))))
    return dict(n=n, mean=mean, median=float(np.median(values)), sd=sd, sem=float(se),
        q25=float(np.quantile(values, .25)), q75=float(np.quantile(values, .75)),
        minimum=float(values.min()), maximum=float(values.max()),
        n_positive=int(np.sum(values > 0)), n_negative=int(np.sum(values < 0)),
        t_statistic=float(mean / se) if usable else None,
        p_raw=float(t.sf(mean / se, n-1)) if usable else 1.,
        lower95_one_sided=float(mean-t.ppf(.95, n-1)*se) if usable else None,
        ci95_low=float(mean-t.ppf(.975, n-1)*se) if usable else None,
        ci95_high=float(mean+t.ppf(.975, n-1)*se) if usable else None,
        variance_usable=bool(usable),
        skewness=float(skew(values, bias=False)) if usable and n >= 3 else None,
        shapiro_p=float(shapiro(values).pvalue) if usable and n >= 3 else None,
        maximum_mean_change_on_cell_removal=float(np.max(np.abs((values-mean)/(n-1)))))

def describe(values):
    x = np.asarray(values)
    return dict(mean=float(x.mean()), median=float(np.median(x)),
                q25=float(np.quantile(x, .25)), q75=float(np.quantile(x, .75)),
                minimum=float(x.min()), maximum=float(x.max()))

def collapse_cells(records):
    grouped = defaultdict(lambda: defaultdict(list))
    for row in records:
        grouped[row['cell']][row['mode']].append(row)
    cells = []
    for cell, modes in sorted(grouped.items()):
        rows = [r for rs in modes.values() for r in rs]
        labels = {r['phenotype'] for r in rows}
        if len(labels) != 1:
            raise ValueError(f'Inconsistent cell phenotype: {cell}')
        result = dict(cell=cell, phenotype=labels.pop(), modes=sorted(modes),
            n_records=len(rows), source_paths=sorted(r['source_path'] for r in rows),
            record_weights={r['source_path']: 1/len(modes)/len(rs)
                            for rs in modes.values() for r in rs})
        for field in FIELDS:
            result[field] = np.mean([np.mean([r[field] for r in rs], axis=0)
                                    for _, rs in sorted(modes.items())], axis=0)
        cells.append(result)
    return cells

def fit_record(row, matrix, directions, ti):
    pair = np.asarray(row['profiles'], dtype=float)
    if pair.shape != (2, 100) or not np.isfinite(pair).all() or (pair < 0).any():
        raise ValueError('Expected finite nonnegative E/I profiles')
    np.testing.assert_allclose(pair.max(), 1., atol=1e-10)
    coef = np.array([nnls(matrix, y, maxiter=3000)[0] for y in pair])
    prediction = coef @ matrix.T
    areas = coef * matrix.mean(axis=0)
    if areas.sum() <= 0:
        raise ValueError('No fitted phasic input')
    scores = pair @ np.array([d['weights'] for d in directions]).T
    residual_energy = np.sum((pair-prediction)**2, axis=1)
    observed_energy = np.sum(pair**2, axis=1)
    relative = np.divide(residual_energy, observed_energy,
                         out=np.zeros(2), where=observed_energy > 0)
    return dict(source_path=row['source_path'], cell=row['working_cell_key'],
        phenotype=row['analysis_phenotype'], mode=row['mode'],
        reference_kind=row['reference_kind'], ti=ti,
        phenotype_assignment_status=row['phenotype_assignment_status'],
        ei_mV=row['ei_mV'], ee_mV=row['ee_mV'],
        unclipped_negative_fraction=row['unclipped_negative_fraction'],
        profiles=pair, scores=scores, coefficients=coef, shares=areas/areas.sum(),
        prediction=prediction, rmse_joint_peak=np.sqrt(np.mean((pair-prediction)**2, axis=1)),
        relative_residual_energy=relative)

def summarize(cells):
    elementary, families, groups = [], [], []
    for target in NAMES:
        selected = [c for c in cells if c['phenotype'] == target]
        scores = np.array([c['scores'] for c in selected])
        shares = np.array([c['shares'] for c in selected])
        groups.append(dict(target=target, n_cells=len(selected),
            n_records=sum(c['n_records'] for c in selected),
            mean_profile=np.mean([c['profiles'] for c in selected], axis=0),
            mean_prediction=np.mean([c['prediction'] for c in selected], axis=0),
            median_rmse_joint_peak=np.median([c['rmse_joint_peak'] for c in selected], axis=0),
            median_relative_residual_energy=np.median(
                [c['relative_residual_energy'] for c in selected], axis=0)))
        for si, sign in enumerate(SIGNS):
            for family, members in FAMILIES:
                tests = [dict(target=target, sign=sign, source=family,
                              contrast=NAMES[j], **one_sided_test(scores[:, si, j]))
                         for j in members]
                elementary.extend(tests)
                p_family = min(1., len(members)*min(r['p_raw'] for r in tests))
                strongest = min(tests, key=lambda r: r['p_raw'])
                families.append(dict(target=target, sign=sign, source=family,
                    n_cells=len(selected), n_contrasts=len(members),
                    p_family=p_family, displayed_contrast=strongest['contrast'],
                    descriptive_contrast_selection='minimum elementary p; family test Bonferroni corrected',
                    **{'share_'+k: v for k, v in describe(shares[:, si, members].sum(axis=1)).items()}))
    if len(families) != 30 or len(elementary) != 50:
        raise AssertionError('Incorrect test family')
    for row, p in zip(families, holm([r['p_family'] for r in families])):
        row['p_holm'] = float(p)
        row['supported'] = bool(p < ALPHA)
    return dict(groups=groups, families=families, elementary=elementary)
