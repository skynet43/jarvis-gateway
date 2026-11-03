import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const headers = { "X-Jarvis-Token": process.env.JARVIS_ACCEPTANCE_TOKEN! };
async function login(page: Page) {
  await page.addInitScript(() =>
    localStorage.setItem("jarvis-tour-done", "true"),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByText("Workspace ready", { exact: true }),
  ).toBeVisible({ timeout: 20000 });
}
test("focused guided tour", async ({ page }) => {
  await page.goto("/dashboard");
  const dialog = page.getByRole("dialog", { name: "Welcome to Jarvis" });
  await expect(dialog).toBeVisible();
  await expect(page.locator("#brand")).toHaveClass(/tour-focus/);
  await dialog.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.locator("#auth")).toHaveClass(/tour-focus/);
  await expect(
    dialog.getByRole("heading", { name: "Ready when you are" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await page.getByRole("button", { name: /Need a hand/ }).click();
  await page.getByRole("button", { name: "Replay tour" }).click();
  await expect(dialog).toBeVisible();
});
test("expired browser session renews without a token prompt", async ({ page }) => {
  await login(page);
  await page.context().addCookies([{name:"jarvis_browser_session",value:"expired.invalid",url:"http://127.0.0.1:8766",httpOnly:true,sameSite:"Strict"}]);
  await page.getByRole("button",{name:"Refresh",exact:true}).click();
  await expect.poll(async()=> (await page.context().cookies()).find((c)=>c.name==="jarvis_browser_session")?.value).not.toBe("expired.invalid");
  await expect(page.getByText("Workspace ready",{exact:true})).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
test("auth, screens, accessibility and mobile layout", async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("jarvis-tour-done", "true"),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByText("Workspace ready", { exact: true }),
  ).toBeVisible({ timeout: 20000 });
  for (const name of [
    "Overview",
    "Agents",
    "Tasks",
    "Activity",
    "Models",
    "Connections",
    "Security",
    "Settings",
  ]) {
    await page
      .getByRole("navigation")
      .getByRole("button", { name, exact: true })
      .click();
    await page.screenshot({
      path: "../work/screenshots/" + name.toLowerCase() + ".png",
      fullPage: true,
    });
  }
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(
    scan.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Overview", exact: true })
    .click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../work/screenshots/android.png",
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByText("Workspace ready", { exact: true })).toBeVisible();
});
test("real inference result and persistence", async ({ page, request }) => {
  await login(page);
  await page.getByRole("button", { name: "New task", exact: true }).click();
  await page
    .getByLabel("What would you like done?")
    .fill("Reply with exactly READY. No explanation.");
  await page.getByRole("button", { name: "Queue task", exact: true }).click();
  const row = page
    .locator(".task-row")
    .filter({ hasText: "Reply with exactly READY" });
  await expect(row).toBeVisible();
  await row.click();
  await expect(page.getByRole("dialog").locator(".badge")).toHaveText(
    "completed",
    { timeout: 150000 },
  );
  await expect(page.getByRole("dialog").locator("pre")).toContainText("READY");
  const list = await (await request.get("/control/jobs", { headers })).json();
  expect(
    list.find((j: { prompt: string }) =>
      j.prompt.startsWith("Reply with exactly READY"),
    ).result,
  ).toContain("READY");
  await page.reload();
  await expect(page.getByText("Workspace ready", { exact: true })).toBeVisible();
  await expect(
    page.locator(".task-row").filter({ hasText: "Reply with exactly READY" }),
  ).toBeVisible();
});
test("queued and running cancellation in browser", async ({
  page,
  request,
}) => {
  await login(page);
  const blockers = [];
  for (let i = 0; i < 8; i++) {
    const response = await request.post("/control/jobs", {
      headers,
      data: {
        agent: "rosie",
        prompt:
          "Acceptance blocker " +
          i +
          ": Print every integer from 1 through 10000 on its own line. Do not summarize or skip numbers. Begin immediately.",
      },
    });
    expect(response.ok()).toBe(true);
    blockers.push(await response.json());
  }
  await page.getByRole("button", { name: "New task", exact: true }).click();
  await page
    .getByLabel("What would you like done?")
    .fill("Queued cancellation browser check");
  await page.getByRole("button", { name: "Queue task", exact: true }).click();
  await page
    .locator(".task-row")
    .filter({ hasText: "Queued cancellation browser check" })
    .click();
  await expect(page.getByRole("dialog").locator(".badge")).toHaveText("queued");
  const cancelled = page.waitForResponse(
    (r) => r.url().endsWith("/cancel") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Cancel task", exact: true }).click();
  expect((await cancelled).status()).toBe(200);
  await expect(page.getByRole("dialog").locator(".badge")).toHaveText(
    "cancelled",
    { timeout: 10000 },
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  let cancelledRunning: { id: string; prompt: string } | undefined;
  for (let attempt = 0; attempt < blockers.length; attempt++) {
    const list = await (await request.get("/control/jobs", { headers })).json();
    const running = list.find(
      (j: { status: string; prompt: string }) =>
        j.status === "running" && j.prompt.startsWith("Acceptance blocker"),
    );
    if (!running) {
      await page.waitForTimeout(250);
      continue;
    }
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await page.locator(".task-row").filter({ hasText: running.prompt }).click();
    const stopped = page.waitForResponse(
      (r) => r.url().endsWith("/cancel") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Cancel task", exact: true }).click();
    if ((await stopped).status() === 200) {
      cancelledRunning = running;
      break;
    }
    await page.getByRole("button", { name: "Close", exact: true }).click();
  }
  expect(cancelledRunning).toBeTruthy();
  await expect(page.getByRole("dialog").locator(".badge")).toHaveText(
    "cancelled",
    { timeout: 15000 },
  );
  const job = await (
    await request.get("/control/jobs/" + cancelledRunning!.id, { headers })
  ).json();
  expect(job.stream_closed).toBeTruthy();
  await request.post("/control/stop", { headers, data: {} });
});
test("approved runtime executes a real file tool", async ({
  page,
  request,
}) => {
  await login(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Connections", exact: true })
    .click();
  await page.getByLabel("Approved workspace").selectOption({ index: 1 });
  await page
    .getByLabel("Goal", { exact: true })
    .fill(
      "Use read_workspace_file to read README.md, then state the project name from the file in one sentence. You must call the tool before answering.",
    );
  await page.getByRole("button", { name: "Create approval request" }).click();
  await expect(
    page.getByRole("button", { name: "Approve session" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve session" }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/control/sessions", { headers })).json())[0]
          ?.status,
      { timeout: 160000, intervals: [1000, 2000, 5000] },
    )
    .toBe("completed");
  const sessions = await (
    await request.get("/control/sessions", { headers })
  ).json();
  const events = await (
    await request.get("/control/sessions/" + sessions[0].id + "/events", {
      headers,
    })
  ).json();
  expect(
    events.some(
      (e: { kind: string; details: string }) =>
        e.kind === "tool_call" && JSON.parse(e.details).outcome === "ok",
    ),
  ).toBe(true);
  expect(sessions[0].result).toMatch(/Jarvis/i);
});
test("help and safe output rendering", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: /Need a hand/ }).click();
  await page.getByLabel("Search help").fill("stop");
  await expect(page.getByText("How do I stop a task?")).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.route("**/control/jobs?*", async (route) =>
    route.fulfill({
      json: [
        {
          id: "xss-test",
          agent: "rosie",
          prompt: "Render safety check",
          status: "completed",
          created: new Date().toISOString(),
          result: '<img src=x onerror="window.XSS=true">',
          started: null,
          finished: null,
          updated: null,
          error: null,
          stream_closed: null,
        },
      ],
    }),
  );
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page
    .locator(".task-row")
    .filter({ hasText: "Render safety check" })
    .click();
  await expect(page.getByRole("dialog").locator("pre")).toContainText("<img");
  expect(await page.evaluate(() => Object.hasOwn(window, "XSS"))).toBe(false);
});
