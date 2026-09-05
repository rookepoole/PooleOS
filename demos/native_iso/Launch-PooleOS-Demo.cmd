@echo off
setlocal
set "PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON%" (
  echo The workspace Python runtime is missing. See README.md.
  pause
  exit /b 1
)
"%PYTHON%" -B "%~dp0launch.py"
if errorlevel 1 (
  echo Demo stopped. Review the diagnostic above; no physical disk was attached.
  pause
  exit /b 1
)
endlocal
