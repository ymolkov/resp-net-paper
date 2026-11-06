#!/usr/bin/env python3
"""Approved Figure 1 and standalone preview using the same schematic renderer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from plot_cells_to_circuit_preview import (
    BLUE, EDGES, INK, PALE, RED, ROOT, TI, circuit_edge, flow, label, line,
    node, schematic_data, validate_layout,
)

OUT = ROOT / "output/circuit_previews/cells_to_circuit_2026-10-31"
PDF = ROOT / "output/pdf/cells_to_circuit_2026-10-31.pdf"
PAPER_FIGURE = ROOT / "paper/figures/inference_overview.pdf"
PINK = "#f0c7c7"
PALE_BLUE = "#c4e0ee"
MEAN = "#535b60"
DASH = (0, (4, 2.3))
DOT = (0, (1, 1.7))
DASH_DOT = (0, (4, 1.7, 1, 1.7))


def preview_data():
    """Illustrate sampling variation, not confidence bands or test outcomes."""
    original = schematic_data()
    activity = original["activities"]
    weights = np.array([
        [[0, 0, .65], [0, 0, .85], [0, 0, 1], [0, 0, 1.2]],
        [[.75, .02, 0], [.85, .03, 0], [.95, .04, 0], [1.05, .05, 0]],
        [[.6, 0, 0], [1.4, 0, 0], [0, .6, 0], [0, 1.4, 0]],
    ])
    cells = weights @ activity
    means = cells.mean(axis=1)
    # Predictions are averages of the same nonnegative single-source fits used
    # by the earlier cartoon. No hypothesis tests use these constructed cells.
    # The third comparison omits both excitatory sources, leaving zero input.
    predictions = np.zeros((3, 3, activity.shape[1]))
    for row, sources in enumerate(((None, None, None), (1, None, None),
                                   (1, 0, None))):
        for column, source in enumerate(sources):
            if source is not None:
                a = activity[source]
                amplitude = cells[row] @ a / (a @ a)
                predictions[row, column] = amplitude.mean() * a
    return dict(phase=original["phase"], activities=activity, weights=weights,
                cells=cells, means=means, lower=cells.min(axis=1),
                upper=cells.max(axis=1), predictions=predictions)


def trace_axes(fig, rect, phase_labels=False):
    ax = fig.add_axes(rect)
    ax.axvline(TI, color="#d5dadd", lw=.65, zorder=0)
    ax.set(xlim=(0, 1), ylim=(-.035, 1.29), xticks=[], yticks=[])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(PALE)
    if phase_labels:
        ax.set(xticks=(TI/2, (1+TI)/2), xticklabels=("Insp.", "Exp."))
        ax.tick_params(axis="x", length=0, labelsize=9, pad=3)
    return ax


def curve_key(fig, x, y, value, color, linestyle):
    line(fig, (x, y-.007), (x+.029, y-.007), color, 1.8,
         linestyle=linestyle)
    label(fig, x+.037, y, value, 10)


def render_preview():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "pdf.fonttype": 42, "svg.fonttype": "none",
                         "svg.hashsalt": "cells-to-circuit-2026-10-31"})
    fig = plt.figure(figsize=(11.6, 8.2), facecolor="white")
    d = preview_data()
    phase = d["phase"]

    label(fig, .555, .982, "Independent population activity", 11, ha="center")
    for j, x in enumerate((.405, .545, .685)):
        color = RED if j < 2 else BLUE
        node(fig, (x-.023, .911), j+1, radius=.010, color=color, size=10)
        ax = trace_axes(fig, [x, .875, .085, .071])
        ax.plot(phase, d["activities"][j], color=color, lw=1.8)
    flow(fig, (.558, .864), (.558, .825))

    label(fig, .030, .805, "A  Cellular synaptic inputs", 12, weight="bold")
    label(fig, .345, .805, "B  Candidate source inputs", 12, weight="bold")
    label(fig, .835, .805, "C  Circuit", 12, weight="bold")
    rows = (.660, .440, .220)
    for row, y in enumerate(rows):
        color, fill = (BLUE, PALE_BLUE) if row == 0 else (RED, PINK)
        label(fig, .030, y+.073, f"Sampled population {row+1}", 10.5,
              weight="bold")
        for index, x in enumerate((.039, .101, .163, .225)):
            node(fig, (x+.024, y+.028), chr(97+index), radius=.0077, size=8)
            ax = trace_axes(fig, [x, y-.060, .048, .063])
            ax.plot(phase, d["cells"][row, index], color=color, lw=1.3)
        flow(fig, (.288, y-.014), (.329, y-.014))

        ax = trace_axes(fig, [.345, y-.065, .405, .145], phase_labels=row == 2)
        ax.set_label(f"candidate-inputs-{row+1}")
        ax.fill_between(phase, d["lower"][row], d["upper"][row],
                        facecolor=fill, edgecolor="none", zorder=1,
                        label="Cell-to-cell spread")
        for cell in d["cells"][row]:
            ax.plot(phase, cell, color="#aab0b4", lw=.65, alpha=.7, zorder=2)
        # Omission predictions, rather than a full fit on the sample mean,
        # carry the visual comparison. The graph assignments remain schematic.
        ax.plot(phase, d["predictions"][row, 0], color=color, lw=2,
                linestyle=DASH, zorder=4, label="Omission prediction")
        if row == 2:
            ax.plot(phase, d["predictions"][row, 1], color=color, lw=2,
                    linestyle=DOT, zorder=4, label="Omission prediction")
            ax.plot(phase, d["predictions"][row, 2], color=color, lw=2,
                    linestyle=DASH_DOT, zorder=4, label="Omission prediction")
        ax.plot(phase, d["means"][row], color=MEAN, lw=1.15,
                zorder=3, label="Sample mean")
        key_y = y-.092 if row < 2 else y-.112
        curve_key(fig, .345, key_y, "Without 3" if row == 0 else "Without 1",
                  color, DASH)
        if row == 2:
            curve_key(fig, .485, key_y, "Without 2", color, DOT)
            curve_key(fig, .625, key_y, "Without both", color, DASH_DOT)
        flow(fig, (.765, y), (.810, y))
        node(fig, (.854, y), row+1, radius=.022, size=13)

    circuit_edge(fig, (.871, rows[2]-.021), (.871, rows[0]+.021),
                 (.989, .228), (.989, .652), BLUE, inhibitory=True)
    circuit_edge(fig, (.838, rows[0]-.022), (.838, rows[1]+.022),
                 (.795, .593), (.795, .507), RED)
    circuit_edge(fig, (.875, rows[0]-.012), (.875, rows[2]-.012),
                 (.946, .573), (.946, .307), RED, alternative=True)
    circuit_edge(fig, (.838, rows[1]-.022), (.838, rows[2]+.022),
                 (.795, .373), (.795, .287), RED, alternative=True)
    label(fig, .854, .172, "1, 2, or both", 10, ha="center")
    curve_key(fig, .801, .128, "Identified", INK, "solid")
    curve_key(fig, .801, .101, "Alternatives", INK, DASH)

    line(fig, (.030, .067), (.973, .067), "#dce0e2", .8)
    for x, fill in ((.030, PALE_BLUE), (.044, PINK)):
        fig.add_artist(Rectangle((x, .034), .014, .013,
                                  transform=fig.transFigure, fc=fill, ec="none"))
    label(fig, .066, .051, "Cell-to-cell spread", 9.5)
    line(fig, (.265, .041), (.293, .041), "#aab0b4", .9)
    label(fig, .302, .051, "Individual cells", 9.5)
    line(fig, (.445, .041), (.473, .041), MEAN, 1.15)
    label(fig, .480, .051, "Sample mean", 9.5)
    line(fig, (.650, .041), (.678, .041), RED, 1.7)
    label(fig, .688, .051, "Excitation", 9.5)
    line(fig, (.831, .041), (.859, .041), BLUE, 1.7)
    label(fig, .869, .051, "Inhibition", 9.5)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", action="store_true",
                        help="Write the approved figure to paper/figures only.")
    args = parser.parse_args()
    target = PAPER_FIGURE if args.paper else PDF
    target.parent.mkdir(parents=True, exist_ok=True)
    fig = render_preview()
    validate_layout(fig)
    fig.savefig(target, bbox_inches="tight", pad_inches=.12,
                metadata={"CreationDate": None, "ModDate": None,
                          "Title": "Cells to circuit: source omission preview"})
    if args.paper:
        plt.close(fig)
        print(target)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "cells_to_circuit.png", dpi=180,
                bbox_inches="tight", pad_inches=.12)
    svg = OUT / "cells_to_circuit.svg"
    fig.savefig(svg, bbox_inches="tight", pad_inches=.12, metadata={"Date": None})
    svg.write_text("\n".join(row.rstrip() for row in svg.read_text().splitlines()) + "\n")
    plt.close(fig)
    (OUT / "manifest.json").write_text(json.dumps({
        "status": "Approved Figure 1; shared renderer for manuscript and standalone preview",
        "signals": "Constructed schematic signals; no empirical analysis",
        "cell_count_per_population": 4,
        "shading": "Pointwise minimum-to-maximum of the four illustrated cellular profiles",
        "sample_mean": "Thin continuous charcoal curve, drawn below colored omission predictions",
        "statistical_status": "Descriptive spread, not a confidence band or test boundary; circuit assignments are illustrative",
        "comparisons": ["without 3", "without 1",
                        "without 1, without 2, and without both"],
        "full_fit": "Not displayed; omission predictions are compared with the sampled inputs",
        "edges": EDGES,
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "pdf": str(PDF.relative_to(ROOT)),
    }, indent=2) + "\n")
    print(PDF)


if __name__ == "__main__":
    main()
