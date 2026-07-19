#!/usr/bin/env bash
# One command to run the backend. Usage:  bash start.sh
set -e
cd "$(dirname "$0")"

# Create tables if needed, and make sure an API key exists.
.venv/bin/alembic upgrade head
if [ ! -s .devkey.txt ]; then
  .venv/bin/python -m app.issue_key me@example.com "dev" | awk '/^key:/{print $2}' > .devkey.txt
fi

echo ""
echo "=================================================================="
echo "  AI Sales Assistant backend"
echo "  API key : $(cat .devkey.txt)"
echo "  Docs    : http://localhost:8001/docs"
echo "  Health  : http://localhost:8001/api/v1/health"
echo "  (leave this window open; press Ctrl+C to stop)"
echo "=================================================================="
echo ""
exec .venv/bin/uvicorn app.main:app --port 8001 --reload
