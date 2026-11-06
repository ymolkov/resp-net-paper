"""Paper figure helpers extracted from the canonical plot_empirical_connectome.py.

Retained definitions and constants are verbatim; historical CLIs and unrelated
fitting dependencies are omitted.
"""
from __future__ import annotations

# Canonical source: scripts/plot_empirical_connectome.py
# SHA-256: 42882721c4f5a4f7eebba042589f93458224487ee7ce8ce8c206a0197f7b6161
import numpy as np


PHENOTYPES = ["pre-I", "ramp-I", "early-I", "post-I", "aug-E"]


EXCITATORY_CANDIDATES = ["pre-I", "ramp-I", "post-I", "aug-E"]


INHIBITORY_CANDIDATES = ["early-I", "post-I", "aug-E"]


def smith2007_concept_structure_matrices():
    """Return a discharge-pattern projection of the Smith 2007 three-phase circuit.

    Connections follow Figure 7 and Table 3 of Smith et al. (2007). The single
    displayed early-I node combines pre-BotC early-I(1) and rVRG early-I(2).
    The inhibitory and excitatory post-I populations share the incoming edges
    displayed at the overlapping post-I nodes.
    """
    matrix_e = np.zeros((len(PHENOTYPES), len(EXCITATORY_CANDIDATES)))
    matrix_i = np.zeros((len(PHENOTYPES), len(INHIBITORY_CANDIDATES)))

    for target, source in (
        ("pre-I", "pre-I"),
        ("early-I", "pre-I"),
        ("ramp-I", "pre-I"),
    ):
        matrix_e[PHENOTYPES.index(target), EXCITATORY_CANDIDATES.index(source)] = 1.0

    for target, source in (
        ("pre-I", "aug-E"),
        ("pre-I", "post-I"),
        ("early-I", "aug-E"),
        ("early-I", "post-I"),
        ("aug-E", "early-I"),
        ("aug-E", "post-I"),
        ("post-I", "early-I"),
        ("post-I", "aug-E"),
        ("ramp-I", "early-I"),
        ("ramp-I", "aug-E"),
        ("ramp-I", "post-I"),
    ):
        matrix_i[PHENOTYPES.index(target), INHIBITORY_CANDIDATES.index(source)] = 1.0

    return matrix_e, matrix_i

SOURCE_DEFINITIONS = [{'symbols': ['PHENOTYPES'], 'start_line': 67, 'end_line': 67, 'definition_sha256': 'ebf5f9a43a8005e0898c4b520b44c0185fcf17f86d6c3d255fd4caabb163a390'}, {'symbols': ['EXCITATORY_CANDIDATES'], 'start_line': 80, 'end_line': 80, 'definition_sha256': '3b307f04879714260389a7eb18314b98ef66a91ebe8b70a6de750a6e63a57ff5'}, {'symbols': ['INHIBITORY_CANDIDATES'], 'start_line': 81, 'end_line': 81, 'definition_sha256': 'a8b73404e69eae17ebbcee975b370ee49dcfff55f143885d7e80aca744b870ec'}, {'symbols': ['smith2007_concept_structure_matrices'], 'start_line': 469, 'end_line': 502, 'definition_sha256': '7839b0cdc99804742fc393caa5d711f211af6df526791547c81e94a0a8ce7a34'}]
