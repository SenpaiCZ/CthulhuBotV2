# Spec: Discord Activity & Secure Tunneling (Phase 11)

## Goal
Transform the CthulhuBot dashboard into a fully functional Discord Activity, allowing players to manage their character sheets and roll dice directly within the Discord interface. This phase includes a "turnkey" setup for secure tunneling via Cloudflare to support hosting from a Raspberry Pi.

## Architecture
- **Platform:** Discord Embedded App SDK (integrated into the frontend).
- **Hosting Bridge:** Cloudflare Tunnel (`cloudflared`) for secure, high-performance HTTPS access to the local Raspberry Pi.
- **Authentication:** Automatic player identification via Discord OAuth2 (SDK-based).
- **Communication:** Real-time updates via WebSockets (Quart-Schema/Socket.io).

## Tunneling Component (Turnkey Setup)
- **Tool:** `cloudflared` (Cloudflare Tunnel).
- **Automation:** `tools/setup_tunnel.sh` script to automate installation, authentication, and tunnel creation on Linux/RPi.
- **Config:** Integration of tunnel URL into `config.json` for automatic Discord SDK initialization.

## Components
1. **`tools/setup_tunnel.sh`**: One-click setup script for Cloudflare Tunnel.
2. **`services/tunnel_service.py`**: Monitor tunnel status and display the public URL in the bot's console/admin dashboard.
3. **`dashboard/templates/activity.html`**: A dedicated, mobile-optimized view for the Discord Activity window.
4. **`dashboard/static/js/discord-sdk.js`**: Integration of the Discord Embedded App SDK.

## Design System (Activity Optimization)
- **Layout:** Responsive, single-column design optimized for the Discord Activity aspect ratio.
- **Controls:** Touch-friendly buttons and sliders for mobile/desktop parity.
- **Real-time:** Instant SAN/HP updates when changed by the GM on the main dashboard.

## Success Criteria
- The bot dashboard can be launched as a Discord Activity in any voice channel.
- A secure HTTPS tunnel is established automatically with a single setup script.
- Players are automatically logged into their character sheets upon launching the Activity.
- Zero manual port-forwarding or SSL certificate management required.
