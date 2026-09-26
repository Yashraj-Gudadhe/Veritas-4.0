#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "================================"
echo " VERITAS 3.0 — Backend Starting"
echo "================================"
export PYTHONPATH=backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
