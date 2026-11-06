"""Scientific helpers copied verbatim from the canonical analysis.

Only imports, module constants and historical command entry points are adapted
for the focused paper release. The source map records each retained definition.
"""
from __future__ import annotations
import numpy as np
from release_coarse import one_sided_test
from release_subsets import closed_pvalues, BRANCHES

def panel_tests(scores, directions):
    scores = np.asarray(scores, dtype=float)
    stats = [one_sided_test(scores[:, j]) for j in range(len(directions))]
    local = {mask:min(1., mask.bit_count()*min(s['p_raw'] for s, d in zip(stats, directions)
        if d['family'] == 'Inspiratory' and d['omitted_mask'] == mask)) for mask in range(1, 8)}
    joint = {mask:min(1., BRANCHES*p) for mask, p in closed_pvalues(local).items()}
    result = [dict(test=f'subset:{mask}', kind='subset', omitted_mask=mask, source='Inspiratory',
        p_joint=p, supported=p < .05) for mask, p in joint.items()]
    for family in ['Inspiratory', 'post-I', 'aug-E']:
        indices = [j for j, d in enumerate(directions) if d['family'] == family and
            (family != 'Inspiratory' or d['omitted_mask'] == 7)]
        display = min(indices, key=lambda j: stats[j]['p_raw'])
        p = joint[7] if family == 'Inspiratory' else min(1., BRANCHES*stats[display]['p_raw'])
        result.append(dict(test='coarse:'+family, kind='coarse', source=family, omitted_mask=7 if family == 'Inspiratory' else 0,
            p_joint=p, supported=p < .05, display_direction=display, display_template=directions[display]['template']))
    return result, stats
