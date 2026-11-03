import readline from "node:readline";
import crypto from "node:crypto";
import path from "node:path";
import { chromium } from "../frontend/node_modules/playwright/index.mjs";

const outputRoot = path.resolve(process.env.JARVIS_BROWSER_OUTPUT || "");
const allowedHosts = new Set((process.env.JARVIS_BROWSER_HOSTS || "").split(",").filter(Boolean));
const sessions = new Map();
let browser;

function requireSession(id) {
  const row = sessions.get(id);
  if (!row) throw new Error("Browser session is missing or closed");
  return row;
}
function safeUrl(value) {
  const parsed = new URL(value);
  if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("HTTP or HTTPS URL required");
  if (parsed.username || parsed.password) throw new Error("URL credentials are forbidden");
  if (!allowedHosts.has(parsed.hostname)) throw new Error("Browser host is not allowed");
  return parsed.href;
}
async function createSession() {
  browser ||= await chromium.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: false });
  const page = await context.newPage();
  page.on("download", download => download.cancel().catch(() => {}));
  const session_id = crypto.randomUUID();
  sessions.set(session_id, { context, page });
  return { session_id };
}
async function navigate(args) {
  const { page } = requireSession(args.session_id);
  await page.goto(safeUrl(args.url), { waitUntil: "domcontentloaded", timeout: 20000 });
  return { url: page.url(), title: (await page.title()).slice(0, 500) };
}
async function snapshot(args) {
  const { page } = requireSession(args.session_id);
  const text = (await page.locator("body").innerText({ timeout: 10000 })).slice(0, 12000);
  return { url: page.url(), title: (await page.title()).slice(0, 500), text };
}
function locatorFor(page, args) {
  if (args.selector) {
    if (args.selector.length > 300 || /[\n\r{};]/.test(args.selector)) throw new Error("Selector is not allowed");
    return page.locator(args.selector).first();
  }
  if (!args.role || !args.name) throw new Error("Role and accessible name are required");
  return page.getByRole(args.role, { name: args.name, exact: true }).first();
}
async function click(args) {
  const { page } = requireSession(args.session_id);
  const locator = locatorFor(page, args);
  const type = (await locator.getAttribute("type") || "").toLowerCase();
  if (type === "file" || await locator.getAttribute("download") !== null) throw new Error("Upload or download controls are blocked");
  await locator.click({ timeout: 10000 });
  return { status: "clicked" };
}
async function fill(args) {
  if (typeof args.text !== "string" || args.text.length > 4000) throw new Error("Text exceeds limit");
  const { page } = requireSession(args.session_id);
  const locator = locatorFor(page, args);
  const attrs = [
    await locator.getAttribute("type"), await locator.getAttribute("name"),
    await locator.getAttribute("id"), await locator.getAttribute("autocomplete"),
  ].join(" ").toLowerCase();
  if (/password|passcode|credit|card|cc-|cvc|cvv|otp|one-time|recovery|secret|token/.test(attrs)) {
    throw new Error("Sensitive text fields are blocked");
  }
  await locator.fill(args.text, { timeout: 10000 });
  return { status: "filled" };
}
async function screenshot(args) {
  const { page } = requireSession(args.session_id);
  const file = path.resolve(outputRoot, "browser-" + crypto.randomUUID() + ".png");
  if (path.dirname(file) !== outputRoot) throw new Error("Invalid screenshot path");
  await page.screenshot({ path: file, fullPage: false });
  return { path: file };
}
async function closeSession(args) {
  const row = requireSession(args.session_id);
  sessions.delete(args.session_id);
  await row.context.close();
  return { status: "closed" };
}
const actions = {
  create_session: createSession, navigate, snapshot, click, fill, screenshot,
  close_session: closeSession,
};
async function shutdown() {
  for (const row of sessions.values()) await row.context.close().catch(() => {});
  sessions.clear();
  if (browser) await browser.close().catch(() => {});
}
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  let message;
  try {
    message = JSON.parse(line);
    if (message.action === "shutdown") {
      await shutdown();
      process.stdout.write(JSON.stringify({ id: message.id, ok: true, result: { status: "closed" } }) + "\n");
      break;
    }
    const action = actions[message.action];
    if (!action) throw new Error("Browser action is not allowlisted");
    const result = await action(message.arguments || {});
    process.stdout.write(JSON.stringify({ id: message.id, ok: true, result }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({
      id: message?.id || "", ok: false,
      error: String(error?.message || "Browser action failed").slice(0, 500),
    }) + "\n");
  }
}
await shutdown();
