"""Paper figure helpers extracted from the canonical connectome_graph_utils.py.

Retained definitions and constants are verbatim; historical CLIs and unrelated
fitting dependencies are omitted.
"""
from __future__ import annotations

# Canonical source: scripts/connectome_graph_utils.py
# SHA-256: d615eaffbc5cdc4a9d90dd92ad7caae5ace30eab4e4a89fa4bc9c162b137fc05
import math
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon


PHENOTYPES = ["pre-I", "ramp-I", "early-I", "post-I", "aug-E"]


EXCITATORY_CANDIDATES = ["pre-I", "ramp-I", "post-I", "aug-E"]


INHIBITORY_CANDIDATES = ["early-I", "post-I", "aug-E"]


GE_COLOR = "#b2182b"


GI_COLOR = "#313695"


CLAIM_A_COLOR = "#1f77b4"


CLAIM_B_COLOR = "#d62728"


CLAIM_C_COLOR = "#ff7f0e"


NODE_POS = {
    "pre-I": (0.17, 0.58),
    "ramp-I": (0.37, 0.81),
    "post-I^E": (0.840, 0.325),
    "early-I": (0.80, 0.62),
    "post-I^I": (0.750, 0.390),
    "aug-E^I": (0.60, 0.18),
    "aug-E^E": (0.31, 0.22),
}


CIRCLE_NODE_POS = {
    "pre-I": (0.19, 0.50),
    "ramp-I": (0.33, 0.79),
    "post-I^E": (0.56, 0.84),
    "early-I": (0.80, 0.62),
    "post-I^I": (0.78, 0.32),
    "aug-E^I": (0.53, 0.16),
    "aug-E^E": (0.29, 0.25),
}


HEXAGON_NODE_POS = {
    "pre-I": (0.20, 0.50),
    "ramp-I": (0.35, 0.76),
    "early-I": (0.65, 0.76),
    "post-I^E": (0.855, 0.50),
    "post-I^I": (0.80, 0.50),
    "aug-E^I": (0.65, 0.24),
    "aug-E^E": (0.35, 0.24),
}


PENTAGON_NODE_POS = {
    "pre-I": (0.22, 0.50),
    "ramp-I": (0.43, 0.78),
    "early-I": (0.76, 0.67),
    "post-I^E": (0.825, 0.33),
    "post-I^I": (0.76, 0.33),
    "aug-E^I": (0.43, 0.22),
}


MOLKOV2014_CORE_CIRCLE_NODE_POS = {
    "pre-I": (0.18, 0.50),
    "ramp-I": (0.34, 0.78),
    "post-I^I": (0.66, 0.78),
    "early-I": (0.82, 0.50),
    "aug-E^I": (0.50, 0.22),
}


NODE_LABEL = {
    "pre-I": "pre-I/I",
    "ramp-I": "ramp-I",
    "early-I": "early-I",
    "post-I^I": r"post-I$^I$",
    "post-I^E": r"post-I$^E$",
    "aug-E^I": r"aug-E$^I$",
    "aug-E^E": r"aug-E$^E$",
}


NODE_FILL = {
    "pre-I": "#f8d6d6",
    "ramp-I": "#f8d6d6",
    "post-I^E": "#f8d6d6",
    "aug-E^E": "#f8d6d6",
    "early-I": "#d9e1fb",
    "post-I^I": "#d9e1fb",
    "aug-E^I": "#d9e1fb",
}


def source_node(source, sign):
    if source == "aug-E":
        return "aug-E^E" if sign == "E" else "aug-E^I"
    if source == "post-I":
        return "post-I^E" if sign == "E" else "post-I^I"
    return source


def target_node(target):
    if target == "aug-E":
        return "aug-E^I"
    if target == "post-I":
        return "post-I^I"
    return target


