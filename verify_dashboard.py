from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # 1. Login
    page.goto("http://localhost:5000/login")
    page.fill('input[name="password"]', "changeme")
    page.click('button[type="submit"]')

    # 2. Wait for admin dashboard
    page.wait_for_url("http://localhost:5000/admin")

    # 3. Screenshot
    page.screenshot(path="admin_dashboard_screenshot.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
