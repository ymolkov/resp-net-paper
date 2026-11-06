#!/usr/bin/env python3
"""Recompute the published recordings without changing packaged frozen data."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy

from release_reconstruction import (
    decompose, estimate_inhibitory_reversal, parse_numeric_bytes,
    prepare_record, regress, selected_samples,
)


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "manifest": "data/manuscript_reporting/records.csv",
    "reviewed": "data/extended_dataset/current_inventory/recordings.jsonl",
    "configuration": "data/extended_dataset/full_qc/run_config.json",
    "parse": "data/extended_dataset/full_qc/records.json",
    "expected": "data/extended_dataset/conductance_reversal_bounded_ee_minus20/records.json",
}
RTOL = 1e-10
ATOL = 1e-12


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def indexed(rows, key, description):
    result = {}
    for row in rows:
        name = key(row)
        if name in result:
            raise ValueError(f"Duplicate {description} for {name}")
        result[name] = row
    return result


def compare_numeric(actual, expected, description):
    actual, expected = np.asarray(actual, float), np.asarray(expected, float)
    np.testing.assert_allclose(actual, expected, rtol=RTOL, atol=ATOL,
                               equal_nan=False, err_msg=description)
    return float(np.max(np.abs(actual - expected)))


def reconstruct(job):
    root, manifest, reviewed, config, parse, expected = job
    source = manifest["source_path"]
    if reviewed["phase_coordinate"] != "two_part":
        raise ValueError(f"Non-manuscript phase coordinate: {source}")
    if reviewed["working_cell_key"] != manifest["cell"]:
        raise ValueError(f"Cell identity mismatch: {source}")
    if (reviewed["analysis_phenotype"], reviewed["mode"]) != (
            manifest["target"], manifest["mode"]):
        raise ValueError(f"Classification or mode mismatch: {source}")
    if config["mode"] != reviewed["mode"]:
        raise ValueError(f"Configuration mode mismatch: {source}")
    blob = (Path(root) / "data/extended_dataset/raw_archive" / source).read_bytes()
    raw_hash = hashlib.sha256(blob).hexdigest()
    if any(raw_hash != value for value in (
            manifest["source_sha256"], reviewed["source_sha256"],
            config["source_sha256"], expected["source_sha256"])):
        raise ValueError(f"Raw file checksum mismatch: {source}")
    used = int(parse["bytes_used"])
    if not 0 < used <= len(blob):
        raise ValueError(f"Invalid numeric prefix scope: {source}")
    if len(blob) - used != int(parse["quarantined_suffix_bytes"]):
        raise ValueError(f"Quarantined suffix length mismatch: {source}")

    raw = parse_numeric_bytes(blob[:used])[0]
    prepared = prepare_record(raw[:, config["canonical_columns_0based"]], config)
    phase, support = selected_samples(prepared, reviewed)
    if support["sample_mask_sha256"] != expected["diagnostics"]["sample_mask_sha256"]:
        raise ValueError(f"Accepted sample mask changed: {source}")
    fit = regress(prepared.electrical, phase, reviewed["mode"])
    errors = {}
    for key in ("total_g_native_full_precision", "current_intercept_native_full_precision"):
        errors[key] = compare_numeric(fit[key], expected["regression"][key], f"{source}: {key}")
    g = fit["total_g_native_full_precision"]
    c = fit["current_intercept_native_full_precision"]
    geometry = estimate_inhibitory_reversal(g, c)
    if geometry["status"] != "estimated" or geometry.get("ei_mV") is None:
        raise ValueError(f"Inhibitory reversal is not uniquely estimated: {source}")
    errors["unbounded_ei_mV"] = compare_numeric(
        geometry["ei_mV"], expected["reversal_estimation"]["ei_mV"], f"{source}: unbounded Ei")
    ei = float(np.clip(geometry["ei_mV"], -110., -60.))
    result = decompose(g, c, ei, -20.)
    if result["status"] != "ok":
        raise ValueError(f"Primary decomposition failed for {source}: {result.get('reason')}")
    for key in ("ei_mV", "ee_mV", "inferred_grounding_g_native",
                "inferred_grounding_reversal_mV", "joint_scale_relative_to_grounding",
                "profiles", "relative_to_grounding_profiles"):
        errors[key] = compare_numeric(result[key], expected[key], f"{source}: {key}")
    return {
        "source_path": source,
        "source_sha256": raw_hash,
        "working_cell_key": reviewed["working_cell_key"],
        "mode": reviewed["mode"],
        "analysis_phenotype": reviewed["analysis_phenotype"],
        "phenotype_assignment_status": reviewed["phenotype_assignment_status"],
        "phase_coordinate": reviewed["phase_coordinate"],
        "reference_kind": reviewed.get("reference_kind", config.get("reference_kind")),
        "calibration_status": reviewed.get("calibration_status"),
        "chosen_epoch": reviewed["chosen_epoch"],
        "manual_command_windows": reviewed["manual_command_windows"],
        "raw_numeric_bytes_used": used,
        "quarantined_suffix_bytes": len(blob) - used,
        "regression": fit,
        "diagnostics": support,
        "unbounded_ei_mV": geometry["ei_mV"],
        "primary_method": "bounded_estimated_Ei",
        **result,
        "verification_max_absolute_error": errors,
    }


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="Release root; defaults to this script's parent directory")
    parser.add_argument("--output", type=Path,
                        help="Recomputed output JSON; defaults to output/reproduced/reconstruction.json")
    parser.add_argument("--limit", type=int, help="Reconstruct only the first N manifest records for a smoke check")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and not 1 <= args.limit <= 168):
        parser.error("workers must be positive; limit must be between 1 and 168")
    root = args.root.resolve()
    output = (args.output or root / "output/reproduced/reconstruction.json").resolve()
    if output.is_relative_to(root / "data") or output.is_relative_to(root / "scripts"):
        parser.error("Output must be outside packaged data and scripts")
    paths = {key: root / path for key, path in INPUTS.items()}
    input_hashes = {INPUTS[key]: sha256(path) for key, path in paths.items()}
    with paths["manifest"].open(newline="") as stream:
        manifest = list(csv.DictReader(stream))
    indexed(manifest, lambda row: row["source_path"], "manifest entry")
    if len(manifest) != 168 or len({row["cell"] for row in manifest}) != 150:
        raise ValueError("Expected the published 168-recording / 150-cell manifest")
    if sum(row["mode"] == "CC" for row in manifest) != 150 or sum(
            row["mode"] == "VC" for row in manifest) != 18:
        raise ValueError("Published mode counts changed")
    reviewed = indexed((json.loads(line) for line in paths["reviewed"].read_text().splitlines() if line.strip()),
                       lambda row: row["source_path"], "reviewed record")
    configuration = json.loads(paths["configuration"].read_text())
    configs = indexed(configuration["configs"], lambda row: row["source_path"], "configuration")
    parse_rows = indexed(json.loads(paths["parse"].read_text()),
                         lambda row: row.get("source_path") or row["summary"]["source_path"], "parse metadata")
    expected = indexed(json.loads(paths["expected"].read_text()),
                       lambda row: row["source_path"], "frozen reconstruction")
    chosen = manifest[:args.limit] if args.limit else manifest
    jobs = []
    for row in chosen:
        source = row["source_path"]
        jobs.append((str(root), row, reviewed[source], configs[source],
                     parse_rows[source]["parse"], expected[source]))
    if args.workers == 1:
        results = []
        for index, job in enumerate(jobs, 1):
            results.append(reconstruct(job))
            if index % 10 == 0 or index == len(jobs):
                print(f"Verified {index}/{len(jobs)} reconstructions", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            results = []
            for index, result in enumerate(pool.map(reconstruct, jobs), 1):
                results.append(result)
                if index % 10 == 0 or index == len(jobs):
                    print(f"Verified {index}/{len(jobs)} reconstructions", flush=True)
    if input_hashes != {INPUTS[key]: sha256(path) for key, path in paths.items()}:
        raise RuntimeError("A packaged input changed during reconstruction")
    verification = {
        "schema_version": 1,
        "complete_cohort": len(results) == 168,
        "recordings": len(results),
        "cells": len({row["working_cell_key"] for row in results}),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "comparison_rtol": RTOL,
        "comparison_atol": ATOL,
        "input_sha256": input_hashes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, default=json_value, allow_nan=False, indent=2) + "\n")
    verification["reconstruction_sha256"] = sha256(output)
    output.with_suffix(".verification.json").write_text(
        json.dumps(verification, allow_nan=False, indent=2) + "\n")
    print(f"Wrote verified recomputations to {output}")


if __name__ == "__main__":
    main()
