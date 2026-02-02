/**
 * Visualization Helper Functions
 *
 * Pure utility functions for visualization logic.
 * These are extracted from CanvasPanel to enable code reuse.
 */

import {
  VisualizationProduct,
  ProductForApi,
  ChangeDetectionResult,
  ChangeType,
  QuantityDelta,
  normalizeProductId,
} from '@/types/visualization';

// ============================================================================
// Image Formatting Helpers
// ============================================================================

/**
 * Format image source - handles base64 and URLs
 */
export function formatImageSrc(src: string | null | undefined): string {
  if (!src) return '';
  // If it's already a URL or data URI, return as-is
  if (src.startsWith('http') || src.startsWith('data:')) return src;
  // If it's base64 data (starts with /9j/ for JPEG or iVBOR for PNG), add data URI prefix
  if (src.startsWith('/9j/') || src.startsWith('iVBOR')) {
    const isJpeg = src.startsWith('/9j/');
    return `data:image/${isJpeg ? 'jpeg' : 'png'};base64,${src}`;
  }
  return src;
}

/**
 * Check if image source is base64 or data URI (needs <img> tag, not Next.js Image)
 */
export function isBase64Image(src: string | null | undefined): boolean {
  if (!src) return false;
  return src.startsWith('data:') || src.startsWith('/9j/') || src.startsWith('iVBOR');
}

// ============================================================================
// Product Helpers
// ============================================================================

/**
 * Extract dimensions from product attributes
 */
export function extractDimensions(
  attrs?: Array<{ attribute_name: string; attribute_value: string }>
): { width?: string; height?: string; depth?: string } | undefined {
  if (!attrs) return undefined;
  const dimensions: { width?: string; height?: string; depth?: string } = {};
  for (const attr of attrs) {
    if (attr.attribute_name === 'width') dimensions.width = attr.attribute_value;
    else if (attr.attribute_name === 'height') dimensions.height = attr.attribute_value;
    else if (attr.attribute_name === 'depth') dimensions.depth = attr.attribute_value;
  }
  // Only return if at least one dimension exists
  return (dimensions.width || dimensions.height || dimensions.depth) ? dimensions : undefined;
}

/**
 * Get the primary image URL for a product
 */
export function getProductImageUrl(product: VisualizationProduct): string {
  if (product.image_url) return product.image_url;
  if (product.images && product.images.length > 0) {
    const primaryImage = product.images.find(img => img.is_primary);
    const image = primaryImage || product.images[0];
    return image.medium_url || image.original_url || '';
  }
  return '';
}

/**
 * Format a product for API requests
 */
export function formatProductForApi(product: VisualizationProduct): ProductForApi {
  return {
    id: product.id,
    name: product.name,
    full_name: product.name,
    image_url: product.image_url || getProductImageUrl(product),
    description: product.description || '',
    product_type: product.productType || product.product_type || 'furniture',
    furniture_type: product.productType || product.product_type || 'furniture',
    style: 0.8,
    category: product.productType || product.product_type || 'furniture',
    quantity: product.quantity || 1,
    dimensions: extractDimensions(product.attributes),
  };
}

// ============================================================================
// Change Detection
// ============================================================================

interface DetectChangeTypeParams {
  products: VisualizationProduct[];
  visualizedProductIds: Set<string>;
  visualizedProducts: VisualizationProduct[];
  visualizedQuantities: Map<string, number>;
  visualizationResult: string | null;
}

/**
 * Detect what type of visualization change is needed.
 *
 * This function analyzes the difference between current products and
 * what was previously visualized to determine the optimal visualization strategy:
 * - 'initial': First visualization (nothing visualized yet)
 * - 'additive': New products added (can use incremental visualization)
 * - 'removal': Products removed (use removal mode)
 * - 'remove_and_add': Products both removed and added
 * - 'quantity_decrease': Quantity reduced on existing product
 * - 'reset': Mixed changes requiring full re-visualization
 * - 'no_change': No changes detected
 */
