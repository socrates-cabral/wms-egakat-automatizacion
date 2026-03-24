@echo off
cd /d C:\ClaudeWork
py -m streamlit run agente_apuestas\dashboard_apuestas.py --server.port 8504 --server.headless false
pause
