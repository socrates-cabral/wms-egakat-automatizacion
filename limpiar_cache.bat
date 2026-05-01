@echo off
echo Eliminando cache Python...
for /d /r "C:\ClaudeWork" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo Cache Python eliminado
pause
