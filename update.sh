#!/bin/bash

# Ensure we are in the script directory
cd "$(dirname "$0")"

echo "========================================================"
echo "          CthulhuBotV2 Auto-Updater (Linux/macOS)"
echo "========================================================"
echo ""
echo "This script will:"
echo "1. Backup your current bot files."
echo "2. Download the latest code from GitHub."
echo "3. Sync files (Delete obsolete files)."
echo "4. Update files."
echo "5. Update dependencies and start the bot."
echo ""
echo "IMPORTANT: PLEASE ENSURE THE BOT IS STOPPED BEFORE CONTINUING."
echo ""
read -p "Press Enter to continue..."

# Activate Virtual Environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Error: Virtual environment not found in 'venv'."
    exit 1
fi

# Run Updater (No Restart, because we want to run bot in this shell)
echo "Running updater..."
python3 updater.py --no-restart

if [ $? -eq 0 ]; then
    echo ""
    echo "Starting CthulhuBotV2..."
    python3 bot.py
else
    echo "Update failed."
    exit 1
fi
