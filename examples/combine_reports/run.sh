#!/usr/bin/env bash
set -eu

example=examples/combine_reports

echo "Bench A: measure delivered volume."
uv run --locked pytest "$example" -k delivery_volume \
    --xspec-run-id=run-a --xspec-json="$example/report-a.json"

echo "Bench B: measure time until the occlusion alarm."
uv run --locked pytest "$example" -k occlusion_alarm \
    --xspec-run-id=run-b --xspec-json="$example/report-b.json"

echo "Assess both runs together, preserving each observation and its run ID."
uv run --locked python -m pytest_xspec combine \
    "$example/report-a.json" "$example/report-b.json" \
    --output="$example/combined.json" --xspec-strict
