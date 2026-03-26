@ECHO OFF
SETLOCAL

SET VENV_PATH=VENV\IBKR
SET PYTHON=%VENV_PATH%\Scripts\python.exe

REM Make sure venv exists
IF NOT EXIST "%PYTHON%" (
    echo.
    echo Virtual environment not found!
    echo Please run install_requirements.bat first.
    echo.
    pause
    exit /b
)

:START

cls
echo ============================
echo Starting IBKR app...
echo ============================
echo.

"%PYTHON%" __init__.py

echo.
echo ============================
echo Application stopped.
echo.
echo Press ENTER to start again
echo Press CTRL+C to exit
echo ============================

pause >nul
goto START
