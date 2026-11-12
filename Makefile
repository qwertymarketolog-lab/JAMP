.PHONY: lint lint-all lint-update format

lint:
	@python tools/check_ruff_baseline.py

lint-all:
	@ruff check .

lint-update:
	@python tools/check_ruff_baseline.py --update

format:
	@ruff format .
