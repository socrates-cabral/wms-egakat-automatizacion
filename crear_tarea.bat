@echo off
schtasks /delete /tn "AnalisisDerco" /f 2>nul
schtasks /create /tn "AnalisisDerco" /tr "py C:\ClaudeWork\analisis_pedidos_derco.py" /sc once /st 00:00 /f
schtasks /run /tn "AnalisisDerco"
echo RC=%ERRORLEVEL%
