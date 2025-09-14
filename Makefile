.PHONY: help install dev test lint clean build publish

install:
	uv pip install .

dev:
	uv pip install .[dev]

test:
	PYTHONPATH=. pytest tests

clean:
	rm -rf dist

build:
	uv build

publish:
	uv publish