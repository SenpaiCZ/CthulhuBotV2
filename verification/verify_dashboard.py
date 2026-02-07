from playwright.sync_api import sync_playwright, expect
import re

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Login
    print("Navigating to login page...")
    page.goto("http://127.0.0.1:5000/login")
    page.fill("input[name='password']", "changeme")
    page.click("button[type='submit']")
    expect(page).to_have_url("http://127.0.0.1:5000/admin")
    print("Logged in successfully.")

    # Verify Monsters
    print("Navigating to Monsters...")
    page.goto("http://127.0.0.1:5000/admin/monsters")
    expect(page).to_have_title(re.compile("Monsters"))

    # Check for search input
    search_input = page.locator("#searchInput")
    expect(search_input).to_be_visible()

    # Search for "Abhoth"
    search_input.fill("Abhoth")
    page.wait_for_timeout(500) # Wait for filtering

    # Check if "Adherent" is hidden
    adherent = page.get_by_text("Adherent of the Unpeakable Oath")
    expect(adherent).not_to_be_visible()
    print("Filter verified: Adherent is hidden.")

    # Select the specific list item
    spawn_item = page.locator(".monster-list-item").filter(has_text="Spawn of Abhoth").first
    spawn_item.click()

    # Check active class
    expect(spawn_item).to_have_class(re.compile(r"active"))
    print("Item clicked and active class verified.")

    page.screenshot(path="verification/monsters_screenshot_filtered.png")
    print("Monsters screenshot taken.")

    # Verify Deities
    print("Navigating to Deities...")
    page.goto("http://127.0.0.1:5000/admin/deities")
    expect(page).to_have_title(re.compile("Deities"))

    search_input = page.locator("#searchInput")
    expect(search_input).to_be_visible()
    search_input.fill("Cthulhu")
    page.wait_for_timeout(500)

    # Click first available item
    first_deity = page.locator(".monster-list-item:not(.hidden)").first
    if first_deity.count() > 0:
        first_deity.click()
        expect(first_deity).to_have_class(re.compile(r"active"))

    page.screenshot(path="verification/deities_screenshot.png")
    print("Deities screenshot taken.")

    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
