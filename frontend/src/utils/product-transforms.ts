/**
 * Product Transformation Utilities
 *
 * Shared functions for transforming API product data to display format.
 * Used across ProductDiscoveryPanel, CategorySection, CategoryCarousel,
 * and Admin Curation pages to ensure consistent product handling.
 */

import { Product, ProductImage } from '@/types';
import { STORE_CATEGORIES, BUDGET_TIER_OPTIONS } from '@/constants/products';

// Extended product type that includes additional fields from search/recommendations
// Uses Partial to allow missing required fields from API responses
export interface ExtendedProduct {
  id: number;
  name: string;
  description?: string;
  price: number;
  original_price?: number;
  currency: string;
  brand?: string;
  source_website: string;
  source_url?: string;
  is_available: boolean;
  is_on_sale: boolean;
  images: ProductImage[];
  category?: any;
  sku?: string;
  // Extended fields for filtering and display
  is_primary_match?: boolean;
  primary_style?: string;
  similarity_score?: number;
  quantity?: number;
  product_type?: string;
  // Allow additional properties from API
  image_url?: string;
  // Optional fields that may not be present
  external_id?: string;
  stock_status?: string;
  attributes?: any[];
  scraped_at?: string;
  last_updated?: string;
}

/**
 * Transform raw product data from API to display-ready Product type.
 *
 * Handles different image formats from various API endpoints:
 * - primary_image.url from chat API
 * - images array from product listing
 * - image_url fallback
 *
 * @param rawProduct - Raw product data from API
 * @returns Transformed product ready for display
 */
export function transformProduct(rawProduct: any): ExtendedProduct {
  // Handle different image formats from API
  let images: ProductImage[] = [];

  // Backend returns primary_image.url from chat API
  if (rawProduct.primary_image && rawProduct.primary_image.url) {
    images = [{
      id: 1,
      product_id: rawProduct.id,
      original_url: rawProduct.primary_image.url,
      is_primary: true,
      alt_text: rawProduct.primary_image.alt_text || rawProduct.name,
      display_order: 0,
    }];
  }
  // Check for images array
  else if (rawProduct.images && Array.isArray(rawProduct.images)) {
    images = rawProduct.images;
  }
  // Fallback: Check for image_url
  else if (rawProduct.image_url) {
    images = [{
      id: 1,
      product_id: rawProduct.id,
      original_url: rawProduct.image_url,
      is_primary: true,
      alt_text: rawProduct.name,
      display_order: 0,
    }];
  }

  return {
    id: parseInt(rawProduct.id) || rawProduct.id,
    name: rawProduct.name,
    description: rawProduct.description,
    price: parseFloat(rawProduct.price) || 0,
    original_price: rawProduct.original_price ? parseFloat(rawProduct.original_price) : undefined,
    currency: rawProduct.currency || 'INR',
    brand: rawProduct.brand,
    source_website: rawProduct.source || rawProduct.source_website,
    source_url: rawProduct.source_url,
    is_available: rawProduct.is_available !== false,
    is_on_sale: rawProduct.is_on_sale || false,
    images: images,
    category: rawProduct.category,
    sku: rawProduct.sku,
    // Extended fields for filtering and display
    is_primary_match: rawProduct.is_primary_match,
    primary_style: rawProduct.primary_style,
    similarity_score: rawProduct.similarity_score,
    quantity: rawProduct.quantity,
    product_type: rawProduct.product_type,
  };
}

/**
 * Separate products into "Best Matches" (primary) and "More Products" (related).
 *
 * Products with is_primary_match === true are considered best matches,
 * which typically have higher relevance scores and better match the search criteria.
 *
 * @param products - Array of products to separate
 * @returns Object with bestMatches and moreProducts arrays
 */
export function separateProductMatches<T extends { is_primary_match?: boolean }>(
  products: T[]
): { bestMatches: T[]; moreProducts: T[] } {
  const bestMatches = products.filter(p => p.is_primary_match === true);
  const moreProducts = products.filter(p => p.is_primary_match !== true);
  return { bestMatches, moreProducts };
}

/**
 * Get store category based on store name.
 *
 * Categories products into luxury, budget, marketplace, or indian tiers
 * based on the store they come from.
 *
 * @param storeName - Name of the store
 * @returns Category key or 'other' if no match
 */
export function getStoreCategory(
  storeName: string | undefined
): 'luxury' | 'budget' | 'marketplace' | 'indian_luxury' | 'indian_budget' | 'other' {
  if (!storeName) return 'other';

  const normalized = storeName.toLowerCase();

  for (const [category, stores] of Object.entries(STORE_CATEGORIES)) {
    if (stores.some(store => normalized.includes(store))) {
      return category as keyof typeof STORE_CATEGORIES;
    }
  }

  return 'other';
}

