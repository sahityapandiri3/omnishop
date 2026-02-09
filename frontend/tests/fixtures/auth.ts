import { test as base, expect, Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Authentication helpers for Playwright tests.
 *
 * How it works:
 * 1. global.setup.ts logs in once and saves browser state to JSON files.
 * 2. Tests that need auth use the custom `test` fixtures below, which load
 *    the saved state so the browser starts with valid tokens in localStorage.
 * 3. If no credentials are configured, tests are auto-skipped (not failed).
 *
 * Usage in a test file:
 *   import { test } from '../fixtures/auth';
 *   test('my protected page test', async ({ authedPage }) => { ... });
 */

const USER_STATE_PATH = path.join(__dirname, '.auth-user.json');
const ADMIN_STATE_PATH = path.join(__dirname, '.auth-admin.json');

function stateFileExists(filePath: string): boolean {
  try {
    return fs.existsSync(filePath) && fs.statSync(filePath).size > 10;
  } catch {
    return false;
  }
}

/**
 * Extended test fixtures that provide pre-authenticated Page objects.
 * - `authedPage`: logged in as a regular user
 * - `adminPage`: logged in as an admin user
 */
export const test = base.extend<{
  authedPage: Page;
  adminPage: Page;
}>({
  authedPage: async ({ browser }, use) => {
    if (!stateFileExists(USER_STATE_PATH)) {
      base.skip(true, 'User auth state not available — set TEST_USER_EMAIL / TEST_USER_PASSWORD');
      return;
    }
    const context = await browser.newContext({ storageState: USER_STATE_PATH });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },

  adminPage: async ({ browser }, use) => {
    if (!stateFileExists(ADMIN_STATE_PATH)) {
      base.skip(true, 'Admin auth state not available — set TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD');
      return;
    }
    const context = await browser.newContext({ storageState: ADMIN_STATE_PATH });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
});

export { expect };
