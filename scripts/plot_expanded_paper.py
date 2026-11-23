#!/usr/bin/env python3
"""Manuscript figures from frozen expanded-cohort results; no inference rerun."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch
from matplotlib.path import Path as MplPath
import numpy as np
from expanded_paper_reporting import (
    DISPLAY_NAMES, REPORT_INPUTS, TABLES, load_reports, write_tables, write_data,
    score_figure, alternatives_figure, alignment_figure,
)

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("pre-I", "ramp-I", "early-I", "post-I", "aug-E")
FAMILIES = ("Inspiratory", "post-I", "aug-E")
COLORS = {"E": "#b83e3d", "I": "#287ba5"}
ALTERNATIVE_COLORS = {"E": "#cf8988", "I": "#7aa8c0"}
COMPONENT_COLORS = ("#247b68", "#8a62a0", "#bf7e27")
INPUTS = {
    "summary": "data/model_analyses/inspiratory_subset_contrasts/summary.json",
    "cells": "data/model_analyses/coarse_connection_contrasts/cells.json",
    "records": "data/model_analyses/coarse_connection_contrasts/records.json",
    "basis": "data/model_analyses/coarse_connection_contrasts/contrasts.json",
    "geometry": "output/circuit_previews/six_population_2026-09-26/manifest.json",
    **REPORT_INPUTS,
}
FIGURES = (
    "expanded_profiles.pdf", "expanded_fits.pdf", "expanded_circuit.pdf",
    "expanded_prior_circuit.pdf", "expanded_evidence.pdf",
    "expanded_score_diagnostics.pdf", "expanded_alternatives.pdf",
    "expanded_template_alignment.pdf",
)
# Discharge-pattern projection of Smith et al. 2007, Figure 7 and Table 3.
# Early-I(1)/(2) and post-I/post-I(e) are collapsed, not equated anatomically.
PRIOR_RELATIONS = tuple(
    [("pre-I", target, "E") for target in NAMES[:3]]
    + [(source, target, "I") for target, source in (
        ("pre-I", "aug-E"), ("pre-I", "post-I"),
        ("early-I", "aug-E"), ("early-I", "post-I"),
        ("aug-E", "early-I"), ("aug-E", "post-I"),
        ("post-I", "early-I"), ("post-I", "aug-E"),
        ("ramp-I", "early-I"), ("ramp-I", "aug-E"),
        ("ramp-I", "post-I"))]
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return row["source"], row["target"], row["sign"]


def compare_prior(summary):
    coarse = {key(r): r for r in summary["coarse_policy"]}
    panels = {(p["target"], p["sign"]): p for p in summary["panels"]}
    rows = []
    for source, target, sign in PRIOR_RELATIONS:
        family = "Inspiratory" if source in NAMES[:3] else source
        row = coarse[family, target, sign]
        individually_supported = (source in panels[target, sign]["individually_required"]
                                  if family == "Inspiratory" else row["supported"])
        rows.append(dict(source=source, target=target, sign=sign,
                         coarse_source=family, coarse_supported=row["supported"],
                         individually_supported=individually_supported,
                         p_joint_coarse=row["p_joint"]))
    old_keys = {(r["coarse_source"], r["target"], r["sign"]) for r in rows}
    added = [r for r in summary["coarse_policy"] if r["supported"] and key(r) not in old_keys]
    return dict(reference="Smith et al. 2007 Figure 7 / Table 3; pattern-level projection",
                rows=rows, additional_coarse_relations=added,
                counts=dict(projected_relations=len(rows),
                            coarse_supported=sum(r["coarse_supported"] for r in rows),
                            individually_supported=sum(r["individually_supported"] for r in rows),
                            additional=len(added)))


def load_evidence(root=ROOT):
    raw = {k: json.loads((root / p).read_text()) for k, p in INPUTS.items()}
    s = raw["summary"]["fixed_fall50"]
    cells = raw["cells"]["fixed_fall50"]
    records = raw["records"]["fixed_fall50"]
    basis = raw["basis"]["fixed_fall50"][0]
    a = np.asarray(basis["matrix"])
    assert a.shape == (100, 5)
    assert len(cells) == 150 and len(records) == 168
    assert sum(c["n_records"] for c in cells) == 168
    assert [sum(c["phenotype"] == n for c in cells) for n in NAMES] == [17, 41, 8, 54, 30]
    assert len(s["coarse_policy"]) == 30
    assert sum(r["supported"] for r in s["coarse_policy"]) == 20
    assert sum(r["p_joint"] < .05 for r in s["tests"]) == 32
    assert all(r["supported"] == (r["p_joint"] < .05) for r in s["coarse_policy"])
    groups = {}
    for name in NAMES:
        rows = [r for r in cells if r["phenotype"] == name]
        profiles = np.asarray([r["profiles"] for r in rows])
        prediction = np.mean([r["prediction"] for r in rows], axis=0)
        coef = np.mean([r["coefficients"] for r in rows], axis=0)
        components = np.asarray([a[:, ids] @ coef[:, ids].T for ids in ([0, 1, 2], [3], [4])])
        np.testing.assert_allclose(components.sum(axis=0).T, prediction, atol=1e-12)
        np.testing.assert_allclose(np.sum([r["shares"] for r in rows], axis=(1, 2)), 1)
        for si, sign in enumerate(("E", "I")):
            p = next(p for p in s["panels"] if (p["target"], p["sign"]) == (name, sign))
            np.testing.assert_allclose(profiles.mean(axis=0)[si], p["mean_profile"], atol=1e-12)
            np.testing.assert_allclose(prediction[si], p["mean_subset_predictions"][7], atol=1e-12)
            for family, ids in zip(FAMILIES, ([0, 1, 2], [3], [4])):
                row = next(r for r in s["coarse_policy"] if key(r) == (family, name, sign))
                value = np.mean([sum(r["shares"][si][j] for j in ids) for r in rows])
                np.testing.assert_allclose(value, row["share_mean"], atol=1e-12)
        groups[name] = dict(n=len(rows), profiles=profiles, prediction=prediction,
                            components=components,
                            rmse_median=np.median([r["rmse_joint_peak"] for r in rows], axis=0))
    geometry = raw["geometry"]
    assert geometry["input_sha256"][INPUTS["summary"]] == digest(root / INPUTS["summary"])
    members = [m for r in geometry["grouped"]["overview"] for m in r["members"]]
    assert sorted(map(key, members)) == sorted(key(r) for r in s["coarse_policy"] if r["supported"])
    prior = compare_prior(s)
    assert prior["counts"] == dict(projected_relations=14, coarse_supported=12,
                                   individually_supported=9, additional=8)
    return dict(summary=s, cells=cells, records=records, matrix=a, ti=basis["ti"],
                groups=groups, geometry=geometry, prior=prior)


def axes_style(ax, ti, last=False):
    ax.axvspan(0, ti, color="#edf0f1", zorder=0)
    ax.set(xlim=(0, 1), ylim=(0, 1.03), yticks=(0, .5, 1))
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=2.5, pad=2)
    ax.set_xticks((0, ti, 1), ("0", "I/E", "1") if last else ("", "", ""))
    if last:
        ax.set_xlabel("Respiratory phase")


def save(fig, out, name):
    fig.savefig(out / name, metadata={"CreationDate": None, "ModDate": None,
                                     "Author": "Molkov, Rybak and Smith"})
    plt.close(fig)


def profiles_figure(d, out):
    fig = plt.figure(figsize=(7, 8.7))
    grid = fig.add_gridspec(7, 10, height_ratios=[.92, .22, 1, 1, 1, 1, 1],
                           left=.10, right=.98, top=.96, bottom=.06, hspace=.43, wspace=.7)
    x = np.arange(100) / 100
    fig.text(.018, .975, "A", weight="bold", fontsize=12)
    for i, name in enumerate(NAMES):
        ax = fig.add_subplot(grid[0, i*2:i*2+2])
        axes_style(ax, d["ti"])
        ax.plot(x, d["matrix"][:, i], color="#25343b", lw=1.7)
        ax.set_title(DISPLAY_NAMES[name], fontsize=10)
        ax.set_xticks((0, 1), ("0", "1"))
        if i:
            ax.set_yticklabels([])
        else:
            ax.set_ylabel("Activity")
    fig.text(.018, .795, "B", weight="bold", fontsize=12)
    for i, name in enumerate(NAMES):
        group = d["groups"][name]
        for si, sign in enumerate(("E", "I")):
            ax = fig.add_subplot(grid[i+2, si*5:si*5+5])
            axes_style(ax, d["ti"], i == 4)
            for row in group["profiles"][:, si]:
                ax.plot(x, row, color="#aeb7bc", alpha=.40, lw=.55)
            ax.plot(x, group["profiles"].mean(axis=0)[si], color=COLORS[sign], lw=1.8)
            if i == 0:
                ax.set_title("Excitatory conductance" if si == 0 else "Inhibitory conductance", fontsize=10)
            if si == 0:
                ax.set_ylabel(f"{DISPLAY_NAMES[name]}\nn = {group['n']}")
    save(fig, out, FIGURES[0])


def fits_figure(d, out):
    fig, axes = plt.subplots(5, 2, figsize=(7, 7.2), sharex=True, sharey=True)
    fig.subplots_adjust(left=.13, right=.98, bottom=.08, top=.91, hspace=.30, wspace=.18)
    x = np.arange(100) / 100
    for i, name in enumerate(NAMES):
        group = d["groups"][name]
        for si, sign in enumerate(("E", "I")):
            ax = axes[i, si]
            axes_style(ax, d["ti"], i == 4)
            for j, color in enumerate(COMPONENT_COLORS):
                ax.plot(x, group["components"][j, :, si], color=color, lw=1.2)
            ax.plot(x, group["profiles"].mean(axis=0)[si], color="#20282b", lw=1.8)
            ax.plot(x, group["prediction"][si], color="#6a757c", lw=1.5, ls="--")
            if si == 0:
                ax.set_ylabel(DISPLAY_NAMES[name])
            if i == 0:
                ax.set_title("Excitatory conductance" if si == 0 else "Inhibitory conductance", fontsize=10)
    legend = [Line2D([], [], color="#20282b", lw=1.8, label="Sample mean"),
              Line2D([], [], color="#6a757c", ls="--", lw=1.5, label="Full fit")]
    legend += [Line2D([], [], color=c, lw=1.4, label=n) for c, n in zip(COMPONENT_COLORS, FAMILIES)]
    fig.legend(handles=legend, loc="upper center", ncol=5, frameon=False, fontsize=8.5)
    save(fig, out, FIGURES[1])


def inhibitory_terminal(ax, endpoint, width, alpha=1, zorder=8):
    terminal, = ax.plot(*endpoint, marker="o", markersize=max(3.4, width+2.4),
                        markeredgewidth=0, color=COLORS["I"], linestyle="none",
                        alpha=alpha, zorder=zorder)
    return terminal


def curved_edge(ax, points, sign, width, *, halo=False, gid=None):
    path = MplPath(points, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    style = "-|>" if sign == "E" else "-"
    arrow = FancyArrowPatch(path=path, arrowstyle=style, mutation_scale=6.5,
                            lw=width, color=COLORS[sign], zorder=2,
                            capstyle="round", joinstyle="round", gid=gid)
    if halo:
        arrow.set_path_effects([pe.Stroke(linewidth=width+1.5, foreground="white"), pe.Normal()])
    ax.add_patch(arrow)
    if sign == "I":
        inhibitory_terminal(ax, points[-1], width)


def inspiratory_connections(panels):
    rows = []
    for panel in panels:
        masks = panel["minimal_unexcluded_masks"]
        common, included = 7, 0
        for mask in masks:
            common &= mask
            included |= mask
        alternatives = included & ~common
        for mask in range(8):
            general = mask & common == common and (not alternatives or bool(mask & alternatives))
            shown = bool(mask & 1 or mask & 6 == 6) if (panel["target"], panel["sign"]) == ("early-I", "E") else general
            assert shown == any(mask & minimum == minimum for minimum in masks)
        for bit, source in enumerate(NAMES[:3]):
            if included & (1 << bit):
                rows.append(dict(source=source, target=panel["target"], sign=panel["sign"],
                                 style="solid" if common & (1 << bit) else "dashed"))
    return rows


def inspiratory_edge(ax, path, sign, style, gid, endpoint):
    solid = style == "solid"
    width = 1.45 if solid else .82
    color = COLORS[sign] if solid else ALTERNATIVE_COLORS[sign]
    edge = FancyArrowPatch(path=path, arrowstyle="-", lw=width,
                           linestyle="-" if solid else (0, (3.4, 3.2)),
                           color=color, zorder=3 if solid else 2, capstyle="round", gid=gid,
                           path_effects=[pe.Stroke(linewidth=width+1.5, foreground="white"), pe.Normal()])
    ax.add_patch(edge)
    if sign == "I":
        terminal = inhibitory_terminal(ax, endpoint, width)
        terminal.set_color(color)
        terminal.set_markersize(3.6 if solid else 3.0)
    else:
        ax.add_patch(FancyArrowPatch(endpoint-(11, 0), endpoint, shrinkA=0, shrinkB=0,
                                    arrowstyle="-|>", mutation_scale=6 if solid else 5.5, lw=.85,
                                    color=color, zorder=4, gid="terminal:"+gid))


def inspiratory_graph(ax, panels):
    target_y = dict(zip(NAMES, (450, 357, 264, 171, 78)))
    source_y = {"E": {"early-I": 427, "ramp-I": 264, "pre-I": 101},
                "I": {"pre-I": 427, "early-I": 264, "ramp-I": 101}}
    rows = inspiratory_connections(panels)
    pair_branches = []
    pair_join = np.array((385, target_y["early-I"]))
    for row in sorted(rows, key=lambda row: row["style"] == "solid"):
        sign, source, target = row["sign"], row["source"], row["target"]
        direction = 1 if sign == "E" else -1
        sx, tx = (82 if sign == "E" else 918), 500
        sy, ty = source_y[sign][source], target_y[target]
        sdy = np.clip((ty-sy)*.10, -25, 25)
        rank = sorted(source_y[sign], key=source_y[sign].get).index(source)
        tdy = (rank-1)*22
        start = np.array((sx+direction*np.sqrt(39**2-sdy**2), sy+sdy))
        end = np.array((tx-direction*np.sqrt(39**2-tdy**2), ty+tdy))
        if sign == "I":
            end[0] -= direction*4
        span = end[0]-start[0]
        points = np.array((start, start+(span*.40, 0), end-(span*.40, 0), end))
        if sign == "E" and target == "early-I" and source in ("ramp-I", "early-I"):
            assert row["style"] == "dashed"
            span = pair_join[0]-start[0]
            approach = 25 if source == "early-I" else -20
            pair_branches.append(np.array((start, start+(span*.40, 0),
                                           pair_join+(-50, approach), pair_join)))
            continue
        path = MplPath(points, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
        inspiratory_edge(ax, path, sign, row["style"],
                         f"inspiratory:{source}:{target}:{sign}:{row['style']}", end)
    # Draw both branches and their shared terminal as one path so the white
    # crossing outlines cannot separate the paired alternative at its junction.
    assert len(pair_branches) == 2
    pair_end = np.array((500-39, pair_join[1]))
    span = pair_end-pair_join
    trunk = np.array((pair_join, pair_join+span/3, pair_join+2*span/3, pair_end))
    pair_path = MplPath(np.concatenate((*pair_branches, trunk)),
                       [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]*3)
    inspiratory_edge(ax, pair_path, "E", "dashed", "paired-inspiratory:early-I:E:dashed", pair_end)
    for sign in ("E", "I"):
        x = 82 if sign == "E" else 918
        for name, y in source_y[sign].items():
            ax.add_patch(Circle((x, y), 39, fc="#fff7f5" if sign == "E" else "#f2f8fb",
                                ec=COLORS[sign], lw=.9, zorder=5))
            ax.text(x, y, DISPLAY_NAMES[name], color=COLORS[sign], fontsize=8.2, weight="bold",
                    ha="center", va="center", zorder=6)
    for name, y in target_y.items():
        ax.add_patch(Circle((500, y), 39, fc="#f7f8f9", ec="#8798a0", lw=.8, zorder=5))
        ax.text(500, y, name+"*" if name == "early-I" else DISPLAY_NAMES[name],
                fontsize=8.0, ha="center", va="center", zorder=6)
    for x, label, color in ((82, "Excitatory sources", COLORS["E"]),
                             (500, "Receiving populations", "#25343b"),
                             (918, "Inhibitory sources", COLORS["I"])):
        ax.text(x, 515, label, color=color, fontsize=9, ha="center", va="center")
    handles = [Line2D([], [], color=color, lw=width, linestyle=style, label=label)
               for style, width, color, label in (("-", 1.45, "#505b61", "Individual input supported"),
                   ((0, (3.4, 3.2)), .82, "#8d999e", "Unresolved alternatives"))]
    ax.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=9,
              handlelength=3, borderaxespad=0)
    ax.set(xlim=(-25, 1025), ylim=(-18, 540), aspect="equal")
    ax.axis("off")


def overview_geometry():
    centers = {"Inspiratory": (310, 340), "post-I": (110, 120), "aug-E": (510, 120)}
    nodes = {(group, sign): np.array(center)+(dx, 0)
             for group, center in centers.items() for sign, dx in (("E", -28), ("I", 28))}
    # Ports are on the unresolved target enclosure, not on a transmitter node.
    # Separate lanes retain reciprocal directions and all five recurrent loops.
    routes = {
        ("Inspiratory", "Inspiratory", "E"): (150, 120, (190, 387), (220, 451)),
        ("Inspiratory", "Inspiratory", "I"): (30, 60, (430, 387), (400, 451)),
        ("post-I", "post-I", "E"): (200, 245, (-8, 82), (20, 2)),
        ("post-I", "post-I", "I"): (315, 300, (220, 52), (164, 20)),
        ("aug-E", "aug-E", "E"): (240, 300, (431, 16), (555, 10)),
        ("Inspiratory", "post-I", "E"): (230, 100, (225, 253), (117, 216)),
        ("Inspiratory", "post-I", "I"): (235, 45, (284, 245), (211, 221)),
        ("post-I", "Inspiratory", "I"): (75, 190, (170, 221), (198, 317)),
        ("Inspiratory", "aug-E", "E"): (300, 145, (316, 253), (383, 227)),
        ("Inspiratory", "aug-E", "I"): (310, 90, (421, 276), (501, 229)),
        ("aug-E", "Inspiratory", "E"): (140, 280, (435, 206), (358, 232)),
        ("aug-E", "Inspiratory", "I"): (65, 350, (603, 237), (497, 312)),
        ("post-I", "aug-E", "E"): (270, 210, (185, -5), (370, 14)),
        ("post-I", "aug-E", "I"): (0, 180, (253, 136), (359, 136)),
        ("aug-E", "post-I", "I"): (315, 330, (648, -44), (278, -47)),
    }
    paths = {}
    for (source, target, sign), (sa, ta, cp1, cp2) in routes.items():
        sa, ta = np.deg2rad((sa, ta))
        start = nodes[source, sign]+18*np.array((np.cos(sa), np.sin(sa)))
        end = np.array(centers[target])+np.array((77*np.cos(ta), 48*np.sin(ta)))
        paths[source, target, sign] = np.array((start, cp1, cp2, end))
    return centers, nodes, paths


def circuit_figure(d, out):
    fig = plt.figure(figsize=(7, 6.6))
    a = fig.add_axes((.015, .635, .49, .31))
    b = fig.add_axes((.535, .64, .45, .305))
    c = fig.add_axes((.015, .025, .97, .515))
    for ax in (a, b):
        ax.set_aspect("equal")
        ax.axis("off")
    overview = d["geometry"]["pages"][0]["overview"]
    centers, nodes, paths = overview_geometry()
    assert set(paths) == {key(row) for row in overview["edges"]}
    for name, center in centers.items():
        a.add_patch(Ellipse(center, 154, 96, fc="#f7f8f9", ec="#a4b2b9", lw=.8))
    for name, xy, ha, va in (("Insp.", (310, 420), "center", "bottom"),
                              ("post-I", (18, 120), "right", "center"),
                              ("aug-E", (602, 120), "left", "center")):
        a.text(*xy, name, ha=ha, va=va, fontsize=9.5, weight="bold", zorder=4,
               gid="overview-label:"+name)
    for row in overview["edges"]:
        curved_edge(a, paths[key(row)], row["sign"], .45+4*row["target_average_share"],
                    halo=True, gid="overview:"+":".join(key(row)))
    for (group, sign), center in nodes.items():
        a.add_patch(Circle(center, 18, fc="#fff7f5" if sign == "E" else "#f2f8fb",
                           ec=COLORS[sign], lw=1, zorder=5))
    a.set(xlim=(-115, 745), ylim=(-25, 470))
    source_centers = {("aug-E", "E"): (90, 300),
                      ("post-I", "I"): (90, 184), ("aug-E", "I"): (90, 68)}
    target_centers = dict(zip(NAMES[:3], ((450, 300), (450, 184), (450, 68))))
    radius = 43
    incoming = d["geometry"]["pages"][0]["incoming"]["edges"]
    for row in incoming:
        source = np.array(source_centers[row["source"], row["sign"]])
        target = np.array(target_centers[row["target"]])
        # Distinct source ports keep the three post-I projections traceable.
        sdy = (target[1]-source[1])*.16
        tdy = 12 if row["source"] == "post-I" else -12
        if row["target"] == "early-I":
            tdy = 0
        start = source+(np.sqrt(radius**2-sdy**2), sdy)
        end = target+(-np.sqrt(radius**2-tdy**2)-2, tdy)
        span = end[0]-start[0]
        points = np.array((start, start+(span*.38, 0), end-(span*.38, 0), end))
        curved_edge(b, points, row["sign"], .45+4*row["share_mean"], halo=True,
                    gid="expiratory:"+":".join(key(row)))
    for (name, sign), xy in source_centers.items():
        b.add_patch(Circle(xy, radius, fc="#fff7f5" if sign == "E" else "#f2f8fb",
                          ec=COLORS[sign], lw=1, zorder=4))
        b.text(*xy, name, ha="center", va="center", fontsize=8.2, color=COLORS[sign], weight="bold", zorder=5)
    for name, xy in target_centers.items():
        b.add_patch(Circle(xy, radius, fc="#f5f7f8", ec="#8798a0", lw=.8, zorder=4))
        b.text(*xy, DISPLAY_NAMES[name], ha="center", va="center", fontsize=8.2, zorder=5)
    b.text(90, 369, "Expiratory", ha="center", fontsize=9)
    b.text(450, 369, "Inspiratory", ha="center", fontsize=9)
    b.set(xlim=(0, 540), ylim=(0, 395))
    for x, letter, title in ((.015, "A", "Circuit overview"), (.535, "B", "Expiratory inputs")):
        fig.text(x, .967, letter+"  "+title, fontsize=10.5, weight="bold", gid="panel-title-"+letter)
    handles = [Line2D([], [], color=COLORS[s], lw=1.8, label=l)
               for s, l in (("E", "Excitation"), ("I", "Inhibition"))]
    handles[1].set(marker="o", markersize=4.2, markeredgewidth=0)
    handles += [Line2D([], [], color="#505b61", lw=.45+4*v, label=f"{100*v:.0f}%") for v in (.1, .3, .5)]
    legend = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .595), ncol=5,
                        frameon=False, fontsize=8.5, numpoints=2, handlelength=2.3)
    legend.legend_handles[1].set_markevery([1])
    fig.text(.015, .565, "C  Inspiratory inputs", fontsize=10.5, weight="bold", gid="panel-title-C")
    inspiratory_graph(c, d["summary"]["panels"])
    save(fig, out, FIGURES[2])


def prior_figure(out):
    # Reuse only the historical graph renderer, not its fitting pipeline.
    from plot_empirical_connectome import smith2007_concept_structure_matrices
    from connectome_graph_utils import draw_connectome_graph
    e, i = smith2007_concept_structure_matrices()
    fig, ax = plt.subplots(figsize=(4.25, 4.1), layout="constrained")
    draw_connectome_graph(ax, e, i, "", threshold=.5, max_weight=3,
        label_threshold=2, layout="pentagon", straight_edges=True,
        active_nodes=["pre-I", "ramp-I", "early-I", "post-I^E", "post-I^I", "aug-E^I"],
        node_radius=.080, reciprocal_offset=.008,
        node_label_overrides={"pre-I": DISPLAY_NAMES["pre-I"], "aug-E^I": "aug-E",
                              "post-I^I": "post-I", "post-I^E": ""},
        show_legend=False)
    for patch in ax.patches:
        rgb = patch.get_facecolor() if isinstance(patch, Circle) else patch.get_edgecolor()
        sign = "I" if rgb[2] > rgb[0] else "E"
        patch.set_edgecolor(COLORS[sign])
        if isinstance(patch, Circle):
            patch.set_facecolor("#f2f8fb" if sign == "I" else "#fff7f5")
        else:
            patch.set_facecolor(COLORS[sign])
        if isinstance(patch, FancyArrowPatch) and sign == "I":
            patch.set_arrowstyle("-")
            patch.shrinkB = 0
            inhibitory_terminal(ax, patch.get_path().vertices[-1],
                                patch.get_linewidth(), alpha=patch.get_alpha())
    for text in ax.texts:
        text.set_fontsize(max(11, text.get_fontsize()))
    save(fig, out, FIGURES[3])


def p_label(p):
    if p < .001:
        return "<0.001"
    return f"{p:.3f}" if p < 1 else "1"


def matrix_axes(ax, rows, sign, field, title):
    indexed = {key(r): r for r in rows}
    ax.set(xlim=(-.5, 4.5), ylim=(2.5, -.5))
    ax.set_xticks(range(5), [DISPLAY_NAMES[n] for n in NAMES], fontsize=9)
    ax.set_yticks(range(3), ("Inspiratory", "post-I", "aug-E"), fontsize=9)
    ax.tick_params(length=0)
    ax.xaxis.tick_top()
    for spine in ax.spines.values():
        spine.set_visible(False)
    for y, source in enumerate(FAMILIES):
        for x, target in enumerate(NAMES):
            row = indexed[source, target, sign]
            if field == "share_mean":
                value = row[field]*100
                shade = .10 + .7*row[field]
                ax.add_patch(plt.Rectangle((x-.48, y-.46), .96, .92, color=COLORS[sign], alpha=shade, ec="none"))
                label = f"{value:.1f}"
            else:
                if row["supported"]:
                    ax.add_patch(plt.Rectangle((x-.48, y-.46), .96, .92, color=COLORS[sign], alpha=.16, ec="none"))
                label = p_label(row[field])
            ax.text(x, y, label, ha="center", va="center", fontsize=8 if field != "share_mean" else 9,
                    weight="bold" if field != "share_mean" and row["supported"] else "normal")
    ax.set_title(title, fontsize=10, pad=18, color=COLORS[sign])


def evidence_figure(d, out):
    fig, axes = plt.subplots(2, 2, figsize=(7, 5.4))
    fig.subplots_adjust(left=.15, right=.985, top=.83, bottom=.05, hspace=.90, wspace=.41)
    for si, sign in enumerate(("E", "I")):
        title = "Excitation" if sign == "E" else "Inhibition"
        matrix_axes(axes[0, si], d["summary"]["coarse_policy"], sign,
                    "share_mean", title)
        matrix_axes(axes[1, si], d["summary"]["coarse_policy"],
                    sign, "p_joint", title)
    fig.text(.02, .97, "A  Mean fitted contribution (% total excitatory + inhibitory area)",
             fontsize=10, weight="bold")
    fig.text(.02, .46, "B  Adjusted P values for tests of omitted inputs", fontsize=10, weight="bold")
    save(fig, out, FIGURES[4])


def options_figure(d, out):
    """Historical A2 renderer; not included in the current manuscript build."""
    fig, axes = plt.subplots(5, 2, figsize=(7, 6.6))
    fig.subplots_adjust(left=.12, right=.98, bottom=.03, top=.94, hspace=.22, wspace=.10)
    indexed = {(p["target"], p["sign"]): p for p in d["summary"]["panels"]}
    for i, name in enumerate(NAMES):
        for si, sign in enumerate(("E", "I")):
            ax = axes[i, si]
            ax.set(xlim=(0, 360), ylim=(0, 110), aspect="equal")
            ax.axis("off")
            if si == 0:
                ax.text(-.07, .5, name, transform=ax.transAxes, ha="right", va="center", fontsize=10, weight="bold")
            if i == 0:
                ax.set_title("Excitation" if sign == "E" else "Inhibition", fontsize=11, color=COLORS[sign])
            p = indexed[name, sign]
            masks = p["minimal_unexcluded_masks"]
            if masks == [0]:
                ax.text(180, 55, "No inspiratory contribution\nestablished", ha="center", va="center", fontsize=9)
                continue
            gap = 22
            slot = (360 - gap * (len(masks)-1)) / len(masks)
            radius = 20 if len(masks) == 3 else 26
            font = 6.5 if len(masks) == 3 else 7.5
            for j, mask in enumerate(masks):
                sources = [n for bit, n in enumerate(NAMES[:3]) if mask & (1 << bit)]
                left, right = j*(slot+gap), j*(slot+gap)+slot
                sx, tx = left+radius+4, right-radius-4
                ys = [55] if len(sources) == 1 else [82, 28]
                for source, y in zip(sources, ys):
                    start, end = np.array((sx, y)), np.array((tx, 55))
                    direction = (end-start) / np.linalg.norm(end-start)
                    start = start + direction * (radius+1)
                    end = end - direction * (radius+2)
                    ax.add_patch(FancyArrowPatch(start, end, shrinkA=0, shrinkB=0,
                                 arrowstyle="-|>" if sign == "E" else "-",
                                 mutation_scale=6, color=COLORS[sign], lw=1))
                    if sign == "I":
                        inhibitory_terminal(ax, end, 1)
                    ax.add_patch(Circle((sx, y), radius, fc="white", ec=COLORS[sign], lw=.8))
                    ax.text(sx, y, source, color=COLORS[sign], ha="center", va="center", fontsize=font,
                            weight="bold" if source in p["individually_required"] else "normal")
                ax.add_patch(Circle((tx, 55), radius, fc="#f5f7f8", ec="#8798a0", lw=.8))
                ax.text(tx, 55, name, ha="center", va="center", fontsize=font)
                if j < len(masks)-1:
                    ax.text(right+gap/2, 55, "or", ha="center", va="center", fontsize=8)
    save(fig, out, "expanded_inspiratory_options.pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "paper/figures")
    args = parser.parse_args()
    before = {p: digest(ROOT / p) for p in INPUTS.values()}
    d = load_evidence()
    report = load_reports(d)
    if args.check:
        print("Verified 150 cells / 168 recordings, 20 coarse relations, 90 omission tests, and 140 elementary summaries.")
        return
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                         "pdf.fonttype": 42})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    profiles_figure(d, args.output_dir)
    fits_figure(d, args.output_dir)
    circuit_figure(d, args.output_dir)
    prior_figure(args.output_dir)
    evidence_figure(d, args.output_dir)
    save(score_figure(d, report), args.output_dir, FIGURES[5])
    save(alternatives_figure(d, report), args.output_dir, FIGURES[6])
    save(alignment_figure(report), args.output_dir, FIGURES[7])
    write_tables(d, report, args.output_dir.parent / "tables")
    write_data(report, ROOT / "data/manuscript_reporting")
    assert before == {p: digest(ROOT / p) for p in INPUTS.values()}
    manifest = dict(analysis_run=False, input_sha256=before,
        builder_sha256=digest(Path(__file__)), scenario="fixed_fall50",
        prior_comparison=d["prior"],
        counts=dict(cells=150, recordings=168, coarse_supported=20),
        inspiratory_connections=inspiratory_connections(d["summary"]["panels"]),
        group_fit_median_rmse={n: g["rmse_median"].tolist() for n, g in d["groups"].items()},
        output_sha256={name: digest(args.output_dir / name) for name in FIGURES},
        table_sha256={name: digest(args.output_dir.parent / "tables" / name) for name in TABLES},
        reporting_sha256={name: digest(ROOT / "data/manuscript_reporting" / (name+".csv"))
                          for name in ("records", "tests", "elementary", "magnitudes")})
    (args.output_dir / "expanded_figure_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print("Wrote eight figures, four tables and descriptive CSVs; frozen inference inputs unchanged.")


if __name__ == "__main__":
    main()
