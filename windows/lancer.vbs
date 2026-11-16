' Lance blablappli sans fenêtre noire
Set fso = CreateObject("Scripting.FileSystemObject")
dossier = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = dossier
pyw = dossier & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then
    MsgBox "blablappli n'est pas encore installé. Double-clique d'abord sur installer.bat.", 48, "blablappli"
    WScript.Quit
End If
sh.Run """" & pyw & """ -m blablappli", 0, False
