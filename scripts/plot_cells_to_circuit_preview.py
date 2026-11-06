"""Paper figure helpers extracted from the canonical plot_cells_to_circuit_preview.py.

Retained definitions and constants are verbatim; historical CLIs and unrelated
fitting dependencies are omitted.
"""
from __future__ import annotations

# Canonical source: scripts/plot_cells_to_circuit_preview.py
# SHA-256: 4ec29eeae6eba51f001239435c475d646782a8c92465594361899d1da22982fa
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, FancyArrowPatch, PathPatch
from matplotlib.path import Path as MplPath
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


INK = "#252b30"


PALE = "#c4c9cd"


RED = "#b83e3d"


BLUE = "#287ba5"


TI = .4


EDGES = ((3, 1, "inhibitory", "resolved"),
         (1, 2, "excitatory", "resolved"),
         (1, 3, "excitatory", "alternative"),
         (2, 3, "excitatory", "alternative"))


def schematic_data():
    """Construct distinct and overlapping explanations, not statistical results."""
    phase = np.linspace(0, 1, 301)
    u = np.minimum(phase / TI, 1)
    envelope = np.sin(np.pi * u)
    envelope[phase >= TI] = 0
    rising = envelope * (.2 + 1.2 * u)
    falling = envelope * (1.4 - 1.2 * u)
    dec_e = np.zeros_like(phase)
    ex = phase >= TI
    v = (phase[ex] - TI) / (1 - TI)
    onset = -np.expm1(-(v / .05)**2)
    dec_e[ex] = onset * np.exp(-3.5 * v) * (1 - v)
    dec_e /= dec_e.max()
    activities = np.array([rising, falling, dec_e])
    # Each row contains cells sampled from one receiving population. Only one
    # conductance per population is illustrated to keep the source comparison legible.
    weights = np.array([
        [[0, 0, .7], [0, 0, .9], [0, 0, 1.1]],
        [[.85, .03, 0], [.65, .02, 0], [1.1, .05, 0]],
        [[1, 0, 0], [.5, .5, 0], [0, 1, 0]],
    ])
    cells = weights @ activities
    means = cells.mean(axis=1)
    retained = ((2, None), (0, 1), (0, 1))
    predictions = np.zeros((3, 2, phase.size))
    for row, sources in enumerate(retained):
        for column, source in enumerate(sources):
            if source is not None:
                activity = activities[source]
                # Mean of individual nonnegative one-source fits; all scalar
                # projections are nonnegative for these constructed profiles.
                amplitudes = cells[row] @ activity / (activity @ activity)
                predictions[row, column] = amplitudes.mean() * activity
    return dict(phase=phase, activities=activities, cells=cells, means=means,
                predictions=predictions, weights=weights, sources=retained)


def label(fig, x, y, value, size=11, **kw):
    return fig.text(x, y, value, fontsize=size, color=INK, va="top", **kw)


def line(fig, start, end, color=PALE, lw=1, **kw):
    artist = Line2D([start[0], end[0]], [start[1], end[1]],
                    transform=fig.transFigure, color=color, lw=lw, **kw)
    fig.add_artist(artist)
    return artist


def flow(fig, start, end):
    fig.add_artist(FancyArrowPatch(start, end, transform=fig.transFigure,
                                  arrowstyle="-|>", mutation_scale=12,
                                  color=PALE, lw=1.1, zorder=0))


def node(fig, xy, name, radius=.021, color=INK, size=12):
    # Keep circles and labels in the same coordinate system when cropping.
    aspect = fig.get_figwidth() / fig.get_figheight()
    fig.add_artist(Ellipse(xy, 2 * radius, 2 * radius * aspect,
                           transform=fig.transFigure, fc="white", ec=color,
                           lw=1.5, zorder=8))
    fig.text(*xy, str(name), color=color, fontsize=size,
             ha="center", va="center", zorder=9)


