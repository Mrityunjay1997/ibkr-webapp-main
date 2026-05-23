@ECHO OFF
SETLOCAL

SET VENV_PATH=VENV\IBKR
SET PYTHON=%VENV_PATH%\Scripts\python.exe

REM Prefer the project venv, but fall back to the system Python if this copied
REM venv points at a Python install from another machine/user.
IF EXIST "%PYTHON%" (
    "%PYTHON%" --version >nul 2>&1
    IF ERRORLEVEL 1 (
        SET PYTHON=python
    )
) ELSE (
    SET PYTHON=python
)

%PYTHON% --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo.
    echo Python could not be started.
    echo Please repair VENV\IBKR or install Python on PATH.
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
