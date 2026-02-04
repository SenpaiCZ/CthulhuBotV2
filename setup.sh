#!/bin/bash

echo "Starting CthulhuBotV2 Setup for Linux/macOS..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers (chromium)..."
playwright install chromium

# Create data directory if it doesn't exist
if [ ! -d "data" ]; then
    echo "Creating data directory..."
    mkdir data
fi

# Create settings.json if it doesn't exist
if [ ! -f "data/settings.json" ]; then
    echo "Creating data/settings.json template..."
    echo '{
    "token": "YOUR_DISCORD_BOT_TOKEN",
    "youtubetoken": "YOUR_YOUTUBE_API_KEY",
    "enable_dashboard": true,
    "admin_password": "your_secure_password"
}' > data/settings.json
    echo "Please edit data/settings.json with your bot token and API keys."
else
    echo "data/settings.json already exists. Skipping creation."
fi

echo "Setup complete! To run the bot, use: source venv/bin/activate && python bot.py"
