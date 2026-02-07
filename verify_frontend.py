import time
from playwright.sync_api import sync_playwright, expect

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # 1. Login
        print("Logging in...")
        page.goto("http://localhost:5000/login")
        page.fill("input[name='password']", "changeme")
        page.click("button[type='submit']")

        # Verify login success
        expect(page).to_have_url("http://localhost:5000/admin")
        print("Logged in successfully.")

        # 2. Check Monsters Page (Admin)
        print("Checking Monsters Page...")
        page.goto("http://localhost:5000/monsters")

        # Click on "Spawn of Abhoth" in the list
        page.get_by_text("Spawn of Abhoth").click()

        # Wait for content to load and emojis to appear
        # We look for a characteristic label that should now have an emoji
        # e.g. STR should have :muscle: which renders as an image
        # The selector for the image is img.discord-emoji[alt=':muscle:'] or similar
        # But wait, rendered emoji is an img tag.

        # Let's take a screenshot of the detail panel
        time.sleep(1) # Allow JS to render
        page.locator("#monster-content").screenshot(path="/home/jules/verification/monsters_admin.png")
        print("Screenshot saved: monsters_admin.png")

        # 3. Check Deities Page (Admin)
        print("Checking Deities Page...")
        page.goto("http://localhost:5000/deities")

        # Click on "Abhoth"
        page.get_by_text("Abhoth").first.click()

        time.sleep(1)
        page.locator("#monster-content").screenshot(path="/home/jules/verification/deities_admin.png")
        print("Screenshot saved: deities_admin.png")

        # 4. Check Render Monster View
        print("Checking Render Monster View...")
        page.goto("http://localhost:5000/render/monster?name=Spawn%20of%20Abhoth")
        page.screenshot(path="/home/jules/verification/render_monster.png")
        print("Screenshot saved: render_monster.png")

        # 5. Check Render Deity View
        print("Checking Render Deity View...")
        page.goto("http://localhost:5000/render/deity?name=Abhoth")
        page.screenshot(path="/home/jules/verification/render_deity.png")
        print("Screenshot saved: render_deity.png")

        browser.close()

if __name__ == "__main__":
    verify_frontend()
