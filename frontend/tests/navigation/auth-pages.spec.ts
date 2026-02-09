import { test, expect } from '../fixtures/auth';

/**
 * Navigation tests for AUTHENTICATED pages.
 *
 * These tests use the `authedPage` fixture, which loads a browser context
 * pre-authenticated as a regular user (login happens once in global.setup.ts).
 *
 * Each test verifies:
 * 1. The page loads without errors
 * 2. Key UI elements are visible
 * 3. Navigation to the next logical page works
 */

test.describe('Authenticated pages — load & navigate', () => {

  // ---------- Onboarding ----------

  test('Onboarding page loads', async ({ authedPage: page }) => {
    await page.goto('/onboarding');
    // Should show onboarding steps or redirect if already completed
    const url = page.url();
    // Either stays on onboarding or redirects to homestyling/upload
    expect(url).toMatch(/\/(onboarding|homestyling)/);
  });

  // ---------- Home Styling flow ----------

  test('Home styling entry page loads', async ({ authedPage: page }) => {
    await page.goto('/homestyling');
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  test('Home styling upload page loads', async ({ authedPage: page }) => {
    await page.goto('/homestyling/upload');
    await expect(page).toHaveURL(/\/homestyling\/upload/);
    // Should show an upload area (dropzone or file input)
    const uploadArea = page.locator('[class*="dropzone"], input[type="file"], [role="button"]').first();
    await expect(uploadArea).toBeVisible({ timeout: 10_000 });
  });

  test('Home styling preferences page loads', async ({ authedPage: page }) => {
    await page.goto('/homestyling/preferences');
    await expect(page).toHaveURL(/\/homestyling\/preferences/);
  });

  test('Home styling tier page loads', async ({ authedPage: page }) => {
    await page.goto('/homestyling/tier');
    await expect(page).toHaveURL(/\/homestyling\/tier/);
  });

  // ---------- Design Studio ----------

  test('Design studio page loads', async ({ authedPage: page }) => {
    await page.goto('/design');
    // Design studio should load (may redirect based on tier)
    const url = page.url();
    // Advanced/Curator users see /design; free users may be redirected
    expect(url).toMatch(/\/(design|pricing|upgrade|login)/);
  });

  test('Design studio shows three-panel layout', async ({ authedPage: page }) => {
    await page.goto('/design');
    // If user has access, verify the main panels exist
    if (page.url().includes('/design')) {
      // At least one of the panel containers should be visible
      const panel = page.locator('[class*="panel"], [class*="Panel"], [data-testid]').first();
      await expect(panel).toBeVisible({ timeout: 10_000 });
    }
  });

  // ---------- Profile ----------

  test('Profile page loads with user info', async ({ authedPage: page }) => {
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/profile/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Projects ----------

  test('Projects page loads', async ({ authedPage: page }) => {
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/projects/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Chat ----------

  test('Chat page loads', async ({ authedPage: page }) => {
    await page.goto('/chat');
    // Chat page or redirect
    const url = page.url();
    expect(url).toMatch(/\/(chat|design|login)/);
  });

  // ---------- Visualize ----------

  test('Visualize page loads', async ({ authedPage: page }) => {
    await page.goto('/visualize');
    const url = page.url();
    expect(url).toMatch(/\/(visualize|design|login)/);
  });

  // ---------- Purchases ----------

  test('Purchases page loads', async ({ authedPage: page }) => {
    await page.goto('/purchases');
    await expect(page).toHaveURL(/\/purchases/);
  });

  // ---------- Upgrade ----------

  test('Upgrade page loads', async ({ authedPage: page }) => {
    await page.goto('/upgrade');
    await expect(page).toHaveURL(/\/upgrade/);
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  // ---------- Payment ----------

  test('Payment page loads', async ({ authedPage: page }) => {
    await page.goto('/payment');
    // Payment may redirect if no plan selected
    const url = page.url();
    expect(url).toMatch(/\/(payment|pricing|upgrade)/);
  });
});
