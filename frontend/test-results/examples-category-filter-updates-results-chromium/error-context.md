# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: examples.spec.ts >> category filter updates results
- Location: e2e\examples.spec.ts:17:5

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.click: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: /comprehensions/i })

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - banner [ref=e3]:
      - link "← Dashboard" [ref=e4] [cursor=pointer]:
        - /url: /dashboard
      - heading "Example Library" [level=1] [ref=e5]
    - main [ref=e6]:
      - paragraph [ref=e7]:
        - text: Curated AI-generated Python patterns. Each example explains
        - emphasis [ref=e8]: why
        - text: AI writes this code. Save any example to your review queue.
      - button "All" [ref=e10] [cursor=pointer]
      - generic [ref=e11]:
        - generic [ref=e12]: ⚠
        - text: Failed to fetch
        - button "Retry" [ref=e13] [cursor=pointer]
  - button "Open Next.js Dev Tools" [ref=e19] [cursor=pointer]:
    - img [ref=e20]
  - alert [ref=e23]
```

# Test source

```ts
  1  | // File: frontend/e2e/examples.spec.ts
  2  | // Run with: npx playwright test e2e/examples.spec.ts --reporter=list
  3  | 
  4  | import { test, expect } from "@playwright/test";
  5  | 
  6  | const BASE = process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3002";
  7  | 
  8  | test("browse page loads and shows example cards", async ({ page }) => {
  9  |   await page.goto(`${BASE}/examples`);
  10 |   await expect(page.locator("h1")).toContainText("Example Library");
  11 |   await expect(page.getByRole("button", { name: /all/i })).toBeVisible();
  12 |   await page.waitForSelector('[class*="grid"]', { timeout: 10000 });
  13 |   const cards = page.locator('[class*="card"]');
  14 |   await expect(cards.first()).toBeVisible({ timeout: 10000 });
  15 | });
  16 | 
  17 | test("category filter updates results", async ({ page }) => {
  18 |   await page.goto(`${BASE}/examples`);
  19 |   const comprehensionsTab = page.getByRole("button", { name: /comprehensions/i });
> 20 |   await comprehensionsTab.click();
     |                           ^ Error: locator.click: Test timeout of 90000ms exceeded.
  21 |   await page.waitForURL(/category=comprehensions/, { timeout: 5000 });
  22 |   const cards = page.locator('[class*="card"]');
  23 |   const count = await cards.count();
  24 |   expect(count).toBeGreaterThan(0);
  25 | });
  26 | 
  27 | test("detail page renders code and save button", async ({ page }) => {
  28 |   await page.goto(`${BASE}/examples`);
  29 |   await page.waitForSelector('[class*="card"]', { timeout: 10000 });
  30 |   await page.locator('[class*="card"]').first().click();
  31 |   await page.waitForURL(/\/examples\/.+/, { timeout: 5000 });
  32 |   await expect(page.locator("h1")).toBeVisible();
  33 |   await expect(page.locator('[class*="codeSection"]')).toBeVisible();
  34 |   await expect(page.getByRole("button", { name: /save to my review queue/i })).toBeVisible();
  35 | });
  36 | 
  37 | test("save button redirects to login for unauthenticated users", async ({ page }) => {
  38 |   await page.goto(`${BASE}/examples`);
  39 |   await page.waitForSelector('[class*="card"]', { timeout: 10000 });
  40 |   await page.locator('[class*="card"]').first().click();
  41 |   await page.waitForURL(/\/examples\/.+/, { timeout: 5000 });
  42 |   await page.getByRole("button", { name: /save to my review queue/i }).click();
  43 |   await page.waitForURL(/\/auth\/login/, { timeout: 5000 });
  44 | });
  45 | 
```