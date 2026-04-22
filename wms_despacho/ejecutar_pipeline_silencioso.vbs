Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\ClaudeWork\wms_despacho"
WshShell.Run "cmd /c C:\ClaudeWork\wms_despacho\run_pipeline.bat", 0, False
Set WshShell = Nothing
