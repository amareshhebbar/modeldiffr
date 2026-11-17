#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f bench/.env ] && set -a && . bench/.env && set +a
[ -f .env ] && set -a && . ./.env && set +a

ARGS=""
[ "${SMOKE:-0}" = "1" ] && ARGS="--smoke"
[ "${NO_REAL:-0}" = "1" ] && ARGS="$ARGS --no-real"
python bench/make_spec.py $ARGS --exports "${BITNARROW_EXPORTS:-}"

modeldiffr batch bench/spec.yaml --out bench/results/audits
python bench/tamper.py
modeldiffr study bench/results/audits --out bench/results/study || echo "study tables skipped"
python bench/report.py
python bench/verify.py
echo "done. publish with: python bench/publish.py"