export function detectChangeType({
  products,
  visualizedProductIds,
  visualizedProducts,
  visualizedQuantities,
  visualizationResult,
}: DetectChangeTypeParams): ChangeDetectionResult {
  // Ensure IDs are strings for consistent comparison
  const currentIds = new Set(products.map(p => normalizeProductId(p.id)));

  // CRITICAL FIX: If we have a visualizationResult but visualizedProductIds is empty,
  // this is a sync issue. Use visualizedProducts as the source of truth if available.
  let effectiveVisualizedIds = visualizedProductIds;
  if (visualizationResult && visualizedProductIds.size === 0 && products.length > 0) {
    console.warn('[detectChangeType] visualizedProductIds empty with existing visualization');

    // Try to use visualizedProducts if available
    if (visualizedProducts.length > 0) {
      effectiveVisualizedIds = new Set(visualizedProducts.map(p => normalizeProductId(p.id)));
      console.log('[detectChangeType] Using visualizedProducts as fallback:', effectiveVisualizedIds.size, 'products');
    } else {
      // Last resort: check if there are more products now than were visualized
      console.warn('[detectChangeType] visualizedProducts also empty - cannot detect removals');
      if (currentIds.size === 0) {
        return { type: 'no_change', reason: 'no_products' };
      }
      // Use current products as the baseline
      effectiveVisualizedIds = currentIds;
    }
  }

  // Check for removals (products that were visualized but no longer in canvas)
  const removedProductIds = Array.from(effectiveVisualizedIds).filter(id => !currentIds.has(id));

  // Check for additions (products in canvas but not yet visualized)
  const newProducts = products.filter(p => !effectiveVisualizedIds.has(normalizeProductId(p.id)));

  // CRITICAL FIX: Check for quantity changes BEFORE removal checks
  const quantityIncreases: QuantityDelta[] = [];
  const quantityDecreases: QuantityDelta[] = [];

  console.log('[detectChangeType] Checking quantity changes for', products.length, 'products');
  console.log('[detectChangeType] visualizedQuantities map size:', visualizedQuantities.size);

  products.forEach(p => {
    const productIdStr = normalizeProductId(p.id);
    const isInVisualized = effectiveVisualizedIds.has(productIdStr);
    const currentQty = p.quantity || 1;
    const visualizedQty = visualizedQuantities.get(productIdStr) || 1;
    const delta = currentQty - visualizedQty;

    console.log(`[detectChangeType] Product "${p.name}" (id=${productIdStr}): inVisualized=${isInVisualized}, current=${currentQty}, visualized=${visualizedQty}, delta=${delta}`);

    if (isInVisualized) {
      if (delta > 0) {
        quantityIncreases.push({ product: p, delta });
        console.log(`[detectChangeType] -> QUANTITY INCREASE detected: +${delta}`);
      } else if (delta < 0) {
        quantityDecreases.push({ product: p, delta: Math.abs(delta) });
        console.log(`[detectChangeType] -> QUANTITY DECREASE detected: -${Math.abs(delta)}`);
      }
    }
  });

  console.log(`[detectChangeType] Total quantity increases: ${quantityIncreases.length}`);
  console.log(`[detectChangeType] Total quantity decreases: ${quantityDecreases.length}`);

  // Convert quantity increases to product entries for adding (same format as newProducts)
  const quantityIncreaseProducts: VisualizationProduct[] = quantityIncreases.map(qi => ({
    ...qi.product,
    quantity: qi.delta, // Only the delta quantity
    name: `${qi.product.name} (adding ${qi.delta} more)`,
  }));

  // Combine new products AND quantity increases for the "add" part
  // DEFENSIVE: Deduplicate by product ID to prevent any edge cases
  const combinedProducts = [...newProducts, ...quantityIncreaseProducts];
  const seenIds = new Set<string>();
  const allProductsToAdd = combinedProducts.filter(p => {
    const id = normalizeProductId(p.id);
    if (seenIds.has(id)) {
      console.warn(`[detectChangeType] Duplicate product detected and removed: ${p.name} (id=${id})`);
      return false;
    }
    seenIds.add(id);
    return true;
  });

  // Log what we're about to add
  if (allProductsToAdd.length > 0) {
    console.log('[detectChangeType] Products to add:', allProductsToAdd.map(p => ({
      id: p.id,
      name: p.name,
      quantity: p.quantity
    })));
  }

  // OPTIMIZATION: If products are both removed AND added, use remove_and_add workflow
  if (removedProductIds.length > 0 && allProductsToAdd.length > 0 && visualizationResult) {
    // Get full product info for removed products from visualizedProducts state
    const removedProductsInfo = removedProductIds.map(id => {
      const product = visualizedProducts.find(p => normalizeProductId(p.id) === id);
      return product || { id, name: `Product ${id}` } as VisualizationProduct;
    });
    console.log('[detectChangeType] Detected removal AND addition, will use remove_and_add workflow');
    return {
      type: 'remove_and_add',
      removedProducts: removedProductsInfo,
      newProducts: allProductsToAdd,
      reason: 'products_removed_and_added'
    };
  }

  // Simple removal only (no additions, no quantity increases)
  if (removedProductIds.length > 0 && visualizationResult) {
    const removedProductsInfo = removedProductIds.map(id => {
      const product = visualizedProducts.find(p => normalizeProductId(p.id) === id);
      return product || { id, name: `Product ${id}` } as VisualizationProduct;
    });
    console.log('[detectChangeType] Detected removal only, will use removal mode');
    return {
      type: 'removal',
      removedProducts: removedProductsInfo,
      remainingProducts: products,
      reason: 'products_removed'
    };
  }

  // Handle quantity decreases - need to remove extra copies
  if (quantityDecreases.length > 0 && quantityIncreases.length === 0) {
    console.log('[detectChangeType] Detected quantity decrease only');
    return {
      type: 'quantity_decrease',
      quantityDeltas: quantityDecreases,
      reason: 'quantity_decreased'
    };
  }

  // Mixed quantity changes (some increase, some decrease) - use reset
  if (quantityIncreases.length > 0 && quantityDecreases.length > 0) {
    console.log('[detectChangeType] Detected mixed quantity changes, will reset');
    return { type: 'reset', reason: 'mixed_quantity_changes' };
  }

  // Handle additions: new products AND/OR quantity increases (no removals)
  if (allProductsToAdd.length > 0 && effectiveVisualizedIds.size > 0) {
    const reasons: string[] = [];
    if (quantityIncreases.length > 0) reasons.push(`${quantityIncreases.length} quantity increases`);
    if (newProducts.length > 0) reasons.push(`${newProducts.length} new products`);
    console.log('[detectChangeType] Detected additions, will use incremental visualization');
    return { type: 'additive', newProducts: allProductsToAdd, reason: reasons.join('_and_') };
  }

  // Initial visualization (nothing visualized yet AND no existing visualization)
  if (effectiveVisualizedIds.size === 0 && !visualizationResult) {
    console.log('[detectChangeType] Initial visualization');
    return { type: 'initial' };
  }

  return { type: 'no_change' };
}

