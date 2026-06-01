@echo off
REM Lanzador de J.A.R.V.I.S.
REM
REM IMPRESCINDIBLE arrancar via `py -c`, NO con `py jarvis\main.py`.
REM En esta maquina (Python 3.14 + sounddevice/PortAudio + WASAPI) cualquier
REM proceso cuyo __main__ se cargue desde un ARCHIVO no puede abrir el
REM microfono WASAPI (PaErrorCode -9996), y contamina a sus subprocesos de
REM captura. Arrancando con -c (importando el modulo) el microfono funciona.
cd /d "%~dp0.."
py -c "from jarvis.main import main; main()"
