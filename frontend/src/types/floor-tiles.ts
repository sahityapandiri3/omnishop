/**
 * Floor Tile types for the design studio
 *
 * Floor tiles behave like wall textures: singular on canvas (only one at a time),
 * swatch-based visualization. Different filters from furniture: size, finish,
 * look, color, vendor.
 */

/**
 * Floor tile data from API
 */
export interface FloorTile {
  id: number;
  product_code: string;
  name: string;
  description?: string;
  size: string;                    // "1200x1800"
  size_width_mm?: number;
  size_height_mm?: number;
  finish?: string;                 // "Glossy"
  look?: string;                   // "Marble"
  color?: string;                  // "Beige"
  material?: string;               // "Glazed Vitrified"
  vendor: string;                  // "Nitco"
  product_url?: string;
  swatch_data?: string;            // Base64 swatch for AI (only from detail endpoint)
  swatch_url?: string;
  image_url?: string;              // Display thumbnail URL
  image_data?: string;             // Base64 thumbnail (only from detail endpoint)
  additional_images?: string[];
  is_active: boolean;
  display_order: number;
}

/**
 * Available filter values for floor tiles
 */
export interface FloorTileFilterOptions {
  vendors: string[];
  sizes: string[];
  finishes: string[];
  looks: string[];
  colors: string[];
}

/**
 * Floor tiles listing response from API
 */
export interface FloorTilesResponse {
  tiles: FloorTile[];
  filters: FloorTileFilterOptions;
  total_count: number;
}

/**
 * Floor tile filter state for managing multi-select filter selections
 */
export interface FloorTileFilterState {
  selectedVendors: string[];
  selectedSizes: string[];
  selectedFinishes: string[];
  selectedLooks: string[];
  selectedColors: string[];
}

/**
 * Default floor tile filter state
 */
export const DEFAULT_FLOOR_TILE_FILTER_STATE: FloorTileFilterState = {
  selectedVendors: [],
  selectedSizes: [],
  selectedFinishes: [],
  selectedLooks: [],
  selectedColors: [],
};

/**
 * Request to change floor tile in visualization
 */
export interface ChangeFloorTileRequest {
  room_image: string;
  tile_id: number;
  user_id?: string;
  session_id?: string;
}

/**
 * Response from floor tile change API
 */
export interface ChangeFloorTileResponse {
  success: boolean;
  rendered_image?: string;
  error_message?: string;
  processing_time: number;
  tile_name?: string;
  tile_size?: string;
}
