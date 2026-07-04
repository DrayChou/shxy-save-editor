@echo off
cd /d %~dp0
where pyw >nul 2>nul
if %errorlevel%==0 (
    pyw -3 launch_gui.pyw
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    pythonw launch_gui.pyw
    exit /b
)
python launch_gui.pyw
