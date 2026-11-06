const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const C = require("./core.js");
const root = path.resolve(__dirname, "../..");
const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const D = JSON.parse(
  html.match(
    /<script id="dataset" type="application\/json">(.*?)<\/script>/s,
  )[1],
);
const read = (p) => JSON.parse(fs.readFileSync(path.join(root, p), "utf8"));
const original = read(
  "data/model_analyses/inspiratory_subset_contrasts/summary.json",
).fixed_fall50;
const cells = read(
  "data/model_analyses/inspiratory_subset_contrasts/cells.json",
).fixed_fall50;
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-12, `${a} != ${b}`);
const mean = (values) => values.reduce((a, b) => a + b, 0) / values.length;

test("cohort counts, cell identity and recording-level provenance", () => {
  assert.deepEqual(
    D.names.map((n) => D.groups[n].n),
    [17, 41, 8, 54, 30],
  );
  assert.equal(
    Object.values(D.groups).reduce((s, g) => s + g.nRecords, 0),
    168,
  );
  for (const target of D.names) {
    const raw = cells
      .filter((c) => c.phenotype === target)
      .sort((a, b) => (a.cell < b.cell ? -1 : a.cell > b.cell ? 1 : 0));
    D.groups[target].cells.forEach((c, i) => {
      assert.equal(c.id, `${target}-${String(i + 1).padStart(3, "0")}`);
      assert.deepEqual(c.profiles, raw[i].profiles);
      assert.deepEqual(c.coefs, raw[i].subset_coefficients);
      assert.deepEqual(c.rmse, raw[i].subset_rmse);
      assert.deepEqual(c.shares, raw[i].full_shares);
      assert.deepEqual(
        Object.keys(c).sort(),
        [
          "id",
          "label",
          "modes",
          "nRecords",
          "profiles",
          "coefs",
          "rmse",
          "shares",
        ].sort(),
      );
    });
  }
});

test("all 80 mean curves and saved errors match the frozen summary", () => {
  for (const p of original.panels)
    for (let mask = 0; mask < 8; mask++) {
      const s = C.series(D, p.target, p.sign, "mean", mask);
      s.fit.forEach((v, k) => near(v, p.mean_subset_predictions[mask][k]));
      assert.deepEqual(s.observed, p.mean_profile);
      const a = D.panels[`${p.target}|${p.sign}`].alternatives.find(
        (a) => a.retained_mask === mask,
      );
      near(s.rmse * 100, a.mean_rmse_joint_peak_percent);
      near(s.delta * 100, a.mean_added_rmse_pp);
    }
});

test("2400 cell fits use saved restricted coefficients, not masked full fits", () => {
  let refitDiffers = false,
    count = 0;
  for (const target of D.names)
    for (const cell of D.groups[target].cells)
      for (const sign of ["E", "I"])
        for (let mask = 0; mask < 8; mask++) {
          const s = C.series(D, target, sign, cell.id, mask);
          count++;
          assert.equal(s.fit.length, 100);
          assert.ok(s.fit.every((v) => Number.isFinite(v) && v >= 0));
          assert.ok(s.delta >= -1e-12);
          for (let j = 0; j < 3; j++)
            if (!(mask & (1 << j)))
              assert.ok(s.components[j].every((v) => v === 0));
          if (mask === 7) assert.deepEqual(s.fit, s.full);
          else {
            const si = sign === "E" ? 0 : 1;
            if (cell.coefs[mask][si][3] !== cell.coefs[7][si][3])
              refitDiffers = true;
          }
        }
  assert.equal(count, 2400);
  assert.ok(refitDiffers);
});

test("population error is mean cell error, not error of the mean profile", () => {
  let differs = false;
  for (const target of D.names)
    for (const sign of ["E", "I"]) {
      const s = C.series(D, target, sign, "mean", 7),
        si = sign === "E" ? 0 : 1;
      near(s.rmse, mean(D.groups[target].cells.map((c) => c.rmse[7][si])));
      const meanCurveRMSE = Math.sqrt(
        mean(s.fit.map((v, k) => (v - s.observed[k]) ** 2)),
      );
      if (Math.abs(meanCurveRMSE - s.rmse) > 0.001) differs = true;
    }
  assert.ok(differs);
});

test("joint support and exact alternatives are preserved", () => {
  assert.deepEqual(D.coarse, original.coarse_policy);
  assert.equal(D.coarse.filter((r) => r.supported).length, 20);
  for (const p of original.panels) {
    const e = D.panels[`${p.target}|${p.sign}`];
    assert.deepEqual(e.minima, p.minimal_unexcluded_masks);
    assert.deepEqual(e.individual, p.individually_required);
    assert.deepEqual(C.alternatives(D, p.target, p.sign), [
      7,
      ...e.minima.filter((m) => m !== 7),
    ]);
  }
  assert.deepEqual(C.alternatives(D, "early-I", "E"), [7, 1, 6]);
  assert.deepEqual(C.alternatives(D, "early-I", "I"), [7, 0]);
});

test("fine graph has five identified and eighteen alternative connections", () => {
  const edges = C.fineEdges(D);
  assert.equal(edges.length, 23);
  assert.equal(edges.filter((e) => e.style === "solid").length, 5);
  for (const e of edges)
    assert.equal(
      e.style === "solid",
      D.panels[`${e.target}|${e.sign}`].individual.includes(e.source),
    );
  assert.ok(!edges.some((e) => e.target === "early-I" && e.sign === "I"));
});

