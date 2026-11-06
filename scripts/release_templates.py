"""Scientific helpers copied verbatim from the canonical analysis.

Only imports, module constants and historical command entry points are adapted
for the focused paper release. The source map records each retained definition.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
BASIS = ROOT / 'data/model_analyses/postI_figure_registration/results.json'
NAMES = ['pre-I', 'ramp-I', 'early-I', 'post-I', 'aug-E']
PHASE = np.arange(100) / 100
TI = .2406187667

class CorrectedBasis:
    def __init__(self, path=BASIS):
        self.data = json.loads(Path(path).read_text())
        self.landmarks = self.data['smith_landmarks']['rise20_fall50']

    def matrix(self, ti=TI):
        if not 0 < ti < 1:
            raise ValueError('I/E boundary must lie inside the cycle')
        on, off = self.landmarks['onset'], self.landmarks['offset']
        query = on + np.where(PHASE < ti, PHASE / ti * (off-on),
                              off-on+(PHASE-ti)/(1-ti)*(1-off+on))
        cols = []
        for name in NAMES:
            trace = self.data['smith_traces'][name]
            # Use native digitization, not another interpolation of the 100-bin basis.
            x = np.array(self.data['postI_registration']['phase_corrected']
                         if name == 'post-I' else trace['phase'])
            y = np.array(trace['activity'])
            keep = (x >= 0) & (x < 1)
            x, y = x[keep], y[keep]
            assert np.all(np.diff(x) > 0)
            v = np.interp(query, np.r_[x-1, x, x+1], np.r_[y, y, y])
            v -= v.min()
            cols.append(v/v.max())
        return np.column_stack(cols)

def holm(pvalues):
    """Holm step-down adjusted p-values, valid without independent tests."""
    values = np.asarray(pvalues, dtype=float)
    if np.any(~np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError('Invalid p-values')
    order = np.argsort(values, kind='stable')
    adjusted = np.minimum(1, np.maximum.accumulate(
        values[order] * np.arange(len(values), 0, -1)))
    result = np.empty_like(values)
    result[order] = adjusted
    return result
