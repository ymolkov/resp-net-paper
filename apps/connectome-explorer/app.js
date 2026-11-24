(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("dataset").textContent);
  const icons = JSON.parse(document.getElementById("icons").textContent);
  const C = window.ConnectomeCore,
    $ = (id) => document.getElementById(id);
  const color = { E: "#b83e3d", I: "#287ba5" };
  // Component colors follow Figure 3 of the paper: inspiratory, post-I, aug-E.
  // Validated against the excitation red and inhibition blue, which are
  // reserved for the conductances themselves.
  const family = ["#10803a", "#10803a", "#10803a", "#8e44ad", "#c98500"];
  const dash = ["", "7 4", "1.5 4", "", ""];
  const INK = "#25343b";
  const MEMBERS = D.names.slice(0, 3);
  const isMember = (id) => MEMBERS.includes(id);
  // The manuscript calls the first inspiratory population pre-I/I.
  const show = (s) => String(s).replace(/pre-I(?!\/)/g, "pre-I/I");
  const signWord = { E: "excitation", I: "inhibition" };
  const SignWord = { E: "Excitation", I: "Inhibition" };
  // Figure 4A arrangement: inspiratory group above, post-I left, aug-E right.
  const layout = {
    wide: {
      Inspiratory: [750, 150],
      "pre-I": [270, 150],
      "ramp-I": [750, 150],
      "early-I": [1230, 150],
      "post-I": [320, 640],
      "aug-E": [1180, 640],
    },
    narrow: {
      Inspiratory: [320, 130],
      "pre-I": [-160, 130],
      "ramp-I": [320, 130],
      "early-I": [800, 130],
      "post-I": [80, 640],
      "aug-E": [560, 640],
    },
  };
  const PANEL = { rx: 215, ry: 186 };
  const LANE = 0.19;
  const SEEN_KEY = "resp-net-atlas-guide";
  const fresh = () => ({
    expanded: false,
    open: [],
    focus: null,
    edge: null,
    cellsFor: null,
    testsOpen: false,
    samples: {},
    compare: {},
    masks: {},
  });
  let state = fresh(),
    history = [];
  let width = 1,
    height = 1,
    edges = [],
    nodes = [],
    geometry = new Map(),
    reserveBottom = 0,
    hover = null,
    guide = null;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const duration = () => (reduced.matches ? 0 : 380);
  const esc = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const pct = (v) => (v * 100).toFixed(1) + "%";
  const pval = (v) => {
    if (v === null) return "not tested";
    if (v >= 0.001) return v.toFixed(3);
    const [m, e] = v.toExponential(2).split("e");
    return `${m} × 10<sup>−${Math.abs(+e)}</sup>`;
  };
  const icon = (name) =>
    icons[name].replace("<svg ", '<svg aria-hidden="true" ');
  document
    .querySelectorAll("[data-icon]")
    .forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
  const chartLine = (values, x, y, w, h, max = 1) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${(x + (i / 100) * w).toFixed(2)},${(y - (v / max) * h).toFixed(2)}`,
      )
      .join(" ");
  const sample = (target) => state.samples[target] || "mean";
  const compared = (target) => {
    const id = state.compare[target];
    return id && id !== sample(target)
      ? D.groups[target].cells.find((c) => c.id === id)
      : null;
  };
  const mask = (target, sign) => state.masks[`${target}|${sign}`] ?? 7;
  const curve = (target, sign) =>
    C.series(D, target, sign, sample(target), mask(target, sign));
  const modeName = { CC: "current clamp", VC: "voltage clamp" };
  const cellLabel = (target, id) =>
    id === "mean"
      ? `Mean of ${D.groups[target].n} cells`
      : D.groups[target].cells.find((c) => c.id === id).label;
  const svg = d3.select("#atlas"),
    world = d3.select("#world");
  const transform = () => d3.zoomTransform($("atlas"));
  const mobile = () => width < 700;
  const position = (id) => layout[mobile() ? "narrow" : "wide"][id];
  const rootBounds = () =>
    mobile() ? [-170, -95, 810, 810] : [45, -50, 1455, 790];
  const insets = () => ({
    top: mobile() ? 58 : 64,
    bottom: (mobile() ? 64 : 18) + reserveBottom,
  });
  const add = (p, q) => [p[0] + q[0], p[1] + q[1]];
  const scale = (p, k) => [p[0] * k, p[1] * k];
  const dir = (a) => [Math.cos(a), Math.sin(a)];
  const fmt = (p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`;

  function checkpoint() {
    const t = transform();
    history.push({
      state: structuredClone(state),
      camera: { x: t.x, y: t.y, k: t.k, width, height },
    });
    if (history.length > 40) history.shift();
  }
  const zoom = d3
    .zoom()
    .scaleExtent([0.15, 3.8])
    .clickDistance(5)
    .filter(
      (e) =>
        !e.target.closest("foreignObject") && (!e.button || e.type === "wheel"),
    )
    .on("zoom", (e) => world.attr("transform", e.transform));
  svg.call(zoom).on("dblclick.zoom", null);

  // ---------- Camera ----------
  function moveCamera(t, animate = true) {
    svg.interrupt();
    const selection = animate ? svg.transition().duration(duration()) : svg;
    selection.call(zoom.transform, t);
  }
  function scaleFor([x0, y0, x1, y1], maxScale) {
    const i = insets();
    return Math.max(
      0.12,
      Math.min(
        maxScale,
        (width - 50) / (x1 - x0),
        (height - i.top - i.bottom) / (y1 - y0),
      ),
    );
  }
  function fitBounds(bounds, animate = true, maxScale = 1.3) {
    const [x0, y0, x1, y1] = bounds,
      i = insets(),
      k = scaleFor(bounds, maxScale);
    moveCamera(
      d3.zoomIdentity
        .translate(
          width / 2 - ((x0 + x1) / 2) * k,
          i.top + (height - i.top - i.bottom) / 2 - ((y0 + y1) / 2) * k,
        )
        .scale(k),
      animate,
    );
  }
  // Show as much of the graph as possible while the focused object stays
  // fully visible and is never drawn below its natural reading size.
  function fitWithFocus(all, focus, animate = true) {
    const i = insets();
    const k = Math.max(
      scaleFor(all, 1.3),
      Math.min(scaleFor(focus, 1.15), guide ? 0.8 : 0.9),
    );
    let tx = width / 2 - ((all[0] + all[2]) / 2) * k,
      ty =
        i.top + (height - i.top - i.bottom) / 2 - ((all[1] + all[3]) / 2) * k;
    if (focus[2] * k + tx > width - 25) tx = width - 25 - focus[2] * k;
    if (focus[0] * k + tx < 25) tx = 25 - focus[0] * k;
    if (focus[3] * k + ty > height - i.bottom)
      ty = height - i.bottom - focus[3] * k;
    if (focus[1] * k + ty < i.top) ty = i.top - focus[1] * k;
    moveCamera(d3.zoomIdentity.translate(tx, ty).scale(k), animate);
  }
  function boundsFor(items, pad = 35) {
    return [
      Math.min(...items.map((n) => n.x - n.rx - pad)),
      Math.min(...items.map((n) => n.y - n.ry - pad)),
      Math.max(...items.map((n) => n.x + n.rx + pad)),
      Math.max(...items.map((n) => n.y + n.ry + pad)),
    ];
  }
  function visibleBounds() {
    const items = [...nodes];
    const s = satellite();
    if (s) items.push(s);
    if (state.expanded) {
      const h = hull();
      items.push({
        x: (h.x0 + h.x1) / 2,
        y: (h.y0 - 36 + h.y1) / 2,
        rx: (h.x1 - h.x0) / 2,
        ry: (h.y1 - h.y0 + 36) / 2,
      });
    }
    for (const g of geometry.values())
      if (g.loop)
        for (const p of g.pts) items.push({ x: p[0], y: p[1], rx: 0, ry: 0 });
    return boundsFor(items, 30);
  }
  function frameFocus(animate = true) {
    const s = satellite(),
      n = nodes.find((n) => n.id === state.focus && n.open);
    if (mobile()) {
      if (s) return fitBounds(boundsFor([s]), animate, 1.15);
      if (n) return fitBounds(boundsFor([n]), animate, 1.4);
      return fitBounds(visibleBounds(), animate);
    }
    if (!s && !n)
      return state.expanded
        ? fitBounds(visibleBounds(), animate)
        : fitBounds(rootBounds(), animate, 1.3);
    const target = s ? nodes.find((m) => m.id === s.id) : n;
    const near = [...(target ? [target] : []), ...(s ? [s] : [])];
    // Keep the sources of a selected input in view when that still leaves
    // the evidence at a readable size.
    const sources = edges
      .filter((e) => selectedEdge(e) && e.source !== "Inspiratory")
      .map((e) => nodes.find((m) => m.id === e.source))
      .filter(Boolean);
    const wider = boundsFor([...near, ...sources], 14);
    fitWithFocus(
      visibleBounds(),
      sources.length && scaleFor(wider, 1) >= 0.74
        ? wider
        : boundsFor(near, 14),
      animate,
    );
  }

  // ---------- Geometry ----------
  function nodeFor(id) {
    const [x, y] = position(id);
    const open = state.open.includes(id);
    return {
      id,
      x,
      y,
      open,
      rx: open ? PANEL.rx : id === "Inspiratory" ? 140 : 112,
      ry: open ? PANEL.ry : id === "Inspiratory" ? 96 : 88,
    };
  }
  // The dashed outline around the three inspiratory populations. Outputs of
  // the group as a whole leave from this outline.
  function hull() {
    const ms = MEMBERS.map((id) => nodeFor(id));
    return {
      x0: Math.min(...ms.map((n) => n.x - n.rx)) - 46,
      x1: Math.max(...ms.map((n) => n.x + n.rx)) + 46,
      y0: Math.min(...ms.map((n) => n.y - n.ry)) - 72,
      y1: Math.max(...ms.map((n) => n.y + n.ry)) + 36,
    };
  }
  // Direction pointing away from the rest of the circuit; self-connections
  // are drawn on this side so that they never cross other connections.
  function outward(id) {
    if (state.expanded && isMember(id)) return -Math.PI / 2;
    const ids = ["Inspiratory", "post-I", "aug-E"];
    const cx = d3.mean(ids, (i) => position(i)[0]),
      cy = d3.mean(ids, (i) => position(i)[1]),
      p = position(id);
    return Math.atan2(p[1] - cy, p[0] - cx);
  }
  function port(n, angle, gap = 0) {
    const [dx, dy] = dir(angle);
    const t = n.open
      ? Math.min(
          n.rx / Math.max(1e-6, Math.abs(dx)),
          n.ry / Math.max(1e-6, Math.abs(dy)),
        )
      : 1 / Math.hypot(dx / n.rx, dy / n.ry);
    return [n.x + dx * (t + gap), n.y + dy * (t + gap)];
  }
  const cubic = (s, c1, c2, t) => `M${fmt(s)} C${fmt(c1)} ${fmt(c2)} ${fmt(t)}`;
  function layoutEdges() {
    geometry = new Map();
    const gapOf = (e) => (e.sign === "I" ? 6 : 2);
    const pairs = new Map();
    for (const e of edges) {
      if (e.source === e.target) {
        const n = nodeFor(e.source),
          out = outward(n.id);
        const sides = [out - 0.5, out + 0.5].sort((a, b) =>
          Math.abs(Math.sin(a) - Math.sin(b)) > 1e-9
            ? Math.sin(a) - Math.sin(b)
            : Math.cos(a) - Math.cos(b),
        );
        const phi = e.sign === "E" ? sides[0] : sides[1];
        const s = port(n, phi - 0.2),
          t = port(n, phi + 0.2, gapOf(e)),
          c1 = add(s, scale(dir(phi - 0.8), 105)),
          c2 = add(t, scale(dir(phi + 0.8), 105));
        geometry.set(e.id, {
          d: cubic(s, c1, c2, t),
          end: t,
          pts: [s, c1, c2, t],
          loop: true,
        });
      } else if (state.expanded && e.source === "Inspiratory") {
        const T = nodeFor(e.target),
          H = hull(),
          lane = e.sign === "E" ? -1 : 1;
        if (isMember(e.target)) {
          const x = T.x + lane * 26;
          const y = T.open
            ? T.y - T.ry - gapOf(e)
            : T.y - T.ry * Math.sqrt(1 - (26 / T.rx) ** 2) - gapOf(e);
          geometry.set(e.id, {
            d: `M${x},${H.y0} L${x},${y.toFixed(1)}`,
            end: [x, y],
            pts: [
              [x, H.y0],
              [x, y],
            ],
          });
        } else {
          const inward = Math.sign((H.x0 + H.x1) / 2 - T.x) || 1;
          const a =
            Math.atan2(H.y1 - T.y, inward * 80) + lane * 0.85 * LANE;
          const t = port(T, a, gapOf(e));
          const s = [t[0] + (t[0] - T.x) * 1.5, H.y1];
          const L = Math.max(20, (t[1] - s[1]) * 0.38);
          const c1 = [s[0], s[1] + L],
            c2 = add(t, scale(dir(a), L));
          geometry.set(e.id, {
            d: cubic(s, c1, c2, t),
            end: t,
            pts: [s, c1, c2, t],
          });
        }
      } else {
        const key = [e.source, e.target].sort().join("~");
        if (!pairs.has(key)) pairs.set(key, []);
        pairs.get(key).push(e);
      }
    }
    // Connections between the same two populations run in parallel lanes:
    // the two directions never share a side, so they cannot cross.
    for (const [key, list] of pairs) {
      const [p, q] = key.split("~"),
        P = nodeFor(p),
        Q = nodeFor(q);
      // The outer two inspiratory populations have the third between them:
      // arch over it instead of passing through it.
      const between =
        isMember(p) &&
        isMember(q) &&
        MEMBERS.map((id) => nodeFor(id)).find(
          (m) =>
            m.id !== p &&
            m.id !== q &&
            (m.x - P.x) * (m.x - Q.x) < 0 &&
            Math.abs(m.y - P.y) < 1,
        );
      if (between) {
        const [left, right] = P.x < Q.x ? [P, Q] : [Q, P];
        list.forEach((e, i) => {
          const leftToRight = e.source === left.id,
            shift = (i - (list.length - 1) / 2) * LANE;
          const aL = -Math.PI / 6 - shift,
            aR = (-5 * Math.PI) / 6 + shift;
          const s = leftToRight ? port(left, aL) : port(right, aR),
            t = leftToRight
              ? port(right, aR, gapOf(e))
              : port(left, aL, gapOf(e));
          const apex = between.y - between.ry - 42 - i * 14,
            yc = (y) => y + (apex - y) / 0.75,
            dx = (t[0] - s[0]) * 0.22;
          const c1 = [s[0] + dx, yc(s[1])],
            c2 = [t[0] - dx, yc(t[1])];
          geometry.set(e.id, {
            d: cubic(s, c1, c2, t),
            end: t,
            pts: [s, c1, c2, t],
            loop: true,
          });
        });
        continue;
      }
      const theta = Math.atan2(Q.y - P.y, Q.x - P.x);
      const rank = (e) =>
        e.source === p ? (e.sign === "I" ? 0 : 1) : e.sign === "E" ? 2 : 3;
      list
        .sort((a, b) => rank(a) - rank(b))
        .forEach((e, i) => {
          const k = i - (list.length - 1) / 2;
          const aP = theta + k * LANE,
            aQ = theta + Math.PI - k * LANE;
          const fromP = e.source === p;
          const sA = fromP ? aP : aQ,
            tA = fromP ? aQ : aP;
          const s = port(fromP ? P : Q, sA),
            t = port(fromP ? Q : P, tA, gapOf(e));
          const L = Math.max(
            30,
            Math.min(230, Math.hypot(t[0] - s[0], t[1] - s[1]) * 0.36),
          );
          const c1 = add(s, scale(dir(sA), L)),
            c2 = add(t, scale(dir(tA), L));
          geometry.set(e.id, {
            d: cubic(s, c1, c2, t),
            end: t,
            pts: [s, c1, c2, t],
          });
        });
    }
  }
  // A card is first drawn at a nominal height, then fitted to its content so
  // that text never overflows whatever the reader's fonts are.
  let cardHeight = { key: "", h: 0 };
  const cardKey = () =>
    JSON.stringify([
      state.cellsFor,
      state.edge,
      state.testsOpen,
      state.masks,
      state.samples,
      mobile(),
    ]);
  function fitCard(layer, redraw) {
    const el = layer.select(".evidence-content, .cell-content").node(),
      s = satellite();
    if (!el || !s) return;
    const need = Math.ceil(el.scrollHeight) + 4;
    if (Math.abs(need - s.ry * 2) < 3) return;
    cardHeight = { key: cardKey(), h: need };
    redraw();
  }
  // Evidence and cell records unfold beside their population, outside the
  // circuit, so that they never cover a population or a selected connection.
  function satellite() {
    const id = state.cellsFor || state.edge?.target;
    if (!id) return null;
    const wide = !mobile(),
      fine = state.edge?.source === "Inspiratory",
      kind = state.cellsFor ? "cells" : "evidence";
    const w = wide ? (kind === "cells" ? 600 : 520) : 360;
    const h =
      kind === "cells"
        ? wide
          ? 468
          : 440
        : fine
          ? wide
            ? state.testsOpen
              ? 590
              : 486
            : state.testsOpen
              ? 900
              : 770
          : wide
            ? 322
            : 500;
    const n = nodeFor(id);
    const fitted = cardHeight.key === cardKey() ? cardHeight.h : h;
    return placeCard(id, kind, n, w, fitted, wide);
  }
  function placeCard(id, kind, n, w, h, wide) {
    let x, y;
    if (!wide) {
      x = 320;
      y = 900 + h / 2;
    } else {
      const side = { "pre-I": -1, "post-I": -1, "early-I": 1, "aug-E": 1 }[id];
      if (side) {
        x = n.x + side * (n.rx + 26 + w / 2);
        y = n.y;
      } else {
        x = n.x;
        y = hull().y1 + 28 + h / 2;
      }
    }
    return { id, kind, x, y, rx: w / 2, ry: h / 2 };
  }
  function leader(s) {
    const n = nodeFor(s.id);
    if (mobile())
      return `M${n.x},${n.y + n.ry} L${s.x},${s.y - s.ry}`;
    if (Math.abs(s.x - n.x) > 1) {
      const side = Math.sign(s.x - n.x);
      return `M${n.x + side * n.rx},${n.y} L${s.x - side * s.rx},${n.y}`;
    }
    return `M${n.x},${n.y + n.ry} L${s.x},${s.y - s.ry}`;
  }

  // ---------- State changes ----------
  function openNode(id, reframe = true) {
    checkpoint();
    state.focus = id;
    if (id === "Inspiratory") state.expanded = true;
    else {
      if (isMember(id)) state.expanded = true;
      if (!state.open.includes(id)) state.open.push(id);
    }
    render();
    if (reframe) frameFocus();
  }
  function collapseNode(id) {
    checkpoint();
    if (id === "Inspiratory") {
      state.expanded = false;
      state.open = state.open.filter((n) => !isMember(n));
      if (state.edge && isMember(state.edge.target)) state.edge = null;
      if (state.edge?.source === "Inspiratory") state.edge = null;
      if (isMember(state.cellsFor)) state.cellsFor = null;
      state.focus = "Inspiratory";
    } else {
      state.open = state.open.filter((n) => n !== id);
      if (state.cellsFor === id) state.cellsFor = null;
      if (state.edge?.target === id) state.edge = null;
      if (state.focus === id)
        state.focus =
          state.open.at(-1) || (state.expanded ? "Inspiratory" : null);
    }
    render();
    frameFocus();
  }
  function openEdge(edge) {
    checkpoint();
    const target =
      edge.target === "Inspiratory" ? edge.members[0].target : edge.target;
    const source = edge.fine ? "Inspiratory" : edge.source;
    if (source === "Inspiratory" || isMember(target)) state.expanded = true;
    state.edge = { source, target, sign: edge.sign };
    state.cellsFor = null;
    state.focus = target;
    state.testsOpen = false;
    if (!state.open.includes(target)) state.open.push(target);
    render();
    frameFocus();
  }
  function openCells(id) {
    checkpoint();
    if (isMember(id)) state.expanded = true;
    if (!state.open.includes(id)) state.open.push(id);
    state.cellsFor = id;
    state.edge = null;
    state.focus = id;
    render();
    frameFocus();
  }
  function selectedEdge(e) {
    return (
      state.edge &&
      e.target === state.edge.target &&
      e.sign === state.edge.sign &&
      (e.source === state.edge.source ||
        (e.fine && state.edge.source === "Inspiratory"))
    );
  }

  // ---------- Populations ----------
  function pill(id, label, y, w) {
    return `<g class="pill" data-action="expand" data-pop="${id}" transform="translate(0,${y})${mobile() ? " scale(1.25)" : ""}"><rect x="${-w / 2}" y="-14" width="${w}" height="28" rx="14"/><text y="5" text-anchor="middle">${label}</text></g>`;
  }
  function closeButton(id, title, x, y) {
    return `<g class="node-action" role="button" tabindex="0" data-action="fold" data-pop="${id}" aria-label="${title}" transform="translate(${x},${y})"><title>${title}</title><rect x="-14" y="-14" width="28" height="28" rx="5"/><g class="small-icon" transform="translate(-8,-8)">${icon("x")}</g></g>`;
  }
  function profilePlot(target, sign) {
    const si = sign === "E" ? 0 : 1,
      s = curve(target, sign),
      isCell = sample(target) !== "mean",
      other = compared(target),
      mean = D.groups[target].mean.profiles[si];
    const max = Math.max(
      1.05,
      ...s.observed,
      ...(other ? other.profiles[si] : s.fit),
      ...(isCell ? mean : []),
    );
    const X = 34,
      W = 356,
      B = 70,
      Hh = 60,
      split = X + W * D.ti;
    return `<svg viewBox="0 0 400 92" data-chart="${target}|${sign}" role="img" aria-label="${show(target)} ${signWord[sign]} over one respiratory cycle"><rect x="${X}" y="6" width="${W * D.ti}" height="${B - 6}" fill="#edf3ef"/><line x1="${X}" x2="${X + W}" y1="${B}" y2="${B}" stroke="#d7e2dd"/><text x="${X - 6}" y="${B - Hh / max + 4}" text-anchor="end" class="chart-label">100</text><text x="${X - 6}" y="${B + 3}" text-anchor="end" class="chart-label">0</text>${isCell ? `<path d="${chartLine(mean, X, B, W, Hh, max)}" fill="none" stroke="#b9c5c1" stroke-width="1.8"/>` : ""}${other ? `<path d="${chartLine(other.profiles[si], X, B, W, Hh, max)}" fill="none" stroke="#263638" stroke-width="1.7"/>` : `<path d="${chartLine(s.fit, X, B, W, Hh, max)}" fill="none" stroke="#75827e" stroke-width="1.5" stroke-dasharray="4 3"/>`}<path d="${chartLine(s.observed, X, B, W, Hh, max)}" fill="none" stroke="${color[sign]}" stroke-width="2.2"/><text x="${(X + split) / 2}" y="${B + 16}" text-anchor="middle" class="chart-label">Inspiration</text><text x="${(split + X + W) / 2}" y="${B + 16}" text-anchor="middle" class="chart-label">Expiration</text></svg>`;
  }
  function panelLegend(id) {
    const isCell = sample(id) !== "mean",
      other = compared(id),
      main = isCell ? cellLabel(id, sample(id)) : "Mean of cells";
    return `<div class="chart-legend"><span><i class="line two"></i>${main}</span>${other ? `<span><i class="line dark"></i>${other.label}</span>` : ""}${isCell ? '<span><i class="line pale"></i>Mean</span>' : ""}${other ? "" : '<span><i class="line dash"></i>Fit from five patterns</span>'}</div>`;
  }
  function nodeContent(n) {
    const id = n.id,
      group = D.groups[id];
    if (n.open) {
      const other = compared(id);
      return `<rect class="node-shape" x="-${n.rx}" y="-${n.ry}" width="${n.rx * 2}" height="${n.ry * 2}" rx="10"/><text class="node-title" x="${-n.rx + 18}" y="${-n.ry + 33}">${show(id)}<tspan class="node-meta" dx="10">synaptic inputs</tspan></text>${closeButton(id, `Close ${show(id)} inputs`, n.rx - 24, -n.ry + 25)}
        <foreignObject x="-${n.rx}" y="${-n.ry + 46}" width="${n.rx * 2}" height="${n.ry * 2 - 48}"><div xmlns="http://www.w3.org/1999/xhtml" class="node-content"><div class="sample-row"><select data-sample="${id}" aria-label="Record shown for ${show(id)}"><option value="mean">Mean of ${group.n} cells</option>${group.cells.map((c) => `<option value="${c.id}" ${sample(id) === c.id ? "selected" : ""}>${c.label} · ${c.modes.map((m) => modeName[m] || m).join(" + ")}</option>`).join("")}</select><button class="text-button" data-cells="${id}" aria-label="Browse ${show(id)} cells" aria-pressed="${state.cellsFor === id}">${icon("grid-2x2")}<span>Browse ${group.n} cells</span></button></div>${other ? `<div class="compare-row">Compared with <strong>${other.label}</strong><button class="link-button" data-clear-compare="${id}">Remove</button></div>` : ""}<div class="chart-heading"><span class="red">Excitation</span><span>% of peak conductance</span></div>${profilePlot(id, "E")}<div class="chart-heading"><span class="blue">Inhibition</span></div>${profilePlot(id, "I")}${panelLegend(id)}</div></foreignObject>`;
    }
    const grouped = id === "Inspiratory",
      top = grouped ? -52 : -46,
      j = D.names.indexOf(id),
      trace = D.matrix.map((r) => (grouped ? Math.max(r[0], r[1], r[2]) : r[j]));
    return `<ellipse class="node-shape" rx="${n.rx}" ry="${n.ry}"/><text class="node-title" y="${top}" text-anchor="middle">${show(id)}</text><text class="node-meta" y="${top + 19}" text-anchor="middle">${grouped ? "pre-I/I · ramp-I · early-I" : `${group.n} cells`}</text><rect x="-58" y="${top + 28}" width="${116 * D.ti}" height="29" fill="#edf3ef"/><path d="${chartLine(trace, -58, top + 56, 116, 26)}" stroke="${INK}" fill="none" stroke-width="1.7"/><text class="node-caption" y="${top + 72}" text-anchor="middle">${grouped ? "combined discharge pattern" : "discharge pattern"}</text>${grouped ? pill(id, "Show 3 populations", 50, 172) : pill(id, "Show inputs", 46, 122)}`;
  }
  function renderNodes() {
    const ids = state.expanded ? D.names : ["Inspiratory", "post-I", "aug-E"];
    nodes = ids.map((id) => nodeFor(id));
    const join = d3
      .select("#nodes")
      .selectAll("g.population")
      .data(nodes, (n) => n.id);
    join
      .exit()
      .transition()
      .duration(duration())
      .attr("opacity", 0)
      .attr("transform", `translate(${position("Inspiratory")})`)
      .remove();
    const enter = join
      .enter()
      .append("g")
      .attr("class", "population")
      .attr("opacity", 0)
      .attr(
        "transform",
        (n) =>
          `translate(${isMember(n.id) ? position("Inspiratory") : [n.x, n.y]})`,
      );
    const all = enter.merge(join);
    all
      .attr("data-node", (n) => n.id)
      .attr("role", (n) => (n.open ? "group" : "button"))
      .attr("tabindex", 0)
      .attr("aria-label", (n) =>
        n.open
          ? `${show(n.id)} synaptic inputs`
          : n.id === "Inspiratory"
            ? "Show the three inspiratory populations"
            : `Show inputs to ${show(n.id)}, ${D.groups[n.id].n} cells`,
      )
      .attr("aria-expanded", (n) => String(n.open))
      .classed("selected", (n) => n.id === state.focus && n.open)
      .classed("is-open", (n) => n.open)
      .html(nodeContent);
    all
      .transition()
      .duration(duration())
      .attr("opacity", 1)
      .attr("transform", (n) => `translate(${n.x},${n.y})`);
    const layer = d3.select("#family-layer");
    if (!state.expanded) return layer.html("");
    const h = hull();
    layer.html(
      `<rect class="family-hull" x="${h.x0}" y="${h.y0}" width="${h.x1 - h.x0}" height="${h.y1 - h.y0}" rx="46"/><text class="family-title" x="${h.x0 + 18}" y="${h.y0 - 14}">Inspiratory group</text><text class="family-note" x="${h.x0 + 172}" y="${h.y0 - 14}">lines from the dashed outline come from the group as a whole</text><g class="pill fold" role="button" tabindex="0" data-action="fold" data-pop="Inspiratory" aria-label="Show the inspiratory populations as one group" transform="translate(${h.x1 - 104},${h.y0 - 20})"><rect x="-86" y="-14" width="172" height="28" rx="14"/><text y="5" text-anchor="middle">Show as one group</text></g>`,
    );
  }

  // ---------- Connections ----------
  function edgeOpacity(e) {
    if (state.edge)
      return selectedEdge(e)
        ? e.fine && !(mask(e.target, e.sign) & (1 << D.names.indexOf(e.source)))
          ? 0.25
          : 1
        : 0.12;
    const f = state.focus;
    if (f && f !== "Inspiratory" && state.open.includes(f))
      return e.target === f ? 1 : e.source === f ? 0.36 : 0.14;
    return 0.85;
  }
  const edgeName = (e) =>
    `${state.expanded && e.source === "Inspiratory" ? "Inspiratory group" : show(e.source)} → ${show(e.target)} · ${signWord[e.sign]}${e.fine ? (e.style === "solid" ? " · identified source" : " · possible source") : ""}`;
  function renderEdges() {
    edges = C.networkEdges(D, state.expanded, state.edge);
    layoutEdges();
    const join = d3
      .select("#edges")
      .selectAll("g.connection")
      .data(edges, (e) => e.id);
    join.exit().transition().duration(duration()).attr("opacity", 0).remove();
    const enter = join
      .enter()
      .append("g")
      .attr("class", "connection")
      .attr("opacity", 0);
    enter.append("path").attr("class", "edge-line");
    enter.append("circle").attr("class", "inhibitory-end");
    enter.append("path").attr("class", "edge-hit");
    const all = enter.merge(join).attr("data-connection", (e) => e.id);
    all.transition().duration(duration()).attr("opacity", edgeOpacity);
    all
      .select(".edge-line")
      .attr("stroke", (e) => color[e.sign])
      .attr("stroke-width", (e) => (e.fine ? 2.6 : 1.3 + 11 * e.share))
      .attr("stroke-dasharray", (e) => (e.style === "dashed" ? "7 5" : null))
      .attr("marker-end", (e) => (e.sign === "E" ? "url(#arrowE)" : null))
      .transition()
      .duration(duration())
      .attr("d", (e) => geometry.get(e.id).d);
    all
      .select(".inhibitory-end")
      .attr("r", (e) => (e.sign === "I" ? 4.5 : 0))
      .attr("fill", (e) => color[e.sign])
      .transition()
      .duration(duration())
      .attr("cx", (e) => geometry.get(e.id).end[0])
      .attr("cy", (e) => geometry.get(e.id).end[1]);
    all
      .select(".edge-hit")
      .attr("role", "button")
      .attr("tabindex", 0)
      .attr("data-edge", (e) => e.id)
      .attr(
        "aria-label",
        (e) =>
          `${e.source} to ${e.target}, ${signWord[e.sign]}${e.fine ? `, ${e.style === "solid" ? "identified" : "alternative"}` : ""}`,
      )
      .attr("d", (e) => geometry.get(e.id).d);
    applyHover();
  }
  function applyHover() {
    const active = hover && edges.some((e) => hot(e));
    d3.select("#edges")
      .classed("hovering", !!active)
      .selectAll("g.connection")
      .classed("hot", (e) => !!active && hot(e));
    d3.select("#nodes")
      .selectAll("g.population")
      .classed(
        "hot",
        (n) =>
          !!active &&
          edges.some(
            (e) =>
              hot(e) &&
              hover.edge &&
              (e.source === n.id || e.target === n.id),
          ),
      );
  }
  const hot = (e) =>
    hover.edge ? e.id === hover.edge : e.target === hover.node;

  // ---------- Evidence ----------
  // Contributions drawn in an evidence plot. A single input shows the three
  // inspiratory patterns as one line, as Figure 3 of the paper does; an
  // inspiratory input shows them separately, told apart by line style.
  function contributions(s, fine) {
    const present = (v) => v.some((x) => x > 1e-9);
    const lines = [];
    if (fine)
      MEMBERS.forEach((name, j) => {
        if (present(s.components[j]))
          lines.push({ v: s.components[j], color: family[j], dash: dash[j], label: show(name) });
      });
    else {
      const sum = s.components[0].map(
        (_, k) => s.components[0][k] + s.components[1][k] + s.components[2][k],
      );
      if (present(sum))
        lines.push({ v: sum, color: family[0], dash: "", label: "Inspiratory" });
    }
    for (const j of [3, 4])
      if (present(s.components[j]))
        lines.push({ v: s.components[j], color: family[j], dash: "", label: D.names[j] });
    return lines;
  }
  const swatch = (color, dashes = "") =>
    `<svg class="swatch" viewBox="0 0 22 6" aria-hidden="true"><line x1="0" x2="22" y1="3" y2="3" stroke="${color}" stroke-width="2.5" ${dashes ? `stroke-dasharray="${dashes}"` : ""}/></svg>`;
  function fitChart(r, s, lines) {
    const max = Math.max(1.05, ...s.fit, ...s.observed),
      X = 34,
      W = 280,
      B = 104,
      Hh = 92,
      split = X + W * D.ti;
    return `<svg class="fit-chart" viewBox="0 0 324 126" role="img" aria-label="Fit to ${show(r.target)} ${signWord[r.sign]}"><rect x="${X}" y="6" width="${W * D.ti}" height="${B - 6}" fill="#edf3ef"/><line x1="${X}" x2="${X + W}" y1="${B}" y2="${B}" stroke="#d7e2dd"/><text x="${X - 6}" y="${B - Hh / max + 4}" text-anchor="end" class="chart-label">100</text><text x="${X - 6}" y="${B + 3}" text-anchor="end" class="chart-label">0</text>${lines.map((l) => `<path d="${chartLine(l.v, X, B, W, Hh, max)}" fill="none" stroke="${l.color}" stroke-width="1.7" ${l.dash ? `stroke-dasharray="${l.dash}"` : ""}/>`).join("")}<path d="${chartLine(s.observed, X, B, W, Hh, max)}" fill="none" stroke="${INK}" stroke-width="2"/><path d="${chartLine(s.fit, X, B, W, Hh, max)}" fill="none" stroke="#6a757c" stroke-width="1.8" stroke-dasharray="5 3"/><text x="${(X + split) / 2}" y="${B + 16}" text-anchor="middle" class="chart-label">Inspiration</text><text x="${(split + X + W) / 2}" y="${B + 16}" text-anchor="middle" class="chart-label">Expiration</text></svg>`;
  }
  function relationContent() {
    const r = state.edge,
      p = D.panels[`${r.target}|${r.sign}`],
      fine = r.source === "Inspiratory",
      s = curve(r.target, r.sign),
      target = show(r.target),
      n = D.groups[r.target].n,
      mean = sample(r.target) === "mean",
      lines = contributions(s, fine);
    const fitState = C.fitStatus(D, r.target, r.sign, mask(r.target, r.sign));
    const row = D.coarse.find(
      (e) =>
        e.source === r.source && e.target === r.target && e.sign === r.sign,
    );
    const combinations = p.minima
      .map((m) =>
        C.members(m).length > 1
          ? `(${show(C.label(m, D.names))})`
          : show(C.label(m, D.names)),
      )
      .join(" or ");
    const lead = fine
      ? `Without any inspiratory pattern, the two expiratory patterns do not reproduce the timing of ${signWord[r.sign]} in ${target} cells. An inspiratory input is supported.`
      : `Without the ${show(r.source)} pattern, the other patterns do not reproduce the timing of ${signWord[r.sign]} in ${target} cells. This input is supported.`;
    const numbers = `<dl class="numbers"><div><dt>Adjusted P</dt><dd>${pval(row.p_joint)}</dd></div><div><dt>Fitted share</dt><dd>${pct(row.share_mean)}</dd></div><div><dt>Cells</dt><dd>${n}</dd></div></dl>`;
    const sources = fine
      ? `<div class="combination">Which inspiratory population? The tests do not rule out:<br><strong>${combinations}</strong></div><fieldset aria-label="Inspiratory sources included in the fit"><legend>Sources included in the fit shown</legend><div class="switches">${MEMBERS.map(
          (name, j) =>
            `<label><input type="checkbox" data-toggle="${j}" aria-label="Include ${name} source" ${mask(r.target, r.sign) & (1 << j) ? "checked" : ""}/>${show(name)}</label>`,
        ).join(
          "",
        )}</div></fieldset><div class="relation-status ${fitState}">${fitState === "full" ? "This is the fit with all three." : fitState === "excluded" ? "The group tests rule this combination out." : "The group tests do not rule this combination out."}</div>`
      : "";
    const tests = fine
      ? `<details data-test-details ${state.testsOpen ? "open" : ""}><summary>Each omission test · adjusted P</summary><div class="evidence-scroll"><table><tr><th>Sources left out</th><th>Adjusted P</th></tr>${p.tests.map((t) => `<tr><td>${esc(show(t.omitted_sources))}</td><td>${pval(t.p_joint)}</td></tr>`).join("")}</table></div></details>`
      : "";
    const legend = `<div class="component-legend"><span>${swatch(INK)}${mean ? "Mean input" : cellLabel(r.target, sample(r.target))}</span><span>${swatch("#6a757c", "5 3")}Fit</span>${lines.map((l) => `<span>${swatch(l.color, l.dash)}${l.label}</span>`).join("")}</div>`;
    const note = `<div class="small-note">Fit error: ${pct(s.rmse)} of peak conductance${mean ? ", averaged over cells" : ""}${s.delta > 5e-5 ? `; ${(s.delta * 100).toFixed(2)} points more than with all sources` : ""}. The test result always refers to the whole group.</div>`;
    return `<div xmlns="http://www.w3.org/1999/xhtml" class="evidence-content ${mobile() ? "stacked" : ""}"><button class="close-detail icon" data-close-edge title="Close evidence" aria-label="Close evidence">${icon("x")}</button><h2>${fine ? "Inspiratory group" : show(r.source)} → ${target}</h2><div class="subhead">${SignWord[r.sign]} · evidence from ${n} cells</div><p class="lead">${lead}</p>${numbers}<div class="evidence-columns ${fine ? "" : "coarse"}">${fine ? `<div class="evidence-text">${sources}</div>` : ""}<div class="evidence-figure">${fitChart(r, s, lines)}${legend}${fine ? note + tests : ""}</div></div>${fine ? "" : note}</div>`;
  }
  function renderEvidence(fit = true) {
    const layer = d3.select("#evidence-layer"),
      s = satellite();
    if (!state.edge || !s) {
      layer.html("");
      return;
    }
    layer.html(
      `<path class="detail-leader" d="${leader(s)}"/><g class="connection-detail" transform="translate(${s.x - s.rx},${s.y - s.ry})"><rect class="detail-shell" width="${s.rx * 2}" height="${s.ry * 2}" rx="10"/><foreignObject width="${s.rx * 2}" height="${s.ry * 2}">${relationContent()}</foreignObject></g>`,
    );
    if (fit) fitCard(layer, () => renderEvidence(false));
  }

  // ---------- Cell records ----------
  function renderCells(fit = true) {
    const layer = d3.select("#cells-layer");
    const scroll = layer.select(".cell-grid").node()?.scrollTop || 0;
    const s = satellite();
    if (!state.cellsFor || !s) {
      layer.html("");
      return;
    }
    const id = state.cellsFor,
      shown = sample(id),
      other = state.compare[id];
    layer.html(
      `<path class="detail-leader" d="${leader(s)}"/><g class="cell-detail" transform="translate(${s.x - s.rx},${s.y - s.ry})"><rect class="detail-shell" width="${s.rx * 2}" height="${s.ry * 2}" rx="10"/><foreignObject width="${s.rx * 2}" height="${s.ry * 2}"><div xmlns="http://www.w3.org/1999/xhtml" class="cell-content ${mobile() ? "stacked" : ""}"><button class="close-cells icon" data-close-cells title="Close cell records" aria-label="Close cell records">${icon("x")}</button><h2>${show(id)} · ${D.groups[id].n} cells</h2><div class="subhead">Click a cell to show it in the panel. Use Compare to overlay a second cell. <span class="red">Excitation</span> and <span class="blue">inhibition</span> share one scale. CC: current clamp. VC: voltage clamp.</div><div class="cell-grid">${D.groups[id].cells
        .map(
          (c) =>
            `<div class="cell-tile ${shown === c.id ? "shown" : other === c.id ? "compared" : ""}"><button class="cell-main" data-cell="${c.id}" aria-pressed="${shown === c.id}" aria-label="Show ${c.label}"><span>${c.label} · ${c.modes.join(" + ")}</span><svg viewBox="0 0 130 54" aria-hidden="true"><rect x="2" y="2" width="${126 * D.ti}" height="50" fill="#edf3ef"/>${c.profiles.map((v, j) => `<path d="${chartLine(v, 2, 51, 126, 47)}" fill="none" stroke="${color[j === 0 ? "E" : "I"]}" stroke-width="1.5"/>`).join("")}</svg></button><button class="cell-compare" data-compare-cell="${c.id}" aria-pressed="${other === c.id && shown !== c.id}" aria-label="Compare ${c.label}" ${shown === c.id ? "disabled" : ""}>${shown === c.id ? "Shown" : other === c.id ? "Compared" : "Compare"}</button></div>`,
        )
        .join(
          "",
        )}</div><button class="mean-button" data-mean="${id}">Back to the mean</button></div></foreignObject></g>`,
    );
    layer.select(".cell-grid").node().scrollTop = scroll;
    if (fit) fitCard(layer, () => renderCells(false));
  }

  // ---------- Frame ----------
  function hint() {
    if (state.edge)
      return state.edge.source === "Inspiratory"
        ? "Solid lines are identified sources. Dashed lines are sources the tests do not rule out."
        : "Evidence for the selected input. Other connections are dimmed.";
    if (state.cellsFor)
      return "Click a cell to show it in the panel. Use Compare to overlay a second cell.";
    const f = state.focus;
    if (f && f !== "Inspiratory" && state.open.includes(f))
      return `Bright lines are inputs to ${show(f)} neurons.${isMember(f) ? "" : " Its outputs are dimmed."}`;
    if (state.expanded)
      return "Click a population to see its synaptic inputs. Lines from the dashed outline come from the inspiratory group as a whole.";
    return "Click a population to see its synaptic inputs. Click a connection to see the evidence for it.";
  }
  function render() {
    renderNodes();
    renderEdges();
    renderEvidence();
    renderCells();
    $("back").disabled = history.length === 0;
    $("context").textContent = state.edge
      ? `${show(state.edge.source)} → ${show(state.edge.target)}`
      : state.cellsFor
        ? `${show(state.cellsFor)} · cells`
        : show(state.focus || "");
    $("detail-legend").innerHTML =
      state.edge?.source === "Inspiratory"
        ? '<i class="line"></i>Identified <i class="line dash"></i>Possible'
        : "Width: mean fitted share";
    $("hint").textContent = hint();
    syncHash();
    if (guide) paintGuide();
  }
  function back() {
    const previous = history.pop();
    if (!previous) return;
    state = previous.state;
    render();
    if (previous.camera.width !== width || previous.camera.height !== height)
      frameFocus();
    else
      moveCamera(
        d3.zoomIdentity
          .translate(previous.camera.x, previous.camera.y)
          .scale(previous.camera.k),
      );
  }
  function home() {
    checkpoint();
    state = fresh();
    render();
    fitBounds(rootBounds(), true, 1.3);
  }
  function action(target) {
    if (target.closest("[data-close-edge]")) {
      checkpoint();
      state.edge = null;
      render();
      frameFocus();
      return;
    }
    if (target.closest("[data-close-cells]")) {
      checkpoint();
      state.cellsFor = null;
      render();
      frameFocus();
      return;
    }
    const cell = target.closest("[data-cell]");
    if (cell) {
      const id = cell.dataset.cell,
        pop = state.cellsFor;
      state.samples[pop] = id;
      if (state.compare[pop] === id) delete state.compare[pop];
      render();
      document
        .querySelector(`[data-cell="${id}"]`)
        .focus({ preventScroll: true });
      return;
    }
    const versus = target.closest("[data-compare-cell]");
    if (versus) {
      const id = versus.dataset.compareCell,
        pop = state.cellsFor;
      if (state.compare[pop] === id) delete state.compare[pop];
      else if (sample(pop) === "mean") state.samples[pop] = id;
      else state.compare[pop] = id;
      render();
      document
        .querySelector(`[data-compare-cell="${id}"]`)
        ?.focus({ preventScroll: true });
      return;
    }
    const clear = target.closest("[data-clear-compare]");
    if (clear) {
      delete state.compare[clear.dataset.clearCompare];
      render();
      return;
    }
    const mean = target.closest("[data-mean]");
    if (mean) {
      state.samples[mean.dataset.mean] = "mean";
      delete state.compare[mean.dataset.mean];
      render();
      return;
    }
    const cells = target.closest("[data-cells]");
    if (cells) {
      const id = cells.dataset.cells;
      if (state.cellsFor === id) {
        checkpoint();
        state.cellsFor = null;
        render();
        frameFocus();
      } else openCells(id);
      return;
    }
    if (target.closest("foreignObject")) return;
    const control = target.closest("[data-action]");
    if (control) {
      control.dataset.action === "fold"
        ? collapseNode(control.dataset.pop)
        : openNode(control.dataset.pop);
      return;
    }
    const edge = target.closest("[data-edge]");
    if (edge) {
      openEdge(edges.find((e) => e.id === edge.dataset.edge));
      return;
    }
    const node = target.closest("[data-node]");
    if (node) {
      const id = node.dataset.node;
      if (state.open.includes(id)) {
        state.focus = id;
        render();
        frameFocus();
      } else openNode(id);
    }
  }
  $("atlas").addEventListener("click", (e) => {
    if (!e.defaultPrevented) action(e.target);
  });
  $("atlas").addEventListener("keydown", (e) => {
    if (e.target.closest("foreignObject")) return;
    if (e.key === "Enter" || e.key === " ") {
      if (e.target !== $("atlas")) {
        e.preventDefault();
        action(e.target);
      }
    }
    if (e.key === "Escape") {
      e.preventDefault();
      back();
    }
    if (
      e.target === $("atlas") &&
      ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)
    ) {
      e.preventDefault();
      const delta = {
        ArrowUp: [0, 60],
        ArrowDown: [0, -60],
        ArrowLeft: [60, 0],
        ArrowRight: [-60, 0],
      }[e.key];
      svg.call(
        zoom.translateBy,
        delta[0] / transform().k,
        delta[1] / transform().k,
      );
    }
  });
  $("atlas").addEventListener("change", (e) => {
    if (e.target.matches("[data-sample]")) {
      const id = e.target.dataset.sample;
      state.samples[id] = e.target.value;
      if (e.target.value === "mean" || state.compare[id] === e.target.value)
        delete state.compare[id];
      render();
      document
        .querySelector(`[data-sample="${id}"]`)
        .focus({ preventScroll: true });
      return;
    }
    if (!state.edge) return;
    const r = state.edge,
      key = `${r.target}|${r.sign}`;
    if (!e.target.matches("[data-toggle]")) return;
    state.masks[key] = mask(r.target, r.sign) ^ (1 << +e.target.dataset.toggle);
    render();
    document
      .querySelector(`[data-toggle="${e.target.dataset.toggle}"]`)
      ?.focus({ preventScroll: true });
  });
  $("atlas").addEventListener(
    "toggle",
    (e) => {
      if (
        e.target.matches("[data-test-details]") &&
        state.testsOpen !== e.target.open
      ) {
        state.testsOpen = e.target.open;
        renderEvidence();
        syncHash();
        frameFocus();
      }
    },
    true,
  );

  // ---------- Hover: follow one connection, or the inputs of one population
  function setHover(next, event) {
    const same =
      (hover?.edge || null) === (next?.edge || null) &&
      (hover?.node || null) === (next?.node || null);
    hover = next;
    if (!same) applyHover();
    const tip = $("tip");
    const e = next?.edge && edges.find((x) => x.id === next.edge);
    if (!e || !event) {
      tip.hidden = true;
      return;
    }
    tip.textContent = `${edgeName(e)} — click for evidence`;
    tip.hidden = false;
    const r = $("workspace").getBoundingClientRect();
    tip.style.left =
      Math.min(r.width - tip.offsetWidth - 8, event.clientX - r.left + 14) +
      "px";
    tip.style.top = Math.max(4, event.clientY - r.top - 34) + "px";
  }
  $("atlas").addEventListener("pointermove", (e) => {
    if (e.pointerType === "touch") return;
    const edge = e.target.closest?.("[data-edge]"),
      node = e.target.closest?.("[data-node]");
    setHover(
      edge
        ? { edge: edge.dataset.edge }
        : node
          ? { node: node.dataset.node }
          : null,
      e,
    );
  });
  $("atlas").addEventListener("pointerleave", () => setHover(null));
  $("atlas").addEventListener("focusin", (e) => {
    const edge = e.target.closest?.("[data-edge]");
    if (edge) setHover({ edge: edge.dataset.edge });
  });
  $("atlas").addEventListener("focusout", () => setHover(null));

  $("back").addEventListener("click", back);
  $("home").addEventListener("click", home);
  $("fit").addEventListener("click", () => fitBounds(visibleBounds()));
  $("zoom-out").addEventListener("click", () =>
    svg.transition().duration(duration()).call(zoom.scaleBy, 1 / 1.35),
  );
  $("zoom-in").addEventListener("click", () =>
    svg.transition().duration(duration()).call(zoom.scaleBy, 1.35),
  );
  $("about").addEventListener("click", () => $("methods").showModal());
  $("close-methods").addEventListener("click", () => $("methods").close());
  if (!document.fullscreenEnabled) $("fullscreen").hidden = true;
  $("fullscreen").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      toast("Full screen is unavailable in this browser");
    }
  });
  document.addEventListener("fullscreenchange", () => {
    const label = document.fullscreenElement
      ? "Exit full screen"
      : "Full screen";
    $("fullscreen").innerHTML = icon(
      document.fullscreenElement ? "minimize" : "maximize",
    );
    $("fullscreen").setAttribute("aria-label", label);
    $("fullscreen").title = label;
  });
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer);
    $("toast").textContent = message;
    $("toast").classList.add("visible");
    toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 2200);
  }
  $("methods-body").innerHTML =
    `<p>This atlas accompanies the paper <em>From cellular synaptic input profiles to population-level respiratory circuitry</em>. It shows the analysis reported there: ${D.meta.nRecords} recordings from ${D.meta.nCells} neurons. Nothing is fitted, tested or simulated in the browser.</p>
    <h3>The circuit</h3>
    <p>Each ellipse is a population of neurons with one discharge pattern. Red arrows are excitatory inputs. Blue lines ending in a dot are inhibitory inputs. Line width is the mean fitted share of a population's total fitted excitation and inhibition. It is not a synaptic weight and not a measure of significance.</p>
    <p>The first view groups the three inspiratory populations, as in Figure 4A of the paper. A line to the group means that the input is supported for at least one of the three, not necessarily all. Its width is the average over the three.</p>
    <p>When the three inspiratory populations are shown separately, their outputs still start at the dashed outline. The tests often show that an inspiratory input is present without telling which of the three populations supplies it. Selecting such an input shows the candidates. A solid line is a source the tests identify. Dashed lines are alternatives that remain possible. For example, excitation of early-I neurons can be explained by pre-I/I alone, or by ramp-I and early-I together. Other sources are not excluded.</p>
    <p>A connection is an inferred functional input from neurons with one discharge pattern to neurons with another. It is not a traced anatomical projection. A loop on a population means input with that population's own timing, not a neuron that contacts itself.</p>
    <h3>Populations and cells</h3>
    <p>The small trace inside each population is its published discharge pattern (Smith et al., 2007). It is not a recording from the cells shown here. For the inspiratory group it combines the three patterns.</p>
    <p>A population's panel shows excitatory and inhibitory synaptic conductance over one respiratory cycle. Each is measured from its minimum over the cycle. Both are scaled to the larger of the two peaks in that recording, which is the 100 on the axis. The mean gives every cell equal weight. CC and VC mark cells recorded in current clamp and in voltage clamp.</p>
    <p>With one cell shown, the pale line is the population mean. A second cell can be overlaid for comparison.</p>
    <h3>Fits and evidence</h3>
    <p>Each conductance was fitted as a sum of the five discharge patterns with nonnegative weights. The dashed line is that fit. In an evidence card the colored lines are the contributions of the patterns: green for inspiratory, purple for post-I and orange for aug-E, as in Figure 3 of the paper. For an inspiratory input the three inspiratory patterns are drawn separately in green, with different line styles.</p>
    <p>An input is called supported when, with its pattern left out, the remaining patterns fail on average across cells to reproduce the timing of the conductance (adjusted P &lt; 0.05, corrected for all the inputs tested). The test concerns the population even when a single cell is displayed.</p>
    <p>For an inspiratory input, the checkboxes show the fit with any subset of the three inspiratory patterns. Post-I and aug-E are always included. These are fits from the paper's analysis, not new calculations. A combination that the tests do not rule out has not been shown to fit equally well.</p>
    <p>Fitted share, fit error and statistical support are different quantities. The fit error given for a population is the average of the errors of its cells.</p>
    <p>The paper gives the full methods, assumptions and limitations.</p>
    <h3>Software</h3>
    <p>D3 7.9.0 and Lucide 0.468.0 icons, both under the ISC license. All data and code are embedded in this page, which makes no network requests.</p>`;

  // ---------- Links to a specific view ----------
  const validCell = (pop, id) =>
    D.groups[pop]?.cells.some((c) => c.id === id) ? id : null;
  function encodeState() {
    const parts = [];
    if (state.expanded && !state.open.some(isMember)) parts.push("group=open");
    if (state.open.length) parts.push("open=" + state.open.join(","));
    if (state.cellsFor) parts.push("cells=" + state.cellsFor);
    const pairs = (o) =>
      Object.entries(o)
        .filter(([, v]) => v && v !== "mean")
        .map(([k, v]) => `${k}:${v}`)
        .join(",");
    if (pairs(state.samples)) parts.push("cell=" + pairs(state.samples));
    if (pairs(state.compare)) parts.push("compare=" + pairs(state.compare));
    if (state.edge)
      parts.push(
        `input=${state.edge.source}:${state.edge.target}:${state.edge.sign}`,
      );
    const masks = Object.entries(state.masks)
      .filter(([, v]) => v !== 7)
      .map(([k, v]) => `${k.replace("|", ":")}:${v}`)
      .join(",");
    if (masks) parts.push("sources=" + masks);
    return parts.join("&");
  }
  function decodeState(text) {
    const next = fresh();
    let q = {};
    try {
      q = Object.fromEntries(
        text
          .split("&")
          .map((p) => p.split("=").map(decodeURIComponent))
          .filter((p) => p.length === 2),
      );
    } catch {
      return next;
    }
    if (q.group === "open") next.expanded = true;
    for (const id of (q.open || "").split(","))
      if (D.names.includes(id) && !next.open.includes(id)) next.open.push(id);
    for (const [key, store] of [
      ["cell", next.samples],
      ["compare", next.compare],
    ])
      for (const item of (q[key] || "").split(",")) {
        const [pop, id] = item.split(":");
        if (validCell(pop, id)) store[pop] = id;
      }
    for (const item of (q.sources || "").split(",")) {
      const [pop, sign, m] = item.split(":");
      if (D.names.includes(pop) && "EI".includes(sign) && /^[0-7]$/.test(m))
        next.masks[`${pop}|${sign}`] = +m;
    }
    if (q.input) {
      const [source, target, sign] = q.input.split(":");
      if (
        D.coarse.some(
          (r) =>
            r.supported &&
            r.source === source &&
            r.target === target &&
            r.sign === sign,
        )
      ) {
        next.edge = { source, target, sign };
        if (!next.open.includes(target)) next.open.push(target);
        if (source === "Inspiratory") next.expanded = true;
      }
    }
    if (D.names.includes(q.cells) && !next.edge) {
      next.cellsFor = q.cells;
      if (!next.open.includes(q.cells)) next.open.push(q.cells);
    }
    if (next.open.some(isMember)) next.expanded = true;
    next.focus =
      next.edge?.target ||
      next.cellsFor ||
      next.open.at(-1) ||
      (next.expanded ? "Inspiratory" : null);
    return next;
  }
  let lastHash = "";
  function syncHash() {
    const text = encodeState();
    if (text === lastHash) return;
    lastHash = text;
    try {
      window.history.replaceState(
        null,
        "",
        text ? "#" + text : location.pathname + location.search,
      );
    } catch {
      /* Some embedded viewers do not allow the address to change. */
    }
  }
  function applyHash() {
    const text = location.hash.replace(/^#/, "");
    if (text === "guide") return "guide";
    if (!text || text === lastHash) return "";
    state = decodeState(text);
    return "state";
  }
  window.addEventListener("hashchange", () => {
    const result = applyHash();
    if (result === "guide") return startGuide();
    if (result === "state") {
      render();
      frameFocus();
    }
  });

  // ---------- Guide: from the circuit to the cells behind it ----------
  const GUIDE_POP = "pre-I",
    GUIDE_EDGE = "aug-E|pre-I|E";
  // The cells nearest to and farthest from the group mean, so that the
  // comparison shows the spread and not a favorable example.
  function contrastingCells(pop) {
    const g = D.groups[pop];
    const ranked = g.cells
      .map((c) => ({
        id: c.id,
        d: c.profiles.reduce(
          (sum, p, si) =>
            sum +
            p.reduce((t, v, k) => t + (v - g.mean.profiles[si][k]) ** 2, 0),
          0,
        ),
      }))
      .sort((a, b) => a.d - b.d);
    return [ranked[0].id, ranked.at(-1).id];
  }
  const place = (patch) => {
    state = Object.assign(fresh(), patch);
    render();
    if (patch.expanded) frameFocus();
    else fitBounds(rootBounds(), true, 1.3);
  };
  const withPanel = (extra = {}) => ({
    expanded: true,
    open: [GUIDE_POP],
    focus: GUIDE_POP,
    ...extra,
  });
  const nCells = D.groups[GUIDE_POP].n;
  const steps = [
    {
      title: "This is the reconstructed circuit",
      text: "Each ellipse is a population of neurons with one discharge pattern. Red arrows show excitation. Blue lines ending in a dot show inhibition. Thicker lines are larger fitted contributions.",
      setup: () => place({}),
    },
    {
      title: "Separate the inspiratory populations",
      text: "The inspiratory group combines pre-I/I, ramp-I and early-I neurons. Click “Show 3 populations” to see what each one receives.",
      after:
        "Each inspiratory population now has its own inputs. Lines that start at the dashed outline come from the group as a whole, because the tests do not always tell which of the three supplies them.",
      target: '[data-action="expand"][data-pop="Inspiratory"]',
      done: (s) => s.expanded,
      act: () => openNode("Inspiratory"),
      setup: () => place({}),
    },
    {
      title: "Choose a receiving population",
      text: "To see what the cells receiving these inputs showed, click “Show inputs” on pre-I/I.",
      after: `The panel shows mean excitation (red) and inhibition (blue) in ${nCells} pre-I/I cells over one respiratory cycle. Shading marks inspiration. The dashed line is the fit from the five discharge patterns. Bright connections are the inputs that explain these curves.`,
      target: `[data-action="expand"][data-pop="${GUIDE_POP}"]`,
      done: (s) => s.open.includes(GUIDE_POP),
      act: () => openNode(GUIDE_POP),
      setup: () => place({ expanded: true, focus: "Inspiratory" }),
    },
    {
      title: "Open the individual cells",
      text: `A mean hides the variation between cells. Click “Browse ${nCells} cells” in the panel.`,
      after:
        "Every recorded cell is here, including the variable and less clean ones. Red is excitation and blue is inhibition.",
      target: `[data-cells="${GUIDE_POP}"]`,
      done: (s) => s.cellsFor === GUIDE_POP,
      act: () => openCells(GUIDE_POP),
      setup: () => place(withPanel()),
    },
    {
      title: "Compare two cells",
      text: "Click a cell to show it in the panel. Then click “Compare” under another cell to overlay the two. “Show me” picks the cell closest to the mean and the cell farthest from it.",
      after:
        "The panel now shows both cells: one in color and one in dark gray, with the group mean as a pale line.",
      done: (s) =>
        !!s.samples[GUIDE_POP] &&
        s.samples[GUIDE_POP] !== "mean" &&
        !!s.compare[GUIDE_POP],
      act: () => {
        const [near, far] = contrastingCells(GUIDE_POP);
        state.samples[GUIDE_POP] = near;
        state.compare[GUIDE_POP] = far;
        render();
      },
      setup: () => place(withPanel({ cellsFor: GUIDE_POP })),
    },
    {
      title: "See the evidence for a connection",
      text: "Now ask where an input comes from. Click the red line from aug-E to pre-I/I.",
      after:
        "The card says in words what the test showed, then gives the numbers. In the plot, the dark line is the mean input and the gray dashes are the fit. The colored lines are the contributions of the discharge patterns: green for inspiratory, purple for post-I and orange for aug-E.",
      target: `[data-edge="${GUIDE_EDGE}"]`,
      done: (s) =>
        s.edge?.source === "aug-E" &&
        s.edge?.target === GUIDE_POP &&
        s.edge?.sign === "E",
      act: () => openEdge(edges.find((e) => e.id === GUIDE_EDGE)),
      setup: () => place(withPanel()),
    },
    {
      title: "That is the whole route",
      text: "Circuit, population, cells, evidence. An input from the inspiratory group also lists which of its three populations could supply it. “Whole circuit” starts over, and “Guide” replays these steps.",
      setup: () => {},
    },
  ];
  const remember = () => {
    try {
      localStorage.setItem(SEEN_KEY, "seen");
    } catch {
      /* Private windows may refuse storage; the guide still works. */
    }
  };
  const seen = () => {
    try {
      return localStorage.getItem(SEEN_KEY) === "seen";
    } catch {
      return false;
    }
  };
  function dock(visible) {
    $("guide").hidden = !visible;
    const before = reserveBottom;
    reserveBottom = visible ? $("guide").offsetHeight + 16 : 0;
    return before !== reserveBottom;
  }
  function paintGuide() {
    document
      .querySelectorAll(".guide-target")
      .forEach((el) => el.classList.remove("guide-target"));
    if (guide.welcome) {
      $("guide-step").textContent = "First visit?";
      $("guide-title").textContent = "Take the one-minute guide";
      $("guide-body").textContent =
        "It shows the way from the circuit to the individual cell records behind each connection.";
      $("guide-back").hidden = false;
      $("guide-back").disabled = false;
      $("guide-back").textContent = "Not now";
      $("guide-next").textContent = "Start guide";
      dock(true);
      return;
    }
    const step = steps[guide.i],
      waiting = !!step.done && !step.done(state);
    $("guide-step").textContent = `Guide · ${guide.i + 1} of ${steps.length}`;
    $("guide-title").textContent = step.title;
    $("guide-body").textContent = waiting || !step.after ? step.text : step.after;
    $("guide-back").hidden = false;
    $("guide-back").textContent = "Back";
    $("guide-back").disabled = guide.i === 0;
    $("guide-next").textContent =
      guide.i === steps.length - 1 ? "Finish" : waiting ? "Show me" : "Next";
    if (waiting && step.target) {
      const el = document.querySelector(step.target);
      (el?.matches(".edge-hit") ? el.parentNode : el)?.classList.add(
        "guide-target",
      );
    }
    if (dock(true)) frameFocus();
  }
  function showStep(i) {
    guide = { i };
    paintGuide();
    steps[i].setup();
  }
  function startGuide() {
    remember();
    history = [];
    showStep(0);
  }
  function endGuide() {
    remember();
    guide = null;
    document
      .querySelectorAll(".guide-target")
      .forEach((el) => el.classList.remove("guide-target"));
    if (dock(false)) frameFocus();
  }
  $("guide-open").addEventListener("click", startGuide);
  $("guide-exit").addEventListener("click", endGuide);
  $("guide-back").addEventListener("click", () => {
    if (guide.welcome) return endGuide();
    if (guide.i > 0) showStep(guide.i - 1);
  });
  $("guide-next").addEventListener("click", () => {
    if (guide.welcome) return startGuide();
    const step = steps[guide.i];
    if (step.done && !step.done(state)) return step.act();
    if (guide.i === steps.length - 1) return endGuide();
    showStep(guide.i + 1);
  });

  function resize() {
    const r = $("workspace").getBoundingClientRect();
    width = r.width;
    height = r.height;
    if (guide) reserveBottom = $("guide").offsetHeight + 16;
    render();
    if (!state.expanded && !state.open.length && !state.edge)
      fitBounds(rootBounds(), false, 1.3);
    else frameFocus(false);
  }
  const entry = applyHash();
  render();
  new ResizeObserver(resize).observe($("workspace"));
  if (entry === "guide") startGuide();
  else if (!entry && !seen()) {
    guide = { welcome: true };
    paintGuide();
  }
  window.connectome = {
    data: D,
    getState: () => ({
      ...structuredClone(state),
      zoom: transform().k,
      guide: guide ? (guide.welcome ? "welcome" : guide.i) : null,
    }),
    edges: () => edges.map((e) => ({ ...e })),
    getSeries: (
      target = state.edge?.target ||
        (D.names.includes(state.focus) ? state.focus : "post-I"),
      sign = state.edge?.sign || "E",
    ) => curve(target, sign),
    startGuide,
    link: encodeState,
  };
})();
