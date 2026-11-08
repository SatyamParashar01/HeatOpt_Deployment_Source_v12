#!/usr/bin/env bash
# Full pipeline. Run from the folder ABOVE the heatopt package: bash heatopt/run_all.sh
set -euo pipefail
python -m pytest -q heatopt/tests
python -m heatopt.optimize --catalog brands    --out heatopt/outputs_brands
python -m heatopt.optimize --catalog suz_ka    --out heatopt/outputs_suz_ka
python -m heatopt.optimize --catalog oversized --out heatopt/outputs_oversized
for d in outputs_brands outputs_suz_ka outputs_oversized; do python -m heatopt.plot_results --out heatopt/$d; done
python -m heatopt.compare_sizing --brands heatopt/outputs_brands --oversized heatopt/outputs_oversized --out heatopt/outputs_compare
python -m heatopt.annual_totals --out heatopt/outputs_annual
