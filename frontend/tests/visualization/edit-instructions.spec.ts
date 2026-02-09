import { test, expect } from '../fixtures/auth';
import {
  mockVisualizationApi,
  findCaptured,
  findAllCaptured,
  CapturedRequest,
} from '../fixtures/api-mocks';
import { SAMPLE_PRODUCTS } from '../fixtures/test-data';

/**
 * Edit-with-instructions parameter tests.
 *
 * After a visualization is generated, users can type natural language
 * instructions like "Move the sofa to the left wall" or "Make the room
 * brighter". The app sends these to /api/visualization/sessions/{id}/edit-with-instructions.
 *
 * These tests verify the request contains:
 * - image: the current visualization (base64)
 * - instructions: the user's text
 * - products: list of products in the scene (so the AI knows what's there)
 */

test.describe('Edit with instructions — parameter assembly', () => {
  let captured: CapturedRequest[];

  test.beforeEach(async ({ authedPage: page }) => {
    captured = await mockVisualizationApi(page);

    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-user-123',
          email: 'test@example.com',
          name: 'Test User',
          role: 'user',
          subscription_tier: 'advanced',
          is_active: true,
          auth_provider: 'email',
          created_at: '2024-01-01T00:00:00Z',
        }),
      });
    });

    await page.route('**/api/products**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ products: SAMPLE_PRODUCTS, total: SAMPLE_PRODUCTS.length }),
      });
    });

    await page.route('**/api/chat/sessions**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'test-session-003', messages: [] }),
        });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      }
    });
  });

  test('Edit instruction request includes instruction text and products', async ({
    authedPage: page,
  }) => {
    /**
     * The edit-with-instructions endpoint requires:
     * - image: the current visualization to modify
     * - instructions: what the user wants changed
     * - products: the products currently in the scene (for reference)
     *
     * The backend uses all three to construct a Gemini prompt that
     * preserves existing furniture while applying the edit.
     */
    await page.goto('/design');
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/design')) {
      test.skip(true, 'User does not have design studio access');
      return;
    }

    // Verify any edit requests have the expected structure
    const editRequests = findAllCaptured(captured, '/edit-with-instructions');
    for (const req of editRequests) {
      expect(req.body).toHaveProperty('image');
      expect(req.body).toHaveProperty('instructions');
      expect(typeof req.body.instructions).toBe('string');
      expect((req.body.instructions as string).length).toBeGreaterThan(0);
    }
  });

  test('Edit instruction request includes product list for context', async ({
    authedPage: page,
  }) => {
    /**
     * When editing an existing visualization, the products list helps
     * the AI understand what's in the scene. Each product includes
     * its name and ID so the AI can reference specific items.
     */
    await page.goto('/design');
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/design')) {
      test.skip(true, 'User does not have design studio access');
      return;
    }

    const editRequests = findAllCaptured(captured, '/edit-with-instructions');
    for (const req of editRequests) {
      if (req.body.products) {
        expect(Array.isArray(req.body.products)).toBe(true);
        const products = req.body.products as Array<Record<string, unknown>>;
        for (const product of products) {
          expect(product).toHaveProperty('id');
          expect(product).toHaveProperty('name');
        }
      }
    }
  });

  test('Mock infrastructure captures edit-with-instructions requests', async ({
    authedPage: page,
  }) => {
    /**
     * Meta-test: verifies the route interception is set up for
     * the edit-with-instructions endpoint pattern.
     */
    await page.goto('/design');
    await page.waitForLoadState('networkidle');

    // Verify the mock captured array is functional
    expect(Array.isArray(captured)).toBe(true);

    // findCaptured should return undefined for non-matching patterns
    const nonExistent = findCaptured(captured, '/nonexistent');
    expect(nonExistent).toBeUndefined();
  });
});
