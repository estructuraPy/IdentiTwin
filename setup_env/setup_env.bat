@echo off
echo Setting up Identitwin environment...

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Check for requirements.txt in common locations
set "REQ_FILE="
if exist "%PROJECT_ROOT%\requirements.txt" (
    set "REQ_FILE=%PROJECT_ROOT%\requirements.txt"
) else if exist "%SCRIPT_DIR%requirements.txt" (
    set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
) else (
    echo Error: requirements.txt not found
    echo Looked in:
    echo - %PROJECT_ROOT%\requirements.txt
    echo - %SCRIPT_DIR%requirements.txt
    pause
    exit /b 1
)

REM Check if conda is available
where conda >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using Conda environment...
    call conda env remove -n identitwin -y 2>nul
    call conda create -n identitwin python=3.9 -y
    call conda activate identitwin
    pip install -r "%REQ_FILE%"
    echo Conda environment "identitwin" setup complete.
) else (
    echo Creating virtual environment with venv...
    if exist "venv" (
        echo Removing existing venv...
        rmdir /s /q venv
    )
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r "%REQ_FILE%"
    echo Virtual environment setup complete.
)

echo.
echo Environment setup complete! You can now run run_simulation.bat to start the application.
pause