/**
 * Get primary image URL from a product.
 *
 * Handles different image formats and returns the best available image URL.
 *
 * @param product - Product with images
 * @returns Image URL or placeholder
 */
export function getProductImageUrl(product: ExtendedProduct | Product | any): string {
  if (product.images && Array.isArray(product.images) && product.images.length > 0) {
    const primaryImage = product.images.find((img: ProductImage) => img.is_primary);
    const image = primaryImage || product.images[0];
    return image.large_url || image.medium_url || image.original_url;
  }
  return product.image_url || '/placeholder-product.jpg';
}

/**
 * Extract product type from product name.
 *
 * Used for furniture quantity rules and categorization.
 *
 * @param productName - Name of the product
 * @returns Extracted product type
 */
export function extractProductType(productName: string): string {
  const name = productName.toLowerCase();

  // Check for specific product types (order matters - check specific types first)
  if (name.includes('sofa') || name.includes('couch') || name.includes('sectional')) return 'sofa';
  if (name.includes('coffee table') || name.includes('center table') || name.includes('centre table')) return 'coffee_table';
  if (name.includes('side table') || name.includes('end table') || name.includes('nightstand')) return 'side_table';
  if (name.includes('dining table')) return 'dining_table';
  if (name.includes('console table')) return 'console_table';
  if (name.includes('accent chair') || name.includes('armchair')) return 'accent_chair';
  if (name.includes('dining chair')) return 'dining_chair';
  if (name.includes('office chair')) return 'office_chair';
  if (name.includes('table lamp') || name.includes('desk lamp')) return 'table_lamp';
  if (name.includes('floor lamp') || name.includes('standing lamp')) return 'floor_lamp';
  if (name.includes('ceiling lamp') || name.includes('pendant') || name.includes('chandelier')) return 'ceiling_lamp';
  if (name.includes('lamp') || name.includes('light')) return 'lamp';
  if (name.includes('bed')) return 'bed';
  if (name.includes('dresser')) return 'dresser';
  if (name.includes('mirror')) return 'mirror';
  if (name.includes('rug') || name.includes('carpet')) {
    if (name.includes('wall') || name.includes('hanging') || name.includes('tapestry')) {
      return 'wall_rug';
    }
    return 'floor_rug';
  }
  if (name.includes('planter') || name.includes('plant') || name.includes('vase')) return 'planter';
  if (name.includes('ottoman') || name.includes('pouf')) return 'ottoman';
  if (name.includes('bench')) return 'bench';
  if (name.includes('table')) return 'table';
  if (name.includes('chair')) return 'chair';
  return 'other';
}

/**
 * Calculate budget tier based on total price.
 *
 * @param price - Total price in INR
 * @returns Budget tier option object
 */
export function calculateBudgetTier(price: number): typeof BUDGET_TIER_OPTIONS[number] {
  if (price < 200000) return BUDGET_TIER_OPTIONS[0]; // Pocket-friendly
  if (price < 800000) return BUDGET_TIER_OPTIONS[1]; // Mid-tier
  if (price < 1500000) return BUDGET_TIER_OPTIONS[2]; // Premium
  return BUDGET_TIER_OPTIONS[3]; // Luxury
}

/**
 * Calculate discount percentage from original and current price.
 *
 * @param price - Current price
 * @param originalPrice - Original price (before discount)
 * @returns Discount percentage or null if no discount
 */
export function calculateDiscountPercentage(
  price: number,
  originalPrice?: number
): number | null {
  if (originalPrice && price < originalPrice) {
    return Math.round(((originalPrice - price) / originalPrice) * 100);
  }
  return null;
}

/**
 * Check if a product is in the canvas/cart.
 *
 * @param productId - ID of the product to check
 * @param canvasProducts - Array of products in canvas
 * @returns True if product is in canvas
 */
export function isProductInCanvas(
  productId: string | number,
  canvasProducts: Array<{ id: string | number }>
): boolean {
  return canvasProducts.some(p => p.id?.toString() === productId?.toString());
}

/**
 * Get quantity of a product in canvas.
 *
 * @param productId - ID of the product
 * @param canvasProducts - Array of products in canvas
 * @returns Quantity or 0 if not in canvas
 */
export function getCanvasQuantity(
  productId: string | number,
  canvasProducts: Array<{ id: string | number; quantity?: number }>
): number {
  const product = canvasProducts.find(p => p.id?.toString() === productId?.toString());
  return product?.quantity || 0;
}
