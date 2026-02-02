/**
 * Wall Color types for the design studio
 *
 * Used for the Asian Paints wall color catalog and visualization feature.
 */

/**
 * Wall color family enum
 * Groups colors into browsable categories
 */
export type WallColorFamily =
  | 'whites_offwhites'
  | 'greys'
  | 'blues'
  | 'browns'
  | 'yellows_greens'
  | 'reds_oranges'
  | 'purples_pinks';

/**
 * Human-readable labels for color families
 */
export const WALL_COLOR_FAMILY_LABELS: Record<WallColorFamily, string> = {
  whites_offwhites: 'Whites & Off-Whites',
  greys: 'Greys',
  blues: 'Blues',
  browns: 'Browns',
  yellows_greens: 'Yellows & Greens',
  reds_oranges: 'Reds & Oranges',
  purples_pinks: 'Purples & Pinks',
};

/**
 * Order for displaying color families
 */
export const WALL_COLOR_FAMILY_ORDER: WallColorFamily[] = [
  'whites_offwhites',
  'greys',
  'blues',
  'browns',
  'yellows_greens',
  'reds_oranges',
  'purples_pinks',
];

/**
 * Individual wall color from the catalog
 */
export interface WallColor {
  id: number;
  code: string;           // Asian Paints code (e.g., "L134")
  name: string;           // Color name (e.g., "Air Breeze")
  hex_value: string;      // Hex color (e.g., "#F5F5F0")
  family: WallColorFamily;
  brand: string;          // Default: "Asian Paints"
  is_active: boolean;
  display_order: number;
}

/**
 * Color family metadata
 */
export interface WallColorFamilyInfo {
  value: WallColorFamily;
  label: string;
  color_count: number;
}

/**
 * Grouped wall colors response from API
 */
export interface WallColorsGroupedResponse {
  families: WallColorFamilyInfo[];
  colors: Record<string, WallColor[]>;
}

/**
 * Request to change wall color
 */
export interface ChangeWallColorRequest {
  room_image: string;     // Base64 encoded visualization image
  color_name: string;     // Asian Paints color name
  color_code: string;     // Asian Paints code
  color_hex: string;      // Hex color value
  user_id?: string;
  session_id?: string;
}

/**
 * Response from wall color change API
 */
export interface ChangeWallColorResponse {
  success: boolean;
  rendered_image?: string;  // Base64 encoded result image
  error_message?: string;
  processing_time: number;
}

/**
 * Helper to check if a color is light (for border/contrast decisions)
 */
export function isLightColor(hexColor: string): boolean {
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const brightness = (r + g + b) / 3;
  return brightness > 200;
}

/**
 * Helper to get contrasting text color for a background
 */
export function getContrastColor(hexColor: string): string {
  return isLightColor(hexColor) ? '#1f2937' : '#ffffff';
}
