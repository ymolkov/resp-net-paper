# Recordings and saved results

## Sample and identifiers

The release contains 168 recordings from 150 cells: 17 pre-I/I, 41 ramp-I,
8 early-I, 54 post-I, and 30 aug-E cells. There are 150 current-clamp (CC)
and 18 voltage-clamp (VC) recordings. The scientific sampling unit is the
cell, not the recording, respiratory cycle, or phase bin.

`data/manuscript_reporting/records.csv` is the authoritative recording list.
`source_path` joins all per-record tables and identifies a file below
`data/extended_dataset/raw_archive/`. `cell` joins repeated recordings of one
working cell identity. These are archival experimental identifiers, not animal
identifiers. The archive does not support reconstruction of each cell's animal
or preparation, so within-preparation dependence remains unquantified.

The intracellular recording archive was provided by Jeffrey C. Smith. Hidehiko
Koizumi, Anke Borgmann, Noriyuki Hama, and Ruli Zhang contributed recordings and
discussion of their interpretation. The preparation and recording context are
described in [Molkov et al. (2025)](https://doi.org/10.7554/eLife.101959.4).

## Recording bytes and channels

Files are whitespace- or comma-delimited numeric tables, sometimes with an
initial channel header. Preserve original filenames and bytes. The accepted
column indices are zero-based `[0, 1, 2, 3]`: time, current, voltage, and the
respiratory reference. Both CC and VC files retain this I/V column order.
In CC, current is the command and voltage the response; in VC, voltage is
the command and current the response. Additional archived channels are retained
in the file but are not used by this analysis.

The archived sampling interval is approximately 0.01 s in native time. These
are the downsampled inputs used by the analysis. Electrical scales are retained
as archived; the files do not establish uniform nA/mV calibration. No new
current or voltage scaling is applied. In particular, normalized conductance
profiles must not be relabeled as absolute nS values. Two records retain
provisional, unverified calibration annotations.

`data/extended_dataset/raw_archive_manifest.json` gives the full-file SHA-256,
size, and exact number of bytes passed to the parser. Three records contain
a 46-byte nonnumeric suffix outside the accepted numeric prefix:

- `int4/120420-Post-I`
- `int4/120424-Post-I-3`
- `int4/120426-Pre-I`

The suffix bytes remain in the released files; the reader uses the recorded
prefix boundary. Files are not cropped to accepted epochs because filtering,
respiratory event detection, and interval indices depend on full-file context.

## Accepted preprocessing inputs

| File | Contents |
|---|---|
| `data/extended_dataset/current_inventory/recordings.jsonl` | One selected record per line: final discharge-pattern assignment, clamp mode, working cell identity, accepted epoch, and manual command windows. |
| `data/extended_dataset/full_qc/run_config.json` | The 168 resolved configurations: source hashes, column mapping, detector threshold, filtering widths, phase landmarks, and scale annotations. |
| `data/extended_dataset/full_qc/records.json` | Numeric-prefix byte scopes for those same recordings. |
| `data/extended_dataset/conductance_reversal_bounded_ee_minus20/records.json` | Frozen phasewise regressions, chosen reversals, normalized conductance profiles, and reconstruction diagnostics for the selected sample. |

`chosen_epoch.start` and `.end` are native times; `start_index` and `stop_index`
select respiratory intervals, with the stop index exclusive. Manual command
windows are `[start_inclusive, end_exclusive)`; `command_state` is a categorical
label, not a calibrated current or voltage. The sample mask and contributing
cycle counts remain part of the reconstruction check.

There are 51 provisionally classified recordings from 46 cells. These are
retained with their explicit assignment status. Archive reference labels remain
as annotations; phrenic activity is the respiratory reference used in this
analysis.

## Templates and inference arrays

`data/model_analyses/postI_figure_registration/results.json` contains the
digitized activity traces, published phase guides, the post-I registration
assumption, and sampled template matrices. Source order is **pre-I/I, ramp-I,
early-I, post-I, aug-E**; the machine label `pre-I` means pre-I/I.

`data/extended_dataset/connectomics_source_support/timing_evidence.json`
contains the per-record respiratory landmarks used for the two timing checks.

The `coarse_connection_contrasts/` and `inspiratory_subset_contrasts/` directories
contain frozen `records.json`, `cells.json`, `contrasts.json`, and `summary.json`.
Their top-level keys are `fixed_fall50` (primary), `nerve_fall40`, and
`nerve_fall60` (timing checks). These directory names are retained for stable
code paths; they contain empirical analyses, not dynamical-model outputs.

- Profiles have two rows, excitation then inhibition, each with 100 phase bins.
- Template matrices have 100 rows and five columns.
- Coefficients have shape 2 by 5, with the same sign/source order.
- Inspiratory retained masks 0–7 encode pre-I/I (bit 1), ramp-I (bit 2), and
  early-I (bit 4); post-I and aug-E remain available in each retained fit.
- `p_joint` is the final adjusted P value. Earlier coarse-only `p_holm` fields
  are intermediate quantities and do not define the paper's selected circuit.
- `supported`, `individually_required`, and `minimal_unexcluded_masks` describe
  omission-test evidence; coefficient magnitude and fit error are descriptive.

Convenient CSVs in `data/manuscript_reporting/` contain recording metadata,
all 90 tests, 140 elementary contrast summaries, and contribution magnitudes.
The reader-facing workbook is `paper/supporting/Supporting_Data_S1.xlsx`.
To repeat the recording-day sensitivity check on the packaged scores, run
`python3 scripts/audit_recording_day_clustering.py`; recording dates are not animal IDs.
The full LaTeX tables and figure PDFs are under `paper/`; manuscript text is
not included. The cell-removal reference summary is under
`data/model_analyses/cell_influence_uncertainty/`.

