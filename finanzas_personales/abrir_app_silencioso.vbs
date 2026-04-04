' Lanzador Finanzas Personales — sin ventana visible
' El proceso Streamlit corre oculto en segundo plano.
' Para cerrar la app: Administrador de tareas → py.exe → Finalizar tarea

Dim WshShell, oExec, puerto, url, ya_corriendo

puerto = 8501
url    = "http://localhost:" & puerto
Set WshShell = CreateObject("WScript.Shell")

' ── Verificar si ya está corriendo ──────────────────────────────────────────
Set oExec = WshShell.Exec("cmd /c netstat -an | findstr :" & puerto)
Dim salida : salida = ""
Do While Not oExec.StdOut.AtEndOfStream
    salida = salida & oExec.StdOut.ReadLine()
Loop
ya_corriendo = (InStr(salida, ":" & puerto) > 0)

If ya_corriendo Then
    ' Solo abrir navegador
    WshShell.Run url, 1, False
Else
    ' Cambiar al directorio correcto antes de lanzar
    WshShell.CurrentDirectory = "C:\ClaudeWork"

    ' Lanzar Streamlit completamente oculto (windowStyle=0)
    Dim cmd
    cmd = "py -m streamlit run " & _
          "C:\ClaudeWork\finanzas_personales\app\main.py " & _
          "--server.port " & puerto & " " & _
          "--server.headless true " & _
          "--browser.gatherUsageStats false " & _
          "--server.fileWatcherType none"

    WshShell.Run cmd, 0, False   ' 0 = oculto, False = no esperar

    ' Esperar a que Streamlit arranque
    WScript.Sleep 7000

    ' Abrir navegador
    WshShell.Run url, 1, False
End If

Set WshShell = Nothing
