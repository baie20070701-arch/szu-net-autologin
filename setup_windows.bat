@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 goto use_py

python "%~dp0szu_autologin.py" init
goto done

:use_py
py -3 "%~dp0szu_autologin.py" init

:done
echo.
pause
