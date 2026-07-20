#!/bin/sh
set -e

echo "Waiting for database..."
python <<'PY'
import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import settings

for attempt in range(60):
    try:
        engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database is ready.")
        sys.exit(0)
    except Exception as exc:
        print(f"Database not ready (attempt {attempt + 1}/60): {exc}")
        time.sleep(1)

print("Database did not become ready in time.")
sys.exit(1)
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec flask --app app:create_app run --host=0.0.0.0 --port=5000