def edge_records_from_matrices(matrix_e, matrix_i, threshold=0.08):
    records = []
    for r, target in enumerate(PHENOTYPES):
        dst = target_node(target)
        for c, source in enumerate(EXCITATORY_CANDIDATES):
            weight = float(matrix_e[r, c])
            if weight >= threshold:
                records.append({
                    "source": source_node(source, "E"),
                    "target": dst,
                    "source_raw": source,
                    "target_raw": target,
                    "sign": "E",
                    "weight": weight,
                })
        for c, source in enumerate(INHIBITORY_CANDIDATES):
            weight = float(matrix_i[r, c])
            if weight >= threshold:
                records.append({
                    "source": source_node(source, "I"),
                    "target": dst,
                    "source_raw": source,
                    "target_raw": target,
                    "sign": "I",
                    "weight": weight,
                })
    return records


def edge_key(record):
    return (
        record["sign"],
        record["source_raw"],
        record["target_raw"],
    )


def get_node_pos(layout):
    if layout == "molkov2014_core_circle":
        return MOLKOV2014_CORE_CIRCLE_NODE_POS
    if layout == "hexagon":
        return HEXAGON_NODE_POS
    if layout == "pentagon":
        return PENTAGON_NODE_POS
    if layout == "circle":
        return CIRCLE_NODE_POS
    return NODE_POS


def draw_node(ax, name, node_pos=None, node_radius=0.065, node_labels=None):
    node_pos = node_pos or NODE_POS
    node_labels = node_labels or NODE_LABEL
    x, y = node_pos[name]
    circle = Circle((x, y), node_radius, facecolor=NODE_FILL[name],
                    edgecolor="#333333", linewidth=1.2, zorder=6)
    ax.add_patch(circle)
    ax.text(x, y, node_labels.get(name, NODE_LABEL[name]), ha="center", va="center",
            fontsize=8.5, fontweight="bold", zorder=7)


def edge_rad(src, dst, sign):
    names = list(NODE_POS)
    i = names.index(src)
    j = names.index(dst)
    if src == dst:
        return 0.0
    base = 0.13 + 0.04 * ((i + j) % 3)
    if sign == "I":
        base *= -1
    return base if i < j else -base


def offset_segment_points(src_xy, dst_xy, radius, offset):
    sx, sy = src_xy
    tx, ty = dst_xy
    dx = tx - sx
    dy = ty - sy
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return src_xy, dst_xy
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    safe_offset = max(min(offset, radius * 0.82), -radius * 0.82)
    boundary = math.sqrt(max(radius ** 2 - safe_offset ** 2, 0.0))
    return (
        (sx + nx * safe_offset + ux * boundary,
         sy + ny * safe_offset + uy * boundary),
        (sx + nx * safe_offset + ux * (length - boundary),
         sy + ny * safe_offset + uy * (length - boundary)),
    )


def reciprocal_pair_keys(records):
    directed = {
        (record["source"], record["target"])
        for record in records
        if record["source"] != record["target"]
    }
    return {
        frozenset((source, target))
        for source, target in directed
        if (target, source) in directed
    }


def self_loop_arc_params(x, y, node_radius):
    cx, cy = 0.5, 0.5
    ox = x - cx
    oy = y - cy
    norm = math.hypot(ox, oy) or 1.0
    ux = ox / norm
    uy = oy / norm
    center_offset = node_radius * 1.05
    loop_radius = node_radius * 0.90
    center = (
        x + ux * center_offset,
        y + uy * center_offset,
    )
    inward_angle = math.atan2(-uy, -ux)
    # Intersections of the self-loop circle with the node circle. Drawing the
    # exterior arc between these points makes the arrowhead tip, not its base,
    # land on the node boundary.
    cos_alpha = (
        loop_radius ** 2 + center_offset ** 2 - node_radius ** 2
    ) / (2 * loop_radius * center_offset)
    alpha = math.acos(max(-1.0, min(1.0, cos_alpha)))
    theta1 = math.degrees(inward_angle + alpha)
    theta2 = math.degrees(inward_angle + 2 * math.pi - alpha)
    return center, loop_radius, theta1, theta2


