#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set"
  exit 1
fi

echo "Running migrations against: ${DATABASE_URL}"

# Создаём таблицу учёта миграций
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
SQL

# Применяем миграции по имени файла (лексикографически: 001_, 002_, ...)
for file in /migrations/*.sql; do
  version="$(basename "$file")"

  applied="$(psql "${DATABASE_URL}" -tA -v ON_ERROR_STOP=1 \
    -c "SELECT 1 FROM schema_migrations WHERE version='${version}' LIMIT 1;")"

  if [ "$applied" = "1" ]; then
    echo "Skip ${version} (already applied)"
    continue
  fi

  echo "Apply ${version}"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "$file"

  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 \
    -c "INSERT INTO schema_migrations(version) VALUES ('${version}');"
done

echo "Migrations done."