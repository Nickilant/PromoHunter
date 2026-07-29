#!/bin/sh
set -e

echo "==> Waiting for database..."
python - <<'PY'
import sys
import time

from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url)
last_error = None
for _ in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 — печатаем причину при выходе
        last_error = exc
        time.sleep(1)
print(f"Database is not reachable, last error:\n{last_error}", file=sys.stderr)
sys.exit(1)
PY

echo "==> Applying migrations..."
alembic upgrade head

if [ "$SEED_ON_START" = "true" ]; then
    echo "==> Seeding (only if users table is empty)..."
    python -m app.seed --if-empty
fi

echo "==> Starting: $@"
exec "$@"
