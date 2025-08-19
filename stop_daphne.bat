@echo off
:: Find the PID of the Python process running Daphne on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do set PID=%%a

:: Check if a PID was found and terminate it
if defined PID (
    echo Stopping Daphne process with PID %PID%
    taskkill /PID %PID% /F
) else (
    echo No Daphne process found on port 8000
)
