"""Frozen raw-to-conductance functions for the paper-specific release.

Function and class definitions are copied verbatim from the canonical sources
identified below. Imports and module constants are assembled here to omit
historical CLIs, unrelated recording annotations, and local-path metadata.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import numpy as np
from scipy.ndimage import median_filter

# The upstream source location is omitted; this metadata does not enter the fit.
SLICE_SOURCE_REFERENCE = {
    'sha256': '1e61fbd54141a158103a5c58b95f3ee2f645d1cc79152db27335afa1063bc9ab',
    'lines': [479, 567],
    'section': 'Auto Ei Estimation via Global Geometric Pivoting',
}

# Canonical source: scripts/extended_dataset/full_preprocess.py
# SHA-256: 37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488

TARGET_TI = 0.2406187667

N_BINS = 100

@dataclass
class PreparedRecord:
    raw: np.ndarray
    time: np.ndarray
    electrical: np.ndarray
    reference_filtered: np.ndarray
    events: list[dict]
    intervals: list[dict]
    phase_onset: np.ndarray
    phase_two_part: np.ndarray
    cycle_index_onset: np.ndarray
    cycle_index_two_part: np.ndarray
    phase: np.ndarray
    cycle_index: np.ndarray
    control_means: np.ndarray
    response_means: np.ndarray
    control_means_onset: np.ndarray
    response_means_onset: np.ndarray
    control_means_two_part: np.ndarray
    response_means_two_part: np.ndarray
    phase_kind: str
    flags: list[str]
    detector_metadata: dict

    @property
    def times(self):
        return self.time

    @property
    def primary_intervals(self):
        return self.intervals

    @property
    def phase_coordinate(self):
        return self.phase_kind

def _median(values, width):
    """Exact historical med2 median and unfiltered endpoint convention."""
    values = np.asarray(values)
    if width == 0:
        return values.copy()
    result = median_filter(values, size=2*width+1, mode='nearest')
    result[:width], result[-width:] = values[:width], values[-width:]
    return result

def _crossing(time, signal, level, *, upward=False, last=False):
    mask = ((signal[:-1] < level) & (signal[1:] >= level) if upward
            else (signal[:-1] >= level) & (signal[1:] < level))
    indices = np.flatnonzero(mask)
    if not len(indices):
        return None, 0
    i = indices[-1] if last else indices[0]
    value = time[i] + (level-signal[i])/(signal[i+1]-signal[i])*(time[i+1]-time[i])
    return float(value), int(len(indices))

def _landmark_event(time, reference, index, stop, onset_fraction, offset_fraction,
                    segment_start):
    """Historical q-to-next-q container; no relative crossing is imputed."""
    period = float(time[stop]-time[index])
    values = reference[index:stop]
    baseline = float(np.quantile(values, .05))
    peak = index + int(np.argmax(values))
    amplitude = float(reference[peak]-baseline)
    names = ('rise10', 'rise20', 'rise30', 'fall40', 'fall50', 'fall60')
    result = {'original_period': period, 'baseline': baseline, 'amplitude': amplitude,
              'peak_time': float(time[peak]), 'all_landmarks_identified': False,
              **{name: None for name in names},
              **{name+'_crossings': 0 for name in names}, 'flags': []}
    if amplitude <= 0:
        result['flags'].append('nonpositive_reference_amplitude')
        return result
    pad = max(segment_start, int(np.searchsorted(time, time[index]-.2*period)))
    for fraction in (.1, onset_fraction, .3):
        name = f'rise{round(100*fraction)}'
        result[name], result[name+'_crossings'] = _crossing(
            time[pad:peak+1], reference[pad:peak+1],
            baseline+fraction*amplitude, upward=True, last=True)
    rise, count = result['rise20'], result['rise20_crossings']
    if rise is None:
        result['flags'].append('missing_relative_onset')
    elif count > 1:
        result['flags'].append('multiple_relative_onset_crossings_last_used')
    if offset_fraction is not None:
        for fraction in (.4, offset_fraction, .6):
            name = f'fall{round(100*fraction)}'
            result[name], result[name+'_crossings'] = _crossing(
                time[peak:stop], reference[peak:stop], baseline+fraction*amplitude)
        fall, count = result['fall50'], result['fall50_crossings']
        if fall is None:
            result['flags'].append('missing_relative_offset')
        elif count > 1:
            result['flags'].append('multiple_relative_offset_crossings_first_used')
    result['all_landmarks_identified'] = all(result[name] is not None for name in names)
    return result

def _phase_arrays(time, intervals, use_ie):
    phase = np.full(len(time), np.nan)
    index = np.full(len(time), -1, dtype=int)
    for j, row in enumerate(intervals):
        if not row['onsets_valid'] or (use_ie and not row['ie_valid']):
            continue
        start, end = row['start'], row['end']
        a, b = np.searchsorted(time, [start, end])
        relative = (time[a:b]-start)/(end-start)
        if use_ie:
            fraction = (row['fall50']-start)/(end-start)
            relative = np.where(relative < fraction, relative/fraction*TARGET_TI,
                                TARGET_TI+(relative-fraction)/(1-fraction)*(1-TARGET_TI))
        if (index[a:b] != -1).any():
            raise ValueError('Relative onset intervals overlap; input ordering was not preserved')
        phase[a:b], index[a:b] = relative, j
    return phase, index

def _cycle_means(electrical, phase, indices, n_intervals, mode):
    """Rows preserve every interval ID, including rows with no mapped samples."""
    result = np.full((n_intervals, N_BINS, 2), np.nan)
    valid = np.isfinite(phase) & (indices >= 0)
    if valid.any() and mode in ('CC', 'VC'):
        bins = np.floor(N_BINS*phase[valid]).astype(int)
        if (bins < 0).any() or (bins >= N_BINS).any():
            raise ValueError('Mapped phase outside [0,1)')
        keys = indices[valid]*N_BINS+bins
        count = np.bincount(keys, minlength=n_intervals*N_BINS)
        occupied, first = np.unique(keys, return_index=True)
        for col in range(2):
            values = electrical[valid, col]
            # Each cycle/bin gets its own anchor. A later constant-control
            # subepoch must stay exactly constant even when an earlier level
            # differs and retained groups have unequal sample counts.
            anchors = np.full(len(count), np.nan)
            anchors[occupied] = values[first]
            sums = np.bincount(keys, weights=values-anchors[keys], minlength=len(count))
            means = anchors+np.divide(sums, count, out=np.full(len(count), np.nan), where=count > 0)
            result[:, :, col] = means.reshape(n_intervals, N_BINS)
    control, response = (0, 1) if mode == 'CC' else (1, 0)
    return result[:, :, control], result[:, :, response]

def prepare_record(raw, config):
    """Prepare every supplied source sample, with one detector config throughout.

    Config keys: mode, reference_kind, q, electrical_half_width_samples,
    reference_half_width_samples, minimum_period (diagnostic only),
    relative_onset_fraction=.2, relative_offset_fraction=.5/null, ie_supported.
    Optional ``sample_gap_before_indices`` contains independently identified
    acquisition boundaries (indices of first samples after gaps). They split
    filtering/detection domains; no interpolation spans them. Without explicit
    boundaries, nonuniform timestamps are reported, not silently repaired.

    ``phase`` is one coherent coordinate: two_part for a supported phrenic I/E
    reference, onset_only otherwise. Both explicit maps are also returned.
    Missing PN offsets exclude only two_part samples, never primary periods.
    Every control/response matrix has exactly len(intervals) rows.
    """
    raw = np.asarray(raw, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != 4 or len(raw) < 2:
        raise ValueError('Expected at least two canonical time/I/V/reference rows')
    if not np.isfinite(raw).all() or (np.diff(raw[:, 0]) <= 0).any():
        raise ValueError('Nonfinite or nonincreasing raw input must be explicitly quarantined upstream')
    time = raw[:, 0]
    widths = [config.get('electrical_half_width_samples', 10),
              config.get('reference_half_width_samples', 10)]
    if any(not isinstance(w, (int, np.integer)) or w < 0 for w in widths):
        raise ValueError('Median half widths must be explicit nonnegative integer sample counts')
    width, ref_width = (int(w) for w in widths)
    onset_fraction = float(config.get('relative_onset_fraction', .2))
    if onset_fraction != .2:
        raise ValueError('This frozen relative-onset policy requires fraction .2')
    for key, expected in [('relative_onset_lookback_cycle_fraction', .2),
                          ('burst_baseline_quantile', .05), ('target_ie_phase', TARGET_TI)]:
        if key in config and float(config[key]) != expected:
            raise ValueError(f'This frozen landmark policy requires {key}={expected}')
    kind = config.get('reference_kind', 'unknown')
    ie_supported = bool(config.get('ie_supported', kind == 'phrenic')) and kind != 'vagus'
    offset_fraction = config.get('relative_offset_fraction', .5 if ie_supported else None)
    if not ie_supported:
        offset_fraction = None
    if offset_fraction is not None and float(offset_fraction) != .5:
        raise ValueError('This two-part phase policy requires offset fraction .5')
    ie_supported = ie_supported and offset_fraction is not None
    minimum_period = float(config.get('minimum_period', 0))
    if not np.isfinite(minimum_period) or minimum_period < 0:
        raise ValueError('minimum_period must be finite and nonnegative')
    boundaries = sorted(set(int(x) for x in config.get('sample_gap_before_indices', [])))
    if any(x <= 0 or x >= len(raw) for x in boundaries):
        raise ValueError('Acquisition boundaries must be interior source sample indices')
    edges = [0, *boundaries, len(raw)]
    electrical = np.empty((len(raw), 2))
    reference = np.empty(len(raw))
    for a, b in zip(edges[:-1], edges[1:]):
        electrical[a:b] = np.column_stack([_median(raw[a:b, col], width) for col in (1, 2)])
        reference[a:b] = _median(raw[a:b, 3], ref_width)
    flags = []
    if boundaries:
        flags.append('explicit_acquisition_boundaries_preserved')
    dt = np.diff(time)
    if not np.allclose(dt, np.median(dt), rtol=1e-6, atol=1e-10):
        flags.append('nonuniform_sampling_requires_continuity_review')
    if config.get('mode') not in ('CC', 'VC'):
        flags.append('unresolved_recording_mode')
    if not ie_supported:
        flags.append('onset_only_phase_no_respiratory_IE_offset_claim')
    q = config.get('q')
    if q is not None and not np.isfinite(float(q)):
        raise ValueError('Detector threshold must be finite or explicitly unavailable')
    events, segment_metadata = [], []
    for domain, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        rising = (np.flatnonzero((reference[a:b-1] < float(q)) &
                                (reference[a+1:b] >= float(q)))+a+1
                  if q is not None else np.array([], dtype=int))
        segment_metadata.append({'source_domain_id': domain, 'sample_start': a,
                                 'sample_end_exclusive': b, 'n_threshold_rises': len(rising),
                                 'prefix_before_first_threshold_end': float(time[rising[0]]) if len(rising) else None,
                                 'last_threshold_time': float(time[rising[-1]]) if len(rising) else None})
        for k, onset in enumerate(rising):
            event = {'event_index': len(events), 'original_cycle': len(events)+1,
                     'source_domain_id': domain, 'threshold_sample_index': int(onset),
                     'original_onset': float(time[onset]), 'original_period': None,
                     'baseline': None, 'amplitude': None, 'peak_time': None,
                     **{name: None for name in ('rise10', 'rise20', 'rise30', 'fall40', 'fall50', 'fall60')},
                     **{name+'_crossings': 0 for name in ('rise10', 'rise20', 'rise30', 'fall40', 'fall50', 'fall60')},
                     'all_landmarks_identified': False, 'flags': []}
            if k+1 < len(rising):
                event.update(_landmark_event(time, reference, int(onset), int(rising[k+1]),
                                             onset_fraction, offset_fraction, a))
                if minimum_period > 0 and event['original_period'] <= minimum_period:
                    event['flags'].append('historical_minimum_period_would_suppress_next_crossing')
            else:
                event['flags'].append('terminal_incomplete_threshold_container')
            if onset < a+max(width, ref_width) or onset >= b-max(width, ref_width):
                event['flags'].append('threshold_crossing_near_filter_boundary')
            events.append(event)
    if q is None:
        flags.append('unresolved_detector_threshold')
    elif not events:
        flags.append('no_fixed_threshold_rising_crossings')
    # If two measured onsets reverse order, neither can define trustworthy
    # adjacent intervals. Keep the measured values and invalidate the touching
    # slots instead of sorting times or permitting overlapping phase maps.
    order_conflicts = set()
    finite_events = [(j, event) for j, event in enumerate(events) if event['rise20'] is not None]
    for (j, first), (k, following) in zip(finite_events[:-1], finite_events[1:]):
        if (first['source_domain_id'] == following['source_domain_id']
                and following['rise20'] <= first['rise20']):
            order_conflicts.update((j, k))
    for j in order_conflicts:
        events[j]['flags'].append('relative_onset_order_conflict')
    intervals, run_id = [], 0
    for j, (first, following) in enumerate(zip(events[:-1], events[1:])):
        start, end, fall = first['rise20'], following['rise20'], first['fall50']
        reasons = []
        if first['source_domain_id'] != following['source_domain_id']:
            reasons.append('acquisition_boundary')
        if start is None:
            reasons.append('missing_start_relative_onset')
        if end is None:
            reasons.append('missing_end_relative_onset')
        if j in order_conflicts or j+1 in order_conflicts:
            reasons.append('relative_onset_order_conflict_at_endpoint')
        if start is not None and end is not None and end <= start:
            reasons.append('relative_onsets_not_strictly_ordered')
        valid = not reasons
        terminal_edge = ('terminal_incomplete_threshold_container' in following['flags']
                         and start is not None and end is None
                         and first['source_domain_id'] == following['source_domain_id']
                         and not (j in order_conflicts or j+1 in order_conflicts))
        ie_valid = valid and ie_supported and fall is not None and start < fall < end
        if valid and ie_supported and not ie_valid:
            ie_reason = 'missing_relative_offset' if fall is None else 'relative_offset_outside_onset_interval'
        else:
            ie_reason = None
        row = {'interval_index': j, 'original_cycle': j+1, 'next_original_cycle': j+2,
               'source_domain_id': first['source_domain_id'], 'domain_id': run_id,
               'start': start, 'end': end, 'fall50': fall,
               'period': float(end-start) if valid else None,
               'onsets_valid': valid, 'ie_valid': bool(ie_valid),
               'terminal_edge_slot': terminal_edge,
               'interior_onset_gap': not valid and not terminal_edge,
               'missing_status': reasons, 'ie_missing_status': ie_reason,
               'flags': list(dict.fromkeys(first['flags']+following['flags'])),
               'original_threshold_start': first['original_onset'],
               'original_threshold_end': following['original_onset'],
               'original_threshold_period': following['original_onset']-first['original_onset']}
        intervals.append(row)
        if not valid:
            run_id += 1
    if any(r['interior_onset_gap'] for r in intervals):
        flags.append('explicit_interior_onset_gap_slots')
    if any(r['terminal_edge_slot'] for r in intervals):
        flags.append('natural_terminal_container_unavailable')
    if any(r['onsets_valid'] and not r['ie_valid'] for r in intervals) and ie_supported:
        flags.append('some_onset_complete_intervals_lack_ordered_IE_offset')
    if any(set(e['flags'])-{'terminal_incomplete_threshold_container'} for e in events):
        flags.append('event_level_detector_flags_present')
    phase_onset, index_onset = _phase_arrays(time, intervals, False)
    phase_two, index_two = _phase_arrays(time, intervals, True)
    mode = config.get('mode')
    cx_onset, cy_onset = _cycle_means(electrical, phase_onset, index_onset, len(intervals), mode)
    cx_two, cy_two = _cycle_means(electrical, phase_two, index_two, len(intervals), mode)
    phase_kind = 'two_part' if ie_supported else 'onset_only'
    phase, index, cx, cy = ((phase_two, index_two, cx_two, cy_two) if ie_supported
                           else (phase_onset, index_onset, cx_onset, cy_onset))
    metadata = {'scope': 'Every supplied canonical source row; no historical -x/-l selection',
                'q': None if q is None else float(q), 'minimum_period_evidence': minimum_period,
                'minimum_period_policy': 'All crossings retained; spacing is a diagnostic, never a pruning rule',
                'electrical_half_width_samples': width, 'reference_half_width_samples': ref_width,
                'filter': 'median width 2*h+1, nearest extension, original h endpoint values retained',
                'onset_fraction': onset_fraction, 'offset_fraction': offset_fraction,
                'relative_landmark_container': 'fixed q rise to next fixed q rise; q05 baseline, maximum peak, 20%-period prepad',
                'relative_crossing_policy': 'last upward relative onset before peak; first downward relative offset after peak',
                'terminal_event_policy': 'Final q crossing has no complete next-q container; explicit unresolved onset',
                'reference_kind': kind, 'ie_supported': ie_supported, 'phase_kind': phase_kind,
                'target_ti': TARGET_TI if ie_supported else None, 'n_bins': N_BINS,
                'time_start': float(time[0]), 'time_end': float(time[-1]), 'n_source_rows': len(raw),
                'median_dt': float(np.median(dt)), 'maximum_dt': float(dt.max()),
                'source_domains': segment_metadata, 'n_events': len(events),
                'n_adjacent_pair_slots': len(intervals),
                'n_valid_onset_pairs': sum(r['onsets_valid'] for r in intervals),
                'n_valid_ie_pairs': sum(r['ie_valid'] for r in intervals),
                'n_terminal_edge_slots': sum(r['terminal_edge_slot'] for r in intervals),
                'n_interior_onset_gap_slots': sum(r['interior_onset_gap'] for r in intervals),
                'epoch_selection_performed': False, 'reconstruction_performed': False,
                'arithmetic_sources': ['scripts/audit_cycle_alignment.py:med2_filter,crossing,forward_phase',
                                       'scripts/pilot_common_phase_alignment.py:burst_landmarks,raw_phase_map']}
    return PreparedRecord(raw, time, electrical, reference, events, intervals,
                          phase_onset, phase_two, index_onset, index_two, phase, index,
                          cx, cy, cx_onset, cy_onset, cx_two, cy_two, phase_kind, flags, metadata)

# Canonical source: scripts/extended_dataset/raw_qc.py
# SHA-256: ef9a2e4beb8b2cd1dd58308549eddf873981c85763854f82afebf9bffe420584

def parse_numeric_bytes(blob: bytes):
    """One optional first Time/channel header; whitespace or comma numeric data.

    A malformed row produces an explicit parse error, never a dropped sample.
    Numeric equality hashes all columns and timestamps, not only I/V signals.
    """
    text = blob.decode('utf-8-sig')
    lines = text.splitlines(keepends=True)
    first = next((i for i, s in enumerate(lines) if s.strip()), None)
    if first is None:
        raise ValueError('empty file')
    header = []
    if lines[first].lstrip().lower().startswith(('"time"', 'time')):
        h = lines[first].strip()
        delimiter = '\t' if '\t' in h else ',' if ',' in h else None
        header = next(csv.reader([h], delimiter=delimiter)) if delimiter else h.split()
        lines = lines[first+1:]
    data_bytes = ''.join(lines).encode('utf-8')
    first_data = next((s for s in lines if s.strip()), '')
    delimiter = ',' if ',' in first_data else None
    array = np.loadtxt(io.StringIO('\n'.join(s.rstrip('\r\n') for s in lines)), delimiter=delimiter, ndmin=2, comments=None)
    if not len(array) or array.shape[1] < 2:
        raise ValueError('expected timestamp and signal columns')
    return array, header, delimiter or 'whitespace', data_bytes

# Canonical source: scripts/extended_dataset/review_control_support.py
# SHA-256: 0cfd8f434505b0c2dc946dcaa3947cb0257919218faaa058290a9a571a677d76

def plateau_labels(time, phase, cycle_index, n_intervals, windows, *, n_bins=100,
                   physical_control_means=None):
    """Categorical NxB labels; mixed or partly unsupported bins become NaN.

    A window is (start, stop, state), with finite positive integer state. None
    stop means beyond the final sample. Labels are never averaged. The input
    arrays and windows are not mutated.
    """
    time, phase = np.asarray(time, float), np.asarray(phase, float)
    cycle_index = np.asarray(cycle_index)
    if time.ndim != 1 or phase.shape != time.shape or cycle_index.shape != time.shape:
        raise ValueError('Time, phase and cycle index must be aligned 1D arrays')
    if n_bins < 1 or n_intervals < 0:
        raise ValueError('Nonnegative interval count and positive bin count required')
    sample_state = np.zeros(len(time), dtype=np.int64)
    last_stop = -np.inf
    for start, stop, state in windows:
        stop = np.inf if stop is None else float(stop)
        if not np.isfinite(start) or stop <= start or start < last_stop:
            raise ValueError('Stable windows must be ordered, disjoint and positive width')
        if not np.isfinite(state) or int(state) != state or state <= 0:
            raise ValueError('State labels must be positive integers')
        sample_state[(time >= start) & (time < stop)] = int(state)
        last_stop = stop
    mapped = np.isfinite(phase) & (cycle_index >= 0)
    if np.any((phase[mapped] < 0) | (phase[mapped] >= 1)):
        raise ValueError('Mapped phase must lie in [0,1)')
    if np.any(cycle_index[mapped] >= n_intervals):
        raise ValueError('Mapped cycle index exceeds interval rows')
    keys = cycle_index[mapped].astype(int)*n_bins+np.floor(phase[mapped]*n_bins).astype(int)
    size = n_intervals*n_bins
    counts = np.bincount(keys, minlength=size)
    lo, hi = np.full(size, np.iinfo(np.int64).max), np.zeros(size, dtype=np.int64)
    np.minimum.at(lo, keys, sample_state[mapped])
    np.maximum.at(hi, keys, sample_state[mapped])
    labels = np.full(size, np.nan)
    supported = (counts > 0) & (lo > 0) & (lo == hi)
    labels[supported] = lo[supported]
    labels = labels.reshape(n_intervals, n_bins)
    if physical_control_means is not None:
        physical = np.asarray(physical_control_means, float)
        if physical.shape != labels.shape:
            raise ValueError('Physical controls must align with the label matrix')
        labels[~np.isfinite(physical)] = np.nan
    return labels

# Canonical source: scripts/extended_dataset/infer_conductances.py
# SHA-256: aace63d0d00362a0e6dd1a2a519e86d49138694fd1969cf6a9ee96df8d4f3c58

def selected_samples(prepared, reviewed):
    """Recover the accepted epoch and whole-cycle/bin electrical mask exactly."""
    p, r = prepared, reviewed
    coordinate = r['phase_coordinate']
    if coordinate == 'two_part':
        phase, indices, controls = p.phase_two_part, p.cycle_index_two_part, p.control_means_two_part
    elif coordinate == 'onset_only':
        phase, indices, controls = p.phase_onset, p.cycle_index_onset, p.control_means_onset
    else:
        raise ValueError(f'Unknown accepted coordinate {coordinate}')
    epoch = r['chosen_epoch']
    a, b = epoch['start_index'], epoch['stop_index']
    assert 0 <= a < b <= len(p.intervals)
    assert np.isclose(p.intervals[a]['start'], epoch['start'], atol=1e-9, rtol=0)
    assert np.isclose(p.intervals[b-1]['end'], epoch['end'], atol=1e-9, rtol=0)
    periods = np.array([x['period'] for x in p.intervals[a:b]])
    assert len(periods) == epoch['n_primary_intervals']
    cv = np.std(periods, ddof=1) / np.mean(periods)
    assert np.isclose(cv, epoch['primary_cv'], atol=1e-10, rtol=0)
    keep = np.isfinite(phase) & (indices >= a) & (indices < b)
    pre_mask_count = int(keep.sum())
    if r['manual_command_windows']:
        windows = [(w['start_inclusive'], w['end_exclusive'], w['command_state'])
                   for w in r['manual_command_windows']]
        labels = plateau_labels(p.time, phase, indices, len(p.intervals), windows,
                                physical_control_means=controls)
        mapped = np.flatnonzero(keep)
        bins = np.floor(100*phase[mapped]).astype(int)
        keep[mapped] &= np.isfinite(labels[indices[mapped], bins])
    selected_phase = np.where(keep, phase, np.nan)
    mapped = np.flatnonzero(keep)
    bins = np.floor(100*phase[mapped]).astype(int)
    keys = np.unique(indices[mapped]*100 + bins)
    cycle_counts = np.bincount(keys % 100, minlength=100)
    physical = controls[a:b].copy()
    supported = np.zeros_like(physical, dtype=bool)
    supported[(keys // 100)-a, keys % 100] = True
    physical[~supported] = np.nan
    with np.errstate(all='ignore'):
        control_range = np.nanmax(physical, axis=0)-np.nanmin(physical, axis=0)
    info = {'epoch_start_index': a, 'epoch_stop_index': b,
            'n_primary_intervals': len(periods), 'primary_cv': float(cv),
            'samples_before_manual_mask': pre_mask_count,
            'samples_after_manual_mask': int(keep.sum()),
            'contributing_cycles_by_phase': cycle_counts,
            'native_control_range_by_phase': control_range,
            'minimum_contributing_cycles': int(cycle_counts.min()),
            'manual_mask_applied': bool(r['manual_command_windows']),
            'sample_mask_sha256': hashlib.sha256(np.packbits(keep).tobytes()).hexdigest()}
    assert np.all(cycle_counts >= 2), 'Accepted design lost cycle support'
    assert np.all(np.isfinite(control_range) & (control_range > 0)), 'Accepted physical rank lost'
    return selected_phase, info

def regress(electrical, phase, mode):
    """Pooled-sample OLS with centered moments and historical 6-digit output.

    Sample counts and R2 describe regression support; samples are not treated as
    independent biological replicates or used to construct confidence intervals.
    """
    if mode not in ('CC', 'VC'):
        raise ValueError('Recording mode must be CC or VC')
    valid = np.isfinite(phase)
    values = np.asarray(electrical, float)[valid]
    bins = np.floor(np.asarray(phase)[valid]*100).astype(int)
    if np.any((bins < 0) | (bins >= 100)) or not np.isfinite(values).all():
        raise ValueError('Invalid mapped samples')
    counts = np.bincount(bins, minlength=100)
    if np.any(counts < 2):
        raise ValueError('At least two observations needed in each phase bin')
    i, v = values.T
    def means(x):
        return np.bincount(bins, weights=x, minlength=100)/counts
    mi, mv = means(i), means(v)
    di, dv = i-mi[bins], v-mv[bins]
    vi, vv, cov = means(di*di), means(dv*dv), means(di*dv)
    with np.errstate(divide='ignore', invalid='ignore'):
        if mode == 'CC':
            slope = cov/vi
            g, c = 1/slope, -(mv-slope*mi)/slope
            residual_sd = np.sqrt(np.maximum(vv-cov*cov/vi, 0))
        else:
            g = cov/vv
            c = mi-g*mv
            residual_sd = np.sqrt(np.maximum(vi-cov*cov/vv, 0))
        r2 = cov*cov/(vi*vv)
    # The legacy executable serialized its I/V coefficients before decomposition.
    g_full, c_full = g.copy(), c.copy()
    g = np.array([float(f'{x:.6g}') for x in g])
    c = np.array([float(f'{x:.6g}') for x in c])
    return {'total_g_native': g, 'current_intercept_native': c,
            'total_g_native_full_precision': g_full,
            'current_intercept_native_full_precision': c_full,
            'sample_counts_by_phase': counts, 'r2_by_phase': r2,
            'response_residual_sd_native_by_phase': residual_sd,
            'current_mean_native_by_phase': mi, 'voltage_mean_native_by_phase': mv,
            'current_variance_native_by_phase': vi, 'voltage_variance_native_by_phase': vv}

def decompose(total_g, current, ei, ee):
    """Historical extrema grounding and joint E/I normalization, unrepaired."""
    result = {'ei_mV': float(ei), 'ee_mV': float(ee)}
    total_g, current = np.asarray(total_g), np.asarray(current)
    if not ei < ee or not np.isfinite(total_g).all() or not np.isfinite(current).all():
        return dict(result, status='failed', reason='Nonfinite regression or unordered reversals', profiles=None)
    ii, ie = np.max(current+ei*total_g), np.min(current+ee*total_g)
    g = (ie-ii)/(ee-ei)
    result['inferred_grounding_g_native'] = float(g)
    if not np.isfinite(g) or g <= 0:
        return dict(result, status='failed', reason='Nonpositive inferred grounding conductance', profiles=None)
    e = ei-ii/g
    # Algebraically identical extrema differences avoid cancellation that could
    # turn a constant I/V relation into a unit-height roundoff-only profile.
    ge = (ii-(current+ei*total_g))/(ee-ei)/g
    gi = ((current+ee*total_g)-ie)/(ee-ei)/g
    raw = np.array([ge, gi])
    signals = np.maximum(raw, 0)
    scale = float(signals.max())
    if not np.isfinite(signals).all() or not np.isfinite(scale) or scale <= 0:
        return dict(result, status='failed', reason='Nonfinite or zero phasic profile', profiles=None)
    return dict(result, status='ok', inferred_grounding_reversal_mV=float(e),
                profiles=signals/scale, relative_to_grounding_profiles=signals,
                joint_scale_relative_to_grounding=scale,
                unclipped_negative_fraction=float(np.mean(raw < -1e-10)),
                minimum_unclipped_relative_component=float(raw.min()))

# Canonical source: scripts/extended_dataset/reversal_geometry.py
# SHA-256: 044cf23518ee05ca1de036fbf350f3ed75d5a04e52b56a9fa59ed723bd95d7fc

CONDITIONAL_ASSUMPTION = (
    'Interpret Ei as inhibitory reversal only if the upper trajectory boundary '
    'represents variation of inhibition at approximately fixed minimal excitation. '
    'The geometric fit alone cannot establish that condition; a proportional '
    'E/I mixture may yield an equally sharp line.'
)

def estimate_inhibitory_reversal(total_g_native, current_intercept_native,
                                 phase_indices=None):
    """Return JSON-safe geometry and ``estimated``/``not_identifiable`` status.

    Inputs are matching one-dimensional phasewise G and C arrays. Nonfinite
    pairs are logged and omitted from this diagnostic only; the caller must
    preserve any separate regression failure. The original slice minimum of
    three finite points is retained; two distinct G values can suffice.

    Numerical comparisons use 64 binary64 eps in normalized coordinates, not a
    physical conductance or reversal cutoff. Ambiguity means that the objective
    has multiple supporting slopes (or is numerically at such a vertex).
    Returned ``slope`` and ``intercept`` obey C=slope*G+intercept in input units.
    """
    g = np.asarray(total_g_native, dtype=float)
    c = np.asarray(current_intercept_native, dtype=float)
    if g.ndim != 1 or c.shape != g.shape:
        raise ValueError('G and C must be matching one-dimensional phase arrays')
    phases = np.arange(len(g)) if phase_indices is None else np.asarray(phase_indices)
    if phases.shape != g.shape or phases.ndim != 1:
        raise ValueError('phase_indices must align with G and C')
    if (not np.issubdtype(phases.dtype, np.integer)
            and (not np.isfinite(phases).all() or not np.equal(phases, np.floor(phases)).all())):
        raise ValueError('phase_indices must contain integer identifiers')
    phases = phases.astype(np.int64)
    if len(set(phases.tolist())) != len(phases):
        raise ValueError('phase_indices must be unique')
    finite = np.isfinite(g) & np.isfinite(c)
    result = {
        'status': 'not_identifiable', 'ei_mV': None, 'slope': None,
        'intercept': None, 'slice_plot_slope': None,
        'slope_units': 'native current / (native current per mV) = mV',
        'intercept_units': 'native current',
        'n_input_phase_points': int(len(g)), 'n_finite_phase_points': int(finite.sum()),
        'finite_phase_indices': phases[finite].tolist(),
        'excluded_nonfinite_phase_indices': phases[~finite].tolist(),
        'boundary_anchor_phase_indices': [], 'G_span_native': None,
        'max_upper_bound_violation_native': None, 'ambiguity': False,
        'flags': ['inhibitory_boundary_interpretation_is_conditional'],
        'optimal_slope_interval_mV': None, 'optimal_Ei_interval_mV': None,
        'collinear_trajectory': None,
        'conditional_wedge_assumption': CONDITIONAL_ASSUMPTION,
        'biological_reversal_identifiability_established': False,
        'excitatory_reversal_estimated': False,
        'source_reference': dict(SLICE_SOURCE_REFERENCE),
        'method': 'Equal-phase summed vertical gap; global upper concave hull at mean G.',
        'equal_G_policy': 'Retain uppermost C for hull; all points remain in objective and global bound check.',
        'numerical_tolerance_normalized': float(64*np.finfo(float).eps),
        'input_sha256': hashlib.sha256(
            np.column_stack((g, c)).astype('<f8').tobytes()+phases.astype('<i8').tobytes()).hexdigest(),
    }
    if finite.sum() < 3:
        return dict(result, reason='fewer_than_three_finite_phase_points')
    if not finite.all():
        result['flags'].append('nonfinite_phase_points_omitted_from_geometry_only')
    gf, cf, pf = g[finite], c[finite], phases[finite]
    gl, cl = gf.astype(np.longdouble), cf.astype(np.longdouble)
    span = gl.max()-gl.min()
    result['G_span_native'] = float(span)
    result['n_distinct_G_values'] = int(len(np.unique(gf)))
    if result['n_distinct_G_values'] < len(gf):
        result['flags'].append('equal_G_ties_checked_against_global_upper_bound')
    if span == 0:
        return dict(result, reason='constant_total_conductance', ambiguity=True)
    g0, c0 = gl.min(), cl.min()
    cspan = cl.max()-cl.min()
    yscale = cspan if cspan > 0 else np.longdouble(1)
    x, y = (gl-g0)/span, (cl-c0)/yscale
    tol = np.longdouble(result['numerical_tolerance_normalized'])
    unique_g = np.unique(gf)
    vertices = []
    for value in unique_g:
        loc = np.flatnonzero(gf == value)
        top = loc[np.argmax(y[loc])]
        vertices.append((x[top], y[top], int(top)))
    hull = []
    for point in vertices:
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            cross = (b[0]-a[0])*(point[1]-b[1])-(b[1]-a[1])*(point[0]-b[0])
            if cross < 0:
                break
            hull.pop()
        hull.append(point)
    result['upper_hull_vertex_phase_indices'] = [int(pf[v[2]]) for v in hull]
    xmean = x.mean()
    result['mean_G_native'] = float(gl.mean())
    # A line through the extreme upper points suffices to diagnose collinearity
    # of ALL original points, including lower points with equal G.
    end_slope = (hull[-1][1]-hull[0][1])/(hull[-1][0]-hull[0][0])
    end_gap = hull[0][1]+end_slope*(x-hull[0][0])-y
    result['collinear_trajectory'] = bool(np.max(np.abs(end_gap)) <= tol)
    if result['collinear_trajectory']:
        result['flags'].append('collinear_trajectory_cannot_distinguish_pure_inhibition_from_proportional_mixture')
    slopes = [(b[1]-a[1])/(b[0]-a[0]) for a, b in zip(hull[:-1], hull[1:])]
    for j in range(1, len(hull)-1):
        if abs(xmean-hull[j][0]) <= tol:
            low, high = slopes[j], slopes[j-1]
            # Collinear roundoff must not create a spurious slope ambiguity.
            if high-low > tol*max(np.longdouble(1), abs(high), abs(low)):
                native = [float(low*yscale/span), float(high*yscale/span)]
                support = np.flatnonzero((np.abs(x-hull[j][0]) <= tol)
                                         & (np.abs(y-hull[j][1]) <= tol))
                return dict(result, reason='nonunique_optimal_supporting_slope', ambiguity=True,
                            optimal_slope_interval_mV=native,
                            optimal_Ei_interval_mV=[-native[1], -native[0]],
                            boundary_anchor_phase_indices=pf[support].tolist(),
                            ambiguity_tolerance_note='Mean G lies at an upper-hull vertex within normalized arithmetic tolerance.')
    edge = next((j for j in range(len(hull)-1)
                 if hull[j][0] <= xmean <= hull[j+1][0]), None)
    if edge is None:
        return dict(result, reason='numerical_failure_to_locate_mean_on_upper_hull')
    m = slopes[edge]
    # This explicit global bound check fixes the equal-G omission in C++.
    b = np.max(y-m*x)
    gaps = m*x+b-y
    violation = max(np.longdouble(0), -gaps.min())
    native_m = m*yscale/span
    native_b = c0+yscale*b-native_m*g0
    if not np.isfinite([float(native_m), float(native_b)]).all():
        return dict(result, reason='nonfinite_boundary_in_native_units')
    if violation > tol:
        return dict(result, reason='global_upper_boundary_validation_failed',
                    max_upper_bound_violation_native=float(violation*yscale))
    anchors = pf[np.abs(gaps) <= tol].tolist()
    return dict(result, status='estimated', reason=None, ei_mV=float(-native_m),
                slope=float(native_m), intercept=float(native_b),
                slice_plot_slope=float(native_m/1000),
                boundary_anchor_phase_indices=anchors,
                max_upper_bound_violation_native=float(violation*yscale),
                objective_summed_vertical_gap_native=float(gaps.sum()*yscale),
                boundary_gap_native_by_finite_phase=(gaps*yscale).astype(float).tolist(),
                optimal_slope_interval_mV=[float(native_m), float(native_m)],
                optimal_Ei_interval_mV=[float(-native_m), float(-native_m)],
                anchor_G_native=float(g0),
                boundary_at_anchor_G_native=float(c0+yscale*b))

# Definition map supports a read-only source-equivalence check.
SOURCE_DEFINITIONS = [{'symbol': 'TARGET_TI', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 17, 'end_line': 17, 'definition_sha256': 'a81df54cb86c22265d3b4345987ca067b0259741ed5f63eaa42414ed4cf0872c'}, {'symbol': 'N_BINS', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 18, 'end_line': 18, 'definition_sha256': '25424e65790154dad96fb9b881e056d7f75074ad8a0b15413d75f78910e3fe1f'}, {'symbol': 'PreparedRecord', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 21, 'end_line': 55, 'definition_sha256': '4c6b54abddb6e8f2dc5489526f62533441bcb084169008c6aad1d351a2a82716'}, {'symbol': '_median', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 58, 'end_line': 65, 'definition_sha256': 'd08b682fd22ff0c3dbd108d77b9b887b776060774b0b4ec9f164d544a3cf6087'}, {'symbol': '_crossing', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 68, 'end_line': 76, 'definition_sha256': '2a06b6cbb24d5d91aa5386866d4eee32ea3b472bc6b1f2f84aa4ba6a7ea9f449'}, {'symbol': '_landmark_event', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 79, 'end_line': 117, 'definition_sha256': 'f542a5b3bfced7a223d235c62366aef97ab5461bdf3c0e04788e75b6666e8b62'}, {'symbol': '_phase_arrays', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 120, 'end_line': 136, 'definition_sha256': '241f6becdd084511b95a385742046a030bfdc348914d7c694449b38188821f72'}, {'symbol': '_cycle_means', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 139, 'end_line': 161, 'definition_sha256': '2406af3bf524daf91da04dd823a1f15c0df34eb67a3562f43be15cb59886ee7f'}, {'symbol': 'prepare_record', 'source': 'scripts/extended_dataset/full_preprocess.py', 'source_sha256': '37e82a83309fc237c61e40d7ea5577bd2a7d5e2e8e31f0b2e0385923bf087488', 'start_line': 164, 'end_line': 352, 'definition_sha256': '995464b56b732c4fd96b99fd4132a155218deab43963e2fa3f9fee136b0d5b14'}, {'symbol': 'parse_numeric_bytes', 'source': 'scripts/extended_dataset/raw_qc.py', 'source_sha256': 'ef9a2e4beb8b2cd1dd58308549eddf873981c85763854f82afebf9bffe420584', 'start_line': 26, 'end_line': 49, 'definition_sha256': 'b498e70b6a4d153ce8c31672cefd72d1633170d0b6bd934eb7643b55259ba0c4'}, {'symbol': 'plateau_labels', 'source': 'scripts/extended_dataset/review_control_support.py', 'source_sha256': '0cfd8f434505b0c2dc946dcaa3947cb0257919218faaa058290a9a571a677d76', 'start_line': 80, 'end_line': 124, 'definition_sha256': '41027b0dad9def2057828c2007df6fd48f8b6a3caac9a9f7a243d5262b2fa749'}, {'symbol': 'selected_samples', 'source': 'scripts/extended_dataset/infer_conductances.py', 'source_sha256': 'aace63d0d00362a0e6dd1a2a519e86d49138694fd1969cf6a9ee96df8d4f3c58', 'start_line': 62, 'end_line': 113, 'definition_sha256': 'e6b74ec743fe43629cd46d85ec9824ff5d26b609262049fffa0fd13bd54fbe65'}, {'symbol': 'regress', 'source': 'scripts/extended_dataset/infer_conductances.py', 'source_sha256': 'aace63d0d00362a0e6dd1a2a519e86d49138694fd1969cf6a9ee96df8d4f3c58', 'start_line': 116, 'end_line': 158, 'definition_sha256': '8ab4fc0e42f9ff8129df9dffd0f1af2b6be7425eca27cbfe2c2d9a03c6079d45'}, {'symbol': 'decompose', 'source': 'scripts/extended_dataset/infer_conductances.py', 'source_sha256': 'aace63d0d00362a0e6dd1a2a519e86d49138694fd1969cf6a9ee96df8d4f3c58', 'start_line': 161, 'end_line': 186, 'definition_sha256': '2c41f979fe3ab8e9d3f531b0013137ac8a3146a11b004336940a25e4c842978b'}, {'symbol': 'CONDITIONAL_ASSUMPTION', 'source': 'scripts/extended_dataset/reversal_geometry.py', 'source_sha256': '044cf23518ee05ca1de036fbf350f3ed75d5a04e52b56a9fa59ed723bd95d7fc', 'start_line': 33, 'end_line': 38, 'definition_sha256': 'b30eb2fa7177c7c74ee9bff391cc5462d8d958e99f2d576460698e989c3758f7'}, {'symbol': 'estimate_inhibitory_reversal', 'source': 'scripts/extended_dataset/reversal_geometry.py', 'source_sha256': '044cf23518ee05ca1de036fbf350f3ed75d5a04e52b56a9fa59ed723bd95d7fc', 'start_line': 41, 'end_line': 176, 'definition_sha256': '2a54b4ce8a4bc3e547cf77e89232b071592f09ab131bf9d1b110fbca6eaedfdd'}]
