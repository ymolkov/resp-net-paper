# Respiratory circuit atlas

This is the source of the interactive companion to the empirical circuit
analysis in `resp-net-paper`. The finished atlas is one file,
[`explorer/index.html`](../../explorer/index.html). Open it directly in a
browser, or serve it with an ordinary static web server. Data, styles, icons,
libraries, and their notices are embedded; no account, backend, or network
connection is required.

The [reproduction guide](../../docs/reproduction.md) describes the released
analysis, files, and manuscript workflow.

## Explore the circuit

- **Guide** in the header walks through the route from the circuit to the
  individual cell records and the evidence for a connection. It is offered
  once on a first visit. Adding `#guide` to the address starts it.
- The first view follows Figure 4A. **Show 3 populations** separates pre-I/I,
  ramp-I, and early-I as receiving populations. Their outputs stay grouped
  and are drawn from the dashed outline around them.
- **Show inputs** opens a population's mean excitatory and inhibitory
  conductance over one respiratory cycle. **Browse N cells** opens the
  individual cells; clicking one shows it against the mean, and **Compare**
  overlays a second cell. Statistical evidence remains at the population level.
- Click a connection to see its evidence: the test result in one sentence,
  the adjusted P value, the mean fitted share, and the saved fit. For an
  inspiratory input, three checkboxes select among all eight inspiratory
  subsets, including excluded combinations. Post-I and aug-E templates remain
  available in these fits. Plot colors follow Figure 3 of the paper.
- Hover a connection to follow it; the others fade. With a panel open, its
  inputs are bright and its outputs dimmed.
- Pan and zoom, or use keyboard focus and Enter/Space. Zooming opens and
  closes nothing. Back restores the previous view; Whole circuit resets it;
  Fit shows everything. The address records the current view, so a link
  reproduces it.
- The atlas shows saved empirical fits. It contains no simulation and no
  playback through the respiratory cycle.

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

Early-I excitation retains **pre-I/I alone or ramp-I and early-I together**.
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
exercises the guide, graph navigation, source subsets, cell selection and
comparison, view links, responsive layouts, and offline initialization. It is not run by
the Node unit-test command and requires a separate browser automation setup.

## Serve or publish

For local viewing over HTTP:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Run this from the repository root and open `http://127.0.0.1:8000/explorer/`.
Any static host can serve `explorer/index.html`; retain the vendor license
files alongside a distributed copy.

The [live atlas](https://ymolkov.github.io/resp-net-paper/explorer/) is that
same file, served by GitHub Pages from the `main` branch. Pushing to `main`
updates it. See the [study page and atlas
instructions](../../docs/reproduction.md#study-page-and-atlas). No hosting
credentials are bundled here.

## Files and licensing

`index.template.html`, `style.css`, `app.js`, and `core.js` are interface source.
`scripts/build_connectome_explorer.py` exports saved results;
`explorer/index.html` is the generated standalone application. Rebuild it
after changing any source.

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
