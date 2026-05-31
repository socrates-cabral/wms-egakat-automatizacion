@echo off
cd /d "C:\ClaudeWork\YieldSentinel"
"C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe" orchestrator.py --mode once >> data\logs\scheduled_run.log 2>&1
