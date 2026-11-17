#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

cd "$PROJECT_DIR"

echo "[1/4] Verificando sintaxis del backend"
"$PYTHON_BIN" -m py_compile \
  app/backend/api.py \
  app/backend/core/*.py \
  app/backend/ml/*.py \
  app/backend/services/*.py

echo "[2/4] Evaluando el modelo base con la vendimia 2024"
"$PYTHON_BIN" -m app.backend.ml.modelo \
  app/backend/datos/evaluacion_2024.csv

echo "[3/4] Verificando tipos y compilando el frontend"
npm --prefix app/frontend run typecheck
npm --prefix app/frontend run build

echo "[4/4] Revisando formato del diff de Git"
git diff --check

echo "GrapeSense superó todas las verificaciones locales."
