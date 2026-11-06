"""Tables and diagnostic displays from frozen results, without refitting."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("pre-I", "ramp-I", "early-I", "post-I", "aug-E")
TABLE_NAMES = {name: r"\preII{}" if name == "pre-I" else name for name in NAMES}
REPORT_INPUTS = {
    "subset_cells": "data/model_analyses/inspiratory_subset_contrasts/cells.json",
    "directions": "data/model_analyses/inspiratory_subset_contrasts/contrasts.json",
    "coarse_summary": "data/model_analyses/coarse_connection_contrasts/summary.json",
    "reconstruction": "data/extended_dataset/conductance_reversal_bounded_ee_minus20/records.json",
    "configuration": "data/extended_dataset/full_qc/run_config.json",
    "registration": "data/model_analyses/postI_figure_registration/results.json",
}
TABLES = ("inspiratory_alternatives.tex", "archive_summary.tex",
          "omission_tests.tex", "contribution_variation.tex")


def load_reports(d):
    raw = {key: json.loads((ROOT / path).read_text()) for key, path in REPORT_INPUTS.items()}
    for key in ("subset_cells", "directions", "coarse_summary"):
        raw[key] = raw[key]["fixed_fall50"]
    reconstruction = {r["source_path"]: r for r in raw["reconstruction"]}
    configuration = {r["source_path"]: r for r in raw["configuration"]["configs"]}
    records = []
    for row in d["records"]:
        r, c = reconstruction[row["source_path"]], configuration[row["source_path"]]
        epoch = r["chosen_epoch"]
        commands = r["manual_command_windows"] or []
        # Phrenic by design (author confirmation, 2026-10-29); retain archive labels separately.
        records.append(dict(source_path=row["source_path"], cell=row["cell"],
            target=row["phenotype"], mode=row["mode"], reference="phrenic",
            reference_annotation=row["reference_kind"],
            provisional=row["phenotype_assignment_status"].startswith("provisional"),
            ei_mV=row["ei_mV"], ee_mV=row["ee_mV"],
            ei_lower_bound=row["ei_mV"] == -110, ei_upper_bound=row["ei_mV"] == -60,
            epoch_start=epoch["start"], epoch_end=epoch["end"],
            complete_cycles=epoch["n_complete_usable_cycles"],
            minimum_cycles_per_bin=epoch["min_phase_contributing_cycles"],
            maximum_cycles_per_bin=epoch["max_phase_contributing_cycles"],
            annotated_command_levels=len({x["command_state"] for x in commands}) if commands else "",
            sample_interval_native=c["sample_interval_native"],
            electrical_kernel_samples=2*c["electrical_half_width_samples"]+1,
            reference_kernel_samples=2*c["reference_half_width_samples"]+1,
            median_phase_r2=r["diagnostics"]["median_phase_r2"],
            calibration_status=r["calibration_status"], source_sha256=r["source_sha256"]))
    tests = [dict(target=r["target"], sign=r["sign"], omitted_mask=r["omitted_mask"],
                  omitted=" + ".join(r["omitted_sources"]), n=r["n_cells"],
                  p_local=r["p_local"], p_closed=r["p_closed"], p_adjusted=r["p_joint"])
             for r in d["summary"]["tests"]]
    coarse = {(r["target"], r["sign"], r["source"]): r for r in d["summary"]["coarse_policy"]}
    elementary = [dict(r, omitted=" + ".join(NAMES[j] for j in range(3)
                    if r["omitted_mask"] & (1 << j))) for r in d["summary"]["elementary"]]
    for r in raw["coarse_summary"]["elementary"]:
        if r["source"] == "Inspiratory":
            continue
        mask = 1 << NAMES.index(r["source"])
        p = coarse[r["target"], r["sign"], r["source"]]["p_joint"]
        tests.append(dict(target=r["target"], sign=r["sign"], omitted_mask=mask,
            omitted=r["source"], n=r["n"], p_local=r["p_raw"], p_closed="", p_adjusted=p))
        elementary.append(dict(r, omitted=r["source"], omitted_mask=mask))
    assert len(tests) == 90 and len(elementary) == 140
    test_index = {(r["target"], r["sign"], r["omitted_mask"]): r for r in tests}
    for row in elementary:
        test = test_index[row["target"], row["sign"], row["omitted_mask"]]
        row.update({k: test[k] for k in ("p_local", "p_closed", "p_adjusted")})
    magnitudes = []
    for target in NAMES:
        cells = [r for r in d["cells"] if r["phenotype"] == target]
        shares = np.array([r["shares"] for r in cells])
        for si, sign in enumerate(("E", "I")):
            for source, ids in (("Inspiratory", [0, 1, 2]), ("post-I", [3]), ("aug-E", [4])):
                values = shares[:, si, ids].sum(axis=1)*100
                magnitudes.append(dict(target=target, sign=sign, source=source, n=len(cells),
                    mean=float(values.mean()), sd=float(values.std(ddof=1)),
                    median=float(np.median(values)), q25=float(np.quantile(values, .25)),
                    q75=float(np.quantile(values, .75))))
    return dict(raw=raw, records=records, tests=tests, elementary=elementary, magnitudes=magnitudes)


def table(caption, label, columns, header, rows, note=""):
    return "\n".join([
        "% Generated from frozen results by scripts/expanded_paper_reporting.py.",
        r"\begin{table}[htbp]", r"\centering\small", r"\caption{"+caption+"}",
        r"\label{"+label+"}", r"\begin{tabular}{"+columns+"}", r"\toprule",
        header+r" \\", r"\midrule", *rows, r"\bottomrule", r"\end{tabular}",
        r"\par\smallskip\begin{minipage}{\linewidth}\footnotesize "+note+r"\end{minipage}" if note else "",
        r"\end{table}", ""])


def alternatives_text(masks):
    if masks == [0]:
        return "No inspiratory input established"
    combos = [" + ".join(TABLE_NAMES[NAMES[j]] for j in range(3) if mask & (1 << j)) for mask in masks]
    return " or ".join("("+c+")" if " + " in c else c for c in combos)


def p_tex(value):
    if value < .001:
        return r"$\boldsymbol{<0.001}$"
    text = f"{value:.3f}"
    return r"\textbf{"+text+"}" if value < .05 else text


def write_tables(d, report, folder):
    folder.mkdir(parents=True, exist_ok=True)
    panels = {(r["target"], r["sign"]): r for r in d["summary"]["panels"]}
    rows = [TABLE_NAMES[target]+" & "+" & ".join(alternatives_text(panels[target, s]["minimal_unexcluded_masks"])
            for s in ("E", "I"))+r" \\[5pt]" for target in NAMES]
    (folder / TABLES[0]).write_text(table(
        "Inspiratory input combinations consistent with the omission tests.", "tab:inspiratory_alternatives",
        r"@{}p{.12\linewidth}p{.41\linewidth}p{.41\linewidth}@{}",
        "Target & Excitatory input & Inhibitory input", rows,
        "A plus sign joins inputs retained together; ``or'' separates alternatives. "
        "Removing any member from a listed combination conflicts with at least one rejected omission. "
        "Additional inputs remain possible. Both expiratory templates remain available."))
    rows = []
    for target in NAMES:
        records = [r for r in report["records"] if r["target"] == target]
        flagged = lambda predicate: f"{sum(predicate(r) for r in records)} ({len({r['cell'] for r in records if predicate(r)})})"
        rows.append(" & ".join([TABLE_NAMES[target], str(len({r["cell"] for r in records})), str(len(records)),
            f"{sum(r['mode']=='CC' for r in records)}/{sum(r['mode']=='VC' for r in records)}",
            flagged(lambda r: r["provisional"])])+r" \\")
    (folder / TABLES[1]).write_text(table(
        "Recording counts and annotations by sampled population.", "tab:archive_summary",
        "@{}lrrrr@{}", r"Population & Cells & Records & CC/VC & Provisional",
        rows, "Provisional entries give recordings (distinct cells). "
        "CC/VC denotes current-clamp/voltage-clamp recordings."))
    tests = {(r["target"], r["sign"], r["omitted_mask"]): r for r in report["tests"]}
    rows = []
    for sign, title in (("E", "Excitatory conductance"), ("I", "Inhibitory conductance")):
        rows += [r"\multicolumn{6}{l}{\textit{"+title+r"}} \\", r"\addlinespace"]
        for mask in (1, 2, 4, 3, 5, 6, 7, 8, 16):
            label = "All inspiratory" if mask == 7 else " + ".join(TABLE_NAMES[NAMES[j]] for j in range(5) if mask & (1 << j))
            rows.append(label+" & "+" & ".join(p_tex(tests[n, sign, mask]["p_adjusted"]) for n in NAMES)+r" \\")
        rows.append(r"\addlinespace")
    (folder / TABLES[2]).write_text(table(
        "Complete adjusted P values for tests of omitted inputs.", "tab:omission_tests",
        "@{}lrrrrr@{}", "Omitted input(s) & "+" & ".join(TABLE_NAMES[n] for n in NAMES), rows,
        "Columns are receiving populations. Bold values are below 0.05. All 70 inspiratory-subset tests "
        "and 20 expiratory tests are shown. The all-inspiratory rows also appear in the circuit overview; "
        "they are not additional tests. Cell counts are 17, 41, 8, 54 and 30, respectively. "
        "Machine-readable tables retain unrounded P values and all 140 elementary contrast summaries."))
    magnitudes = {(r["target"], r["sign"], r["source"]): r for r in report["magnitudes"]}
    rows = []
    for sign, title in (("E", "Excitation"), ("I", "Inhibition")):
        rows.append(r"\multicolumn{6}{l}{\textit{"+title+r"}} \\")
        for source in ("Inspiratory", "post-I", "aug-E"):
            values = [magnitudes[n, sign, source] for n in NAMES]
            rows.append(source+" & "+" & ".join(
                r"\shortstack{"+f"{r['mean']:.1f}"+r"\\{}"+f"[{r['q25']:.1f}, {r['q75']:.1f}]"+"}"
                for r in values)+r" \\[6pt]")
    (folder / TABLES[3]).write_text(table(
        "Variation in fitted contributions across cells.", "tab:contribution_variation",
        "@{}lrrrrr@{}", "Candidate input & "+" & ".join(TABLE_NAMES[n] for n in NAMES), rows,
        "Each entry is the mean percentage of total fitted excitatory plus inhibitory area, "
        "followed by the 25th and 75th cell percentiles in brackets. These percentiles describe "
        "between-cell variation, not confidence limits. The three inspiratory templates are summed "
        "before computing these summaries. Means, SDs, medians and quartiles are provided in the "
        "machine-readable contribution table."))


def write_csv(rows, path):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_data(report, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("records", "tests", "elementary", "magnitudes"):
        write_csv(report[name], folder / (name+".csv"))


def score_figure(d, report):
    # Fixed reporting selection: all five supported singleton inputs, plus
    # the fragile pre-I whole-family result and both small-n early-I panels.
    selected = [(r["target"], r["sign"], r["omitted_mask"]) for r in d["summary"]["tests"]
                if r["omitted_mask"] in (1, 2, 4) and r["rejected"]]
    selected += [("pre-I", "I", 7), ("early-I", "E", 7), ("early-I", "I", 7)]
    assert len(selected) == 8
    directions = report["raw"]["directions"][0]["directions"]
    fig, axes = plt.subplots(2, 4, figsize=(7, 5.6), layout="constrained")
    for ax, (target, sign, mask) in zip(axes.flat, selected):
        rows = [r for r in report["elementary"] if (r["target"], r["sign"], r["omitted_mask"]) == (target, sign, mask)]
        chosen = min(rows, key=lambda r: r["p_raw"])
        index = next(i for i, r in enumerate(directions)
                     if (r["omitted_mask"], r["template"]) == (mask, chosen["contrast"]))
        values = np.array([r["scores"][0 if sign == "E" else 1][index]
                          for r in report["raw"]["subset_cells"] if r["phenotype"] == target])
        np.testing.assert_allclose([values.mean(), values.std(ddof=1)], [chosen["mean"], chosen["sd"]])
        color = "#b83e3d" if sign == "E" else "#287ba5"
        x = .12*np.sin(np.arange(len(values))*2.399963)
        ax.scatter(x, values, s=12, color=color, alpha=.65, linewidths=0)
        ax.errorbar(.30, chosen["mean"], yerr=chosen["sd"], fmt="s", color="#222222", ms=4, capsize=4)
        ax.axhline(0, color="#777777", lw=.8, ls="--")
        ax.set(xlim=(-.22, .46), xticks=[], ylabel="Contrast score")
        ax.spines[["top", "right", "bottom"]].set_visible(False)
        omitted = "All inspiratory" if mask == 7 else chosen["omitted"]
        label = "Excitation" if sign == "E" else "Inhibition"
        ax.set_title(f"{target}: {label}\nOmit {omitted}", fontsize=8.5)
        p = chosen["p_adjusted"]
        ptext = "<0.001" if p < .001 else f"= {p:.3f}"
        ax.set_xlabel(f"n = {len(values)}; P {ptext}\nSE = {chosen['sem']:.3f}", fontsize=8)
    return fig


def alignment_figure(report):
    fig, ax = plt.subplots(figsize=(6, 2.5), layout="constrained")
    registration = report["raw"]["registration"]
    trace, correction = registration["smith_traces"]["post-I"], registration["postI_registration"]
    ax.plot(trace["phase"], trace["activity"], color="#777777", ls="--", label="As published")
    ax.plot(correction["phase_corrected"], trace["activity"], color="#247b68", label="Aligned to phase guide")
    ax.axvline(correction["published_ie_boundary"], color="#777777", lw=.8)
    ax.set(xlim=(0, 1), ylim=(-.03, 1.06), xlabel="Phase in published figure", ylabel="Post-I activity")
    ax.set_title("Post-I activity-template alignment", loc="left", fontsize=10, weight="bold")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    return fig


def alternatives_figure(d, report):
    fig = plt.figure(figsize=(7, 6.2))
    grid = fig.add_gridspec(3, 3, height_ratios=(1, .42, 1),
                            left=.09, right=.98, top=.88, bottom=.05,
                            hspace=.32, wspace=.24)
    fig.text(.03, .97, "A  Post-I excitation: alternative inspiratory inputs", fontsize=11, weight="bold")
    panel = next(r for r in d["summary"]["panels"] if (r["target"], r["sign"]) == ("post-I", "E"))
    assert panel["family_supported"] and panel["minimal_unexcluded_masks"] == [1, 2]
    assert panel["individually_required"] == []
    x = np.arange(100)/100
    observed = np.array(panel["mean_profile"])
    full = np.array(panel["mean_subset_predictions"][7])
    predictions = [np.array(panel["mean_subset_predictions"][m]) for m in (0, 1, 2)]
    conductance_max = 1.08*max(np.max(v) for v in [observed, full, *predictions])
    residual_max = 1.12*max(np.max(np.abs(observed-v)) for v in [full, *predictions])
    for j, (mask, name) in enumerate(((0, "No inspiratory input"), (1, "pre-I only"), (2, "ramp-I only"))):
        prediction = np.array(panel["mean_subset_predictions"][mask])
        ax = fig.add_subplot(grid[0, j])
        residual = fig.add_subplot(grid[1, j], sharex=ax)
        for a in (ax, residual):
            a.axvspan(0, d["ti"], color="#edf0f1", zorder=0)
            a.set_xlim(0, 1)
        ax.plot(x, observed, color="#222222", label="Sample mean")
        ax.plot(x, full, color="#777777", ls="--", label="Mean full fit")
        ax.plot(x, prediction, color="#8a62a0", label="Mean restricted fit")
        ax.set_title(name, loc="center", fontsize=9, weight="bold")
        ax.set(ylim=(0, conductance_max))
        ax.set_gid(f"postI-input-{mask}")
        ax.tick_params(labelbottom=False)
        if j == 0:
            ax.set_ylabel("Normalized conductance")
            handles, labels = ax.get_legend_handles_labels()
            fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.52, .952),
                       ncol=3, frameon=False, fontsize=8)
        else:
            ax.tick_params(labelleft=False)
        residual.plot(x, observed-prediction, color="#8a62a0")
        residual.plot(x, observed-full, color="#777777", ls="--")
        residual.axhline(0, color="#333333", lw=.7)
        residual.set(ylim=(-residual_max, residual_max), xlabel="Respiratory phase",
                     xticks=(0, d["ti"], 1), xticklabels=("0", "I/E", "1"))
        if j == 0:
            residual.set_ylabel("Residual")
        else:
            residual.tick_params(labelleft=False)
    for ax in fig.axes:
        ax.spines[["top", "right"]].set_visible(False)

    ax = fig.add_subplot(grid[2, :])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.text(-.06, .96, "B  Connections supported by the omission tests", fontsize=11, weight="bold")

    def node(xy, label, source=False):
        color = "#b83e3d" if source else "#59636a"
        ax.add_patch(Ellipse(xy, .17, .25, facecolor="white", edgecolor=color, lw=1.2))
        ax.text(*xy, label, ha="center", va="center", fontsize=9, color=color)

    def edge(start, end, dashed=False):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13,
                                    lw=1.5, color="#b83e3d",
                                    linestyle=(0, (4, 3)) if dashed else "-"))

    node((.10, .47), "Inspiratory", True)
    node((.37, .47), "post-I")
    edge((.185, .47), (.278, .47))
    node((.64, .67), "pre-I", True)
    node((.64, .27), "ramp-I", True)
    node((.91, .47), "post-I")
    edge((.715, .615), (.830, .51), True)
    edge((.715, .325), (.830, .43), True)
    return fig
