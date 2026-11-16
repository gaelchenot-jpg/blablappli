@echo off
chcp 65001 >nul
echo Installation de blablappli...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
echo.
pause
