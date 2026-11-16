@echo off
chcp 65001 >nul
rem Lance blablappli avec une fenêtre qui affiche les messages (pour comprendre un problème)
cd /d "%~dp0"
".venv\Scripts\python.exe" -m blablappli
pause
