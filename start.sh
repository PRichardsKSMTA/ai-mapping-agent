#!/bin/sh
exec /opt/venv/bin/python -m streamlit run /app/app.py --server.port="${PORT:-8501}" --server.address=0.0.0.0
