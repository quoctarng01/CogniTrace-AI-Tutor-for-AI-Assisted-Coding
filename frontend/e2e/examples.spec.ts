// File: frontend/e2e/examples.spec.ts
// Run with: npx playwright test e2e/examples.spec.ts --reporter=list

import { test, expect } from "@playwright/test";

const BASE = process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3002";

test("browse page loads and shows example cards", async ({ page }) => {
  await page.goto(`${BASE}/examples`);
  await expect(page.locator("h1")).toContainText("Example Library");
  await expect(page.getByRole("button", { name: /all/i })).toBeVisible();
  await page.waitForSelector('[class*="grid"]', { timeout: 10000 });
  const cards = page.locator('[class*="card"]');
  await expect(cards.first()).toBeVisible({ timeout: 10000 });
});

test("category filter updates results", async ({ page }) => {
  await page.goto(`${BASE}/examples`);
  const comprehensionsTab = page.getByRole("button", { name: /comprehensions/i });
  await comprehensionsTab.click();
  await page.waitForURL(/category=comprehensions/, { timeout: 5000 });
  const cards = page.locator('[class*="card"]');
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);
});

test("detail page renders code and save button", async ({ page }) => {
  await page.goto(`${BASE}/examples`);
  await page.waitForSelector('[class*="card"]', { timeout: 10000 });
  await page.locator('[class*="card"]').first().click();
  await page.waitForURL(/\/examples\/.+/, { timeout: 5000 });
  await expect(page.locator("h1")).toBeVisible();
  await expect(page.locator('[class*="codeSection"]')).toBeVisible();
  await expect(page.getByRole("button", { name: /save to my review queue/i })).toBeVisible();
});

test("save button redirects to login for unauthenticated users", async ({ page }) => {
  await page.goto(`${BASE}/examples`);
  await page.waitForSelector('[class*="card"]', { timeout: 10000 });
  await page.locator('[class*="card"]').first().click();
  await page.waitForURL(/\/examples\/.+/, { timeout: 5000 });
  await page.getByRole("button", { name: /save to my review queue/i }).click();
  await page.waitForURL(/\/auth\/login/, { timeout: 5000 });
});
