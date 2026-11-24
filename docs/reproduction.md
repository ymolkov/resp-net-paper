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

## Study page and atlas

The repository holds the two published pages as finished files:

- `index.html` is the study homepage.
- `explorer/index.html` is the interactive circuit atlas.

Each is one self-contained file. The atlas embeds its data, code, icons and
licence notices. The homepage embeds its stylesheet and its three images.
Either opens directly from a download and works offline. No fitting or
statistical testing takes place in the browser.

GitHub Pages serves the `main` branch as it is, so the
[live homepage](https://ymolkov.github.io/resp-net-paper/) and
[live atlas](https://ymolkov.github.io/resp-net-paper/explorer/) are these two
files. Pushing to `main` updates the site. There is no separate site branch
and no build step on GitHub; the empty `.nojekyll` file tells Pages to serve
the files unchanged.

To regenerate the pages after changing their sources:

```sh
make site
make site-test
make serve
```

`make serve` shows the repository at `http://127.0.0.1:8000/`, as Pages does.

- **Atlas.** `scripts/build_connectome_explorer.py` assembles
  `explorer/index.html` from `apps/connectome-explorer/` and the saved fits.
  It verifies all 80 group-mean retained-set predictions. Thirteen Node tests
  check the saved fits, alternatives, transformations and packaging.
- **Homepage.** `scripts/build_paper_companion.py` writes `index.html` from
  `companion/index.html` and `companion/companion.css`. It crops the inferred
  circuit from the packaged Figure 4 PDF without redrawing connections,
  renders Figure 1, and plots the mean of the two normalized conductance
  profiles of the 17 pre-I/I cells in the primary analysis (the profiles used
  for Figure 2). It needs Poppler's `pdftocairo` in addition to the Python
  dependencies above. No inference is run.
- **Paper link.** The homepage links the paper only when
  `companion/paper_url.txt` holds its public bioRxiv or DOI address. Put the
  address on its own line there, run `make site`, and commit `index.html`.

`make site-test` checks that the committed homepage still matches its sources,
that it refers to no separate stylesheet, script or image file, and that every
link leads to a file in the repository.

## Interpretation and citation

Verification means reproduction of the selected computation, not validation of
the fixed-template, reversal, independence, or sampling assumptions. See
[methods.md](methods.md) and [data_dictionary.md](data_dictionary.md).

Use the [current repository](https://github.com/ymolkov/resp-net-paper) for
updates. To reproduce the preprint from the exact files used, use the
[`preprint-v1` archive](https://doi.org/10.5281/zenodo.24477107).

