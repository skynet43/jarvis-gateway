import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto("http://127.0.0.1:8765/dashboard")
    page.locator("#token").fill(os.environ["JARVIS_ADMIN_TOKEN"])
    page.get_by_role("button",name="Refresh").click()
    page.get_by_text("Connected",exact=True).wait_for(timeout=10000)
    prompt="Browser cancellation acceptance "+os.urandom(4).hex()
    page.locator("#prompt").fill(prompt)
    page.get_by_role("button",name="Queue task").click()
    row=page.locator("#jobs p").filter(has_text=prompt)
    row.wait_for(timeout=10000)
    row.get_by_role("button",name="Cancel").click()
    page.locator("#jobs p").filter(has_text=prompt).get_by_text("cancelled").wait_for(timeout=10000)
    print("BROWSER_CANCEL_PASS")
    browser.close()
