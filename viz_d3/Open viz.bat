@echo off
rem Double-click to open the Typical Orange Cats page in your browser.
rem Keep this window open while you use the page; close it to stop the server.
where py >nul 2>nul
if %errorlevel%==0 (py "%~dp0serve.py") else (python "%~dp0serve.py")
if errorlevel 1 pause
