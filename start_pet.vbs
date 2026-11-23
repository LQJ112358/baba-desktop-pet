Option Explicit
Dim fso, shell, base, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = base
cmd = "python.exe """ & base & "\baba_pet.py"""
On Error Resume Next
shell.Run cmd, 0, False
If Err.Number <> 0 Then
    MsgBox "python.exe was not found. Install Python 3.8+ and add it to PATH, then double-click start_pet.vbs again.", 16, "Baba Desktop Pet"
End If
