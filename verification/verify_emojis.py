from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Test 1: List Characters (Active)
        try:
            print("Navigating to /characters...")
            page.goto("http://localhost:5000/characters")

            print("Clicking View Sheet...")
            page.click("button[data-bs-target='#modal-123456789-987654321']")

            print("Waiting for modal...")
            page.wait_for_selector("#modal-123456789-987654321", state="visible")

            time.sleep(1)

            # Scroll down in the modal
            # The modal body is likely scrollable
            print("Scrolling modal...")
            # We target the .modal-body inside the active modal
            page.evaluate("document.querySelector('#modal-123456789-987654321 .modal-body').scrollTo(0, 1000)")
            time.sleep(1)

            print("Taking screenshot of list_characters modal...")
            page.screenshot(path="verification/list_characters_modal.png")

        except Exception as e:
            print(f"Error in Test 1: {e}")
            page.screenshot(path="verification/error_list_characters.png")

        # Test 2: Render Character
        try:
            print("Navigating to /render/character/...")
            page.goto("http://localhost:5000/render/character/123456789/987654321")

            print("Scrolling down...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            print("Taking screenshot of render_character...")
            page.screenshot(path="verification/render_character.png")

        except Exception as e:
            print(f"Error in Test 2: {e}")
            page.screenshot(path="verification/error_render_character.png")

        browser.close()

if __name__ == "__main__":
    run()
