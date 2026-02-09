import { Page, Route } from '@playwright/test';

/**
 * API mock helpers for Playwright tests.
 *
 * Why mock?
 * - Visualization endpoints call the Gemini AI API, which is slow (~5s), costs
 *   money, and returns non-deterministic results.
 * - By intercepting HTTP requests in the browser, we can:
 *   1. Return instant fake "success" responses so the app behaves normally.
 *   2. Capture the request body so we can assert exactly what parameters the
 *      frontend sent (product IDs, images, surface configs, etc.).
 *
 * How Playwright route interception works:
 *   page.route(pattern, handler)
 *   This tells Playwright: whenever the browser tries to fetch this URL, run
 *   my handler function instead of going to the real server. The handler can
 *   inspect the request and return a custom response.
 */

// A tiny 1x1 transparent PNG encoded as base64.
// Used as the "generated visualization" in mock responses so the app
// has a valid image to display without calling the real AI.
export const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

export const MOCK_VISUALIZATION_IMAGE = `data:image/png;base64,${TINY_PNG_BASE64}`;

/** Stores captured request bodies so tests can assert on them. */
export interface CapturedRequest {
  url: string;
  method: string;
  body: Record<string, unknown>;
  timestamp: number;
}

/**
 * Sets up interception on all visualization-related API endpoints.
 * Returns an array that accumulates every intercepted request body —
 * tests read this array to verify the correct parameters were sent.
 */
export async function mockVisualizationApi(page: Page): Promise<CapturedRequest[]> {
  const captured: CapturedRequest[] = [];

  // --- Product visualization (the main "Visualize" button) ---
  await page.route('**/api/chat/sessions/*/visualize', async (route: Route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    captured.push({
      url: request.url(),
      method: request.method(),
      body,
      timestamp: Date.now(),
    });

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        visualization_image: MOCK_VISUALIZATION_IMAGE,
        products_visualized: body.products || [],
        processing_time: 0.1,
      }),
    });
  });

  // --- Room image upload ---
  await page.route('**/api/visualization/upload-room-image', async (route: Route) => {
    captured.push({
      url: route.request().url(),
      method: route.request().method(),
      body: { _note: 'multipart upload — body not parsed' },
      timestamp: Date.now(),
    });

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        image_data: MOCK_VISUALIZATION_IMAGE,
        filename: 'test-room.jpg',
        size: 1024,
        content_type: 'image/jpeg',
        upload_timestamp: new Date().toISOString(),
        room_analysis: {
          room_type: 'living_room',
          dimensions: { width: 15, length: 12, height: 10 },
          camera_view: 'front',
          existing_furniture: [],
          lighting_conditions: 'natural',
          color_palette: ['#FFFFFF', '#F5F5DC'],
          architectural_features: ['window', 'door'],
          style_assessment: 'modern',
          confidence_score: 0.9,
        },
      }),
    });
  });

  // --- Apply surfaces (wall color, texture, floor tile) ---
  await page.route('**/api/visualization/apply-surfaces', async (route: Route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    captured.push({
      url: request.url(),
      method: request.method(),
      body,
      timestamp: Date.now(),
    });

    const surfacesApplied: string[] = [];
    if (body.wall_color_name) surfacesApplied.push(`wall_color:${body.wall_color_name}`);
    if (body.texture_variant_id) surfacesApplied.push(`texture:${body.texture_variant_id}`);
    if (body.tile_id) surfacesApplied.push(`tile:${body.tile_id}`);

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        rendered_image: MOCK_VISUALIZATION_IMAGE,
        processing_time: 0.05,
        surfaces_applied: surfacesApplied,
      }),
    });
  });

  // --- Edit with instructions ---
  await page.route('**/api/visualization/sessions/*/edit-with-instructions', async (route: Route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    captured.push({
      url: request.url(),
      method: request.method(),
      body,
      timestamp: Date.now(),
    });

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        edited_image: MOCK_VISUALIZATION_IMAGE,
        processing_time: 0.1,
      }),
    });
  });

  // --- Analyze room (used by upload flow) ---
  await page.route('**/api/visualization/analyze-room', async (route: Route) => {
    const request = route.request();
    const body = JSON.parse(request.postData() || '{}');
    captured.push({
      url: request.url(),
      method: request.method(),
      body,
      timestamp: Date.now(),
    });

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        room_type: 'living_room',
        dimensions: { width: 15, length: 12, height: 10 },
        confidence_score: 0.92,
      }),
    });
  });

  return captured;
}

/**
 * Helper to find a specific captured request by URL pattern.
 * Useful in assertions: `findCaptured(captured, '/visualize')`.
 */
export function findCaptured(
  captured: CapturedRequest[],
  urlPattern: string
): CapturedRequest | undefined {
  return captured.find((r) => r.url.includes(urlPattern));
}

/**
 * Helper to find ALL captured requests matching a URL pattern.
 */
export function findAllCaptured(
  captured: CapturedRequest[],
  urlPattern: string
): CapturedRequest[] {
  return captured.filter((r) => r.url.includes(urlPattern));
}
