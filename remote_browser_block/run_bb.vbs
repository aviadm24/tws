Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run Chr(34) & "run_bb.bat" & Chr(34), 0
Set WinScriptHost = Nothing