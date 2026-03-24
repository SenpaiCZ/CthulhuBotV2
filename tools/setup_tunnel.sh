#!/bin/bash

# CthulhuBotV2 Cloudflare Tunnel Turnkey Setup Script
# Designed for Debian/Ubuntu based systems (including Raspberry Pi OS)

# Exit on any error
set -e

echo "-------------------------------------------------------"
echo "   CthulhuBotV2 Cloudflare Tunnel Setup Tool"
echo "-------------------------------------------------------"

# 1. Dependency Check & Installation
if ! command -v cloudflared &> /dev/null; then
    echo "[*] cloudflared not found. Starting installation..."
    
    # Check for curl
    if ! command -v curl &> /dev/null; then
        echo "[*] Installing curl..."
        sudo apt-get update && sudo apt-get install -y curl
    fi

    # Add Cloudflare GPG key
    echo "[*] Adding Cloudflare GPG key..."
    sudo mkdir -p --mode=0755 /usr/share/keyrings
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

    # Add Cloudflare repository
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "[*] Adding repository for $VERSION_CODENAME..."
        echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $VERSION_CODENAME main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
    else
        echo "[!] OS release file not found. Cannot automate repository addition."
        echo "[!] Please install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        exit 1
    fi

    echo "[*] Updating package list and installing cloudflared..."
    sudo apt-get update && sudo apt-get install -y cloudflared
    echo "[+] cloudflared installed successfully."
else
    echo "[+] cloudflared is already installed."
fi

# 2. Authentication
echo ""
echo "[*] Step 1: Authenticating with Cloudflare..."
echo "[!] A URL will be displayed below. Copy it into your browser to log in."
cloudflared tunnel login

# 3. Tunnel Creation
echo ""
echo "[*] Step 2: Creating tunnel 'cthulhubot'..."
# Check if it already exists
if cloudflared tunnel list | grep -q "cthulhubot"; then
    echo "[!] Tunnel 'cthulhubot' already exists. Reusing existing tunnel."
else
    cloudflared tunnel create cthulhubot
fi

# Extract Tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep cthulhubot | awk '{print $1}')
echo "[+] Tunnel ID: $TUNNEL_ID"

# 4. Configuration Generation
echo ""
echo "[*] Step 3: Generating tunnel configuration..."
CONF_DIR="$HOME/.cloudflared"
mkdir -p "$CONF_DIR"
CONF_FILE="$CONF_DIR/config.yml"

# Backup existing config if it exists
if [ -f "$CONF_FILE" ]; then
    echo "[*] Backing up existing config to $CONF_FILE.bak"
    cp "$CONF_FILE" "$CONF_FILE.bak"
fi

# Create the config file
cat <<EOF > "$CONF_FILE"
tunnel: $TUNNEL_ID
credentials-file: $CONF_DIR/$TUNNEL_ID.json

ingress:
  - hostname: YOUR_TUNNEL_URL_HERE
    service: http://localhost:5000
  - service: http_status:404
EOF

echo "[+] Configuration written to $CONF_FILE"

# 5. Final Instructions
echo ""
echo "-------------------------------------------------------"
echo "   Setup Complete! Final Steps:"
echo "-------------------------------------------------------"
echo "1. Route your custom domain to this tunnel:"
echo "   cloudflared tunnel route dns cthulhubot <your.domain.com>"
echo ""
echo "2. Update the config.yml at $CONF_FILE:"
echo "   Replace 'YOUR_TUNNEL_URL_HERE' with <your.domain.com>"
echo ""
echo "3. Update your CthulhuBotV2 config.json:"
echo "   \"tunnel_url\": \"https://<your.domain.com>\""
echo "   \"activity_client_id\": \"<your_discord_application_id>\""
echo ""
echo "4. Run the tunnel manually to test:"
echo "   cloudflared tunnel run cthulhubot"
echo ""
echo "5. (Recommended) Install as a system service:"
echo "   sudo cloudflared --config $CONF_FILE service install"
echo "   sudo systemctl start cloudflared"
echo "   sudo systemctl enable cloudflared"
echo "-------------------------------------------------------"
