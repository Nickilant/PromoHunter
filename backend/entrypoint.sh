#!/bin/sh
set -e

echo "==> Waiting for database..."
python - <<'PY'
import sys
import time

from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url)
for _ in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        sys.exit(0)
    except Exception:
        time.sleep(1)
print("Database is not reachable", file=sys.stderr)
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
