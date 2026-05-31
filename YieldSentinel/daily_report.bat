@echo off
cd /d "C:\ClaudeWork\YieldSentinel"
"C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe" orchestrator.py --mode report >> data\logs\daily_report.log 2>&1
