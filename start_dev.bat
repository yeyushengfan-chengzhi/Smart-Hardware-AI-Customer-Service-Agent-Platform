@echo off
setlocal

echo Starting Smart Hardware AI Customer Service Platform...
echo Backend Swagger: http://127.0.0.1:8000/docs
echo Frontend: http://localhost:5173/

start "Backend - Smart Hardware AI" cmd /k call "%~dp0start_backend.bat"
start "Frontend - Smart Hardware AI" cmd /k call "%~dp0start_frontend.bat"

endlocal