// ============================================================================
// Fetch with Retry
// ============================================================================

interface FetchWithRetryOptions {
  maxRetries?: number;
  timeoutMs?: number;
  retryDelayMs?: number;
}

/**
 * Make a fetch request with timeout and retry support.
 * Includes exponential backoff for retries.
 */
export async function fetchWithRetry(
  url: string,
  options: RequestInit,
  {
    maxRetries = 2,
    timeoutMs = 180000,  // 3 minutes default
    retryDelayMs = 2000  // 2 seconds initial delay
  }: FetchWithRetryOptions = {}
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      console.error(`[fetchWithRetry] Request timeout after ${timeoutMs / 1000}s (attempt ${attempt + 1}/${maxRetries + 1})`);
      controller.abort();
    }, timeoutMs);

    try {
      if (attempt > 0) {
        const delay = retryDelayMs * Math.pow(2, attempt - 1);  // Exponential backoff
        console.log(`[fetchWithRetry] Retry attempt ${attempt}/${maxRetries} after ${delay}ms delay...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      console.log(`[fetchWithRetry] Starting request (attempt ${attempt + 1}/${maxRetries + 1})...`);
      const requestStartTime = Date.now();

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const fetchTime = Date.now() - requestStartTime;
      console.log(`[fetchWithRetry] HTTP response received in ${fetchTime}ms, status: ${response.status}`);

      // Don't retry on client errors (4xx), only on server errors (5xx) or network issues
      if (response.ok || (response.status >= 400 && response.status < 500)) {
        return response;
      }

      // Server error - will retry
      const errorText = await response.text().catch(() => 'Unknown server error');
      lastError = new Error(`Server error ${response.status}: ${errorText}`);
      console.error(`[fetchWithRetry] Server error on attempt ${attempt + 1}:`, lastError.message);

    } catch (error: unknown) {
      clearTimeout(timeoutId);
      lastError = error instanceof Error ? error : new Error(String(error));

      if (lastError.name === 'AbortError') {
        console.error(`[fetchWithRetry] Request timed out on attempt ${attempt + 1}`);
        // Continue to retry on timeout
      } else if (lastError.message?.includes('fetch') || lastError.message?.includes('network')) {
        console.error(`[fetchWithRetry] Network error on attempt ${attempt + 1}:`, lastError.message);
        // Continue to retry on network errors
      } else {
        // Unknown error - don't retry
        throw lastError;
      }
    }
  }

  // All retries exhausted
  throw lastError || new Error('Request failed after all retries');
}

// ============================================================================
// Progress Messages
// ============================================================================

/**
 * Get progress message based on elapsed time
 */
export function getProgressMessage(elapsedSeconds: number): string {
  if (elapsedSeconds < 10) {
    return 'Preparing visualization...';
  } else if (elapsedSeconds < 30) {
    return 'Generating visualization...';
  } else if (elapsedSeconds < 60) {
    return 'Placing furniture in your space...';
  } else if (elapsedSeconds < 90) {
    return 'Still working - adding finishing touches...';
  } else {
    return 'Almost there - finalizing details...';
  }
}

// ============================================================================
// Quantity Helpers
// ============================================================================

/**
 * Build a Map of product quantities from an array of products
 */
export function buildQuantityMap(products: VisualizationProduct[]): Map<string, number> {
  const map = new Map<string, number>();
  products.forEach(p => {
    map.set(normalizeProductId(p.id), p.quantity || 1);
  });
  return map;
}

/**
 * Build a Set of product IDs from an array of products
 */
export function buildProductIdSet(products: VisualizationProduct[]): Set<string> {
  return new Set(products.map(p => normalizeProductId(p.id)));
}

// ============================================================================
// Total Calculations
// ============================================================================

/**
 * Calculate total price accounting for quantities
 */
export function calculateTotalPrice(products: VisualizationProduct[]): number {
  return products.reduce((sum, product) => {
    const qty = product.quantity || 1;
    return sum + (product.price || 0) * qty;
  }, 0);
}

/**
 * Calculate total item count accounting for quantities
 */
export function calculateTotalItems(products: VisualizationProduct[]): number {
  return products.reduce((sum, product) => sum + (product.quantity || 1), 0);
}