def self_loop_arrowhead(center, loop_radius, theta_degrees, node_radius, direction=1):
    theta = math.radians(theta_degrees)
    tip = (
        center[0] + loop_radius * math.cos(theta),
        center[1] + loop_radius * math.sin(theta),
    )
    tangent = (
        direction * -math.sin(theta),
        direction * math.cos(theta),
    )
    normal = (-tangent[1], tangent[0])
    head_len = node_radius * 0.38
    half_width = node_radius * 0.18
    base = (
        tip[0] - tangent[0] * head_len,
        tip[1] - tangent[1] * head_len,
    )
    return [
        tip,
        (base[0] + normal[0] * half_width, base[1] + normal[1] * half_width),
        (base[0] - normal[0] * half_width, base[1] - normal[1] * half_width),
    ]


def draw_self_loop(
    ax, record, max_weight, linestyle="solid", alpha=0.82, color=None,
    label=None, underlay=False, node_pos=None, node_radius=0.065,
    compact_loop=False,
):
    src = record["source"]
    node_pos = node_pos or NODE_POS
    x, y = node_pos[src]
    sign = record["sign"]
    weight = record["weight"]
    color = color or (GE_COLOR if sign == "E" else GI_COLOR)
    scale = math.sqrt(max(weight, 0.0) / max(max_weight, 1e-9))
    lw = (5.8 if underlay else 1.0) + (4.2 if underlay else 3.2) * scale
    if compact_loop:
        center, loop_radius, theta1, theta2 = self_loop_arc_params(
            x, y, node_radius
        )
        arc = Arc(
            center,
            2 * loop_radius,
            2 * loop_radius,
            theta1=theta1,
            theta2=theta2,
            linewidth=lw,
            color=color,
            linestyle=linestyle,
            alpha=alpha,
            zorder=4 if underlay else 5,
        )
        ax.add_patch(arc)

        arrow_endpoint = record.get("loop_arrow_endpoint", "end")
        arrow_theta = theta1 if arrow_endpoint == "start" else theta2
        arrow_direction = -1 if arrow_endpoint == "start" else 1
        ax.add_patch(Polygon(
            self_loop_arrowhead(
                center, loop_radius, arrow_theta, node_radius,
                direction=arrow_direction,
            ),
            closed=True,
            facecolor=color,
            edgecolor=color,
            alpha=alpha,
            zorder=8 if not underlay else 5,
        ))
        return
    cx, cy = x, y + 0.085
    width, height = 0.16, 0.12
    arc = Arc(
        (cx, cy),
        width,
        height,
        theta1=15,
        theta2=332,
        linewidth=lw,
        color=color,
        linestyle=linestyle,
        alpha=alpha,
        zorder=3 if underlay else 4,
    )
    ax.add_patch(arc)

    end_angle = math.radians(332)
    start_angle = math.radians(318)
    end = (cx + (width / 2) * math.cos(end_angle),
           cy + (height / 2) * math.sin(end_angle))
    start = (cx + (width / 2) * math.cos(start_angle),
             cy + (height / 2) * math.sin(start_angle))
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=10 + 5 * scale,
        linewidth=0,
        color=color,
        alpha=alpha,
        zorder=4 if underlay else 5,
    )
    ax.add_patch(arrow)
    if label:
        ax.text(x + 0.105, y + 0.115, label, color=color,
                fontsize=7.5, ha="center", va="center",
                fontweight="bold", zorder=8)


