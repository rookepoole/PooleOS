@echo off
setlocal
cd /d "%~dp0"
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B tools\launch_native_userspace_iso.py %*
if errorlevel 1 pause
