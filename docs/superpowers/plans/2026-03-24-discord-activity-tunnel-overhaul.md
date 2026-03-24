# Phase 11: Discord Activity & Secure Tunneling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the bot into a Discord Activity with a "turnkey" Cloudflare Tunnel setup for easy Raspberry Pi hosting.

**Architecture:**
- **Tunneling:** `cloudflared` for secure HTTPS ingress.
- **Activity SDK:** Discord Embedded App SDK for frontend integration.
- **Backend:** Quart-based API routes for Activity-specific data.
- **UI:** Mobile-optimized Glassmorphism view for the Activity iframe.

**Tech Stack:** Bash, Cloudflare Tunnel, Javascript (Discord SDK), Quart, Tailwind CSS.

---

### Task 1: Turnkey Tunnel Setup Script

**Files:**
- Create: `tools/setup_tunnel.sh`
- Modify: `config.json`

- [ ] **Step 1: Implement setup_tunnel.sh**
Automate: `cloudflared` installation, `login` helper, `tunnel create`, and `config` generation.
- [ ] **Step 2: Add tunnel_url and activity_client_id to config.json**
- [ ] **Step 3: Commit**
```bash
git add tools/setup_tunnel.sh config.json
git commit -m "feat: add turnkey Cloudflare Tunnel setup script"
```

### Task 2: Discord Activity SDK Infrastructure

**Files:**
- Create: `dashboard/static/js/activity.js`
- Create: `dashboard/templates/activity.html`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Implement the initial /activity route in app.py**
- [ ] **Step 2: Set up Discord SDK initialization in activity.js**
- [ ] **Step 3: Create the basic activity.html shell extending base_glass.html**
- [ ] **Step 4: Commit**
```bash
git add dashboard/
git commit -m "feat: set up Discord Activity SDK and initial route"
```

### Task 3: Activity UI - Character Quick-View

**Files:**
- Modify: `dashboard/templates/activity.html`
- Create: `dashboard/templates/includes/activity_stats.html`

- [ ] **Step 1: Create a single-column layout for character stats (HP, SAN, Luck)**
- [ ] **Step 2: Add interactive "Quick Roll" buttons for core skills**
- [ ] **Step 3: Implement real-time SAN/HP updates via long-polling or WebSockets**
- [ ] **Step 4: Commit**
```bash
git add dashboard/templates/
git commit -m "feat: implement character quick-view for Discord Activity"
```

### Task 4: Admin & Status Monitoring

**Files:**
- Create: `services/tunnel_service.py`
- Modify: `dashboard/templates/admin_dashboard.html`

- [ ] **Step 1: Implement TunnelService to monitor cloudflared status**
- [ ] **Step 2: Display the public Tunnel URL on the Admin Dashboard**
- [ ] **Step 3: Add "Copy Activity URL" helper for Discord Developer Portal**
- [ ] **Step 4: Commit**
```bash
git add services/ dashboard/
git commit -m "feat: add tunnel monitoring and admin helpers"
```

### Task 5: Final Polish & Documentation

**Files:**
- Modify: `README.md`
- Modify: `setup.sh`

- [ ] **Step 1: Add "Hosting as Activity" section to README.md**
- [ ] **Step 2: Integrate optional tunnel setup into main setup.sh**
- [ ] **Step 3: Final end-to-end verification**
- [ ] **Step 4: Commit**
```bash
git add README.md setup.sh
git commit -m "docs: finalize activity setup instructions"
```
