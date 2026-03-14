' Chiquito_Finanzas_Launcher.vbs
' - Si la app ya esta corriendo -> abre el navegador al instante
' - Si no esta corriendo -> la inicia y espera solo lo necesario (sin tiempo fijo)

Dim shell, fso
Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

Dim batPath
batPath = "C:\ClaudeWork\chiquito_financiero\Iniciar_ChiquitoFinanzas.bat"

If Not fso.FileExists(batPath) Then
    MsgBox "No se encontro:" & vbNewLine & batPath, vbCritical, "Chiquito Finanzas"
    WScript.Quit
End If

' --- Funcion: devuelve True si el puerto 8502 ya esta escuchando ---
Function PuertoActivo()
    Dim exec, output
    Set exec = shell.Exec("cmd /c netstat -an 2>nul | findstr :8502")
    output = exec.StdOut.ReadAll()
    PuertoActivo = (InStr(output, "8502") > 0)
End Function

' --- Si ya esta corriendo, abrir directamente ---
If PuertoActivo() Then
    shell.Run "http://localhost:8502"
    WScript.Quit
End If

' --- No esta corriendo: iniciar el servidor ---
shell.Run Chr(34) & batPath & Chr(34), 0, False

' --- Esperar a que el puerto responda (maximo 20 segundos, revisando cada 500ms) ---
Dim intentos
intentos = 0
Do While Not PuertoActivo() And intentos < 40
    WScript.Sleep 500
    intentos = intentos + 1
Loop

' --- Abrir navegador ---
shell.Run "http://localhost:8502"

Set shell = Nothing
Set fso   = Nothing
