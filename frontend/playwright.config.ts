import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Omnishop E2E tests.
 *
 * Key concepts:
 * - baseURL: All page.goto('/login') calls resolve relative to this URL.
 *   Defaults to localhost:3000 for local dev; override via PLAYWRIGHT_BASE_URL for staging.
 * - storageState: Saves browser cookies/localStorage after login so subsequent
 *   tests skip the login form (faster test runs).
 * - Chromium-only: We start with one browser for speed. Add Firefox/WebKit later
 *   by uncommenting the extra projects below.
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'html' : 'list',

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
  },

  timeout: 30_000,

  projects: [
    // Setup project: runs login once and saves auth state for reuse
    {
      name: 'setup',
      testMatch: /global\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
      dependencies: ['setup'],
    },
    // Uncomment to add more browsers:
    // { name: 'firefox', use: { ...devices['Desktop Firefox'] }, dependencies: ['setup'] },
    // { name: 'webkit',  use: { ...devices['Desktop Safari'] }, dependencies: ['setup'] },
  ],
});