def draw_edge(ax, record, max_weight, linestyle="solid", alpha=0.78,
              color=None, label=None, underlay=False, node_pos=None,
              node_radius=0.065, straight=False, compact_loop=False,
              parallel_offset=0.0):
    node_pos = node_pos or NODE_POS
    if record["source"] == record["target"]:
        draw_self_loop(ax, record, max_weight, linestyle=linestyle,
                       alpha=alpha, color=color, label=label,
                       underlay=underlay, node_pos=node_pos,
                       node_radius=node_radius, compact_loop=compact_loop)
        return

    src = record["source"]
    dst = record["target"]
    sign = record["sign"]
    weight = record["weight"]
    color = color or (GE_COLOR if sign == "E" else GI_COLOR)
    scale = math.sqrt(max(weight, 0.0) / max(max_weight, 1e-9))
    lw = (5.2 if underlay else 0.9) + (4.0 if underlay else 3.0) * scale
    rad = 0.0 if straight else edge_rad(src, dst, sign)
    if straight:
        start, end = offset_segment_points(
            node_pos[src], node_pos[dst], node_radius, parallel_offset
        )
    else:
        start, end = node_pos[src], node_pos[dst]
    patch = FancyArrowPatch(
        start,
        end,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>",
        mutation_scale=10 + 5 * scale,
        linewidth=lw,
        color=color,
        linestyle=linestyle,
        alpha=alpha,
        shrinkA=0 if straight else 51,
        shrinkB=0 if straight else 51,
        zorder=2 if underlay else 4,
    )
    ax.add_patch(patch)

    if label:
        sx, sy = node_pos[src]
        tx, ty = node_pos[dst]
        mx = (sx + tx) / 2 + rad * (ty - sy) * 0.18
        my = (sy + ty) / 2 - rad * (tx - sx) * 0.18
        ax.text(mx, my, label, color=color, fontsize=7.2,
                ha="center", va="center", fontweight="bold", zorder=8,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.70, pad=0.5))


def draw_connectome_graph(
    ax,
    matrix_e,
    matrix_i,
    title,
    threshold=0.08,
    max_weight=None,
    label_threshold=0.70,
    missing_records=None,
    highlight_keys=None,
    layout="default",
    straight_edges=False,
    node_radius=0.065,
    extra_records=None,
    reciprocal_offset=0.018,
    active_nodes=None,
    node_label_overrides=None,
    show_legend=True,
):
    records = edge_records_from_matrices(matrix_e, matrix_i, threshold=threshold)
    records.extend(extra_records or [])
    max_weight = max_weight or max([r["weight"] for r in records] + [0.1])
    highlight_keys = highlight_keys or {}
    node_pos = get_node_pos(layout)
    node_labels = {**NODE_LABEL, **(node_label_overrides or {})}
    active_nodes = active_nodes or list(node_pos)
    reciprocal_pairs = reciprocal_pair_keys(records)

    def edge_parallel_offset(record):
        if not straight_edges or record["source"] == record["target"]:
            return 0.0
        pair = frozenset((record["source"], record["target"]))
        return reciprocal_offset if pair in reciprocal_pairs else 0.0

    ax.set_xlim(0.03, 0.97)
    ax.set_ylim(0.04, 0.96)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=11, pad=8)

    # Draw dashed "data-permits, dynamics-require" records first. These use
    # the same sign-based color as regular edges (E=red, I=blue) so they
    # read as part of the circuit, only the dash and lower alpha mark them
    # as data-compatible auxiliary edges. No claim letter is drawn on these edges.
    for rec in missing_records or []:
        draw_edge(ax, rec, max_weight, linestyle=(0, (4, 3)),
                  alpha=0.7, label=None,
                  node_pos=node_pos, node_radius=node_radius,
                  straight=straight_edges, compact_loop=straight_edges,
                  parallel_offset=edge_parallel_offset(rec))

    # Underlay selected edges so the graph reads as a circuit, not a matrix.
    for rec in records:
        claim = highlight_keys.get(edge_key(rec))
        if claim:
            color = {
                "A": CLAIM_A_COLOR,
                "B": CLAIM_B_COLOR,
                "C": CLAIM_C_COLOR,
            }[claim]
            draw_edge(ax, rec, max_weight, alpha=0.30, color=color,
                      underlay=True, node_pos=node_pos,
                      node_radius=node_radius, straight=straight_edges,
                      compact_loop=straight_edges,
                      parallel_offset=edge_parallel_offset(rec))

    for rec in records:
        label = f"{rec['weight']:.2f}" if rec["weight"] >= label_threshold else None
        draw_edge(ax, rec, max_weight, label=label, node_pos=node_pos,
                  node_radius=node_radius, straight=straight_edges,
                  compact_loop=straight_edges,
                  parallel_offset=edge_parallel_offset(rec))

    for node in active_nodes:
        draw_node(
            ax, node, node_pos=node_pos, node_radius=node_radius,
            node_labels=node_labels,
        )

    if show_legend:
        ax.text(0.08, 0.07, "red: excitatory source", color=GE_COLOR,
                fontsize=8.5, ha="left", va="center")
        ax.text(0.08, 0.025, "blue: inhibitory source", color=GI_COLOR,
                fontsize=8.5, ha="left", va="center")

