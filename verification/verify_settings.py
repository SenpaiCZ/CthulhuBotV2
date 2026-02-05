from playwright.sync_api import sync_playwright
import os

def verify_settings():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        # Login
        page.goto("http://127.0.0.1:5000/login")
        page.fill("input[name='password']", "changeme")
        page.click("button[type='submit']")

        # Navigate to Karma
        page.goto("http://127.0.0.1:5000/admin/karma")

        # Wait a bit for table
        page.wait_for_selector('table')

        page.screenshot(path="/home/jules/verification/karma_settings.png")
        print("Screenshot saved: karma_settings.png")

        browser.close()

if __name__ == "__main__":
    verify_settings()
