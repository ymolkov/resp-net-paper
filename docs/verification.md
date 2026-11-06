# Release preparation verification

The release was checked on 6 November 2026 with Python 3.12, NumPy 2.4.2,
SciPy 1.17.1, Matplotlib 3.10.8, pypdf 6.21.4, and Node.js 22.

- Exactly 168 archived recording files, from 150 working cell identities, match
  the manuscript list. Their total original size is 158,011,289 bytes.
- All original recording SHA-256 hashes match. The three numeric-prefix
  exceptions are explicit; every archived byte is retained.
- All 168 recordings were reconstructed from the exported files. Sample-mask
  hashes, full-precision I/V coefficients, reversals, normalization scales, and
  conductance profiles matched the frozen reference within the declared
  floating-point tolerances.
- The reconstructed profiles were passed into the inference runner. All three
  timing scenarios reproduced the frozen per-record and per-cell arrays,
  contrasts, P values, 90 omission decisions per scenario, and alternatives.
- Whole-cell deletion reproduced all 100 displayed reference summaries
  (90 unique omission hypotheses), including the 3,000 cell-deletion rows.
- Eight empirical/diagnostic figures and four tables were rebuilt from the
  packaged results. The prior-circuit figure and approved schematic Figure 1
  were also checked with the extracted drawing helpers and were byte-identical
  to canonical renders.
- The standalone atlas built without the manuscript or private working checkout.
  All 13 Node tests passed. Its numerical payload and interface were unchanged;
  the portable build adds complete software license notices.
- Local documentation links resolve. Exported text was checked for host paths,
  private service identifiers, and credential-like strings. The export uses a
  file/field allowlist and refuses to seal unexpected files.

`make verify` checks the exact packaged file inventory. `make reproduce` repeats
the numerical reconstruction and inference checks, writing separate outputs.
These checks establish computational reproduction, not validation of the
scientific assumptions described in [methods.md](methods.md). Browser regression
code is provided; a new cross-browser or physical-touch-device review was not
part of this release preparation because the interface is unchanged.

