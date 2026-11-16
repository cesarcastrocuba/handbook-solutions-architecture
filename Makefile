TOOLKIT ?= handbook-toolkit
PYTHON ?= python3
COMMIT ?= $(shell git rev-parse HEAD)
OUTPUT ?= ../dist
BUILD_FLAGS ?=

.PHONY: check full build book-checks checklist-exports

# Fast checks: book-owned gates plus descriptor, reading order and cross-references.
check: book-checks
	$(TOOLKIT) --root . validate-book --full
	$(TOOLKIT) --root . validate-references book.yaml

# Full check: fast checks plus a real seven-file local build. Requires Quarto 1.11.9 and pdfinfo.
full: check build

# The build also runs manuscript validation before rendering.
build: check
	$(TOOLKIT) build-book --repo . --commit $(COMMIT) --output $(OUTPUT) --mode chapter $(BUILD_FLAGS)

# Book-owned data freshness, canonical checklist parity and portable diagram integrity.
book-checks:
	$(PYTHON) scripts/generate_catalogs.py --check
	$(PYTHON) scripts/checklists.py --check
	$(PYTHON) scripts/render_diagrams.py --check
	$(PYTHON) -m unittest discover -s scripts/tests -v

# Generated deliverables stay in the ignored build directory, never canonical source.
checklist-exports:
	$(PYTHON) scripts/checklists.py --check --export
	$(PYTHON) scripts/export_checklists_csv.py --all
