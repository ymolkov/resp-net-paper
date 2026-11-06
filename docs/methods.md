# Method and implementation reference

## Sample selection

The analyzed sample is 168 recordings from 150 neurons in arterially perfused
in situ rat brainstem-spinal cord preparations. Recordings required stable
intracellular measurements, variation in electrical command, and identifiable
inspiratory onset and offset. The longest eligible contiguous interval has
respiratory-period coefficient of variation no greater than 15%. At least
two cycles and nonzero command range must contribute to every phase bin.
Stable command windows, where annotated, retain at least two command states.
Selection preceded source fitting. This differs from the earlier conductance
study's stated period variation below 10% and three current levels maintained
for five cycles each.

The review started with 194 candidate in situ recordings. Measurement and epoch
review retained 180; four failed the positive-reference conductance condition,
and eight successful reconstructions had onset-only coordinates. The release
contains only the remaining 168 two-part-aligned recordings. The counts describe
recordings; shared cell identities prevent deriving cell counts by subtraction.
The exact cell-level overlap with the earlier publication is not established.

## Filtering and respiratory phase

Median filtering is applied within acquisition domains. Electrical channels use
a 21-sample kernel except for `int4/120419-Pre-I`, which uses 41 samples; the
respiratory reference uses 21 samples. The half-kernel at each endpoint remains
unfiltered, following the accepted implementation. The original recording byte
scope, channel order, filter settings, and sample-mask hash are preserved.

Relative onset and offset use the 20% rising and 50% falling crossings. Within
each detector container the baseline is the fifth percentile and the peak
defines amplitude. Crossings are linearly interpolated; missing crossings and
acquisition boundaries remain gaps. Inspiration and expiration are mapped
separately to a common cycle with offset at `0.2406187667`, and samples enter
bins through `floor(100*phase)`. The evaluation grid is `k/100`, k=0,…,99.
Complete cycles range from 2 to 147 per recording; partial cycles can supply
individual bins. Cycles and samples are not independent cell replicates.

## Conductance reconstruction

Within each phase bin, current-clamp reconstruction regresses voltage on current
and inverts the fitted line. Voltage-clamp reconstruction regresses current on
voltage directly. Both give `I = G V + C`. Full-precision G and C feed the
reversal geometry. Six-significant-digit coefficients, where present, are
retained numerical diagnostics rather than the primary calculation.

An upper supporting line of the phasewise (G,C) points minimizes its summed
vertical gap. Its slope is minus the estimated inhibitory reversal. Under the
separation assumption this boundary corresponds to minimum excitation. The
inhibitory reversal is bounded to −110…−60 mV and the excitatory reversal is
fixed at −20 mV. The intercept and decomposition are recomputed after bounding;
58 of 168 records reach a bound.

Before minimum subtraction:

```text
GE = (-C - EI*G) / (EE - EI)
GI = ( C + EE*G) / (EE - EI)
```

Each component's cycle minimum is subtracted, residual negatives are clipped
to zero, and both dynamic components share their larger peak as normalization.
The inferred reference conductance must be positive. Tonic leak and synaptic
components are not separated. Common positive current scaling cancels from
normalization; voltage scales and offsets remain consequential.

The [reconstruction illustration](../paper/figures/conductance_reconstruction_example.pdf)
reproduces the earlier eLife example with its original settings and nS units;
see [attribution](../THIRD_PARTY_NOTICES.md). It is not a new expanded-cohort
measurement.

## Source activity and post-I alignment

The five source traces come from the pontine-medullary condition of Smith et al.
(2007), Figure 4. Their published signals were rectified, integrated with a
50-ms time constant, and cycle-averaged. They are fixed representative waveforms
from separate experiments, not a sample of presynaptic activity from these cells.
Each template is minimum-subtracted and peak-normalized, and its timing is shared
between the candidate excitatory and inhibitory source of that discharge pattern.

The post-I rising half-amplitude point is mapped to the published inspiratory
offset guide. The saved half-rise is 0.38703125 and the guide is 0.3375, an advance
of 0.04953125 cycles (7.925 native pixels). A piecewise-linear transformation
preserves integer cycle endpoints and extracted amplitudes. Baseline is the
median over figure phase 0.10–0.25; peak is measured over 0.30–0.55. The original
trace, 40%/60% anchors, and corrected template remain available.

The [before/after plot](../paper/figures/expanded_template_alignment.pdf) shows
the vertical inspiratory-offset guide in the original figure coordinate, before
the common nerve-based alignment. This adjustment assumes displacement in the
published display; raw Smith recordings did not verify it. Its anchor was
measured independently of conductance-fit error. The `nerve_fall40` and
`nerve_fall60` scenarios are separate local timing checks and do not validate
that display-displacement assumption.

## Fits, contrasts, and source alternatives

Each conductance profile is fitted as a nonnegative sum of the five templates.
Repeated recordings are averaged within clamp mode and then across modes,
giving cells equal weight. Phase bins within a cell may be correlated.

To test omission of a template, approximate it by nonnegative least squares
using the retained columns. For residual r and omitted column a, normalize the
contrast as `w = r/(rᵀa)`. Projection gives `wᵀa = 1` and nonpositive products
with retained columns. Thus the expected cell score `wᵀy` is nonpositive under
the omission hypothesis. A positive mean is tested with a one-sided t statistic
using across-cell standard error. Contrast weights depend only on templates.
A relative residual norm no greater than `1e-10` is treated as redundant, with
zero weights and P=1; numerical projection identities are checked in the code.

For inspiratory omissions, local tests use Bonferroni across the omitted
templates, then closed testing across all seven nonempty subsets. The final
procedure corrects across 10 inspiratory families and 20 single-template
expiratory tests: 30 branches and 90 omission hypotheses, at alpha=0.05.
Use final `p_joint` values. No fitted-magnitude cutoff is applied.

A retained inspiratory set is consistent with the rejections only if it
intersects every rejected omitted set. Displayed alternatives are minimal by
inclusion: no member can be removed while preserving that condition. Larger
sets remain possible; both unresolved sources may contribute. Similar fits do
not prove equivalent origins, anatomical connections, or presynaptic identity.

Exact t significance requires independent Gaussian cell scores with common
positive variance and a correctly specified fixed-template mean model. Skewed
scores and the eight-cell early-I sample make calibration approximate. Missing
animal/preparation identities prevent estimating shared-preparation dependence.
Provisional classifications, reversal assumptions, minimum subtraction, and
template representation affect interpretation. The correction does not include
uncertainty from prior exploratory procedure selection or shared template and
reconstruction errors.

## Sensitivity checks

Both nerve-landmark scenarios retain the 70 inspiratory decisions. The
whole-cell-deletion check recomputes the same tests after each cell is removed,
without changing the primary sample. It tests sensitivity, not a new exclusion
rule. The release runner compares its detailed results to the frozen reference.
The paper's notable vulnerability is the pre-I/I inhibitory inspiratory-family
result; the exact changed decisions and cell identifiers are in the output.

Raw-cycle jackknife trials, alternative baseline policies, robust-estimator
pilots, and dynamical models are outside this paper-specific release. The
primary reconstruction, input hypotheses, and decisions remain those selected
for the paper.

