from playwright.sync_api import sync_playwright
import os
import time

def verify_notification():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 800, 'height': 400})

        # Test 1: Rank Up
        print("Testing Rank Up...")
        page.goto("http://127.0.0.1:5000/render/karma/123/456?rank=Grand%20Wizard&type=up")
        try:
            page.wait_for_selector('.karma-card', timeout=5000)
        except Exception as e:
            print(f"Failed to find .karma-card (Up): {e}")

        page.screenshot(path="/home/jules/verification/notification_up.png")
        print("Screenshot saved: notification_up.png")

        # Test 2: Rank Down
        print("Testing Rank Down...")
        page.goto("http://127.0.0.1:5000/render/karma/123/456?rank=Novice&type=down")
        try:
            page.wait_for_selector('.karma-card', timeout=5000)
        except Exception as e:
             print(f"Failed to find .karma-card (Down): {e}")

        page.screenshot(path="/home/jules/verification/notification_down.png")
        print("Screenshot saved: notification_down.png")

        browser.close()

if __name__ == "__main__":
    if not os.path.exists("/home/jules/verification"):
        os.makedirs("/home/jules/verification")
    verify_notification()
