@ECHO OFF
SETLOCAL

SET VENV_PATH=VENV\IBKR
SET PYTHON=%VENV_PATH%\Scripts\python.exe

REM Create virtual environment if it doesn't exist
IF NOT EXIST "%PYTHON%" (
    echo Creating virtual environment in %VENV_PATH% ...
    python -m venv %VENV_PATH%
)

echo.
echo Installing requirements...

"%PYTHON%" -m pip install --upgrade pip
"%PYTHON%" -m pip install -r requirements.txt

echo.
echo Installation complete.
echo You can now use runthis.bat
pause
