import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto("http://127.0.0.1:8765/dashboard")
    assert page.title()=="Jarvis Command Center"
    assert page.locator("#agent option").count()==3
    page.locator("#token").fill(os.environ["JARVIS_ADMIN_TOKEN"])
    page.get_by_role("button",name="Refresh").click()
    page.get_by_text("Connected",exact=True).wait_for(timeout=10000)
    page.locator("#prompt").fill("Browser acceptance test")
    page.get_by_role("button",name="Queue task").click()
    page.get_by_text("Browser acceptance test").first.wait_for(timeout=10000)
    print("BROWSER_DASHBOARD_PASS")
    browser.close()
