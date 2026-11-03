import { test, expect } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.addInitScript(() => localStorage.setItem("jarvis-tour-done", "true"));
  await page.goto("/dashboard");
  await expect(page.getByText("Workspace ready", { exact: true })).toBeVisible({
    timeout: 20000,
  });
}

test("automation request requires exact one-use approval", async ({ page }) => {
  await login(page);
  await page.getByRole("navigation").getByRole("button", {
    name: "Automation", exact: true,
  }).click();
  await expect(page.getByRole("heading", {
    name: "Request an approved action",
  })).toBeVisible();
  await page.getByLabel("Exact automation arguments").fill('{"limit":5}');
  await page.getByRole("button", { name: "Create approval request" }).click();

  await expect(page.getByRole("heading", {
    name: "Automation approvals",
  })).toBeVisible();
  const approval = page.locator(".session").filter({ hasText: "list_processes" });
  await expect(approval).toContainText("LOW RISK");
  await expect(approval).toContainText('"limit": 5');
  await approval.getByRole("button", { name: "Approve once" }).click();

  await page.getByRole("navigation").getByRole("button", {
    name: "Automation", exact: true,
  }).click();
  const completed = page.locator(".session").filter({ hasText: "list_processes" }).first();
  await expect(completed).toContainText("completed", { timeout: 20000 });
  await expect(completed).toContainText("pid");

  await page.getByLabel("Exact automation arguments").fill("{}");
  await page.getByRole("button", { name: "Create approval request" }).click();
  const second = page.locator(".session").filter({ hasText: "list_processes" }).first();
  await second.getByRole("button", { name: "Reject" }).click();
  await expect(second).not.toBeVisible();
});
