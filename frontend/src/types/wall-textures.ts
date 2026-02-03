/**
 * Wall Texture types for the design studio
 *
 * Used for the Asian Paints (and other vendors) textured wall finishes
 * and visualization feature. Textures are grouped by base name with
 * multiple color variants per texture.
 */

import { WallColorFamily } from './wall-colors';

/**
 * Texture type enum for categorizing wall textures
 */
export type TextureType =
  | 'marble'
  | 'velvet'
  | 'stone'
  | 'concrete'
  | '3d'
  | 'wall_tile'
  | 'stucco'
  | 'rust'
  | 'other';

/**
 * Human-readable labels for texture types
 */
export const TEXTURE_TYPE_LABELS: Record<TextureType, string> = {
  marble: 'Marble',
  velvet: 'Velvet',
  stone: 'Stone',
  concrete: 'Concrete',
  '3d': '3D',
  wall_tile: 'Wall Tile',
  stucco: 'Stucco',
  rust: 'Rust',
  other: 'Other',
};

/**
 * Order for displaying texture types
 */
export const TEXTURE_TYPE_ORDER: TextureType[] = [
  'marble',
  'velvet',
  'stone',
  'concrete',
  '3d',
  'wall_tile',
  'stucco',
  'rust',
  'other',
];

/**
 * Individual texture variant
 * Each variant is a separate product with its own swatch image and product page.
 * image_data is optional — the list endpoint returns variants WITHOUT inline images
 * to keep the response small. Use the image endpoint URL for <img> tags instead.
 */
export interface WallTextureVariant {
  id: number;
  code: string;                    // Variant code (e.g., "TNB1003CMB1001")
  name?: string;                   // Variant name if different from parent
  image_data?: string;             // Base64 encoded texture swatch image (only from individual variant endpoint)
  image_url?: string;              // Original source URL for swatch image
  product_url?: string;            // Product page URL for this variant
  color_family?: WallColorFamily;  // For color filtering
  is_active: boolean;
  display_order: number;
}

/**
 * Base wall texture (without variants)
 */
export interface WallTexture {
  id: number;
  name: string;                    // Texture name (e.g., "Basket", "Bandhej")
  collection?: string;             // Collection name (e.g., "Lux Imprints")
  texture_type?: TextureType;      // Type of texture finish
  brand: string;                   // Brand/vendor (e.g., "Asian Paints")
  description?: string;
  is_active: boolean;
  display_order: number;
}

/**
 * Wall texture with all its color variants
 */
export interface WallTextureWithVariants extends WallTexture {
  variants: WallTextureVariant[];
}

/**
 * Texture type metadata for filter UI
 */
export interface TextureTypeInfo {
  value: TextureType;
  label: string;
  texture_count: number;
}

/**
 * Texture brand metadata for filter UI
 */
export interface TextureBrandInfo {
  name: string;
  texture_count: number;
}

/**
 * Full textures response from API with filter metadata
 */
export interface WallTexturesGroupedResponse {
  textures: WallTextureWithVariants[];
  brands: TextureBrandInfo[];
  texture_types: TextureTypeInfo[];
  total_count: number;
}

/**
 * Request to change wall texture in visualization
 */
export interface ChangeWallTextureRequest {
  room_image: string;           // Base64 encoded current visualization image
  texture_variant_id: number;   // ID of the texture variant to apply
  user_id?: string;
  session_id?: string;
}

/**
 * Response from wall texture change API
 */
export interface ChangeWallTextureResponse {
  success: boolean;
  rendered_image?: string;      // Base64 encoded result image
  error_message?: string;
  processing_time: number;
  texture_name?: string;
  texture_type?: string;
}

/**
 * Wall type toggle options (for Panel 1 filter)
 */
export type WallType = 'color' | 'textured';

/**
 * Wall filter state for managing filter selections
 */
export interface WallFilterState {
  wallType: WallType;
  // Color filters
  selectedFamilies: WallColorFamily[];
  // Texture filters
  selectedBrands: string[];
}

/**
 * Default wall filter state
 */
export const DEFAULT_WALL_FILTER_STATE: WallFilterState = {
  wallType: 'color',
  selectedFamilies: [],
  selectedBrands: [],
};
