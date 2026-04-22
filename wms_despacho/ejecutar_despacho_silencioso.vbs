Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\ClaudeWork\wms_despacho"
WshShell.Run """C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"" despacho.py", 0, False
