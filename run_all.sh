#!/usr/bin/env bash
# Rejoue tout le pipeline de préparation, de bout en bout (≈ 1 min).
set -euo pipefail
cd "$(dirname "$0")"
for s in 01_load 02_eda 03_audit_labels 04_clean_text 04b_resolve_labels 05_build_targets 06_split 07_export 08_smoke_baseline; do
  echo "=== $s"; python3 "$s.py"
done
