/* Pure transformations of the frozen analysis. No optimizer or test is run. */
(function (root) {
  "use strict";
  const members = (mask) => [0, 1, 2].filter((i) => mask & (1 << i));
  const label = (mask, names) =>
    members(mask)
      .map((i) => names[i])
      .join(" + ") || "No inspiratory source";
  function fineEdges(data) {
    const edges = [];
    for (const target of data.names)
      for (const sign of ["E", "I"]) {
        const panel = data.panels[`${target}|${sign}`];
        const union = panel.minima.reduce((a, b) => a | b, 0);
        const common = panel.minima.reduce((a, b) => a & b, 7);
        for (const i of members(union))
          edges.push({
            source: data.names[i],
            target,
            sign,
            style: common & (1 << i) ? "solid" : "dashed",
          });
      }
    return edges;
  }
  function series(data, target, sign, cellId, mask) {
    const group = data.groups[target],
      si = sign === "E" ? 0 : 1;
    const cell =
      cellId === "mean" ? group.mean : group.cells.find((c) => c.id === cellId);
    if (!cell || !Number.isInteger(mask) || mask < 0 || mask > 7)
      throw new Error("Invalid waveform selection");
    const components = data.names.map((_, j) =>
      data.matrix.map((row) => row[j] * cell.coefs[mask][si][j]),
    );
    const fit = data.matrix.map((_, k) =>
      components.reduce((s, c) => s + c[k], 0),
    );
    const full = data.matrix.map((row) =>
      row.reduce((s, a, j) => s + a * cell.coefs[7][si][j], 0),
    );
    return {
      observed: cell.profiles[si],
      components,
      fit,
      full,
      rmse: cell.rmse[mask][si],
      delta: cell.rmse[mask][si] - cell.rmse[7][si],
      shares: cell.shares[si],
      cell,
    };
  }
  function alternatives(data, target, sign) {
    const panel = data.panels[`${target}|${sign}`];
    return [7, ...panel.minima.filter((m) => m !== 7)];
  }
  function fitStatus(data, target, sign, mask) {
    if (!Number.isInteger(mask) || mask < 0 || mask > 7)
      throw new Error("Invalid source combination");
    const panel = data.panels[`${target}|${sign}`];
    if (mask === 7) return "full";
    if (panel.minima.includes(mask)) return "minimal";
    return panel.allowed.includes(mask) ? "retained" : "excluded";
  }
  function networkEdges(data, expanded, relation = null) {
    const mappedTarget = (name) =>
      !expanded && data.names.slice(0, 3).includes(name) ? "Inspiratory" : name;
    const grouped = new Map();
    for (const row of data.coarse.filter((r) => r.supported)) {
      const target = mappedTarget(row.target);
      const id = `${row.source}|${target}|${row.sign}`;
      if (!grouped.has(id))
        grouped.set(id, {
          id,
          source: row.source,
          target,
          sign: row.sign,
          style: "solid",
          fine: false,
          members: [],
        });
      grouped.get(id).members.push(row);
    }
    const edges = [...grouped.values()];
    for (const edge of edges) {
      const rows = data.coarse.filter(
        (r) =>
          r.source === edge.source &&
          mappedTarget(r.target) === edge.target &&
          r.sign === edge.sign,
      );
      edge.share = rows.reduce((sum, r) => sum + r.share_mean, 0) / rows.length;
    }
    if (!expanded || !relation || relation.source !== "Inspiratory")
      return edges;
    const coarseId = `Inspiratory|${relation.target}|${relation.sign}`;
    return edges
      .filter((e) => e.id !== coarseId)
      .concat(
        fineEdges(data)
          .filter(
            (e) => e.target === relation.target && e.sign === relation.sign,
          )
          .map((e) => ({
            ...e,
            id: `${e.source}|${e.target}|${e.sign}`,
            fine: true,
            members: [],
          })),
      );
  }
  const api = {
    members,
    label,
    fineEdges,
    series,
    alternatives,
    fitStatus,
    networkEdges,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ConnectomeCore = api;
})(typeof window === "undefined" ? globalThis : window);