test("overview grouping preserves target-specific support and averaged width", () => {
  assert.equal(D.overview.edges.length, 15);
  for (const edge of D.overview.edges) {
    const targets =
      edge.target === "Inspiratory" ? D.names.slice(0, 3) : [edge.target];
    const rows = D.coarse.filter(
      (r) =>
        r.source === edge.source &&
        r.sign === edge.sign &&
        targets.includes(r.target),
    );
    assert.ok(rows.some((r) => r.supported));
    near(edge.target_average_share, mean(rows.map((r) => r.share_mean)));
    assert.deepEqual(
      edge.members.map((r) => r.target).sort(),
      rows
        .filter((r) => r.supported)
        .map((r) => r.target)
        .sort(),
    );
  }
});

test("post-I example preserves practical differences among retained fits", () => {
  const pre = C.series(D, "post-I", "E", "mean", 1).delta * 100;
  const ramp = C.series(D, "post-I", "E", "mean", 2).delta * 100;
  assert.ok(pre > 0.67 && pre < 0.68);
  assert.ok(ramp > 0.02 && ramp < 0.03);
});

test("invalid cell or subset selections fail explicitly", () => {
  assert.throws(() => C.series(D, "pre-I", "E", "missing", 7));
  for (const mask of [-1, 8, 1.5])
    assert.throws(() => C.series(D, "pre-I", "E", "mean", mask));
  assert.equal(C.label(6, D.names), "ramp-I + early-I");
  assert.equal(C.label(0, D.names), "No inspiratory source");
});

test("all eight switch combinations preserve frozen group-level decisions", () => {
  for (const target of D.names)
    for (const sign of ["E", "I"])
      for (let mask = 0; mask < 8; mask++) {
        const panel = D.panels[`${target}|${sign}`];
        assert.equal(
          C.fitStatus(D, target, sign, mask),
          mask === 7
            ? "full"
            : panel.minima.includes(mask)
              ? "minimal"
              : panel.allowed.includes(mask)
                ? "retained"
                : "excluded",
        );
      }
  assert.equal(C.fitStatus(D, "early-I", "E", 6), "minimal");
  assert.equal(C.fitStatus(D, "early-I", "E", 1), "minimal");
  assert.equal(C.fitStatus(D, "early-I", "E", 2), "excluded");
  assert.equal(C.fitStatus(D, "early-I", "E", 4), "excluded");
  for (const mask of [-1, 8, 1.5])
    assert.throws(() => C.fitStatus(D, "post-I", "E", mask));
});

test("standalone page and manifest match sources without remote dependencies", () => {
  assert.ok(!/<script[^>]+src=|<link[^>]+href="https?:/i.test(html));
  // D3 includes unused fetch helpers; the application never invokes them.
  const application = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
  assert.ok(
    !/\bfetch\s*\(|d3\.(json|csv|tsv|text|xml|html|image)\s*\(/.test(
      application,
    ),
  );
  assert.ok(!/<!--(?:STYLE|CORE|APP|DATA|ICONS|VENDOR)-->/i.test(html));
  const manifest = read("apps/connectome-explorer/manifest.json");
  const sha = (p) =>
    crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
  assert.equal(manifest.output_sha256, sha(path.join(__dirname, "index.html")));
  assert.equal(
    manifest.builder_sha256,
    sha(path.join(root, "scripts/build_connectome_explorer.py")),
  );
  for (const [p, hash] of Object.entries(manifest.source_sha256))
    assert.equal(hash, sha(path.join(root, p)));
  for (const [p, hash] of Object.entries(manifest.assets_sha256))
    assert.equal(hash, sha(path.join(__dirname, p)));
  assert.equal(manifest.analysis_run, false);
});

test("semantic expansion preserves coarse support and target-specific widths", () => {
  const collapsed = C.networkEdges(D, false);
  assert.equal(collapsed.length, 15);
  for (const e of collapsed) {
    const old = D.overview.edges.find(
      (r) =>
        r.source === e.source && r.target === e.target && r.sign === e.sign,
    );
    near(e.share, old.target_average_share);
    assert.deepEqual(
      e.members.map((r) => r.target).sort(),
      old.members.map((r) => r.target).sort(),
    );
  }
  const expanded = C.networkEdges(D, true);
  assert.equal(expanded.length, 20);
  for (const e of expanded) {
    assert.notEqual(e.target, "Inspiratory");
    assert.equal(e.members.length, 1);
    near(e.share, e.members[0].share_mean);
  }
});

test("only the focused inspiratory relation unfolds into exact fine alternatives", () => {
  for (const target of D.names)
    for (const sign of ["E", "I"]) {
      const base = C.networkEdges(D, true);
      const expanded = C.networkEdges(D, true, {
        source: "Inspiratory",
        target,
        sign,
      });
      const fine = expanded.filter((e) => e.fine);
      assert.deepEqual(
        fine.map(({ source, target, sign, style }) => ({
          source,
          target,
          sign,
          style,
        })),
        C.fineEdges(D).filter((e) => e.target === target && e.sign === sign),
      );
      assert.deepEqual(
        expanded.filter((e) => !e.fine),
        base.filter(
          (e) =>
            !(
              e.source === "Inspiratory" &&
              e.target === target &&
              e.sign === sign
            ),
        ),
      );
      assert.equal(new Set(expanded.map((e) => e.id)).size, expanded.length);
    }
});
