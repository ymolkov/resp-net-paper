async (page) => {
  const errors = [],
    onError = (e) => errors.push(e.message);
  page.on("pageerror", onError);
  const check = (v, m) => {
    if (!v) throw Error(m);
  };
  const state = () => page.evaluate(() => connectome.getState());
  const settle = () => page.waitForTimeout(460);
  const find = page.getByRole("combobox", { name: "Find a population" });
  const home = async () => {
    await page
      .getByRole("button", { name: "Whole circuit", exact: true })
      .click();
    await settle();
  };
  const open = async (name) => {
    await find.selectOption(name);
    await settle();
  };
  const edge = async (source, target, sign) => {
    const el = page.locator(`[data-edge="${source}|${target}|${sign}"]`);
    await el.focus();
    await page.keyboard.press("Enter");
    await settle();
  };
  await page.setViewportSize({ width: 1440, height: 1000 });
  await home();
  check(
    (await page.locator("[data-node]").count()) === 3,
    "three overview groups",
  );
  check(
    (await page.evaluate(() => connectome.edges().length)) === 15,
    "15 coarse grouped relations",
  );
  // Actual wheel gesture, then semantic folding on zoom-out.
  const family = await page.locator('[data-node="Inspiratory"]').boundingBox();
  await page.mouse.move(
    family.x + family.width / 2,
    family.y + family.height / 2,
  );
  await page.mouse.wheel(0, -360);
  await page.waitForFunction(() => connectome.getState().expanded);
  await settle();
  check(
    (await page.locator("[data-node]").count()) === 5,
    "wheel opens family",
  );
  await page.mouse.wheel(0, 1200);
  await page.waitForFunction(() => !connectome.getState().expanded);
  await home();
  await page.screenshot({ path: "output/playwright/atlas-overview.png" });

  await open("Inspiratory");
  check(
    (await page.evaluate(() => connectome.edges().length)) === 20,
    "expanded receiving groups preserve 20 relations",
  );
  const anchors = await page
    .locator("[data-node]")
    .evaluateAll((es) =>
      es.map((e) => [e.dataset.node, e.getAttribute("transform")]),
    );
  await open("post-I");
  await open("ramp-I");
  const anchors2 = await page
    .locator("[data-node]")
    .evaluateAll((es) =>
      es.map((e) => [e.dataset.node, e.getAttribute("transform")]),
    );
  check(
    JSON.stringify(anchors) === JSON.stringify(anchors2),
    "persistent anchors",
  );
  check(
    (await state()).open.includes("post-I") &&
      (await state()).open.includes("ramp-I"),
    "two populations remain open",
  );
  // Real stroke hit test for a curved connection.
  const curve = page.locator('[data-edge="Inspiratory|post-I|E"]');
  const point = await curve.evaluate((el) => {
    const p = el.getPointAtLength(el.getTotalLength() * 0.65);
    const q = new DOMPoint(p.x, p.y).matrixTransform(el.getScreenCTM());
    return { x: q.x, y: q.y };
  });
  await page.mouse.click(point.x, point.y);
  await settle();
  check(
    (await state()).edge?.target === "post-I" &&
      (await state()).edge?.sign === "E",
    "pointer opens correct relation",
  );
  check(
    (await page.evaluate(
      () => connectome.edges().filter((e) => e.fine).length,
    )) === 2,
    "post-I alternatives unfolded",
  );
  await page.screenshot({ path: "output/playwright/atlas-connection.png" });
  await page.getByRole("button", { name: "Fold connection detail" }).click();
  await settle();
  await edge("Inspiratory", "early-I", "E");
  await page
    .getByRole("radio", { name: "ramp-I + early-I", exact: true })
    .check();
  check(
    (await state()).masks["early-I|E"] === 6,
    "paired alternative retained",
  );
  await page
    .getByRole("checkbox", { name: "Include early-I source", exact: true })
    .uncheck();
  check(
    await page
      .locator(".relation-status")
      .evaluate((e) => e.classList.contains("excluded")),
    "single ramp-I excluded",
  );
  await page
    .getByRole("checkbox", { name: "Include early-I source", exact: true })
    .check();
  check(
    !(await page
      .locator(".relation-status")
      .evaluate((e) => e.classList.contains("excluded"))),
    "pair restores status",
  );
  await page.locator("[data-test-details] summary").click();
  await settle();
  check((await state()).testsOpen, "test details unfold");
  const overflow = await page
    .locator(".evidence-content")
    .evaluate((e) => e.scrollHeight > +e.parentElement.getAttribute("height"));
  check(!overflow, "expanded evidence stays in its graph object");
  await page.screenshot({ path: "output/playwright/atlas-paired.png" });

  // Every supported inspiratory-family relation reaches all eight saved fits.
  const relations = await page.evaluate(() =>
    connectome.data.coarse
      .filter((e) => e.source === "Inspiratory" && e.supported)
      .map((e) => [e.target, e.sign]),
  );
  for (const [target, sign] of relations) {
    if ((await state()).edge) {
      await page
        .getByRole("button", { name: "Fold connection detail" })
        .click();
      await settle();
    }
    await edge("Inspiratory", target, sign);
    for (let mask = 0; mask < 8; mask++) {
      for (let j = 0; j < 3; j++)
        await page
          .locator(`[data-toggle="${j}"]`)
          .setChecked(Boolean(mask & (1 << j)));
      check(
        (await state()).masks[`${target}|${sign}`] === mask,
        "all saved subsets accessible",
      );
      check(
        await page.evaluate(() =>
          connectome.getSeries().fit.every(Number.isFinite),
        ),
        "finite refit",
      );
    }
  }
  await home();
  await open("post-I");
  await page.getByRole("button", { name: "Browse post-I cells" }).click();
  await settle();
  check(
    (await page.locator("[data-cell]").count()) === 54,
    "complete cell gallery",
  );
  await page.locator('[data-cell="post-I-044"]').click();
  check((await state()).samples["post-I"] === "post-I-044", "cell selection");
  check(
    await page.locator(".cell-grid").evaluate((e) => e.scrollTop > 0),
    "gallery preserves scroll",
  );
  await page.getByRole("button", { name: "Group mean", exact: true }).click();
  check((await state()).samples["post-I"] === "mean", "return to mean");
  await page.screenshot({ path: "output/playwright/atlas-cells.png" });
  await page.getByRole("button", { name: "Fold cell records" }).click();
  await settle();
  await page.locator('[data-sample="post-I"]').selectOption("post-I-003");
  const before = (await state()).phase;
  await page
    .locator('[data-chart="post-I|E"]')
    .click({ position: { x: 90, y: 30 } });
  check((await state()).phase !== before, "chart phase scrub");
  await page
    .getByRole("button", { name: "Play empirical phase replay" })
    .click();
  const p = (await state()).phase;
  await page.waitForFunction((p) => connectome.getState().phase !== p, p);
  await page.getByRole("button", { name: "Pause phase replay" }).click();
  await page.getByRole("slider", { name: "Respiratory phase" }).fill("77");
  check((await state()).phase === 77, "phase slider");

  await page.getByRole("button", { name: "Evidence and methods" }).click();
  check(await page.getByRole("dialog").isVisible(), "methods");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Back one expansion" }).click();
  await settle();
  await home();
  await open("Inspiratory");
  await open("pre-I");
  await page.getByRole("button", { name: "Zoom out and fold detail" }).click();
  await settle();
  check(
    (await state()).open.length === 0 && (await state()).expanded,
    "fold details first",
  );
  await page.getByRole("button", { name: "Zoom out and fold detail" }).click();
  await settle();
  check(!(await state()).expanded, "fold family next");
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await settle();
  check((await state()).expanded, "zoom button unfolds");
  const t = await page.locator("#world").getAttribute("transform");
  await page.locator("#atlas").focus();
  await page.keyboard.press("ArrowLeft");
  check(
    (await page.locator("#world").getAttribute("transform")) !== t,
    "keyboard pan",
  );
  await page.getByRole("button", { name: "Fit expanded graph" }).click();
  await settle();
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download current graph" }).click();
  const download = await pending;
  await download.saveAs("output/playwright/atlas-export.svg");
  check(!(await download.failure()), "SVG export");

  for (const width of [320, 390, 800, 1440]) {
    await page.setViewportSize({ width, height: width < 700 ? 844 : 1000 });
    await home();
    check(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `no horizontal overflow ${width}`,
    );
    if (width === 390)
      await page.screenshot({
        path: "output/playwright/atlas-overview-mobile.png",
      });
    await open("Inspiratory");
    await edge("Inspiratory", "early-I", "E");
    await page
      .getByRole("radio", { name: "ramp-I + early-I", exact: true })
      .check();
    await settle();
    const box = await page.locator(".connection-detail").boundingBox();
    check(
      box.x >= 0 && box.x + box.width <= width + 1,
      `focused detail framed ${width}`,
    );
    check(
      await page
        .locator(".evidence-content")
        .evaluate(
          (e) => e.scrollHeight <= +e.parentElement.getAttribute("height"),
        ),
      `detail text fits ${width}`,
    );
    if (width === 390)
      await page.screenshot({
        path: "output/playwright/atlas-detail-mobile.png",
      });
    await page.locator("[data-test-details] summary").click();
    await settle();
    const expanded = await page.locator(".connection-detail").boundingBox();
    const workspace = await page.locator("#workspace").boundingBox();
    check(
      expanded.y >= workspace.y &&
        expanded.y + expanded.height <= workspace.y + workspace.height,
      `expanded tests stay vertically framed ${width}`,
    );
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await home();
  await open("post-I");
  check((await state()).open.includes("post-I"), "reduced motion");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.getByRole("button", { name: "Full screen", exact: true }).click();
  await page.waitForFunction(() => document.fullscreenElement);
  await page.getByRole("button", { name: "Exit full screen", exact: true }).click();
  await page.waitForFunction(() => !document.fullscreenElement);
  // The bundled D3 fetch helpers must never be invoked by the application.
  const requests = [];
  const block = (route) => {
    requests.push(route.request().url());
    route.abort();
  };
  const html = await (await page.request.get(page.url())).text();
  const offline = await page.context().newPage();
  offline.on("pageerror", onError);
  await offline.route("**/*", block);
  try {
    await offline.setContent(html, { waitUntil: "load" });
    await offline
      .getByRole("combobox", { name: "Find a population" })
      .selectOption("Inspiratory");
    await offline.waitForFunction(() => connectome.getState().expanded);
    check(
      (await offline.evaluate(() => connectome.edges().length)) === 20,
      "offline graph",
    );
    check(requests.length === 0, "zero runtime requests");
  } finally {
    offline.off("pageerror", onError);
    await offline.close();
    page.off("pageerror", onError);
  }
  check(errors.length === 0, errors.join("\n"));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await home();
  return `PASS: semantic wheel expansion/folding; fixed anchors and multiple open nodes; connection pointer/keyboard focus; ${relations.length * 8} source combinations; paired-source rule; evidence sizing; cell browsing; phase playback/scrub; history; keyboard pan; SVG; 320/390/800/1440 layouts; offline with zero requests; no JS errors.`;
}
