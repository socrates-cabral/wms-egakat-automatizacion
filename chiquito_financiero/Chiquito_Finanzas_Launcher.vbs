' Chiquito_Finanzas_Launcher.vbs
' Lanza la app sin mostrar ventana de consola negra
' Coloca este archivo en el Escritorio

Dim shell
Set shell = CreateObject("WScript.Shell")

' Ruta al .bat (ajusta si moviste el proyecto)
Dim batPath
batPath = "C:\ClaudeWork\chiquito_financiero\Iniciar_ChiquitoFinanzas.bat"

' Verificar que existe el archivo
Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FileExists(batPath) Then
    MsgBox "No se encontro el archivo:" & vbNewLine & batPath & vbNewLine & vbNewLine & _
           "Verifica que el proyecto esta en C:\ClaudeWork\chiquito_financiero\", _
           vbCritical, "Chiquito Finanzas"
    WScript.Quit
End If

' Mostrar mensaje de inicio
' MsgBox "Iniciando Chiquito Finanzas..." & vbNewLine & "El navegador se abrira en unos segundos.", vbInformation, "Chiquito Finanzas"

' Lanzar sin ventana de consola (0 = oculta, 1 = normal)
shell.Run Chr(34) & batPath & Chr(34), 0, False

' Esperar 4 segundos y abrir el navegador
WScript.Sleep 4000
shell.Run "http://localhost:8502"

Set shell = Nothing
Set fso = Nothing
