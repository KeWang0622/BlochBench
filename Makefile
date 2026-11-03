# Common development tasks. Choose the interpreter with PYTHON, for example: make test PYTHON=.venv/bin/python
PYTHON ?= python3
LINT_PATHS := mragentbench tools tests infra

.DEFAULT_GOAL := help
.PHONY: help setup setup-grader test lint families build-board build-site check-results packages

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-13s %s\n", $$1, $$2}'

setup: ## install mrab (editable) with the test and lint tools of requirements-dev.txt (jsonschema, ruff)
	$(PYTHON) -m pip install -e . -r requirements-dev.txt

setup-grader: ## install the pinned grader dependencies (Python 3.12 or later; Julia and KomaMRI: see harness/)
	$(PYTHON) -m pip install -r harness/grader-env/requirements.txt

test: ## run the unit tests, as CI does
	$(PYTHON) -m unittest discover -s tests -v

lint: ## ruff check and format check
	$(PYTHON) -m ruff check $(LINT_PATHS)
	$(PYTHON) -m ruff format --check $(LINT_PATHS)

families: ## regenerate families/*/family.json from each family's README.md, instances.json and task.example.json
	$(PYTHON) tools/make_family_metadata.py

build-board: ## rebuild the offline board from the frozen aggregate/Core snapshot; no agent runs
	$(PYTHON) tools/build_offline_leaderboard.py

build-site: ## rebuild task guide, site/data and README/results tables
	$(PYTHON) tools/build_task_guide.py
	$(PYTHON) tools/build_site.py

check-results: ## check the frozen offline board and generated docs/site without writing
	$(PYTHON) tools/build_task_guide.py --check
	$(PYTHON) tools/build_offline_leaderboard.py --check
	$(PYTHON) tools/build_site.py --check

packages: ## maintainers only (rewrites the hashes in instances.json): one tar per instance; needs SOURCE_ROOT, OUT_DIR
	@if [ -z "$(SOURCE_ROOT)" ] || [ -z "$(OUT_DIR)" ]; then \
		echo "usage: make packages SOURCE_ROOT=<folder with the instance sources> OUT_DIR=<folder for the tars>"; \
		exit 2; \
	fi
	$(PYTHON) tools/make_packages.py "$(SOURCE_ROOT)" "$(OUT_DIR)"
