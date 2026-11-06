# Respiratory circuit atlas

This is the interactive companion to the empirical circuit analysis in
`resp-net-paper`. Open `index.html` directly in a browser, or serve it with an
ordinary static web server. Data, styles, icons, libraries, and their notices
are embedded; no account, backend, or network connection is required.

The [reproduction guide](../../docs/reproduction.md) describes the released
analysis, files, and manuscript workflow.

## Explore the circuit

- Open the inspiratory group to reveal pre-I, ramp-I, and early-I receiving
  populations. Their outgoing sources remain grouped by discharge timing.
- Open a population to see its excitatory and inhibitory conductance profiles.
  The grid button opens individual cells; selecting a cell changes the curves
  while statistical evidence remains at the population level.
- Open a connection to inspect its evidence and saved restricted fits. Source
  switches select among all eight inspiratory subsets, including excluded
  combinations. Post-I and aug-E templates remain available in these fits.
- Pan and zoom, use keyboard focus and Enter/Space, or use the population
  selector to explore. Back restores the previous view; Whole circuit resets
  it. The download button exports the current graph as SVG.
- Replay and scrubbing move through the saved respiratory phase. Replay is
  empirical playback, not a dynamical simulation.

## Scientific scope

The atlas preserves the frozen `fixed_fall50` analysis: 150 cells and 168
recordings, with 20 supported target-specific grouped inputs. The initial
overview combines these into 15 connections. The five source activity
templates come from Smith et al. (2007), independently of the conductance
cohort. The browser does not estimate coefficients or run statistical tests.

A grouped connection indicates support in at least one receiving member.
Coarse widths show mean fitted conductance area divided by total dynamic
excitation plus inhibition. Widths for grouped inspiratory targets average all
three target populations, including unsupported contributions. Fine
inspiratory connections have uniform widths: solid means individually
identified; dashed means an unresolved alternative. Width is neither synaptic
weight nor significance.

Early-I excitation retains **pre-I alone or ramp-I and early-I together**.
These are alternatives, and additional sources remain possible. Selecting a
restricted fit changes the displayed curves, not the saved support decisions.
Fits, test evidence, and anatomical connectivity are distinct interpretations.

Both conductances share each recording's normalization peak. Repeated records
are averaged within clamp mode and then within cell; population means weight
cells equally. Group RMSE is the mean of individual-cell RMSEs, not the error
of the mean waveform. Cell labels are display indices; original archive
identifiers are not embedded in the HTML. The methods panel and reproduction
guide describe the assumptions and approximate statistical calibration.

## Build and test

Run from the repository root using Python 3.12 and Node.js 22 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install numpy==2.4.2
.venv/bin/python scripts/build_connectome_explorer.py
node --test apps/connectome-explorer/test-core.cjs
```

NumPy is the only Python dependency of this builder. Node tests use built-in
modules; there is no npm installation or JavaScript bundling step. The builder
checks the frozen inputs before and after export and verifies all 80 mean
subset predictions. Thirteen Node tests cover the 2,400 saved cell fits,
alternatives, graph transformations, offline packaging, and source hashes.
`manifest.json` records data, source, icon, license, builder, and HTML hashes.

The optional `smoke-browser.js` is a Playwright browser-test function. It
exercises graph navigation, source subsets, cell selection, phase replay,
SVG export, responsive layouts, and offline initialization. It is not run by
the Node unit-test command and requires a separate browser automation setup.

## Serve or publish

For local viewing over HTTP:

```sh
python3 -m http.server 8768 --bind 127.0.0.1 --directory apps/connectome-explorer
```

Open `http://127.0.0.1:8768/`. Any static host can serve the generated
`index.html`; retain the vendor license files alongside a distributed copy.

The optional [GitHub Pages workflow template](../../docs/pages-workflow.yml.example)
is inactive during private preparation. For public release, copy it to
`.github/workflows/pages.yml` with workflow-authorized access. Configure this
repository's Pages publishing source as **GitHub Actions**, then run **Publish
circuit atlas** from the Actions tab. It builds and tests the atlas before
publishing only the generated page and license notices. Pushing commits
does not trigger deployment. No hosting identity or deployment credentials
are bundled in this release.

## Files and licensing

`index.template.html`, `style.css`, `app.js`, and `core.js` are interface source.
`scripts/build_connectome_explorer.py` exports saved results; `index.html` is
the generated standalone application. Rebuild it after changing any source.

Project code is released under MIT; project data and documentation are under
CC BY 4.0, as described in the repository's top-level notices. Third-party
material retains its own terms: D3 7.9.0 uses its supplied ISC notice, and
Lucide 0.468.0 icons use their supplied ISC notice, including Feather-derived
credits. The full notices remain in `vendor/d3/LICENSE` and
`vendor/lucide/LICENSE` and are embedded alongside the project's MIT notice in
the standalone HTML. Derived Smith
et al. activity templates retain their source attribution and are covered by
the release's third-party/data notices rather than a blanket claim of
ownership. Refer to the reproduction guide and manuscript bibliography for
scientific citations.
