' WatermarkTool silent launcher - no console window
Dim fso, shell, base, app, pyw
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
app  = base & "\app.py"
pyw  = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe"
If fso.FileExists(pyw) Then
    shell.Run """" & pyw & """ """ & app & """", 1, False
Else
    shell.Run "pythonw.exe """ & app & """", 1, False
End If
