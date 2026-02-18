#!/bin/bash

echo "Starting CthulhuBotV2 Setup for Linux/macOS..."

# Check for Pi OS and install Emoji Font
if [ -f /etc/os-release ]; then
    if grep -qi "Raspberry Pi" /etc/os-release || grep -qi "Raspbian" /etc/os-release; then
        echo "Raspberry Pi OS detected. Installing Noto Color Emoji font..."
        # sudo is typically available on Pi OS default user
        sudo apt update
        sudo apt install -y fonts-noto-color-emoji
    fi
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.11 or higher."
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

# Create config.json if it doesn't exist
if [ ! -f "config.json" ]; then
    echo "Creating config.json template..."
    echo '{
    "token": "YOUR_DISCORD_BOT_TOKEN",
    "enable_dashboard": true,
    "admin_password": "your_secure_password"
}' > config.json
    echo "Please edit config.json with your bot token and API keys."
else
    echo "config.json already exists. Skipping creation."
fi

echo "Setup complete! To run the bot, use: source venv/bin/activate && python bot.py"
