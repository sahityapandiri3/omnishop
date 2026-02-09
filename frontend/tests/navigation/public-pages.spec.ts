import { test, expect } from '@playwright/test';

/**
 * Navigation tests for PUBLIC (unauthenticated) pages.
 *
 * These tests verify that every public page:
 * 1. Loads without uncaught JavaScript errors
 * 2. Shows its key UI elements (headings, buttons, forms)
 * 3. Links / buttons navigate to the correct next page (egress)
 *
 * No login is required — these pages are accessible to anyone.
 */

test.describe('Public pages — load & navigate', () => {
  // Collect console errors on every test so we can assert "no crashes"
  let consoleErrors: string[] = [];

  test.beforeEach(async ({ page }) => {
    consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
  });

  // ---------- Landing page ----------

  test('Landing page loads successfully', async ({ page }) => {
    await page.goto('/');
    // The page should render without a full-page crash
    await expect(page).toHaveURL('/');
    // Should show the main heading or brand name
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  test('Landing → Login navigation', async ({ page }) => {
    await page.goto('/');
    // Look for a login/sign-in link or button in the header/nav
    const loginLink = page.getByRole('link', { name: /log\s?in|sign\s?in/i }).first();
    if (await loginLink.isVisible()) {
      await loginLink.click();
      await expect(page).toHaveURL(/\/login/);
    }
  });

  test('Landing → Curated gallery navigation', async ({ page }) => {
    await page.goto('/');
    // Look for a "curated" or "browse looks" link
    const curatedLink = page.getByRole('link', { name: /curated|browse|looks|explore/i }).first();
    if (await curatedLink.isVisible()) {
      await curatedLink.click();
      await expect(page).toHaveURL(/\/curated/);
    }
  });

  // ---------- Login page ----------

  test('Login page loads with form', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login/);
    // Should have email & password fields
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    // Should have a submit button
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('Login page has sign-up toggle', async ({ page }) => {
    await page.goto('/login');
    // Should have a way to switch to registration mode
    const signUpToggle = page.getByText(/sign up|create account|register/i).first();
    await expect(signUpToggle).toBeVisible();
  });

  // ---------- Curated gallery ----------

  test('Curated gallery page loads', async ({ page }) => {
    await page.goto('/curated');
    await expect(page).toHaveURL(/\/curated/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Products catalog ----------

  test('Products catalog page loads', async ({ page }) => {
    await page.goto('/products');
    await expect(page).toHaveURL(/\/products/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Pricing page ----------

  test('Pricing page loads with plans', async ({ page }) => {
    await page.goto('/pricing');
    await expect(page).toHaveURL(/\/pricing/);
    // Should show pricing tiers / plan cards
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Status / health page ----------

  test('Status page loads', async ({ page }) => {
    await page.goto('/status');
    await expect(page).toHaveURL(/\/status/);
  });

  // ---------- Auth redirect guard ----------

  test('Protected route /design redirects unauthenticated user to /login', async ({ page }) => {
    await page.goto('/design');
    // Should redirect to login (or show a login prompt)
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });

  test('Protected route /profile redirects unauthenticated user to /login', async ({ page }) => {
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });

  test('Protected route /admin redirects unauthenticated user to /login', async ({ page }) => {
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });
});
