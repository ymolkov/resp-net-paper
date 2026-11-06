#!/usr/bin/env python3
"""Build the portable resp-net-paper atlas from frozen fits; no inference run."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/connectome-explorer"
INPUTS = {
    "summary": "data/model_analyses/inspiratory_subset_contrasts/summary.json",
    "cells": "data/model_analyses/inspiratory_subset_contrasts/cells.json",
    "basis": "data/model_analyses/coarse_connection_contrasts/contrasts.json",
    "geometry": "output/circuit_previews/six_population_2026-09-26/manifest.json",
}
NAMES = ["pre-I", "ramp-I", "early-I", "post-I", "aug-E"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload():
    raw = {key: json.loads((ROOT/path).read_text()) for key, path in INPUTS.items()}
    summary = raw["summary"]["fixed_fall50"]
    cells = raw["cells"]["fixed_fall50"]
    basis = raw["basis"]["fixed_fall50"][0]
    matrix = np.array(basis["matrix"])
    groups, panels = {}, {}
    for target in NAMES:
        records = sorted((c for c in cells if c["phenotype"] == target), key=lambda c: c["cell"])
        exported = []
        for i, cell in enumerate(records):
            coef = np.array(cell["subset_coefficients"])
            assert coef.shape == (8, 2, 5)
            for mask in range(8):
                for bit in range(3):
                    if not mask & (1 << bit):
                        assert np.all(coef[mask, :, bit] == 0)
            exported.append(dict(id=f"{target}-{i+1:03d}", label=f"Cell {i+1:02d}",
                                 modes=cell["modes"], nRecords=cell["n_records"],
                                 profiles=cell["profiles"], coefs=cell["subset_coefficients"],
                                 rmse=cell["subset_rmse"], shares=cell["full_shares"]))
        mean = {key: np.mean([c[key] for c in exported], axis=0).tolist()
                for key in ("profiles", "coefs", "rmse", "shares")}
        groups[target] = dict(n=len(records), nRecords=sum(c["n_records"] for c in records),
                              cells=exported, mean=mean)
        for sign, si in (("E", 0), ("I", 1)):
            p = next(p for p in summary["panels"] if (p["target"], p["sign"]) == (target, sign))
            np.testing.assert_allclose(mean["profiles"][si], p["mean_profile"], atol=1e-12)
            predicted = np.array(mean["coefs"])[:, si] @ matrix.T
            np.testing.assert_allclose(predicted, p["mean_subset_predictions"], atol=1e-12)
            panels[f"{target}|{sign}"] = dict(
                minima=p["minimal_unexcluded_masks"], allowed=p["unexcluded_retained_masks"],
                individual=p["individually_required"], familyP=p["family_p_joint"],
                supported=p["family_supported"],
                alternatives=[r for r in summary["alternatives"] if (r["target"], r["sign"]) == (target, sign)],
                tests=[r for r in summary["tests"] if (r["target"], r["sign"]) == (target, sign)])
    overview = raw["geometry"]["pages"][0]["overview"]
    assert sum(g["n"] for g in groups.values()) == 150
    assert sum(g["nRecords"] for g in groups.values()) == 168
    assert sum(r["supported"] for r in summary["coarse_policy"]) == 20
    return dict(names=NAMES, matrix=basis["matrix"], ti=basis["ti"], groups=groups,
                panels=panels, coarse=summary["coarse_policy"], overview=overview,
                meta=dict(title="Conductance-constrained respiratory connectome", scenario="fixed_fall50",
                          checkpoint="Expanded cohort, 20 September 2026", nCells=150, nRecords=168,
                          sourceHashes={path: sha(ROOT/path) for path in INPUTS.values()}))


def main():
    protected = [ROOT/path for path in INPUTS.values()]
    before = {str(p): sha(p) for p in protected}
    data = payload()
    template = (APP/"index.template.html").read_text()
    assets = {"STYLE": (APP/"style.css").read_text(), "CORE": (APP/"core.js").read_text(),
              "VENDOR": (APP/"vendor/d3/d3.min.js").read_text(),
              "APP": (APP/"app.js").read_text(), "DATA": json.dumps(data, separators=(",", ":"))}
    icons = {p.stem: p.read_text() for p in sorted((APP/"vendor/lucide").glob("*.svg"))}
    assets["ICONS"] = json.dumps(icons, separators=(",", ":"))
    for key, value in assets.items():
        assert f"<!--{key}-->" in template
        template = template.replace(f"<!--{key}-->", value.replace("</script", "<\\/script") if key in ("DATA", "ICONS") else value)
    licenses = [("Project software (MIT)", ROOT/"LICENSE"),
                ("D3", APP/"vendor/d3/LICENSE"),
                ("Lucide", APP/"vendor/lucide/LICENSE")]
    notices = "\n\n".join(f"{name}\n{p.read_text()}" for name, p in licenses)
    notices = notices.replace("</script", "<\\/script")
    assert template.count("</body>") == 1
    template = template.replace("</body>",
        f'<script id="third-party-licenses" type="text/plain">\n{notices}\n</script>\n  </body>')
    (APP/"index.html").write_text(template)
    source_assets = [APP/"app.js", APP/"core.js", APP/"style.css", APP/"index.template.html",
                     APP/"vendor/d3/d3.min.js", *sorted((APP/"vendor/lucide").glob("*.svg")),
                     *(p for _, p in licenses if p.is_relative_to(APP))]
    manifest = dict(analysis_run=False, source_sha256=data["meta"]["sourceHashes"],
                    builder_sha256=sha(Path(__file__)), output_sha256=sha(APP/"index.html"),
                    license_sha256={"LICENSE": sha(ROOT/"LICENSE")},
                    assets_sha256={str(p.relative_to(APP)): sha(p) for p in source_assets})
    (APP/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    assert before == {str(p): sha(p) for p in protected}
    print(f"Built {APP/'index.html'} ({len(template.encode()):,} bytes).")
    print("150 cells, 168 recordings, all 80 mean subset predictions verified; frozen inputs unchanged.")


if __name__ == "__main__":
    main()
