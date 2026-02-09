import { test as setup, expect } from '@playwright/test';
import path from 'path';

/**
 * Global setup: runs ONCE before all test suites.
 *
 * It logs in as a regular user and an admin user, then saves their browser
 * state (cookies + localStorage) to JSON files. Later test files load these
 * files via storageState so every test starts already authenticated — no
 * need to fill the login form each time.
 *
 * Credentials come from environment variables so they stay out of source code.
 */

const USER_STATE_PATH = path.join(__dirname, 'fixtures/.auth-user.json');
const ADMIN_STATE_PATH = path.join(__dirname, 'fixtures/.auth-admin.json');

setup('authenticate as user', async ({ page }) => {
  const email = process.env.TEST_USER_EMAIL;
  const password = process.env.TEST_USER_PASSWORD;

  if (!email || !password) {
    console.warn(
      'TEST_USER_EMAIL / TEST_USER_PASSWORD not set — skipping user auth setup. ' +
      'Tests requiring login will be skipped.'
    );
    return;
  }

  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();

  // Wait for redirect away from /login (confirms successful auth)
  await expect(page).not.toHaveURL(/\/login/);

  await page.context().storageState({ path: USER_STATE_PATH });
});

setup('authenticate as admin', async ({ page }) => {
  const email = process.env.TEST_ADMIN_EMAIL;
  const password = process.env.TEST_ADMIN_PASSWORD;

  if (!email || !password) {
    console.warn(
      'TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD not set — skipping admin auth setup. ' +
      'Admin tests will be skipped.'
    );
    return;
  }

  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();

  await expect(page).not.toHaveURL(/\/login/);

  await page.context().storageState({ path: ADMIN_STATE_PATH });
});
