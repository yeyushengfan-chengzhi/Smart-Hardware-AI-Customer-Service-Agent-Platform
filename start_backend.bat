@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".env" (
  echo [ERROR] backend\.env not found.
  echo Run setup_windows.bat from the repository root first.
  echo Then configure MySQL and LLM_API_KEY before starting the demo.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] backend\.venv not found.
  echo Run setup_windows.bat from the repository root first.
  exit /b 1
)

echo Starting Smart Hardware AI backend...
echo Health: http://127.0.0.1:8000/health
echo Swagger: http://127.0.0.1:8000/docs

".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

endlocal
