@echo off
setlocal

echo Starting CthulhuBotV2 Setup for Windows...

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH. Please install Python 3.11 or higher.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

REM Install Playwright browsers
echo Installing Playwright browsers (chromium)...
playwright install chromium

REM Create data directory if it doesn't exist
if not exist "data" (
    echo Creating data directory...
    mkdir data
)

REM Create config.json if it doesn't exist
if not exist "config.json" (
    echo Creating config.json template...
    echo {> config.json
    echo     "token": "YOUR_DISCORD_BOT_TOKEN",>> config.json
    echo     "enable_dashboard": true,>> config.json
    echo     "admin_password": "your_secure_password">> config.json
    echo }>> config.json
    echo Please edit config.json with your bot token and API keys.
) else (
    echo config.json already exists. Skipping creation.
)

echo Setup complete! To run the bot, use: venv\Scripts\activate && python bot.py
echo.
pause
