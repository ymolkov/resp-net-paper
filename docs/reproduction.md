# Reproduce the paper

## Environment

Use Python 3.12 and the versions in `requirements.txt`. Node.js 22 or newer is
needed only for the atlas tests. No Julia, MATLAB, C++ executable, database,
credentials, or original working checkout is required. Numerical reproduction
uses only files in this repository; installing dependencies needs internet
access once.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
make verify
make site-test
```

The checksum manifest covers the packaged inputs, software, documentation, and
generated deliverables. `release-origin.json` records copies and metadata
selections relative to the research source. Numerical helper definitions are
preserved from the original implementation; their origins and hashes are in
`scripts/scientific_source_map.json` and the reconstruction helper header.

## Full numerical reproduction

```sh
make reproduce
```

This first reconstructs every recording from its original archived bytes,
accepted configuration, epoch, and manual masks. It compares full-precision
regressions, sample masks, reversals, scales, and conductance profiles to the
frozen reference. It then passes those newly reconstructed profiles into source
inference and compares all three scenarios with the frozen results: per-record
fits, cell aggregation, contrasts, P values, all 90 omission decisions, and
retained source alternatives. Whole-cell deletion reproduces the sensitivity
check from the same fixed-template cell scores.

Results go to `output/reproduced/`; packaged inputs remain unchanged. Numerical
comparisons allow floating-point roundoff as specified in the scripts, while
support decisions, alternative sets, and identifiers must match exactly.

For a short reconstruction check or parallel reconstruction:

```sh
python scripts/reconstruct_recordings.py --limit 2
python scripts/reconstruct_recordings.py --workers 4
```

A limited run is explicitly marked incomplete in its verification sidecar and
cannot be passed off as the full inference input. To reproduce source inference
directly from packaged frozen conductances:

```sh
make inference
```

These commands hold the accepted epoch selection and classifications fixed;
they do not redo manual review, optimize thresholds, redigitize the published
templates, or select a new analysis policy. The code for the template mapping
uses the supplied digitized coordinates, with the alignment assumption explained
in [methods.md](methods.md).

## Figures and tables

```sh
make figures
```

The plotting code reads frozen numerical results without refitting. Outputs
include the paper's empirical figures, the schematic Figure 1, the alignment
and score diagnostics, all four tables, and descriptive CSVs. The eLife
illustration is supplied separately with attribution. Its optional regeneration
command downloads a checksum-pinned publisher file:

```sh
python scripts/prepare_conductance_reconstruction_figure.py
```

The illustration uses the earlier paper's example settings and physical units.
It must not be interpreted as another recording in the present cohort. Rebuilding
graphics on different library/font versions may change PDF bytes without changing
numerical results; investigate any checksum difference and use the numerical
reproduction checks to assess the science.

## Companion site

```sh
make site
make site-test
make serve
```

Open `http://127.0.0.1:8000/`, or open
`apps/connectome-explorer/index.html` directly. It contains the data and vendored
libraries and runs offline. No fitting or statistical testing takes place in
the browser. The build verifies all 80 group-mean retained-set predictions;
13 Node tests check the saved fits, alternatives, transformations, and packaging.

The site source, builder, browser regression script, and licenses are included.

### Paper companion and GitHub Pages

The companion opens with the inferred circuit from Figure 4A, cropped from the
packaged Figure 4 PDF without redrawing connections. The atlas is under
`explorer/`. The methods section includes Figure 1 and a plot of the mean of the two
normalized conductance profiles of the 17 pre-I/I cells in the primary analysis
(the same profiles used for Figure 2). No inference is run during site assembly.

The page builder needs Poppler's `pdftocairo` in addition to the Python
dependencies above. Run `make companion-test` to check the two publication
modes, packaged resources and project-relative links. For a private preview,
supply a local manuscript PDF:

```sh
python scripts/build_paper_companion.py ../preview/resp-net-paper --preview-pdf /path/to/manuscript.pdf
```

Open the resulting `index.html` directly. Do not upload this preview.
For a public companion **before the preprint is posted**, use a fresh output
directory and `--preprint-pending` instead of `--preview-pdf`. This includes
the overview, methods figures and explorer but omits the manuscript,
supporting workbook and private repository links. For the
public release, make the repository public, copy the inactive
[workflow template](pages-workflow.yml.example) to `.github/workflows/pages.yml`
using an account authorized to manage workflows, configure Pages to use GitHub
Actions, and run **Publish paper companion** from the Actions tab with the
paper's public bioRxiv or DOI URL. It builds a fresh artifact without a
manuscript PDF. Verify the home page, paper link, explorer and workbook while
signed out. Its trigger is manual; a normal push does not publish the site.
Preserve the vendor notices when redistributing the
standalone HTML. The existing hosted atlas is managed separately; this
repository does not contain its service credentials or deployment identity.

## Interpretation and citation

Verification means reproduction of the selected computation, not validation of
the fixed-template, reversal, independence, or sampling assumptions. See
[methods.md](methods.md) and [data_dictionary.md](data_dictionary.md).

The repository is private during preparation and will be made public with the
preprint, together with a versioned release. A permanent archive
DOI and the paper's final bibliographic citation should be added when assigned;
none is fabricated in `CITATION.cff`. Retain versioned checksums when archiving a
release so readers can identify exactly which inputs and outputs they used.

