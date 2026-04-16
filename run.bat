@echo off
REM Launcher local para Windows - Equivalencia Masiva (Despacho EARM)
REM
REM Uso: doble click en este archivo, o desde una terminal: run.bat
REM
REM Requisitos previos:
REM   1. Python 3.11 o superior instalado
REM   2. pip install -r requirements.txt
REM   3. pip install torch --index-url https://download.pytorch.org/whl/cpu

echo.
echo ============================================================
echo   Equivalencia Masiva - Despacho EARM (CNSC)
echo ============================================================
echo.
echo Arrancando Streamlit en http://localhost:8501 ...
echo (Ctrl+C para detener)
echo.

python -m streamlit run app.py --server.port=8501 --browser.gatherUsageStats=false

pause
