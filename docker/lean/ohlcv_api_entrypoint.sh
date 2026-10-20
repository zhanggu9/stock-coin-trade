#!/usr/bin/env sh
set -eu

mkdir -p /results
# Leave LEAN's bundled reference data untouched and stage API records separately.
cp /custom-data/ohlcv.jsonl /Lean/Data/ohlcv.jsonl
cp /module/ohlcv_api_config.json /results/config.json
cd /results

exec dotnet /Lean/Launcher/bin/Debug/QuantConnect.Lean.Launcher.dll
