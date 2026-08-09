@echo off
title Watermark Tool
cd /d "%~dp0"
start "" /b "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%~dp0app.py"
exit
