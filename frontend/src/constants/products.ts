/**
 * Shared Product Constants
 *
 * This file contains constants used across product discovery components
 * to ensure consistency between ProductDiscoveryPanel, CategorySection,
 * CategoryCarousel, and Admin Curation pages.
 */

// Product style options (matches Product.primary_style values from database)
export const PRODUCT_STYLES = [
  { value: 'modern', label: 'Modern' },
  { value: 'modern_luxury', label: 'Modern Luxury' },
  { value: 'indian_contemporary', label: 'Indian Contemporary' },
  { value: 'minimalist', label: 'Minimalist' },
  { value: 'japandi', label: 'Japandi' },
  { value: 'scandinavian', label: 'Scandinavian' },
  { value: 'mid_century_modern', label: 'Mid-Century Modern' },
  { value: 'boho', label: 'Boho' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'contemporary', label: 'Contemporary' },
  { value: 'eclectic', label: 'Eclectic' },
] as const;

// Style label options for curated looks (slightly different from product styles)
export const STYLE_LABEL_OPTIONS = [
  { value: 'modern', label: 'Modern' },
  { value: 'modern_luxury', label: 'Modern Luxury' },
  { value: 'indian_contemporary', label: 'Indian Contemporary' },
  { value: 'minimalist', label: 'Minimalist' },
  { value: 'japandi', label: 'Japandi' },
  { value: 'scandinavian', label: 'Scandinavian' },
  { value: 'mid_century_modern', label: 'Mid-Century Modern' },
  { value: 'bohemian', label: 'Bohemian' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'contemporary', label: 'Contemporary' },
  { value: 'eclectic', label: 'Eclectic' },
] as const;

// Common furniture colors for filtering
// Note: 'border' is optional - only used for light colors that need a visible border
export const FURNITURE_COLORS: readonly { name: string; value: string; color: string; border?: boolean }[] = [
  { name: 'White', value: 'white', color: '#FFFFFF', border: true },
  { name: 'Black', value: 'black', color: '#000000' },
  { name: 'Brown', value: 'brown', color: '#8B4513' },
  { name: 'Beige', value: 'beige', color: '#F5F5DC' },
  { name: 'Gray', value: 'gray', color: '#808080' },
  { name: 'Blue', value: 'blue', color: '#4169E1' },
  { name: 'Green', value: 'green', color: '#228B22' },
  { name: 'Red', value: 'red', color: '#DC143C' },
  { name: 'Yellow', value: 'yellow', color: '#FFD700' },
  { name: 'Orange', value: 'orange', color: '#FF8C00' },
  { name: 'Pink', value: 'pink', color: '#FFB6C1' },
  { name: 'Purple', value: 'purple', color: '#9370DB' },
];

// Common material options for filtering
export const PRODUCT_MATERIALS = [
  { value: 'wood', label: 'Wood' },
  { value: 'metal', label: 'Metal' },
  { value: 'glass', label: 'Glass' },
  { value: 'fabric', label: 'Fabric' },
  { value: 'leather', label: 'Leather' },
  { value: 'ceramic', label: 'Ceramic' },
  { value: 'marble', label: 'Marble' },
  { value: 'brass', label: 'Brass' },
  { value: 'iron', label: 'Iron' },
  { value: 'concrete', label: 'Concrete' },
  { value: 'linen', label: 'Linen' },
  { value: 'velvet', label: 'Velvet' },
  { value: 'cotton', label: 'Cotton' },
  { value: 'stone', label: 'Stone' },
  { value: 'bamboo', label: 'Bamboo' },
  { value: 'rattan', label: 'Rattan' },
] as const;

// Store categories for grouped store filtering
export const STORE_CATEGORIES = {
  luxury: ['west elm', 'cb2', 'crate & barrel', 'rh', 'pottery barn', 'arhaus'],
  budget: ['ikea', 'target', 'wayfair', 'amazon', 'home depot'],
  marketplace: ['etsy', 'chairish', '1stdibs'],
  indian_luxury: ['gulmohar lane', 'orange tree', 'fabindia', 'hometown'],
  indian_budget: ['pepperfry', 'urban ladder', 'flipkart', 'amazon india'],
} as const;

// Price range options for filtering
export const PRICE_RANGES = [
  { id: 'under10k', label: 'Under \u20B910,000', min: 0, max: 10000 },
  { id: '10kto25k', label: '\u20B910,000 - \u20B925,000', min: 10000, max: 25000 },
  { id: '25kto50k', label: '\u20B925,000 - \u20B950,000', min: 25000, max: 50000 },
  { id: '50kto1L', label: '\u20B950,000 - \u20B91,00,000', min: 50000, max: 100000 },
  { id: 'over1L', label: 'Over \u20B91,00,000', min: 100000, max: Infinity },
] as const;

// Budget tier options (auto-calculated based on total price)
// Must match backend BudgetTier enum in database/models.py
export const BUDGET_TIER_OPTIONS = [
  { value: 'pocket_friendly', label: 'Pocket-friendly', range: '< \u20B92L' },
  { value: 'mid_tier', label: 'Mid-tier', range: '\u20B92L \u2013 \u20B98L' },
  { value: 'premium', label: 'Premium', range: '\u20B98L \u2013 \u20B915L' },
  { value: 'luxury', label: 'Luxury', range: '\u20B915L+' },
] as const;

// Furniture quantity rules - determines if multiple of same type are allowed
// SINGLE_INSTANCE: Only one of this type allowed in the canvas (replaces existing)
// UNLIMITED: Multiple instances allowed (always adds new)
export const FURNITURE_QUANTITY_RULES = {
  SINGLE_INSTANCE: ['sofa', 'bed', 'coffee_table', 'floor_rug', 'ceiling_lamp'],
  UNLIMITED: ['planter', 'floor_lamp', 'standing_lamp', 'side_table', 'ottoman', 'table_lamp'],
} as const;

// Type exports for TypeScript
export type ProductStyle = typeof PRODUCT_STYLES[number];
export type StyleLabel = typeof STYLE_LABEL_OPTIONS[number];
export type FurnitureColor = { name: string; value: string; color: string; border?: boolean };
export type ProductMaterial = typeof PRODUCT_MATERIALS[number];
export type PriceRange = typeof PRICE_RANGES[number];
export type BudgetTier = typeof BUDGET_TIER_OPTIONS[number];
export type StoreCategoryKey = keyof typeof STORE_CATEGORIES;
