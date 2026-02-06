from playwright.sync_api import sync_playwright, expect
import os

def verify_admin_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Login
        print("Navigating to login...")
        page.goto("http://127.0.0.1:5000/login")

        # Fill password
        print("Logging in...")
        page.fill("input[name='password']", "changeme")
        page.click("button[type='submit']")

        # 2. Go to Admin Dashboard
        print("Navigating to Admin Dashboard...")
        # Should be redirected to /admin
        page.goto("http://127.0.0.1:5000/admin")

        expect(page.get_by_role("heading", name="Admin Dashboard")).to_be_visible()

        # 3. Verify New Cards

        # Auto Rooms
        print("Verifying Auto Rooms...")
        # Find the card that contains the title "Auto Rooms"
        auto_rooms_card = page.locator(".card", has=page.locator(".card-title", has_text="Auto Rooms"))
        expect(auto_rooms_card).to_be_visible()

        # Find the button inside that card
        auto_rooms_btn = auto_rooms_card.locator("a.btn")
        expect(auto_rooms_btn).to_be_visible()
        expect(auto_rooms_btn).to_have_text("Manage Auto Rooms")
        expect(auto_rooms_btn).to_have_attribute("href", "/admin/autorooms")

        # Auto Deleter
        print("Verifying Auto Deleter...")
        auto_deleter_card = page.locator(".card", has=page.locator(".card-title", has_text="Auto Deleter"))
        expect(auto_deleter_card).to_be_visible()

        auto_deleter_btn = auto_deleter_card.locator("a.btn")
        expect(auto_deleter_btn).to_be_visible()
        expect(auto_deleter_btn).to_have_text("Manage Auto Deleter")
        expect(auto_deleter_btn).to_have_attribute("href", "/admin/deleter")

        # 4. Take Screenshot
        print("Taking screenshot...")
        screenshot_path = os.path.abspath("verification/admin_dashboard_verification.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    verify_admin_dashboard()
