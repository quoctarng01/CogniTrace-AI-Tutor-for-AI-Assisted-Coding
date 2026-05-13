import { test, expect, Page } from "@playwright/test";

// ─── Configuration ────────────────────────────────────────────────────────────

const TEST_EMAIL = process.env.E2E_TEST_EMAIL;
const TEST_PASSWORD = process.env.E2E_TEST_PASSWORD;
const hasTestCredentials = !!TEST_EMAIL && !!TEST_PASSWORD;

// Timeouts (ms) — named for clarity and easy tuning
const AUTH_TIMEOUT = 15_000;
const NETWORK_TIMEOUT = 10_000;
const ANIMATION_TIMEOUT = 15_000;

// ─── Shared Fixtures ──────────────────────────────────────────────────────────

/**
 * Creates a new authenticated page context.
 * Each test gets its own isolated browser context to prevent session leakage.
 */
async function createAuthenticatedContext(
  browser: import("@playwright/test").Browser
): Promise<import("@playwright/test").BrowserContext | null> {
  if (!hasTestCredentials) return null;

  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    // Credentials are validated by TypeScript
    await page.fill('input[id="email"]', TEST_EMAIL!);
    await page.fill('input[id="password"]', TEST_PASSWORD!);
    await page.click('button[type="submit"]');

    await page.waitForURL("**/dashboard", { timeout: AUTH_TIMEOUT });
    await page.waitForLoadState("networkidle");

    return context;
  } catch {
    await context.close();
    return null;
  }
}

/**
 * Authenticates using the current page instance.
 * Prefer `createAuthenticatedContext` for new tests.
 */
async function authenticateUser(page: Page): Promise<boolean> {
  if (!hasTestCredentials) {
    console.log("⚠️ No E2E_TEST_EMAIL/E2E_TEST_PASSWORD set — skipping auth-dependent tests");
    return false;
  }

  try {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");
    await page.fill('input[id="email"]', TEST_EMAIL!);
    await page.fill('input[id="password"]', TEST_PASSWORD!);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/dashboard", { timeout: AUTH_TIMEOUT });
    await page.waitForLoadState("networkidle");
    return true;
  } catch (error) {
    console.log("⚠️ Auth error:", error);
    return false;
  }
}

/**
 * Captures console errors emitted during page navigation.
 * Must be called BEFORE page.goto() to catch load-time errors.
 */
function captureConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  const listener = (msg: { type: () => string; text: () => string }) => {
    if (msg.type() === "error") errors.push(msg.text());
  };
  page.on("console", listener);
  return errors;
}

// ─── Login Page UI ────────────────────────────────────────────────────────────

test.describe("Login Page UI", () => {
  test("renders all required form elements", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    // Heading
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();

    // Email input
    const emailInput = page.locator('input[id="email"]');
    await expect(emailInput).toBeVisible();
    await expect(emailInput).toHaveAttribute("type", "email");
    await expect(emailInput).toHaveAttribute("autocomplete", "email");

    // Password input
    const passwordInput = page.locator('input[id="password"]');
    await expect(passwordInput).toBeVisible();
    await expect(passwordInput).toHaveAttribute("type", "password");

    // Submit button
    await expect(page.locator('button[type="submit"]')).toBeVisible();

    // Sign up link
    await expect(page.getByRole("link", { name: /create an account/i })).toBeVisible();
  });

  test("shows error message on invalid credentials", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    await page.fill('input[id="email"]', "nonexistent@test123456789.com");
    await page.fill('input[id="password"]', "wrongpassword123");
    await page.click('button[type="submit"]');

    await expect(page.getByText(/invalid email or password/i)).toBeVisible({ timeout: NETWORK_TIMEOUT });
  });

  test("email field accepts and retains typed value", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    const testEmail = "user@example.com";
    await page.fill('input[id="email"]', testEmail);
    await expect(page.locator('input[id="email"]')).toHaveValue(testEmail);
  });

  test("password field accepts and masks input", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    const testPassword = "securepassword";
    await page.fill('input[id="password"]', testPassword);
    await expect(page.locator('input[id="password"]')).toHaveValue(testPassword);
    await expect(page.locator('input[id="password"]')).toHaveAttribute("type", "password");
  });
});

// ─── Sign-Up Page ────────────────────────────────────────────────────────────

