# check: the store follows the format. build: generate the site. publish: push it to GitHub Pages.
.PHONY: check build publish
check:
	python3 tools/check.py
build:
	uv run tools/build.py
publish:
	tools/publish.sh
