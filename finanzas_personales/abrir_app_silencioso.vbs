' Lanzador silencioso — no muestra ventana CMD
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "C:\ClaudeWork\finanzas_personales\abrir_app.bat" & Chr(34), 0, False
Set WshShell = Nothing