def circuit_edge(fig, start, end, control1, control2, color, inhibitory=False,
                 alternative=False):
    vertices = [start, control1, control2, end]
    path = MplPath(vertices, [MplPath.MOVETO, MplPath.CURVE4,
                              MplPath.CURVE4, MplPath.CURVE4])
    dash = (0, (4, 3)) if alternative else "solid"
    if inhibitory:
        fig.add_artist(PathPatch(path, transform=fig.transFigure, fill=False,
                                  color=color, lw=1.9, linestyle=dash, zorder=4))
        fig.add_artist(Line2D([end[0]], [end[1]], transform=fig.transFigure,
                              color=color, marker="o", markersize=5, zorder=7))
    else:
        fig.add_artist(FancyArrowPatch(path=path, transform=fig.transFigure,
                                      arrowstyle="-|>", mutation_scale=13,
                                      color=color, lw=1.9, linestyle=dash, zorder=4))


def validate_layout(fig):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height
    for item in [*fig.texts, *(text for ax in fig.axes for text in ax.get_xticklabels())]:
        if not item.get_text():
            continue
        box = item.get_window_extent(renderer)
        if not (0 <= box.x0 < box.x1 <= width and 0 <= box.y0 < box.y1 <= height):
            raise ValueError(f"Text outside preview: {item.get_text()}")
    # Independently positioned figure labels must not collide.
    labels = [item for item in fig.texts if item.get_text()]
    for i, first in enumerate(labels):
        a = first.get_window_extent(renderer)
        for second in labels[i+1:]:
            if a.overlaps(second.get_window_extent(renderer)):
                raise ValueError(f"Overlapping text: {first.get_text()} / {second.get_text()}")

SOURCE_DEFINITIONS = [{'symbols': ['ROOT'], 'start_line': 17, 'end_line': 17, 'definition_sha256': '6c0caf441a1aad2240e7aaccbb2a73915fc5ce62a90eb857836d905c68760c7d'}, {'symbols': ['INK'], 'start_line': 20, 'end_line': 20, 'definition_sha256': '9872fe13267544fa16a76caf5f3ab60e4145a85e3ce580770f49ea90109b95b3'}, {'symbols': ['PALE'], 'start_line': 22, 'end_line': 22, 'definition_sha256': 'f4bfabc3cbeae530dff0e83bb8ed048e5d7ef866d43762c368a1b31d19a039b8'}, {'symbols': ['RED'], 'start_line': 23, 'end_line': 23, 'definition_sha256': '0749d6e2eb09219f21bc522c090484e3383f34d980664d1cb64b9a4ba8e639dc'}, {'symbols': ['BLUE'], 'start_line': 24, 'end_line': 24, 'definition_sha256': '41ce37a974039fffd8cd14a0cb812402b05dd873c64968bee8f5b517f13d0b73'}, {'symbols': ['TI'], 'start_line': 25, 'end_line': 25, 'definition_sha256': 'd80fe70a3701a0cd8d2532cbc8472d119d8df058270c3b7175bc76479b743d8c'}, {'symbols': ['EDGES'], 'start_line': 27, 'end_line': 30, 'definition_sha256': '05a1c6388c76e78eb03eed9179a2bbd2ea10116179cb34e35a437aa46eb8e37c'}, {'symbols': ['schematic_data'], 'start_line': 33, 'end_line': 68, 'definition_sha256': '7c75b64470e367489350b0ba52797f81851d97ee6f19d652652a1da0bada2482'}, {'symbols': ['label'], 'start_line': 71, 'end_line': 72, 'definition_sha256': 'd76b40808d61814c453a900b3ff679ab41a961e6d322be86035bad2c7ac0ff02'}, {'symbols': ['line'], 'start_line': 75, 'end_line': 79, 'definition_sha256': '8410aa2a74aca8d75bbb4e24b765c5eedb482804b9ada6f44f49d7cd21725f61'}, {'symbols': ['flow'], 'start_line': 82, 'end_line': 85, 'definition_sha256': 'dabcac04b649f4854950ae49660bdff90ffeaa3502a56c4e1f79c6b3d16604d7'}, {'symbols': ['node'], 'start_line': 88, 'end_line': 95, 'definition_sha256': '302fd63821192190aaa1f329ee51dfc9f3977ae7e04d69bed009460a52107dc4'}, {'symbols': ['circuit_edge'], 'start_line': 117, 'end_line': 131, 'definition_sha256': 'b3f28bd15ce4af178d2e6c001e64ad73374e074e595b513cf98a273e870b1b6c'}, {'symbols': ['validate_layout'], 'start_line': 225, 'end_line': 241, 'definition_sha256': '23e2afb0048f62bdb8fca8b84a7c3b493df72dc761cf360c2bce16d655c7deca'}]
