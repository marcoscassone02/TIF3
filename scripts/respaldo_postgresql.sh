#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups/render"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DATABASE_NAME="${DB_NAME:-tesis_uva}"
OUTPUT="$BACKUP_DIR/${DATABASE_NAME}_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump --format=custom --no-owner --no-acl --file="$OUTPUT" "$DATABASE_URL"
else
  pg_dump --format=custom --no-owner --no-acl --file="$OUTPUT" "$DATABASE_NAME"
fi

sha256sum "$OUTPUT" > "$OUTPUT.sha256"
chmod 600 "$OUTPUT" "$OUTPUT.sha256"

echo "Respaldo creado en: $OUTPUT"
echo "Este directorio está excluido de Git."
