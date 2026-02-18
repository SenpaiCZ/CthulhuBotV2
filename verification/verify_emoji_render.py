from playwright.sync_api import sync_playwright
import os

def verify_emoji(page):
    # Navigate to the render route for a monster
    url = "http://127.0.0.1:5000/render/monster?name=Spawn%20of%20Abhoth"
    print(f"Navigating to {url}")
    page.goto(url)

    # Check for Twemoji image presence
    # STR should map to :muscle: -> Twemoji
    # We look for img with src containing twemoji
    print("Checking for Twemoji images...")

    # Wait for any image to load
    page.wait_for_selector('img.discord-emoji')

    images = page.query_selector_all('img.discord-emoji')
    if not images:
        print("FAIL: No discord-emoji images found.")
    else:
        found_twemoji = False
        for img in images:
            src = img.get_attribute('src')
            if 'twemoji' in src:
                found_twemoji = True
                print(f"Found Twemoji: {src}")
                break

        if found_twemoji:
            print("PASS: Twemoji image found.")
        else:
            print("FAIL: Discord emoji images found, but no Twemoji images.")

    # Screenshot
    page.screenshot(path="verification/verification.png")
    print("Screenshot saved to verification/verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            verify_emoji(page)
        finally:
            browser.close()
