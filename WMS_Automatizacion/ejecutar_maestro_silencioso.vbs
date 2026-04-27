Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\ClaudeWork"
WshShell.Run """C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"" WMS_Automatizacion\maestro_articulos_derco.py", 0, False
