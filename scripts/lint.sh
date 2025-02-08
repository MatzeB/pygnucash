#!/usr/bin/env bash
ruff format
ruff check "$@"
mypy .
