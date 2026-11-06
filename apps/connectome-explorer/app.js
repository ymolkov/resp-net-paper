(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("dataset").textContent);
  const icons = JSON.parse(document.getElementById("icons").textContent);
  const C = window.ConnectomeCore,
    $ = (id) => document.getElementById(id);
  const color = { E: "#b83e3d", I: "#287ba5" };
  const pattern = ["#277e68", "#b86182", "#ac8424", "#6775ad", "#916635"];
  const anchors = {
    Inspiratory: [270, 410],
    "pre-I": [260, 120],
    "ramp-I": [230, 410],
    "early-I": [260, 700],
    "post-I": [1160, 200],
    "aug-E": [1160, 650],
  };
  const fresh = () => ({
    expanded: false,
    open: [],
    focus: null,
    edge: null,
    cellsFor: null,
    testsOpen: false,
    samples: {},
    masks: {},
  });
  let state = fresh(),
    history = [],
    phase = 12,
    playing = false,
    frame,
    lastTime = 0,
    accumulated = 0;
  let width = 1,
    height = 1,
    baseScale = 1,
    edges = [],
    nodes = [],
    wheelPoint = null,
    zoomStart = 1;
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
  const pval = (v) =>
    v === null ? "Not tested" : v < 0.001 ? v.toExponential(2) : v.toFixed(3);
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
  const mask = (target, sign) => state.masks[`${target}|${sign}`] ?? 7;
  const curve = (target, sign) =>
    C.series(D, target, sign, sample(target), mask(target, sign));
  const svg = d3.select("#atlas"),
    world = d3.select("#world");
  const transform = () => d3.zoomTransform($("atlas"));
  const mobile = () => width < 700;
  const position = (id) =>
    mobile()
      ? {
          Inspiratory: [320, 130],
          "pre-I": [-140, 130],
          "ramp-I": [320, 130],
          "early-I": [780, 130],
          "post-I": [100, 620],
          "aug-E": [550, 620],
        }[id]
      : anchors[id];
  const rootBounds = () =>
    mobile() ? [-115, -80, 785, 880] : [65, 15, 1350, 850];
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
    .scaleExtent([0.12, 3.8])
    .clickDistance(5)
    .filter(
      (e) =>
        !e.target.closest("foreignObject") && (!e.button || e.type === "wheel"),
    )
    .on("start", (e) => {
      zoomStart = e.transform.k;
    })
    .on("zoom", (e) => {
      world.attr("transform", e.transform);
      $("zoom-level").textContent =
        Math.round((e.transform.k / baseScale) * 100) + "%";
      updateMap();
    })
    .on("end", (e) => {
      if (!e.sourceEvent || !["wheel", "touchend"].includes(e.sourceEvent.type))
        return;
      const ratio = e.transform.k / baseScale;
      if (
        e.transform.k < zoomStart &&
        ratio < 0.91 &&
        (state.expanded || state.open.length || state.edge)
      ) {
        checkpoint();
        state = fresh();
        render();
        return;
      }
      if (
        e.transform.k < zoomStart &&
        ratio < 1.1 &&
        (state.edge || state.open.length)
      ) {
        checkpoint();
        state.edge = null;
        state.cellsFor = null;
        state.open = [];
        state.focus = state.expanded ? "Inspiratory" : null;
        render();
        return;
      }
      if (e.transform.k <= zoomStart || ratio < 1.32) return;
      const point = wheelPoint || [width / 2, height / 2];
      const p = e.transform.invert(point);
      const near = nodes.find(
        (n) =>
          Math.abs(p[0] - n.x) < n.rx + 50 && Math.abs(p[1] - n.y) < n.ry + 50,
      );
      if (
        near &&
        ((near.id === "Inspiratory" && !state.expanded) ||
          (near.id !== "Inspiratory" && !state.open.includes(near.id)))
      )
        openNode(near.id, false);
    });
  svg.call(zoom).on("dblclick.zoom", null);
  $("atlas").addEventListener(
    "wheel",
    (e) => {
      const r = $("atlas").getBoundingClientRect();
      wheelPoint = [e.clientX - r.left, e.clientY - r.top];
    },
    { passive: true, capture: true },
  );
  $("atlas").addEventListener(
    "touchmove",
    (e) => {
      if (!e.touches.length) return;
      const r = $("atlas").getBoundingClientRect();
      const touches = [...e.touches];
      wheelPoint = [
        d3.mean(touches, (t) => t.clientX) - r.left,
        d3.mean(touches, (t) => t.clientY) - r.top,
      ];
    },
    { passive: true, capture: true },
  );
  function moveCamera(t, animate = true) {
    svg.interrupt();
    const selection = animate ? svg.transition().duration(duration()) : svg;
    selection.call(zoom.transform, t);
  }
  function fitBounds(bounds, animate = true, maxScale = 1.3) {
    const [x0, y0, x1, y1] = bounds;
    const k = Math.max(
      0.12,
      Math.min(maxScale, (width - 50) / (x1 - x0), (height - 125) / (y1 - y0)),
    );
    moveCamera(
      d3.zoomIdentity
        .translate(
          width / 2 - ((x0 + x1) / 2) * k,
          62 + (height - 125) / 2 - ((y0 + y1) / 2) * k,
        )
        .scale(k),
      animate,
    );
  }
  function boundsFor(items) {
    return [
      Math.min(...items.map((n) => n.x - n.rx - 35)),
      Math.min(...items.map((n) => n.y - n.ry - 35)),
      Math.max(...items.map((n) => n.x + n.rx + 35)),
      Math.max(...items.map((n) => n.y + n.ry + 35)),
    ];
  }
  function evidenceBox() {
    return {
      x: mobile() ? 325 : 735,
      y: mobile() ? 1030 : 420,
      rx: 180,
      ry:
        state.edge?.source === "Inspiratory"
          ? state.testsOpen
            ? 312
            : 257
          : 197,
    };
  }
  function cellBox() {
    const n = nodeFor(state.cellsFor);
    return {
      x: n.x + (D.names.indexOf(n.id) < 3 ? -375 : 375),
      y: n.y,
      rx: 145,
      ry: 202,
    };
  }
  function visibleBounds() {
    return boundsFor([
      ...nodes,
      ...(state.edge ? [evidenceBox()] : []),
      ...(state.cellsFor ? [cellBox()] : []),
    ]);
  }
  function frameFocus() {
    if (width < 700) {
      if (state.cellsFor) return fitBounds(boundsFor([cellBox()]), true, 1.15);
      if (state.edge) return fitBounds(boundsFor([evidenceBox()]), true, 1.15);
      const n = nodes.find((n) => n.id === state.focus);
      if (n && n.open) return fitBounds(boundsFor([n]), true, 1.4);
    }
    fitBounds(visibleBounds());
  }
  function nodeFor(id, role = "target") {
    if (id === "Inspiratory" && state.expanded && role === "source")
      return {
        id,
        x: mobile() ? 320 : 520,
        y: mobile() ? 335 : 410,
        rx: 25,
        ry: 25,
      };
    const [x, y] = position(id);
    const open = state.open.includes(id);
    return {
      id,
      x,
      y,
      open,
      rx: open ? 172 : id === "Inspiratory" ? 132 : 104,
      ry: open ? 133 : id === "Inspiratory" ? 92 : 82,
    };
  }
  function openNode(id, reframe = true) {
    checkpoint();
    state.focus = id;
    if (id === "Inspiratory") state.expanded = true;
    else {
      if (D.names.indexOf(id) < 3) state.expanded = true;
      if (!state.open.includes(id)) state.open.push(id);
    }
    render();
    if (reframe) frameFocus();
  }
  function collapseNode(id) {
    checkpoint();
    if (id === "Inspiratory") {
      state.expanded = false;
      state.open = state.open.filter((n) => D.names.indexOf(n) > 2);
      state.edge = null;
      state.cellsFor = null;
      state.focus = "Inspiratory";
    } else {
      state.open = state.open.filter((n) => n !== id);
      if (state.cellsFor === id) state.cellsFor = null;
      if (state.edge?.target === id) state.edge = null;
    }
    render();
    frameFocus();
  }
  function openEdge(edge) {
    checkpoint();
    const target =
      edge.target === "Inspiratory" ? edge.members[0].target : edge.target;
    const source = edge.fine ? "Inspiratory" : edge.source;
    if (source === "Inspiratory" || D.names.indexOf(target) < 3)
      state.expanded = true;
    state.edge = { source, target, sign: edge.sign };
    state.focus = target;
    state.testsOpen = false;
    if (!state.open.includes(target)) state.open.push(target);
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
  function boundary(n, dx, dy, gap = 0) {
    const t = n.open
      ? Math.min(
          n.rx / Math.max(0.001, Math.abs(dx)),
          n.ry / Math.max(0.001, Math.abs(dy)),
        )
      : 1 / Math.sqrt((dx / n.rx) ** 2 + (dy / n.ry) ** 2);
    const length = Math.hypot(dx, dy) || 1;
    return [
      n.x + dx * t + (gap * dx) / length,
      n.y + dy * t + (gap * dy) / length,
    ];
  }
  function pathFor(e) {
    const a = nodeFor(e.source, "source"),
      b = nodeFor(e.target),
      sign = e.sign === "E" ? -1 : 1;
    if (selectedEdge(e)) {
      const box = evidenceBox(),
        rank = e.fine ? D.names.indexOf(e.source) : 1;
      const end = [box.x - box.rx, box.y - 60 + rank * 42];
      const start = boundary(a, end[0] - a.x, end[1] - a.y);
      return {
        d: `M${start} C${start[0] + 100},${start[1]} ${end[0] - 70},${end[1]} ${end}`,
        end,
        terminal: false,
      };
    }
    if (e.source === e.target) {
      const start = [a.x + sign * a.rx * 0.5, a.y - a.ry * 0.85],
        end = boundary(
          a,
          sign * a.rx * 0.88,
          -a.ry * 0.42,
          e.sign === "I" ? 6 : 2,
        );
      return {
        d: `M${start} C${a.x + sign * (a.rx + 110)},${a.y - a.ry - 150} ${a.x + sign * (a.rx + 170)},${a.y - a.ry + 20} ${end}`,
        end,
        terminal: true,
      };
    }
    const dx = b.x - a.x,
      dy = b.y - a.y,
      len = Math.hypot(dx, dy),
      bend = 50 + sign * 22;
    const nx = -dy / len,
      ny = dx / len;
    const p1 = [a.x + dx * 0.34 + nx * bend, a.y + dy * 0.34 + ny * bend];
    const p2 = [a.x + dx * 0.66 + nx * bend, a.y + dy * 0.66 + ny * bend];
    const start = boundary(a, p1[0] - a.x, p1[1] - a.y),
      end = boundary(b, p2[0] - b.x, p2[1] - b.y, e.sign === "I" ? 6 : 2);
    return { d: `M${start} C${p1} ${p2} ${end}`, end, terminal: true };
  }
  function nodeAction(id, name, title, x, y) {
    return `<g class="node-action" role="button" tabindex="0" data-action="${name}" data-pop="${id}" aria-label="${title}" transform="translate(${x},${y})"><title>${title}</title><rect x="-13" y="-13" width="26" height="26" rx="4" fill="#f3f7f4" stroke="#d8e4dc"/><g class="small-icon" transform="translate(-8,-8)">${icon(name === "fold" ? "minus" : "plus")}</g></g>`;
  }
  function profilePlot(target, sign, x = 0, y = 0) {
    const s = curve(target, sign),
      max = Math.max(1.05, ...s.fit, ...s.observed);
    return `<svg viewBox="0 0 316 67" data-chart="${target}|${sign}" aria-label="${target} ${sign === "E" ? "excitatory" : "inhibitory"} conductance"><rect x="22" y="3" width="${284 * D.ti}" height="48" fill="#edf3ef"/><line x1="22" x2="306" y1="51" y2="51" stroke="#d7e2dd"/><text x="17" y="${55 - 43 / max}" text-anchor="end" class="chart-label">100</text><text x="17" y="54" text-anchor="end" class="chart-label">0</text><path d="${chartLine(s.observed, 22, 51, 284, 43, max)}" fill="none" stroke="${color[sign]}" stroke-width="1.9"/><path d="${chartLine(s.fit, 22, 51, 284, 43, max)}" fill="none" stroke="#75827e" stroke-width="1.5" stroke-dasharray="4 3"/><line class="phase-cursor" data-cursor-x="22" data-cursor-width="284" y1="3" y2="52"/><text x="22" y="65" class="chart-label">0</text><text x="${22 + 284 * D.ti}" y="65" text-anchor="middle" class="chart-label">I/E</text><text x="306" y="65" text-anchor="end" class="chart-label">1</text></svg>`;
  }
  function nodeContent(n) {
    const id = n.id,
      group = D.groups[id];
    if (n.open) {
      return `<rect class="node-shape" x="-${n.rx}" y="-${n.ry}" width="${n.rx * 2}" height="${n.ry * 2}" rx="8"/><text class="node-title" x="${-n.rx + 17}" y="${-n.ry + 29}">${id}</text><text class="node-meta" x="${-n.rx + 105}" y="${-n.ry + 26}">${group.n} cells</text>${nodeAction(id, "fold", `Fold ${id}`, n.rx - 21, -n.ry + 23)}
        <foreignObject x="-${n.rx}" y="${-n.ry + 42}" width="${n.rx * 2}" height="${n.ry * 2 - 44}"><div xmlns="http://www.w3.org/1999/xhtml" class="node-content"><div class="sample-row"><select data-sample="${id}" aria-label="${id} conductance sample"><option value="mean">Group mean</option>${group.cells.map((c) => `<option value="${c.id}" ${sample(id) === c.id ? "selected" : ""}>${c.label} · ${c.modes.join(" + ")}</option>`).join("")}</select><button class="icon" data-cells="${id}" title="Browse ${id} cells" aria-label="Browse ${id} cells">${icon("grid-2x2")}</button></div><div class="chart-heading"><span class="red">Excitation</span><span>% of joint peak</span></div>${profilePlot(id, "E")}<div class="chart-heading"><span class="blue">Inhibition</span></div>${profilePlot(id, "I")}<div class="chart-legend"><span><i class="line"></i>Reconstructed</span><span><i class="line dash"></i>Saved fit</span></div></div></foreignObject>`;
    }
    const family = id === "Inspiratory",
      js = family ? [0, 1, 2] : [D.names.indexOf(id)];
    return `<ellipse class="node-shape" rx="${n.rx}" ry="${n.ry}"/><text class="node-title" y="-28" text-anchor="middle">${id}</text><text class="node-meta" y="-8" text-anchor="middle">${family ? "pre-I · ramp-I · early-I" : `${group.n} cells`}</text><rect x="-58" y="4" width="${116 * D.ti}" height="30" fill="#edf3ef"/>${js
      .map(
        (j) =>
          `<path d="${chartLine(
            D.matrix.map((r) => r[j]),
            -58,
            33,
            116,
            27,
          )}" stroke="${pattern[j]}" fill="none" stroke-width="1.8"/>`,
      )
      .join(
        "",
      )}<circle class="port" data-phase-pop="${id}" cx="-15" cy="53" r="7" fill="${color.E}" stroke="${color.E}"/><circle class="port" data-phase-pop="${id}" cx="15" cy="53" r="7" fill="${color.I}" stroke="${color.I}"/>${nodeAction(id, "expand", `Expand ${id}`, n.rx - 19, -n.ry + 20)}`;
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
          `translate(${D.names.indexOf(n.id) < 3 ? position("Inspiratory") : [n.x, n.y]})`,
      );
    const all = enter.merge(join);
    all
      .attr("data-node", (n) => n.id)
      .attr("role", (n) => (n.open ? "group" : "button"))
      .attr("tabindex", 0)
      .attr("aria-label", (n) => `${n.open ? "Focus" : "Expand"} ${n.id}`)
      .attr("aria-expanded", (n) => String(n.open))
      .classed("selected", (n) => n.id === state.focus)
      .html(nodeContent);
    all
      .transition()
      .duration(duration())
      .attr("opacity", 1)
      .attr("transform", (n) => `translate(${n.x},${n.y})`);
    const layer = d3.select("#family-layer");
    const hub = nodeFor("Inspiratory", "source");
    layer.html(
      state.expanded
        ? `<rect class="family-hull" x="${mobile() ? -325 : 25}" y="-45" width="${mobile() ? 1290 : 545}" height="${mobile() ? 440 : 900}" rx="80"/><text class="family-title" x="${mobile() ? -285 : 62}" y="-13">Inspiratory family</text>${nodeAction("Inspiratory", "fold", "Fold inspiratory family", mobile() ? 920 : 528, -16)}<g class="source-hub" transform="translate(${hub.x},${hub.y})"><circle r="25" fill="#edf3ef" stroke="#a6beb1"/><circle cx="-9" r="6" fill="${color.E}" data-phase-pop="Inspiratory"/><circle cx="9" r="6" fill="${color.I}" data-phase-pop="Inspiratory"/><text y="45" text-anchor="middle">Family outputs</text></g>`
        : "",
    );
  }
  function edgeOpacity(e) {
    if (state.edge)
      return selectedEdge(e)
        ? e.fine && !(mask(e.target, e.sign) & (1 << D.names.indexOf(e.source)))
          ? 0.2
          : 1
        : 0.13;
    if (state.focus && state.focus !== "Inspiratory")
      return e.source === state.focus || e.target === state.focus ? 1 : 0.23;
    return 0.85;
  }
  function renderEdges() {
    edges = C.networkEdges(D, state.expanded, state.edge);
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
      .attr("stroke-width", (e) => (e.fine ? 2.5 : 1.2 + 11 * e.share))
      .attr("stroke-dasharray", (e) => (e.style === "dashed" ? "7 5" : null))
      .attr("marker-end", (e) =>
        e.sign === "E" && pathFor(e).terminal ? "url(#arrowE)" : null,
      )
      .transition()
      .duration(duration())
      .attr("d", (e) => pathFor(e).d);
    all
      .select(".inhibitory-end")
      .attr("r", (e) => (e.sign === "I" && pathFor(e).terminal ? 4 : 0))
      .attr("fill", (e) => color[e.sign])
      .transition()
      .duration(duration())
      .attr("cx", (e) => pathFor(e).end[0])
      .attr("cy", (e) => pathFor(e).end[1]);
    all
      .select(".edge-hit")
      .attr("role", "button")
      .attr("tabindex", 0)
      .attr("data-edge", (e) => e.id)
      .attr(
        "aria-label",
        (e) =>
          `${e.source} to ${e.target}, ${e.sign === "E" ? "excitation" : "inhibition"}${e.fine ? `, ${e.style === "solid" ? "identified" : "alternative"}` : ""}`,
      )
      .attr("d", (e) => pathFor(e).d);
  }
  function relationContent() {
    const r = state.edge,
      p = D.panels[`${r.target}|${r.sign}`],
      fine = r.source === "Inspiratory",
      s = curve(r.target, r.sign);
    const fitState = C.fitStatus(D, r.target, r.sign, mask(r.target, r.sign));
    const row = D.coarse.find(
      (e) =>
        e.source === r.source && e.target === r.target && e.sign === r.sign,
    );
    const combinations = p.minima
      .map((m) =>
        C.members(m).length > 1
          ? `(${C.label(m, D.names)})`
          : C.label(m, D.names),
      )
      .join(" or ");
    return `<div xmlns="http://www.w3.org/1999/xhtml" class="evidence-content"><button class="close-detail icon" data-close-edge title="Fold connection detail" aria-label="Fold connection detail">${icon("x")}</button><h2>${r.source} → ${r.target}</h2><div class="subhead">${r.sign === "E" ? "Excitatory" : "Inhibitory"} input · ${D.groups[r.target].n} cells · group evidence</div>
      ${
        fine
          ? `<div class="combination">Smallest sets not ruled out:<br><strong>${combinations}</strong></div><fieldset aria-label="Retained inspiratory combinations">${C.alternatives(
              D,
              r.target,
              r.sign,
            )
              .map(
                (m) =>
                  `<label class="option"><input type="radio" name="subset" value="${m}" ${m === mask(r.target, r.sign) ? "checked" : ""}/>${m === 7 ? "All three inspiratory sources" : C.label(m, D.names)}</label>`,
              )
              .join("")}</fieldset><div class="switches">${D.names
              .slice(0, 3)
              .map(
                (n, j) =>
                  `<label><input type="checkbox" data-toggle="${j}" aria-label="Include ${n} source" ${mask(r.target, r.sign) & (1 << j) ? "checked" : ""}/>${n}</label>`,
              )
              .join(
                "",
              )}</div><div class="fixed">Post-I and aug-E remain available in every saved fit.</div><div class="relation-status ${fitState}">${fitState === "full" ? "All-source fit" : fitState === "excluded" ? "This combination is ruled out by group tests" : "This combination is not ruled out by group tests"}</div>`
          : `<div class="relation-status"><strong>Supported input</strong><br>Adjusted P = ${pval(row.p_joint)}<br>Full-fit area: ${pct(row.share_mean)} of total dynamic excitation + inhibition</div>`
      }
      <svg class="fit-chart" viewBox="0 0 328 100" data-chart="${r.target}|${r.sign}" aria-label="Selected input fit"><rect x="8" y="4" width="${310 * D.ti}" height="78" fill="#edf3ef"/>${s.components.map((v, j) => `<path d="${chartLine(v, 8, 82, 310, 71, Math.max(1.05, ...s.fit, ...s.observed))}" fill="none" stroke="${pattern[j]}" stroke-width="1.3" opacity=".55"/>`).join("")}<path d="${chartLine(s.observed, 8, 82, 310, 71, Math.max(1.05, ...s.fit, ...s.observed))}" fill="none" stroke="#263638" stroke-width="1.8"/><path d="${chartLine(s.fit, 8, 82, 310, 71, Math.max(1.05, ...s.fit, ...s.observed))}" fill="none" stroke="#277961" stroke-width="1.8" stroke-dasharray="4 3"/><line class="phase-cursor" data-cursor-x="8" data-cursor-width="310" y1="4" y2="82"/><text x="8" y="96" class="chart-label">0</text><text x="${8 + 310 * D.ti}" y="96" class="chart-label">I/E</text><text x="318" y="96" text-anchor="end" class="chart-label">1</text></svg><div class="error-row"><span>${sample(r.target) === "mean" ? "Mean cell" : "Cell"} RMSE ${pct(s.rmse)}</span><span>Extra error +${(s.delta * 100).toFixed(2)} pts</span></div><div class="small-note">${sample(r.target) === "mean" ? "Equal-cell mean" : "Selected cell"} · black: reconstructed · green dashed: selected fit.<br>Joint conductance peak normalization. Statistical evidence remains group-level.</div>
      <div class="component-legend">${D.names.map((name, j) => `<span><i style="background:${pattern[j]}"></i>${name}</span>`).join("")}</div>
      ${fine ? `<details data-test-details ${state.testsOpen ? "open" : ""}><summary>Omission tests · adjusted P</summary><div class="evidence-scroll"><table>${p.tests.map((t) => `<tr><td>${esc(t.omitted_sources)}</td><td>${pval(t.p_joint)}</td></tr>`).join("")}</table></div></details>` : ""}</div>`;
  }
  function renderEvidence() {
    const layer = d3.select("#evidence-layer");
    if (!state.edge) {
      layer.html("");
      return;
    }
    const b = evidenceBox(),
      target = nodeFor(state.edge.target),
      start = [b.x + b.rx, b.y];
    const end = boundary(
      target,
      start[0] - target.x,
      start[1] - target.y,
      state.edge.sign === "I" ? 6 : 2,
    );
    const d = `M${start} C${start[0] + 65},${start[1]} ${end[0] - 80},${end[1]} ${end}`;
    layer.html(
      `<path class="edge-line" d="${d}" stroke="${color[state.edge.sign]}" stroke-width="2.8" ${state.edge.sign === "E" ? 'marker-end="url(#arrowE)"' : ""}/>${state.edge.sign === "I" ? `<circle cx="${end[0]}" cy="${end[1]}" r="4" fill="${color.I}"/>` : ""}<g class="connection-detail" transform="translate(${b.x - b.rx},${b.y - b.ry})"><rect class="detail-shell" width="${b.rx * 2}" height="${b.ry * 2}" rx="8"/><foreignObject width="${b.rx * 2}" height="${b.ry * 2}">${relationContent()}</foreignObject></g>`,
    );
  }
  function renderCells() {
    const layer = d3.select("#cells-layer");
    const scroll = layer.select(".cell-grid").node()?.scrollTop || 0;
    if (!state.cellsFor) {
      layer.html("");
      return;
    }
    const id = state.cellsFor,
      b = cellBox(),
      n = nodeFor(id);
    layer.html(
      `<path class="detail-leader" d="M${n.x},${n.y} L${b.x},${b.y}"/><g transform="translate(${b.x - b.rx},${b.y - b.ry})"><rect class="detail-shell" width="290" height="404" rx="8"/><foreignObject width="290" height="404"><div xmlns="http://www.w3.org/1999/xhtml" class="cell-content"><button class="close-cells icon" data-close-cells title="Fold cell records" aria-label="Fold cell records">${icon("x")}</button><h2>${id} · ${D.groups[id].n} cells</h2><div class="cell-grid">${D.groups[id].cells.map((c) => `<button class="cell-tile" data-cell="${c.id}" aria-pressed="${sample(id) === c.id}"><span>${c.label} · ${c.modes.join(" + ")}</span><svg viewBox="0 0 125 48" aria-label="${c.label} conductances"><rect x="2" y="2" width="${120 * D.ti}" height="43" fill="#edf3ef"/>${c.profiles.map((v, j) => `<path d="${chartLine(v, 2, 45, 120, 40)}" fill="none" stroke="${color[j === 0 ? "E" : "I"]}" stroke-width="1.4"/>`).join("")}</svg></button>`).join("")}</div><button class="mean-button" data-mean="${id}">Group mean</button></div></foreignObject></g>`,
    );
    layer.select(".cell-grid").node().scrollTop = scroll;
  }
  function render() {
    renderNodes();
    renderEdges();
    renderEvidence();
    renderCells();
    $("back").disabled = history.length === 0;
    $("context").textContent = state.edge
      ? `${state.edge.source} → ${state.edge.target}`
      : state.cellsFor
        ? `${state.cellsFor} · cells`
        : state.focus || "";
    $("detail-legend").innerHTML =
      state.edge?.source === "Inspiratory"
        ? '<i class="line"></i>Identified <i class="line dash"></i>Alternatives'
        : "Width: full-fit area";
    $("selection-caption").textContent = state.edge
      ? "Connection detail · saved evidence"
      : state.expanded
        ? "Inspiratory populations · family outputs remain bundled"
        : "Grouped source patterns · reconstructed functional inputs";
    d3.select("#map-nodes").html(
      nodes
        .map(
          (n) =>
            `<ellipse cx="${n.x}" cy="${n.y}" rx="${n.rx}" ry="${n.ry}" fill="${n.id === state.focus ? "#277961" : "#b2c9bd"}"/>`,
        )
        .join(""),
    );
    updatePhase();
    updateMap();
  }
  function updateMap() {
    const t = transform();
    if (nodes.length) {
      const b = visibleBounds();
      d3.select("#minimap").attr(
        "viewBox",
        `${b[0] - 50} ${b[1] - 50} ${b[2] - b[0] + 100} ${b[3] - b[1] + 100}`,
      );
      d3.select(".map-ground")
        .attr("x", b[0] - 50)
        .attr("y", b[1] - 50)
        .attr("width", b[2] - b[0] + 100)
        .attr("height", b[3] - b[1] + 100);
    }
    d3.select("#map-window")
      .attr("x", -t.x / t.k)
      .attr("y", -t.y / t.k)
      .attr("width", width / t.k)
      .attr("height", height / t.k);
  }
  function updatePhase() {
    $("phase").value = phase;
    $("phase-readout").textContent = (phase / 100).toFixed(2);
    $("phase-name").textContent =
      phase / 100 < D.ti ? "Inspiration" : "Expiration";
    document.querySelectorAll("[data-cursor-width]").forEach((el) => {
      const x = +el.dataset.cursorX + (phase / 100) * +el.dataset.cursorWidth;
      el.setAttribute("x1", x);
      el.setAttribute("x2", x);
    });
    document.querySelectorAll("[data-phase-pop]").forEach((el) => {
      const j = D.names.indexOf(el.dataset.phasePop),
        v =
          j < 0 ? Math.max(...D.matrix[phase].slice(0, 3)) : D.matrix[phase][j];
      el.setAttribute("fill-opacity", 0.15 + 0.85 * v);
    });
  }
  function stop() {
    playing = false;
    cancelAnimationFrame(frame);
    $("play").innerHTML = icon("play");
    $("play").setAttribute("aria-label", "Play empirical phase replay");
  }
  function tick(time) {
    if (!playing) return;
    accumulated += Math.min(time - lastTime, 100) * 0.0125;
    lastTime = time;
    if (accumulated >= 1) {
      phase = (phase + Math.floor(accumulated)) % 100;
      accumulated %= 1;
      updatePhase();
    }
    frame = requestAnimationFrame(tick);
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
  function foldLevel() {
    checkpoint();
    if (state.cellsFor) state.cellsFor = null;
    else if (state.edge) state.edge = null;
    else if (state.open.length) {
      state.open.pop();
      state.focus =
        state.open.at(-1) || (state.expanded ? "Inspiratory" : null);
    } else if (state.expanded) {
      state.expanded = false;
      state.focus = null;
    } else {
      history.pop();
      svg.transition().duration(duration()).call(zoom.scaleBy, 0.8);
      return;
    }
    render();
    frameFocus();
  }
  function action(target) {
    const close = target.closest("[data-close-edge]");
    if (close) {
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
      const id = cell.dataset.cell;
      state.samples[state.cellsFor] = id;
      render();
      document
        .querySelector(`[data-cell="${id}"]`)
        .focus({ preventScroll: true });
      return;
    }
    const mean = target.closest("[data-mean]");
    if (mean) {
      state.samples[mean.dataset.mean] = "mean";
      render();
      return;
    }
    const cells = target.closest("[data-cells]");
    if (cells) {
      checkpoint();
      state.cellsFor = cells.dataset.cells;
      render();
      frameFocus();
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
      render();
      document
        .querySelector(`[data-sample="${id}"]`)
        .focus({ preventScroll: true });
      return;
    }
    if (!state.edge) return;
    const r = state.edge,
      key = `${r.target}|${r.sign}`;
    if (e.target.name === "subset") state.masks[key] = +e.target.value;
    else if (e.target.matches("[data-toggle]"))
      state.masks[key] =
        mask(r.target, r.sign) ^ (1 << +e.target.dataset.toggle);
    else return;
    const focus = e.target.matches("[data-toggle]")
      ? `[data-toggle="${e.target.dataset.toggle}"]`
      : `input[name="subset"][value="${e.target.value}"]`;
    render();
    document.querySelector(focus)?.focus({ preventScroll: true });
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
        renderEdges();
        updatePhase();
        frameFocus();
      }
    },
    true,
  );
  let scrubChart = null;
  function scrub(e) {
    if (!scrubChart) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
      scrubChart.getScreenCTM().inverse(),
    );
    const isFit = scrubChart.classList.contains("fit-chart");
    stop();
    phase = Math.max(
      0,
      Math.min(
        99,
        Math.round(((p.x - (isFit ? 8 : 22)) / (isFit ? 310 : 284)) * 100),
      ),
    );
    updatePhase();
  }
  $("atlas").addEventListener("pointerdown", (e) => {
    const chart = e.target.closest("[data-chart]");
    if (chart) {
      scrubChart = chart;
      chart.setPointerCapture(e.pointerId);
      scrub(e);
    }
  });
  $("atlas").addEventListener("pointermove", scrub);
  $("atlas").addEventListener("pointerup", () => (scrubChart = null));
  $("atlas").addEventListener("pointercancel", () => (scrubChart = null));
  $("find").addEventListener("change", (e) => {
    if (e.target.value) openNode(e.target.value);
    e.target.value = "";
  });
  $("back").addEventListener("click", back);
  $("home").addEventListener("click", home);
  $("fit").addEventListener("click", () => fitBounds(visibleBounds()));
  $("zoom-out").addEventListener("click", foldLevel);
  $("zoom-in").addEventListener("click", () => {
    if (!state.expanded && !state.focus) openNode("Inspiratory");
    else svg.transition().duration(duration()).call(zoom.scaleBy, 1.35);
  });
  $("minimap").addEventListener("click", () => fitBounds(visibleBounds()));
  $("minimap").addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fitBounds(visibleBounds());
    }
  });
  $("phase").addEventListener("input", (e) => {
    stop();
    phase = +e.target.value;
    updatePhase();
  });
  $("play").addEventListener("click", () => {
    if (playing) return stop();
    playing = true;
    lastTime = performance.now();
    accumulated = 0;
    $("play").innerHTML = icon("pause");
    $("play").setAttribute("aria-label", "Pause phase replay");
    frame = requestAnimationFrame(tick);
  });
  $("about").addEventListener("click", () => $("methods").showModal());
  $("close-methods").addEventListener("click", () => $("methods").close());
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
  $("download").addEventListener("click", () => {
    const copy = $("atlas").cloneNode(true);
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    copy.setAttribute("width", width);
    copy.setAttribute("height", height);
    copy.setAttribute("viewBox", `0 0 ${width} ${height}`);
    copy
      .querySelectorAll(".edge-hit,[data-action]")
      .forEach((el) => el.remove());
    const style = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "style",
    );
    style.textContent = document.querySelector("head style").textContent;
    copy.prepend(style);
    const desc = document.createElementNS("http://www.w3.org/2000/svg", "desc");
    desc.textContent =
      "Frozen 150-cell respiratory reconstruction. Grouped edges mean support for at least one receiving member. Red arrowheads: excitation; blue filled circles: inhibition. Coarse widths: mean full-fit area divided by total dynamic excitation plus inhibition. Expanded inspiratory inputs have uniform widths: solid individually identified, dashed alternatives. Early-I excitation retains pre-I alone OR ramp-I plus early-I together. The connection-detail rectangle is an evidence expansion, not a neural population. Phase replay is empirical, not dynamical.";
    copy.prepend(desc);
    const url = URL.createObjectURL(
      new Blob([new XMLSerializer().serializeToString(copy)], {
        type: "image/svg+xml",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "resp-net-circuit-atlas.svg";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Current graph downloaded");
  });
  $("methods-body").innerHTML =
    `<p><strong>${D.meta.checkpoint}</strong><br>150 cells; 168 recordings. This atlas displays the frozen empirical reconstruction, not a dynamical simulation.</p><h3>Graph levels</h3><p>The wide view groups inspiratory targets and source patterns. A grouped connection means support for at least one member, not necessarily every member. Width is mean full-fit conductance area relative to total dynamic excitation plus inhibition; grouped widths average all three inspiratory targets. Red arrowheads denote excitation and blue filled circles inhibition. Colored ports denote candidate transmitter modes, not separately identified recorded cell types.</p><p>Opening the inspiratory family resolves receiving populations while keeping its outgoing sources bundled. Opening an inspiratory connection reveals individually identified sources (solid) and retained alternatives (dashed), only for that target and conductance sign. Their widths are uniform, not source weights. Early-I excitation retains pre-I alone OR ramp-I plus early-I together. Additional sources remain possible.</p><h3>Profiles and fits</h3><p>Small activity traces are published Smith et al. (2007) templates, not firing recorded from this conductance cohort. Expanded nodes show reconstructed dynamic excitatory and inhibitory conductance. Both share the recording's normalization peak. Repeat recordings are averaged within mode, then within cell; groups give equal weight to cells. CC and VC denote current and voltage clamp.</p><p>All eight inspiratory subsets use saved restricted NNLS coefficients. Post-I and aug-E remain available in every fit. Browser switches select saved fits, not dynamical interventions or new optimizations. Cell RMSE is computed on each saved fit; group RMSE is the mean of those cell errors, not the error of a group-average curve. Full-fit area, fit error and statistical support are distinct quantities.</p><h3>Statistical evidence</h3><p>Input tests use fixed template-derived contrasts and cell-level one-sided t tests with joint coarse/fine multiple-comparison control at adjusted P &lt; 0.05. Distributional assumptions make calibration approximate. Evidence remains group-level even when an individual cell is selected. Failure to exclude a source combination does not establish equal fit quality or prove an anatomical connection. No baseline policy or threshold was changed.</p><h3>Phase replay</h3><p>Phase traverses the common saved grid. Shading marks inspiration (0 to ${D.ti.toFixed(4)}); source-port brightness follows activity templates. No conduction delays or network dynamics are generated.</p><h3>Provenance</h3><p>Cell labels are stable within-group display indices. Raw identifiers and archive paths are not distributed. Scenario: <code>${D.meta.scenario}</code>.</p><details><summary>Source checksums</summary>${Object.entries(
      D.meta.sourceHashes,
    )
      .map(([p, h]) => `<p><code>${esc(p)}<br>${h}</code></p>`)
      .join(
        "",
      )}</details><p>D3 7.9.0 (ISC) handles graph navigation and transitions. Lucide 0.468.0 icons (ISC). All dependencies and data are embedded; no network requests are needed.</p>`;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
  });
  function resize() {
    const r = $("workspace").getBoundingClientRect();
    width = r.width;
    height = r.height;
    const old = baseScale,
      b = rootBounds();
    baseScale = Math.max(
      0.12,
      Math.min(
        1.3,
        (width - 50) / (b[2] - b[0]),
        (height - 125) / (b[3] - b[1]),
      ),
    );
    render();
    if (old === 1 || (!state.expanded && !state.open.length && !state.edge))
      fitBounds(b, false, 1.3);
    else frameFocus();
  }
  render();
  new ResizeObserver(resize).observe($("workspace"));
  window.connectome = {
    data: D,
    getState: () => ({
      ...structuredClone(state),
      phase,
      playing,
      zoom: transform().k / baseScale,
    }),
    edges: () => edges.map((e) => ({ ...e })),
    getSeries: (
      target = state.edge?.target ||
        (D.names.includes(state.focus) ? state.focus : "post-I"),
      sign = state.edge?.sign || "E",
    ) => curve(target, sign),
  };
})();
