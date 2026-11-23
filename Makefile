PYTHON ?= python3
NODE ?= node

.PHONY: verify reconstruct inference reproduce figures site site-test companion-test serve

verify:
	$(PYTHON) scripts/verify_release.py
	$(PYTHON) scripts/plot_expanded_paper.py --check

reconstruct:
	$(PYTHON) scripts/reconstruct_recordings.py

inference:
	$(PYTHON) scripts/reproduce_inference.py

reproduce: reconstruct
	$(PYTHON) scripts/reproduce_inference.py --conductances output/reproduced/reconstruction.json

figures:
	$(PYTHON) scripts/plot_expanded_paper.py
	$(PYTHON) scripts/plot_cells_to_circuit_variability_preview.py --paper

site:
	$(PYTHON) scripts/build_connectome_explorer.py

site-test:
	$(NODE) --test apps/connectome-explorer/test-core.cjs

companion-test:
	$(PYTHON) -B scripts/test_paper_companion.py

serve:
	$(PYTHON) -m http.server 8000 --bind 127.0.0.1 --directory apps/connectome-explorer

