.PHONY: check test compile

check:
	python check.py check

test:
	python -m pytest -q

compile:
	python -m compileall -q src api