SOURCE_DEFINITIONS = [{'symbols': ['PHENOTYPES'], 'start_line': 8, 'end_line': 8, 'definition_sha256': 'ebf5f9a43a8005e0898c4b520b44c0185fcf17f86d6c3d255fd4caabb163a390'}, {'symbols': ['EXCITATORY_CANDIDATES'], 'start_line': 9, 'end_line': 9, 'definition_sha256': '3b307f04879714260389a7eb18314b98ef66a91ebe8b70a6de750a6e63a57ff5'}, {'symbols': ['INHIBITORY_CANDIDATES'], 'start_line': 10, 'end_line': 10, 'definition_sha256': 'a8b73404e69eae17ebbcee975b370ee49dcfff55f143885d7e80aca744b870ec'}, {'symbols': ['GE_COLOR'], 'start_line': 12, 'end_line': 12, 'definition_sha256': '25352aa9a247150e1473ed8ef5db15d086439641326ab89d65600ed909117b95'}, {'symbols': ['GI_COLOR'], 'start_line': 13, 'end_line': 13, 'definition_sha256': '9026dc190089effb7e9a65aaaf741755db0bce8851867a4b942a4b36e003dd7a'}, {'symbols': ['CLAIM_A_COLOR'], 'start_line': 14, 'end_line': 14, 'definition_sha256': '154e7aeb58a33694b20724903df70ee26b761fce7041bc09980d7884d134d214'}, {'symbols': ['CLAIM_B_COLOR'], 'start_line': 15, 'end_line': 15, 'definition_sha256': 'bd51415de4985000e80308d5012372682498068f1994a687e08c5dbe970e1f62'}, {'symbols': ['CLAIM_C_COLOR'], 'start_line': 16, 'end_line': 16, 'definition_sha256': 'b1fac7d96bf290a36701d325e0fe8eb50dbfad865c354e8e7bf0cf3bb56132ee'}, {'symbols': ['NODE_POS'], 'start_line': 18, 'end_line': 26, 'definition_sha256': 'fa54040381f15e1666be7e157fc67f574aacc271c066de86e8c2aa8d3ae851ef'}, {'symbols': ['CIRCLE_NODE_POS'], 'start_line': 28, 'end_line': 36, 'definition_sha256': '162f847e641579a686e776321640e0daa2a72c34a909a5ffb38131ef2b99a058'}, {'symbols': ['HEXAGON_NODE_POS'], 'start_line': 38, 'end_line': 46, 'definition_sha256': '4a0d89737fd5f960f779221ce8ef5d6a227b2a5f2bec7039002148c9a631a360'}, {'symbols': ['PENTAGON_NODE_POS'], 'start_line': 48, 'end_line': 55, 'definition_sha256': '64ec7df22901552cc1550303280429eecd1c7757529ba2ee6d36d7542b36968c'}, {'symbols': ['MOLKOV2014_CORE_CIRCLE_NODE_POS'], 'start_line': 57, 'end_line': 63, 'definition_sha256': '767600d2fa8e3df9f6194382cc4ad0a33419ce0b306db53c7a1fca1a820dccf3'}, {'symbols': ['NODE_LABEL'], 'start_line': 65, 'end_line': 73, 'definition_sha256': '8196cbf522bc2f47cbf7111ea40f3314ead5e02deeac8a36115d507997811b39'}, {'symbols': ['NODE_FILL'], 'start_line': 75, 'end_line': 83, 'definition_sha256': 'fa1964e35136ef3e465daa80af5525213b63a934977079e24c6cb6f992c4e48e'}, {'symbols': ['source_node'], 'start_line': 86, 'end_line': 91, 'definition_sha256': '225b87483c151cedff8dfef9f1fb556fc98b99b20190008337af48dce57959ae'}, {'symbols': ['target_node'], 'start_line': 94, 'end_line': 99, 'definition_sha256': '188795ab2e44c2e0e0836e2eb7544e7d2da6a481652ef6de992a48abff87cc31'}, {'symbols': ['edge_records_from_matrices'], 'start_line': 102, 'end_line': 128, 'definition_sha256': 'fba4da6059e70224f493f8517d71233b0f8a78c458042716f47afe59186bf4f4'}, {'symbols': ['edge_key'], 'start_line': 141, 'end_line': 146, 'definition_sha256': '4241ea0000dc8f535c941921d495a4de4f6b956c8bb94cdcfcefedc18344b781'}, {'symbols': ['get_node_pos'], 'start_line': 149, 'end_line': 158, 'definition_sha256': 'd913b017d0ba68bd34159f1e5e9c519d5c0c1c95790c89e7158507df654ce84c'}, {'symbols': ['draw_node'], 'start_line': 161, 'end_line': 169, 'definition_sha256': '1603b83199d2cca7ae3e1897ca8c0ad875c3954ab24055609f9090365891c4e8'}, {'symbols': ['edge_rad'], 'start_line': 172, 'end_line': 181, 'definition_sha256': '98ac1ef559e7e7aa34dc0b70d8c287a1d3314146a4ce3b124b36d165bb29f4f7'}, {'symbols': ['offset_segment_points'], 'start_line': 200, 'end_line': 219, 'definition_sha256': '73a042d343c19311bae45c925b908b8fb5eeff80ce2865cb3c0e1b7da1f67cde'}, {'symbols': ['reciprocal_pair_keys'], 'start_line': 222, 'end_line': 232, 'definition_sha256': '664d09e0844c676c7423df324789c074d0366c61badca24b069327d36f8a793a'}, {'symbols': ['self_loop_arc_params'], 'start_line': 235, 'end_line': 258, 'definition_sha256': '56e798b101aca9a8c17833499e8fb1f0cc71cf1a85f130946f203ecee76cb37b'}, {'symbols': ['self_loop_arrowhead'], 'start_line': 261, 'end_line': 282, 'definition_sha256': '2e09747f3946ef47e9b56cae035e0e3ded75817483a220ff1cccf834ce69269e'}, {'symbols': ['draw_self_loop'], 'start_line': 285, 'end_line': 367, 'definition_sha256': 'eff045f172ae7a1e2cf6ce3ab47781cf84e45ec1efcc0f76e56b6a563827cc27'}, {'symbols': ['draw_edge'], 'start_line': 370, 'end_line': 419, 'definition_sha256': '95b05740efdc21a4a9ec36cd8d070f8952d7232286aef12a812e5a2a7fe85325'}, {'symbols': ['draw_connectome_graph'], 'start_line': 422, 'end_line': 505, 'definition_sha256': '46fb3ea8dc4fa0939326460de9528a4c0e6738a1d096be60bc7e72f36f80d5d7'}]
