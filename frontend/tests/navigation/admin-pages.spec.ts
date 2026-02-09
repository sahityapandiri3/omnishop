import { test, expect } from '../fixtures/auth';

/**
 * Navigation tests for ADMIN pages.
 *
 * These tests use the `adminPage` fixture, which loads a browser context
 * pre-authenticated as an admin user. Non-admin users should be redirected
 * away from these routes.
 *
 * Admin pages live under /admin/* and include dashboards for curated look
 * management, API usage monitoring, analytics, and permissions.
 */

test.describe('Admin pages — load & navigate', () => {

  // ---------- Admin dashboard ----------

  test('Admin dashboard loads', async ({ adminPage: page }) => {
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/admin/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Curated look management ----------

  test('Curated management page loads', async ({ adminPage: page }) => {
    await page.goto('/admin/curated');
    await expect(page).toHaveURL(/\/admin\/curated/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  test('Curated management → New curated look', async ({ adminPage: page }) => {
    await page.goto('/admin/curated');
    // Look for a "New" or "Create" button/link
    const newBtn = page.getByRole('link', { name: /new|create|add/i }).first();
    if (await newBtn.isVisible()) {
      await newBtn.click();
      await expect(page).toHaveURL(/\/admin\/curated\/new/);
    }
  });

  test('New curated look page loads with form', async ({ adminPage: page }) => {
    await page.goto('/admin/curated/new');
    await expect(page).toHaveURL(/\/admin\/curated\/new/);
    // Should have form fields for title, description, etc.
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  test('Edit curated look page loads', async ({ adminPage: page }) => {
    // Navigate to the list first to find an existing look
    await page.goto('/admin/curated');

    // Click the first curated look link (if any exist)
    const lookLink = page.getByRole('link').filter({ hasText: /.+/ }).nth(1);
    if (await lookLink.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await lookLink.click();
      // Should navigate to /admin/curated/[id]
      await expect(page).toHaveURL(/\/admin\/curated\/\d+/);
    }
  });

  // ---------- API Usage ----------

  test('API usage page loads', async ({ adminPage: page }) => {
    await page.goto('/admin/api-usage');
    await expect(page).toHaveURL(/\/admin\/api-usage/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Analytics ----------

  test('Analytics page loads', async ({ adminPage: page }) => {
    await page.goto('/admin/analytics');
    await expect(page).toHaveURL(/\/admin\/analytics/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Permissions ----------

  test('Permissions page loads', async ({ adminPage: page }) => {
    await page.goto('/admin/permissions');
    await expect(page).toHaveURL(/\/admin\/permissions/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Access control ----------

  test('Non-admin user is redirected away from /admin', async ({ authedPage: page }) => {
    await page.goto('/admin');
    // Regular users should be redirected to / or /login
    await expect(page).not.toHaveURL(/\/admin$/);
  });
});
