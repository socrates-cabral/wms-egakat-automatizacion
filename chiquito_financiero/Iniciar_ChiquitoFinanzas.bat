@echo off
title Chiquito Finanzas — Iniciando...
color 0A

echo.
echo  ============================================
echo   CHIQUITO FINANZAS  -  Centro de Mando
echo  ============================================
echo.
echo  Iniciando la aplicacion...
echo  (Esto tarda unos segundos la primera vez)
echo.

:: Ir al directorio del proyecto
cd /d "C:\ClaudeWork\chiquito_financiero"

:: Lanzar Streamlit (el navegador lo abre el .vbs)
py -m streamlit run app\main.py --server.port 8502 --server.headless true --browser.gatherUsageStats false

:: Si se cierra Streamlit, pausar para ver el error
echo.
echo  La aplicacion se cerro. Presiona cualquier tecla para salir.
pause >nul
