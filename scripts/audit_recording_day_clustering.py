#!/usr/bin/env python3
"""Sensitivity of grouped omission decisions to averaging cells by recording day.

This is a read-only sensitivity check, not the primary analysis. It writes no files.

The manuscript treats cells as independent because the archive does not link
cells to animals. Recording dates can be parsed from the recording file names.
A recording day is NOT a certified animal or preparation identifier, and this
script does not provide an animal count. Day averaging is a conservative
grouping only if no preparation spans two days and same-day cells may share one.

Procedure:
1. Read the saved per-cell contrast scores for the 30 grouped tests.
2. Recompute the saved adjusted P values at cell level and require an exact
   match with the frozen results.
3. Average the scores of same-population cells recorded on the same day.
4. Repeat the same one-sided t test and the same corrections on the day means.

Usage: python3 scripts/audit_recording_day_clustering.py
"""

from __future__ import annotations

import collections
import csv
import math
import re
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SCORES = ROOT / "data/model_analyses/cell_influence_uncertainty/cell_evidence.csv"
SAVED = ROOT / "data/model_analyses/inspiratory_subset_contrasts/coarse_policy.csv"
TARGETS = ("pre-I", "ramp-I", "early-I", "post-I", "aug-E")
N_FAMILIES = 30  # ten inspiratory families plus twenty expiratory tests
ALPHA = 0.05


def recording_day(cell: str) -> str:
    """Return the ISO recording date encoded in a cell identifier."""
    name = cell.split("/")[1]
    match = re.match(r"^(\d{2})(\d{2})(\d{2})\d{2}_", name)  # DDMMYYnn_file
    if match:
        day, month, year = match.groups()
        return f"20{year}-{month}-{day}"
    match = re.match(r"^(\d{2})(\d{2})(\d{2})-", name)  # YYMMDD-label
    if match:
        year, month, day = match.groups()
        return f"20{year}-{month}-{day}"
    match = re.search(r"-(\d{2})(\d{2})(\d{2})(?:-|$)", name)  # label-YYMMDD(-n)
    if match:
        year, month, day = match.groups()
        return f"20{year}-{month}-{day}"
    raise ValueError(f"no recording date in {cell!r}")


def one_sided_t(values) -> tuple[float, float]:
    """One-sided t test of a positive mean; returns (P, T)."""
    x = np.asarray(values, dtype=float)
    t = x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))
    return float(stats.t.sf(t, len(x) - 1)), float(t)


def load_scores():
    """Map (target, sign, source) to {contrast template: {cell: score}}."""
    scores = collections.defaultdict(lambda: collections.defaultdict(dict))
    with SCORES.open() as handle:
        for row in csv.DictReader(handle):
            if row["family"] == "Inspiratory" and row["omitted_mask"] != "7":
                continue  # grouped inspiratory test omits all three templates
            key = (row["target"], row["sign"], row["family"])
            scores[key][row["template"]][row["cell"]] = float(row["score"])
    return scores


def grouped_test(contrasts, by_day: bool):
    """Adjusted P for one grouped test: local Bonferroni, then 30 families."""
    best = None
    for template, cell_scores in contrasts.items():
        if by_day:
            groups = collections.defaultdict(list)
            for cell, score in cell_scores.items():
                groups[recording_day(cell)].append(score)
            values = [float(np.mean(group)) for group in groups.values()]
        else:
            values = list(cell_scores.values())
        p, t = one_sided_t(values)
        if best is None or p < best["p"]:
            best = {"p": p, "t": t, "n": len(values), "template": template,
                    "positive": sum(v > 0 for v in values)}
    best["p_adjusted"] = min(1.0, N_FAMILIES * min(1.0, len(contrasts) * best["p"]))
    return best


def main() -> None:
    scores = load_scores()
    with SAVED.open() as handle:
        saved = {(r["target"], r["sign"], r["source"]): r
                 for r in csv.DictReader(handle) if r["scenario"] == "fixed_fall50"}
    assert len(saved) == 30 and set(saved) == set(scores)

    cells = {target: set() for target in TARGETS}
    for (target, _sign, _source), contrasts in scores.items():
        for cell_scores in contrasts.values():
            cells[target].update(cell_scores)
    all_days = collections.Counter(
        recording_day(cell) for group in cells.values() for cell in group)
    print(f"{sum(all_days.values())} cells on {len(all_days)} recording days; "
          f"{sum(n > 1 for n in all_days.values())} days with more than one cell; "
          f"at most {max(all_days.values())} cells on one day")
    for target in TARGETS:
        days = collections.Counter(recording_day(cell) for cell in cells[target])
        print(f"  {target:8s} {len(cells[target]):3d} cells, {len(days):3d} days, "
              f"at most {max(days.values())} cells per day")

    print("\n| Input | Cells | T | Adjusted P | Positive scores | Days | T | Adjusted P |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    kept = lost = 0
    for key in saved:
        target, sign, source = key
        cell = grouped_test(scores[key], by_day=False)
        day = grouped_test(scores[key], by_day=True)
        frozen = float(saved[key]["p_joint"])
        assert math.isclose(cell["p_adjusted"], frozen, rel_tol=1e-9), key
        supported = saved[key]["supported"] == "True"
        assert supported == (cell["p_adjusted"] < ALPHA), key
        if not supported:
            assert day["p_adjusted"] >= ALPHA, key  # no unsupported input gains support
            continue
        if day["p_adjusted"] < ALPHA:
            kept += 1
        else:
            lost += 1
        kind = "excitation" if sign == "E" else "inhibition"
        flag = "" if day["p_adjusted"] < ALPHA else " **(not supported)**"
        print(f"| {source} {kind} of {target} | {cell['n']} | {cell['t']:.2f} | "
              f"{cell['p_adjusted']:.3g} | {cell['positive']}/{cell['n']} | "
              f"{day['n']} | {day['t']:.2f} | {day['p_adjusted']:.3g}{flag} |")
    print(f"\nAll 30 saved adjusted P values reproduced at cell level. "
          f"After day averaging, {kept} of {kept + lost} supported inputs keep support.")


if __name__ == "__main__":
    main()
