from playwright.sync_api import sync_playwright
import time
import os

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a fixed viewport for consistent screenshots
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Ensure directory exists
        os.makedirs('/tmp/screenshots', exist_ok=True)

        try:
            # 1. Main Page
            print("Navigating to home...")
            page.goto("http://localhost:8000/")
            time.sleep(1) # Wait for render
            page.screenshot(path="/tmp/screenshots/home_page.png", full_page=True)
            print("Home page screenshot taken.")

            # 2. Login
            print("Logging in...")
            page.goto("http://localhost:8000/login")
            page.fill("input[name='password']", "changeme")
            page.click("button[type='submit']")
            time.sleep(1)

            # 3. Admin Dashboard
            print("Navigating to Admin Dashboard...")
            page.goto("http://localhost:8000/admin")
            time.sleep(1)
            page.screenshot(path="/tmp/screenshots/admin_dashboard.png", full_page=True)
            print("Admin dashboard screenshot taken.")

            # 4. Navbar - Keeper Tools
            print("Opening Keeper Tools dropdown...")
            # Reload to ensure clean state
            page.reload()
            time.sleep(0.5)
            page.click("#keeperDropdown")
            time.sleep(0.5)
            page.screenshot(path="/tmp/screenshots/navbar_keeper.png")
            print("Navbar Keeper Tools screenshot taken.")

            # 5. Navbar - Server Administration
            print("Opening Server Admin dropdown...")
            page.reload()
            time.sleep(0.5)
            page.click("#serverAdminDropdown")
            time.sleep(0.5)
            page.screenshot(path="/tmp/screenshots/navbar_server.png")
            print("Navbar Server Admin screenshot taken.")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="/tmp/screenshots/error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
