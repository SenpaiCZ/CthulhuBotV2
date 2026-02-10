@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo          CthulhuBotV2 Auto-Updater
echo ========================================================
echo.
echo This script will:
echo 1. Backup your current bot files.
echo 2. Download the latest code from GitHub.
echo 3. Sync files (Delete obsolete files).
echo 4. Update files.
echo 5. Update dependencies and start the bot.
echo.
echo IMPORTANT: PLEASE CLOSE THE BOT WINDOW BEFORE CONTINUING.
echo.
pause

if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found in 'venv'.
    echo Please run setup.bat to create the environment first.
    pause
    exit /b
)

call venv\Scripts\activate.bat

echo Running updater...
python updater.py --no-restart

if %errorlevel% neq 0 (
    echo.
    echo Update failed.
    pause
    exit /b
)

echo.
echo Starting CthulhuBotV2...
python bot.py

pause
