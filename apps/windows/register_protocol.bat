@echo off
REM Register drive-local-open:// URL scheme (per-user) and ensure launcher exists.
setlocal
set "ROOT=%~dp0..\.."
set "LAUNCHER=%LOCALAPPDATA%\DriveLocalOpen\drive-local-open.cmd"
mkdir "%LOCALAPPDATA%\DriveLocalOpen" 2>nul

> "%LAUNCHER%" (
  echo @echo off
  echo set "PYTHONPATH=%ROOT%\src"
  echo python -m drive_local_open %%*
)

reg add "HKCU\Software\Classes\drive-local-open" /ve /d "URL:Drive Local Open" /f >nul
reg add "HKCU\Software\Classes\drive-local-open" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\drive-local-open\shell\open\command" /ve /d "\"%LAUNCHER%\" --open files \"%%1\"" /f >nul

echo Registered drive-local-open://
echo Launcher: %LAUNCHER%
echo NOTE: Bookmarklet passes drive-local-open://open?url=ENCODED — a small parser shim may be needed.
echo For reliable use, prefer the Chrome bookmark that calls the cmd with the raw Drive URL after install of the helper extension ^(future^).
endlocal