test.describe("Sign-Up Page", () => {
  test("sign-up link navigates to signup page", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    await page.getByRole("link", { name: /create an account/i }).click();
    await page.waitForURL("**/auth/signup", { timeout: NETWORK_TIMEOUT });
    // Wait for the page to finish rendering before asserting on content
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /Create your account/i })).toBeVisible();
  });
});

// ─── Authenticated Dashboard ─────────────────────────────────────────────────

test.describe("Authenticated Dashboard", { tag: ["@auth"] }, () => {
  test.beforeEach(async ({ page }) => {
    const authenticated = await authenticateUser(page);
    if (!authenticated) test.skip();
  });

  test.afterEach(async ({ page }) => {
    // Sign out after each test to prevent session leakage
    const signOutBtn = page.getByRole("button", { name: /sign out/i });
    if (await signOutBtn.isVisible().catch(() => false)) {
      await signOutBtn.click();
      await page.waitForURL(/\/auth\/login/, { timeout: NETWORK_TIMEOUT }).catch(() => {});
    }
  });

  test("loads dashboard with main sections", async ({ page }) => {
    await expect(page.url()).toContain("/dashboard");
    await expect(page.getByRole("heading", { name: "My Traces" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  });

  test("shows user email in header", async ({ page }) => {
    await expect(page.locator('[class*="userEmail"]')).toBeVisible();
  });

  test("sign out button is present", async ({ page }) => {
    await expect(page.getByRole("button", { name: /sign out/i })).toBeVisible();
  });

  test("sign out clears session and redirects to login", async ({ page }) => {
    await page.getByRole("button", { name: /sign out/i }).click();
    await page.waitForURL(/\/auth\/login/, { timeout: NETWORK_TIMEOUT });

    // Verify unauthenticated state by attempting to access dashboard
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test("streak badge is visible in Review Queue section", async ({ page }) => {
    const reviewSection = page.locator("section").filter({ hasText: /Review Queue/i });
    await expect(reviewSection).toBeVisible();

    const hasStreakContent = await reviewSection.getByText(/streak|Start/i).isVisible().catch(() => false);
    const hasBadgeArea = await reviewSection.locator('[class*="streakBadge"]').isVisible().catch(() => false);
    expect(hasStreakContent || hasBadgeArea).toBeTruthy();
  });

  test("shows review cards or empty state (not both missing)", async ({ page }) => {
    // Wait for dashboard to finish loading (not just network idle — React state update needed)
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/Loading dashboard/i)).not.toBeVisible({ timeout: 5000 }).catch(() => {});

    const hasReviewCards = await page.getByRole("link", { name: /Review Now/i }).isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/No reviews due/i).isVisible().catch(() => false);
    expect(hasReviewCards || hasEmptyState).toBeTruthy();
  });

  test("no critical console errors on dashboard load", async ({ page }) => {
    // Start fresh — go directly without prior navigation
    const errors = captureConsoleErrors(page);
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // Filter out known non-critical noise
    // - Warning: Next.js dev warnings
    // - NEXT_REDIRECT: Internal Next.js redirects
    // - ERR_CONNECTION_REFUSED: Backend API not running in test environment
    const criticalErrors = errors.filter(
      (e) =>
        !e.includes("Warning:") &&
        !e.includes("NEXT_REDIRECT") &&
        !e.includes("ERR_CONNECTION_REFUSED")
    );
    expect(criticalErrors).toHaveLength(0);
  });
});

// ─── Review Flow ──────────────────────────────────────────────────────────────

test.describe("Review Flow", { tag: ["@auth", "@review"] }, () => {
  test.beforeEach(async ({ page }) => {
    const authenticated = await authenticateUser(page);
    if (!authenticated) test.skip();
  });

  test.afterEach(async ({ page }) => {
    const signOutBtn = page.getByRole("button", { name: /sign out/i });
    if (await signOutBtn.isVisible().catch(() => false)) {
      await signOutBtn.click();
      await page.waitForURL(/\/auth\/login/, { timeout: NETWORK_TIMEOUT }).catch(() => {});
    }
  });

  test("authenticated user can navigate to a review card", async ({ page }) => {
    const reviewBtn = page.getByRole("link", { name: /Review Now/i });

    const hasReviews = await reviewBtn.isVisible().catch(() => false);
    if (!hasReviews) test.skip();

    await reviewBtn.click();
    await page.waitForURL(/\/review\/.+/, { timeout: NETWORK_TIMEOUT });

    // Should NOT be on login
    await expect(page.url()).not.toContain("/auth/login");
  });

  test("review page shows SM-2 rating buttons after animation", async ({ page }) => {
    const reviewBtn = page.getByRole("link", { name: /Review Now/i });
    const hasReviews = await reviewBtn.isVisible().catch(() => false);
    if (!hasReviews) test.skip();

    await reviewBtn.click();
    await page.waitForURL(/\/review\/.+/, { timeout: NETWORK_TIMEOUT });

    // Wait for animation to finish — SM-2 rating buttons appear after
    await expect(page.getByText("How well did you understand this?")).toBeVisible({
      timeout: ANIMATION_TIMEOUT,
    });

    // All four SM-2 rating buttons must be present
    await expect(page.getByRole("button", { name: /^Again$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Hard$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Good$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Easy$/ })).toBeVisible();
  });

  test("submitting a rating shows completion state with next review date", async ({ page }) => {
    const reviewBtn = page.getByRole("link", { name: /Review Now/i });
    const hasReviews = await reviewBtn.isVisible().catch(() => false);
    if (!hasReviews) test.skip();

    await reviewBtn.click();
    await page.waitForURL(/\/review\/.+/, { timeout: NETWORK_TIMEOUT });

    // Wait for rating UI
    await expect(page.getByText("How well did you understand this?")).toBeVisible({
      timeout: ANIMATION_TIMEOUT,
    });

    // Submit "Good" rating
    await page.getByRole("button", { name: /^Good$/ }).click();

    // Completion state should appear
    await expect(page.getByText("Review complete!")).toBeVisible({ timeout: 5000 });

    // Next review info should be shown
    await expect(
      page.getByText(/next review|due|day/i)
    ).toBeVisible({ timeout: 5000 });

    // "Back to Dashboard" navigation should be available
    await expect(page.getByRole("button", { name: /back to dashboard/i })).toBeVisible();
  });

  test("back to dashboard navigation works after review submission", async ({ page }) => {
    const reviewBtn = page.getByRole("link", { name: /Review Now/i });
    const hasReviews = await reviewBtn.isVisible().catch(() => false);
    if (!hasReviews) test.skip();

    await reviewBtn.click();
    await page.waitForURL(/\/review\/.+/, { timeout: NETWORK_TIMEOUT });

    await expect(page.getByText("How well did you understand this?")).toBeVisible({
      timeout: ANIMATION_TIMEOUT,
    });
    await page.getByRole("button", { name: /^Good$/ }).click();
    await expect(page.getByText("Review complete!")).toBeVisible({ timeout: 5000 });

    await page.getByRole("button", { name: /back to dashboard/i }).click();
    await page.waitForURL(/\/dashboard/, { timeout: NETWORK_TIMEOUT });

    await expect(page.getByRole("heading", { name: "My Traces" })).toBeVisible();
  });
});

// ─── Route Protection ─────────────────────────────────────────────────────────

test.describe("Route Protection", () => {
  test("unauthenticated user redirected from dashboard to login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test("unauthenticated user redirected from review page to login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/review/some-card-id");
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test("tracer page is publicly accessible without authentication", async ({ page }) => {
    await page.context().clearCookies();
    const errors = captureConsoleErrors(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator("body")).toBeVisible();

    // Should have code input (textarea or contenteditable)
    await expect(page.locator("textarea, [contenteditable]").first()).toBeVisible();

    // No critical errors on public page
    const criticalErrors = errors.filter(
      (e) => !e.includes("Warning:") && !e.includes("NEXT_REDIRECT")
    );
    expect(criticalErrors).toHaveLength(0);
  });
});

// ─── Test Environment ────────────────────────────────────────────────────────

test.describe("Test Environment", () => {
  test("frontend app loads without crashing", async ({ page }) => {
    const errors = captureConsoleErrors(page);
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator("body")).toBeVisible();

    // Verify env vars are accessible (app doesn't crash on missing vars)
    const criticalErrors = errors.filter(
      (e) => !e.includes("Warning:") && !e.includes("NEXT_REDIRECT")
    );
    if (criticalErrors.length > 0) {
      console.log("Console errors:", criticalErrors);
    }
  });
});
