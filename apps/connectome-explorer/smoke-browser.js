async (page) => {
  const errors = [],
    onError = (e) => errors.push(e.message);
  page.on("pageerror", onError);
  const check = (v, m) => {
    if (!v) throw Error(m);
  };
  const state = () => page.evaluate(() => connectome.getState());
  const settle = () => page.waitForTimeout(460);
  const MEMBERS = ["pre-I", "ramp-I", "early-I"];
  const base = page.url().split("#")[0];
  const home = async () => {
    await page
      .getByRole("button", { name: "Whole circuit", exact: true })
      .click();
    await settle();
  };
  const open = async (name) => {
    if (
      !(await state()).expanded &&
      (name === "Inspiratory" || MEMBERS.includes(name))
    ) {
      await page
        .locator('[data-action="expand"][data-pop="Inspiratory"]')
        .click();
      await settle();
    }
    if (name !== "Inspiratory") {
      await page.locator(`[data-node="${name}"]`).focus();
      await page.keyboard.press("Enter");
      await settle();
    }
  };
  const edge = async (source, target, sign) => {
    const el = page.locator(`[data-edge="${source}|${target}|${sign}"]`);
    await el.focus();
    await page.keyboard.press("Enter");
    await settle();
  };
  const closeEvidence = async () => {
    await page.getByRole("button", { name: "Close evidence" }).click();
    await settle();
  };
  const cardFits = () =>
    page
      .locator(".evidence-content")
      .evaluate(
        (e) => e.scrollHeight <= +e.parentElement.getAttribute("height"),
      );
  await page.setViewportSize({ width: 1440, height: 1000 });

  // First visit: the guide is offered, not started.
  await page.evaluate(() => localStorage.clear());
  await page.goto(base);
  await settle();
  check((await state()).guide === "welcome", "guide offered on a first visit");
  await page.getByRole("button", { name: "Not now", exact: true }).click();
  await settle();
  check((await state()).guide === null, "offer can be declined");
  await page.reload();
  await settle();
  check((await state()).guide === null, "offer is not repeated");

  check(
    (await page.locator("[data-node]").count()) === 3,
    "three overview groups",
  );
  check(
    (await page.evaluate(() => connectome.edges().length)) === 15,
    "15 coarse grouped relations",
  );
  // Figure 4A arrangement: inspiratory above, post-I left, aug-E right.
  const at = async (id) =>
    page.locator(`[data-node="${id}"]`).evaluate((e) => {
      const r = e.getBoundingClientRect();
      return [r.x + r.width / 2, r.y + r.height / 2];
    });
  const [insp, post, aug] = [
    await at("Inspiratory"),
    await at("post-I"),
    await at("aug-E"),
  ];
  check(
    insp[1] < post[1] && insp[1] < aug[1] && post[0] < insp[0] && insp[0] < aug[0],
    "triangle arrangement",
  );
  // The wheel only zooms. It opens and closes nothing.
  const family = await page.locator('[data-node="Inspiratory"]').boundingBox();
  await page.mouse.move(
    family.x + family.width / 2,
    family.y + family.height / 2,
  );
  const scale = (await state()).zoom;
  await page.mouse.wheel(0, -360);
  await settle();
  check(
    (await state()).zoom > scale &&
      !(await state()).expanded &&
      (await page.locator("[data-node]").count()) === 3,
    "wheel zooms in without opening anything",
  );
  await page.mouse.wheel(0, 1200);
  await settle();
  check((await state()).zoom < scale, "wheel zooms out");
  for (const gone of ["#find", "#download", "#minimap", "#zoom-level", "#play"])
    check((await page.locator(gone).count()) === 0, `${gone} is retired`);
  await home();
  await page.screenshot({ path: "output/playwright/atlas-overview.png" });

  // Following one connection: the others fade and its name appears.
  const hovered = page.locator('[data-edge="post-I|aug-E|I"]');
  const mid = await hovered.evaluate((el) => {
    const p = el.getPointAtLength(el.getTotalLength() * 0.5);
    const q = new DOMPoint(p.x, p.y).matrixTransform(el.getScreenCTM());
    return { x: q.x, y: q.y };
  });
  await page.mouse.move(mid.x, mid.y);
  check(
    (await page.locator(".connection.hot").count()) === 1,
    "hover follows one connection",
  );
  check(await page.locator("#tip").isVisible(), "hover names the connection");
  await page.mouse.move(5, 5);

  await page.locator('[data-action="expand"][data-pop="Inspiratory"]').click();
  await settle();
  check(
    (await page.evaluate(() => connectome.edges().length)) === 20,
    "separated receiving populations preserve 20 relations",
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
  check(
    await page
      .locator(".node-content")
      .evaluateAll((es) =>
        es.every(
          (e) => e.scrollHeight <= +e.parentElement.getAttribute("height"),
        ),
      ),
    "panel content fits",
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
  check(await cardFits(), "evidence fits its card");
  await page.screenshot({ path: "output/playwright/atlas-connection.png" });
  await closeEvidence();
  await edge("Inspiratory", "early-I", "E");
  check(
    (await page.locator('input[type="radio"]').count()) === 0,
    "one control for the sources",
  );
  await page
    .getByRole("checkbox", { name: "Include pre-I source", exact: true })
    .uncheck();
  check(
    (await state()).masks["early-I|E"] === 6 &&
      !(await page
        .locator(".relation-status")
        .evaluate((e) => e.classList.contains("excluded"))),
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
  check(await cardFits(), "expanded evidence stays in its card");
  await page.screenshot({ path: "output/playwright/atlas-paired.png" });

  // Every supported inspiratory-group relation reaches all eight saved fits.
  const relations = await page.evaluate(() =>
    connectome.data.coarse
      .filter((e) => e.source === "Inspiratory" && e.supported)
      .map((e) => [e.target, e.sign]),
  );
  for (const [target, sign] of relations) {
    if ((await state()).edge) await closeEvidence();
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
  // Every supported relation has an evidence card that fits.
  const supported = await page.evaluate(() =>
    connectome.data.coarse
      .filter((e) => e.supported)
      .map((e) => [e.source, e.target, e.sign]),
  );
  for (const [source, target, sign] of supported) {
    await page.goto(`${base}#input=${source}:${target}:${sign}`);
    await page.reload();
    await settle();
    check((await state()).edge?.target === target, "link opens the relation");
    check(await cardFits(), `evidence fits: ${source} to ${target} ${sign}`);
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
  await page.locator('[data-compare-cell="post-I-043"]').click();
  check(
    (await state()).compare["post-I"] === "post-I-043",
    "second cell compared",
  );
  check(
    (await page.locator('[data-chart="post-I|E"] path').count()) === 3,
    "panel overlays the two cells and the mean",
  );
  await page.screenshot({ path: "output/playwright/atlas-cells.png" });
  await page
    .getByRole("button", { name: "Back to the mean", exact: true })
    .click();
  check(
    (await state()).samples["post-I"] === "mean" &&
      !(await state()).compare["post-I"],
    "return to mean",
  );
  await page.getByRole("button", { name: "Close cell records" }).click();
  await settle();
  await page.locator('[data-sample="post-I"]').selectOption("post-I-003");
  check((await state()).samples["post-I"] === "post-I-003", "cell from menu");

  // A link reproduces a view, and the guide can be linked directly.
  const link = await page.evaluate(() => connectome.link());
  await page.goto(`${base}#${link}`);
  await page.reload();
  await settle();
  check(
    (await state()).samples["post-I"] === "post-I-003" &&
      (await state()).open.includes("post-I"),
    "link restores the view",
  );
  await page.goto(`${base}#guide`);
  await page.reload();
  await settle();
  check((await state()).guide === 0, "guide link starts the guide");
  const press = async () => {
    await page.locator("#guide-next").click();
    await settle();
  };
  await press();
  check(
    (await page.locator(".guide-target").count()) === 1,
    "guide marks what to click",
  );
  await page.locator('[data-action="expand"][data-pop="Inspiratory"]').click();
  await settle();
  check(
    (await state()).expanded &&
      (await page.locator("#guide-next").textContent()) === "Next",
    "guide follows the reader's own click",
  );
  await press(); // step 3
  await press(); // show me: pre-I/I inputs
  check((await state()).open.includes("pre-I"), "guide opens a population");
  await press(); // step 4
  await press(); // show me: cells
  check((await state()).cellsFor === "pre-I", "guide opens the cells");
  await press(); // step 5
  await press(); // show me: compare
  check(
    !!(await state()).compare["pre-I"] &&
      (await state()).samples["pre-I"] !== "mean",
    "guide compares two cells",
  );
  await press(); // step 6
  await press(); // show me: evidence
  check((await state()).edge?.source === "aug-E", "guide opens the evidence");
  await page.screenshot({ path: "output/playwright/atlas-guide.png" });
  await press(); // step 7
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await settle();
  check((await state()).guide === 5, "guide steps back");
  await press();
  await press();
  await press(); // finish
  check((await state()).guide === null, "guide finishes");

  await page.getByRole("button", { name: "About this atlas" }).click();
  check(await page.getByRole("dialog").isVisible(), "about panel");
  check(
    !/fixed_fall50|baseline|checksum/i.test(
      await page.getByRole("dialog").innerText(),
    ),
    "about panel is written for readers",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Back one expansion" }).click();
  await settle();
  await home();
  await open("Inspiratory");
  await open("pre-I");
  const before = (await state()).zoom;
  await page.getByRole("button", { name: "Zoom out", exact: true }).click();
  await settle();
  check(
    (await state()).zoom < before &&
      (await state()).open.includes("pre-I") &&
      (await state()).expanded,
    "zoom out keeps everything open",
  );
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await settle();
  check(
    Math.abs((await state()).zoom - before) < 1e-6 &&
      (await state()).open.length === 1,
    "zoom in only zooms",
  );
  const t = await page.locator("#world").getAttribute("transform");
  await page.locator("#atlas").focus();
  await page.keyboard.press("ArrowLeft");
  check(
    (await page.locator("#world").getAttribute("transform")) !== t,
    "keyboard pan",
  );
  await page.getByRole("button", { name: "Fit everything in view" }).click();
  await settle();

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
      .getByRole("checkbox", { name: "Include pre-I source", exact: true })
      .uncheck();
    await settle();
    const box = await page.locator(".connection-detail").boundingBox();
    check(
      box.x >= 0 && box.x + box.width <= width + 1,
      `focused detail framed ${width}`,
    );
    check(await cardFits(), `detail text fits ${width}`);
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
  const html = await (await page.request.get(base)).text();
  const offline = await page.context().newPage();
  offline.on("pageerror", onError);
  await offline.route("**/*", block);
  try {
    await offline.setContent(html, { waitUntil: "load" });
    await offline
      .locator('[data-action="expand"][data-pop="Inspiratory"]')
      .click();
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
  return `PASS: first-visit guide offer and full guided route; Figure 4A arrangement; plain wheel and button zoom; fixed anchors and multiple open panels; hover path highlighting; connection pointer/keyboard focus; ${relations.length * 8} source combinations; paired-source rule; ${supported.length} evidence cards fitted; cell browsing and two-cell comparison; view links; history; keyboard pan; reader-facing about panel; 320/390/800/1440 layouts; offline with zero requests; no JS errors.`;
}
