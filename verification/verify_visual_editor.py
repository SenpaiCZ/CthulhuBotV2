from playwright.sync_api import sync_playwright, expect
import time

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Login
    page.goto("http://localhost:5000/login")
    page.fill("input[name='password']", "changeme")
    page.click("button[type='submit']")

    # Wait for redirect
    page.wait_for_url("http://localhost:5000/admin")

    # 2. Go to Edit Page
    page.goto("http://localhost:5000/admin/edit/infodata/test_visual.json")

    # 3. Verify Raw Mode
    expect(page.locator("#rawEditorContainer")).to_be_visible()
    expect(page.locator("#toggleViewBtn")).to_be_visible()

    page.screenshot(path="verification/1_raw_mode.png")
    print("Screenshot 1: Raw Mode")

    # 4. Switch to Visual Mode
    page.click("#toggleViewBtn")

    # Verify Visual Mode
    expect(page.locator("#visualEditorContainer")).to_be_visible()
    expect(page.locator("#rawEditorContainer")).not_to_be_visible()

    # Check Table Content
    # We expect 2 rows
    rows = page.locator("#visualTbody tr")
    expect(rows).to_have_count(2)

    page.screenshot(path="verification/2_visual_mode.png")
    print("Screenshot 2: Visual Mode")

    # 5. Add Row
    page.click("#addRowBtn")
    expect(rows).to_have_count(3)

    # Edit the new row
    # The last row should have an empty input
    last_input = rows.last.locator("input")
    last_input.fill("New Item Added by Playwright")

    page.screenshot(path="verification/3_added_row.png")
    print("Screenshot 3: Added Row")

    # 6. Switch Back to Raw
    page.click("#toggleViewBtn")
    expect(page.locator("#rawEditorContainer")).to_be_visible()

    # Verify the textarea contains the new item
    content = page.locator("#jsonContent").input_value()
    if "New Item Added by Playwright" in content:
        print("Success: New item found in Raw JSON")
    else:
        print("Failure: New item NOT found in Raw JSON")
        print("Content:", content)

    page.screenshot(path="verification/4_back_to_raw.png")

    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
