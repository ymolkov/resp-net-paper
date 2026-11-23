# Respiratory circuit inference: data, code, and interactive atlas

This repository accompanies **From cellular synaptic input profiles to
population-level respiratory circuitry**, by Yaroslav I. Molkov, Ilya A.
Rybak, and Jeffrey C. Smith.

This public repository contains the **168 archived recordings from 150 cells** used in the paper,
the accepted preprocessing settings, conductance reconstruction and source
inference code, frozen results, figure code, and the companion interactive site.
The primary analysis is `fixed_fall50`; the two accompanying timing scenarios
are sensitivity checks of the same recordings.

## Start here

Open the [paper companion](https://ymolkov.github.io/resp-net-paper/) for the
study overview, or go directly to the [interactive circuit atlas](https://ymolkov.github.io/resp-net-paper/explorer/)
to inspect connections and individual cell profiles.

- Open [the interactive atlas](apps/connectome-explorer/index.html) in a browser
  after downloading or cloning the repository. It also works offline.
- Read [reproduction instructions](docs/reproduction.md) to verify files, rebuild
  the figures/site, or recompute the analysis.
- Read [data and file descriptions](docs/data_dictionary.md) for recording
  channels, identifiers, units, accepted epochs, and result formats.
- Read [the method reference](docs/methods.md) for preprocessing, assumptions,
  statistical tests, and interpretive limits.
- Download [Supporting Data S1](paper/supporting/Supporting_Data_S1.xlsx) for
  fitted contributions, omission decisions and underlying contrasts.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
make verify
make site-test                    # requires Node.js 22 or newer
```

`make verify` checks the release inventory and saved scientific results. Full
recomputation is a separate command and writes to `output/reproduced/`.

## Scope

The recordings are downsampled archival inputs used by this analysis, rather
than a claim to provide the original acquisition-rate files. Native byte
content and stable recording identifiers are preserved. There are 150
current-clamp and 18 voltage-clamp records. Repeated recordings share a cell
identifier and are averaged within mode and then across modes for inference.

The repository includes the five digitized source activity patterns, the
post-inspiratory alignment diagnostic, all omission-test tables, and the
cell-removal and timing checks discussed in the paper. The atlas displays
saved empirical fits; its phase replay is not a dynamical simulation.

Excluded recordings, unrelated experiments, exploratory model fits, internal
correspondence, and the working repository's Git history are outside this
release. Numerical results are tied to the frozen analysis by file checksums
and recomputation comparisons. The paper's manuscript draft is maintained
separately.

## Citation and reuse

Cite the version used in the preprint: Molkov YI, Rybak IA, Smith JC (2026).
*Resp-net: data and code for population-level respiratory circuit inference*,
version `preprint-v1`. Zenodo. [doi:10.5281/zenodo.24477107](https://doi.org/10.5281/zenodo.24477107).
The DOI identifies the archived files; the [current repository](https://github.com/ymolkov/resp-net-paper)
contains subsequent updates. See [CITATION.cff](CITATION.cff).
The earlier conductance method is described in
[Molkov et al. (2025)](https://doi.org/10.7554/eLife.101959.4); the source activity
patterns are from [Smith et al. (2007)](https://doi.org/10.1152/jn.00985.2007).

Original code is available under [MIT](LICENSE), and the recordings and original
scientific documentation under [CC BY 4.0](LICENSE-DATA.md). Third-party material
retains its own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

