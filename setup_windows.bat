@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking required tools...
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 --version >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_LAUNCHER=py -3.12"
  ) else (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_LAUNCHER=py -3.11"
  )
)

if not defined PYTHON_LAUNCHER (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_LAUNCHER=python"
)

if not defined PYTHON_LAUNCHER (
  echo [ERROR] Python 3.11 or 3.12 was not found in PATH.
  exit /b 1
) else (
  echo Using: %PYTHON_LAUNCHER%
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js 20 LTS and npm were not found in PATH.
  exit /b 1
)

echo [2/4] Creating the backend virtual environment...
if not exist "backend\.venv\Scripts\python.exe" (
  %PYTHON_LAUNCHER% -m venv "backend\.venv"
  if errorlevel 1 exit /b 1
)

echo [3/4] Installing backend dependencies...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 exit /b 1

echo [4/4] Installing frontend dependencies...
pushd frontend
call npm ci
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "backend\.env" (
  copy /Y ".env.example" "backend\.env" >nul
  echo Created backend\.env from .env.example.
)

echo.
echo Setup completed.
echo Next: edit backend\.env, make sure MySQL is running, then run start_dev.bat.
endlocal
