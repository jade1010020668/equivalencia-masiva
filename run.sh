#!/usr/bin/env bash
# Launcher local para Linux/Mac - Equivalencia Masiva (Despacho EARM)
#
# Uso: bash run.sh
#
# Requisitos previos:
#   1. Python 3.11 o superior
#   2. pip install -r requirements.txt
#   3. pip install torch --index-url https://download.pytorch.org/whl/cpu

set -e

echo ""
echo "============================================================"
echo "  Equivalencia Masiva — Despacho EARM (CNSC)"
echo "============================================================"
echo ""
echo "Arrancando Streamlit en http://localhost:8501 ..."
echo "(Ctrl+C para detener)"
echo ""

python -m streamlit run app.py \
    --server.port=8501 \
    --browser.gatherUsageStats=false
