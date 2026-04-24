Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\ClaudeWork\wms_despacho"
WshShell.Run """C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"" C:\ClaudeWork\wms_despacho\run_pipeline.py", 0, False
Set WshShell = Nothing
