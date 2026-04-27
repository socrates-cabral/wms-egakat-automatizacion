@echo off
REM ============================================================
REM  NutriMetab BI — Setup inicial del proyecto
REM  Ejecutar una sola vez desde C:\ClaudeWork\NutriMetab_BI\
REM ============================================================

echo [1/4] Creando estructura de carpetas...

mkdir data\raw
mkdir data\processed
mkdir data\exports
mkdir src\ingesta
mkdir src\procesamiento
mkdir src\modelos
mkdir src\reportes
mkdir src\utils
mkdir dashboard\pages
mkdir dashboard\components
mkdir notebooks
mkdir tests
mkdir launchers

echo [2/4] Creando archivos __init__.py...

type nul > src\__init__.py
type nul > src\ingesta\__init__.py
type nul > src\procesamiento\__init__.py
type nul > src\modelos\__init__.py
type nul > src\reportes\__init__.py
type nul > src\utils\__init__.py
type nul > dashboard\__init__.py

echo [3/4] Creando .env base...

(
echo # NutriMetab BI — Variables de entorno
echo DATA_RAW_PATH=data/raw
echo DATA_PROCESSED_PATH=data/processed
echo DATA_EXPORTS_PATH=data/exports
echo DB_PATH=data/nutrimetab.db
echo STREAMLIT_PORT=8504
) > .env

echo [4/4] Instalando dependencias...

py -m pip install -r requirements.txt

echo.
echo ============================================================
echo  Setup completado. Abre VS Code en esta carpeta y ejecuta:
echo  py -m streamlit run dashboard/app.py --server.port 8504
echo ============================================================
pause
