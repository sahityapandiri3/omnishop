/**
 * Visualization Types
 *
 * Shared types for the visualization panel logic used across:
 * - CanvasPanel (design page)
 * - Admin Curation page
 *
 * These types ensure consistent behavior between pages.
 */

import { ViewingAngle } from '@/components/AngleSelector';
import { WallColor } from '@/types/wall-colors';

// ============================================================================
// Product Types (for visualization context)
// ============================================================================

export interface ProductAttribute {
  attribute_name: string;
  attribute_value: string;
}

/**
 * Product type used in visualization context.
 * This is a simplified version focused on what the visualization system needs.
 */
export interface VisualizationProduct {
  id: string | number;
  name: string;
  price: number;
  image_url?: string;
  images?: Array<{
    original_url?: string;
    medium_url?: string;
    large_url?: string;
    is_primary?: boolean;
  }>;
  productType?: string;
  product_type?: string;
  source?: string;
  description?: string;
  quantity?: number;  // Quantity for multiple of same product (default: 1)
  attributes?: ProductAttribute[];  // Product attributes including dimensions
}

/**
 * Product formatted for API requests
 */
export interface ProductForApi {
  id: string | number;
  name: string;
  full_name: string;
  image_url?: string;
  description?: string;
  product_type: string;
  furniture_type: string;
  style: number;
  category: string;
  quantity: number;
  dimensions?: {
    width?: string;
    height?: string;
    depth?: string;
  };
}

// ============================================================================
// History Types
// ============================================================================

/**
 * Visualization history entry for local undo/redo tracking.
 *
 * CRITICAL: Includes visualizedQuantities to fix the bug where
 * undo/redo doesn't restore quantity state, causing false
 * "needs revisualization" detection.
 */
export interface VisualizationHistoryEntry {
  image: string;
  products: VisualizationProduct[];
  productIds: Set<string>;
  visualizedQuantities: Map<string, number>;  // CRITICAL: Must track quantities
  wallColor?: WallColor | null;  // Wall color applied in this visualization state
}

/**
 * Serializable version of history entry for storage
 */
export interface SerializableHistoryEntry {
  image: string;
  products: VisualizationProduct[];
  productIds: string[];  // Array instead of Set
  visualizedQuantities: Record<string, number>;  // Object instead of Map
  wallColor?: WallColor | null;  // Wall color applied in this visualization state
}

// ============================================================================
// Change Detection Types
// ============================================================================

export type ChangeType =
  | 'initial'      // First visualization
  | 'additive'     // Adding new products to existing visualization
  | 'removal'      // Removing products from visualization
  | 'remove_and_add'  // Both removing and adding products
  | 'quantity_decrease'  // Reducing quantity of existing product
  | 'reset'        // Full reset (e.g., mixed changes)
  | 'no_change';   // No changes detected

export interface QuantityDelta {
  product: VisualizationProduct;
  delta: number;
}

/**
 * Result of change detection analysis
 */
export interface ChangeDetectionResult {
  type: ChangeType;
  reason?: string;

  // For 'additive' type
  newProducts?: VisualizationProduct[];

  // For 'removal' and 'remove_and_add' types
  removedProducts?: VisualizationProduct[];
  remainingProducts?: VisualizationProduct[];

  // For 'quantity_decrease' type
  quantityDeltas?: QuantityDelta[];
}

// ============================================================================
// Visualization Hook Types
// ============================================================================

/**
 * Configuration for the useVisualization hook.
 * Allows feature flags and page-specific behavior.
 */
export interface VisualizationConfig {
  /** Enable text-based position editing (type instructions to move items) */
  enableTextBasedEdits?: boolean;

  /** Enable click-to-select position editing */
  enablePositionEditing?: boolean;

  /** Enable multi-angle viewing (front/left/right/back) */
  enableMultiAngle?: boolean;

  /** Enable "Improve Quality" button */
  enableImproveQuality?: boolean;

  /** Curated look ID for precomputation cache */
  curatedLookId?: number;

  /** Project ID for design page room analysis cache */
  projectId?: string | null;
}

/**
 * State returned by useVisualization hook
 */
export interface VisualizationState {
  // Core visualization state
  visualizationImage: string | null;
  isVisualizing: boolean;
  visualizationProgress: string;

  // Product tracking
  visualizedProductIds: Set<string>;
  visualizedProducts: VisualizationProduct[];
  visualizedQuantities: Map<string, number>;
  needsRevisualization: boolean;

  // Undo/redo
  canUndo: boolean;
  canRedo: boolean;

  // Edit mode (text-based)
  isEditingPositions: boolean;
  editInstructions: string;

  // Multi-angle
  currentAngle: ViewingAngle;
  angleImages: Record<ViewingAngle, string | null>;
  loadingAngle: ViewingAngle | null;

  // Quality improvement
  isImprovingQuality: boolean;
}

/**
 * Actions returned by useVisualization hook
 */
export interface VisualizationActions {
  /** Trigger visualization with smart change detection */
  handleVisualize: () => Promise<void>;

  /** Undo last visualization change */
  handleUndo: () => void;

  /** Redo previously undone change */
  handleRedo: () => void;

  /** Re-visualize all products on clean base image */
  handleImproveQuality: () => Promise<void>;

  /** Switch viewing angle */
  handleAngleSelect: (angle: ViewingAngle) => Promise<void>;

  /** Enter text-based position edit mode */
  enterEditMode: () => void;

  /** Exit edit mode without saving */
  exitEditMode: () => void;

  /** Apply text-based position edit instructions */
  applyEditInstructions: (instructions: string) => Promise<void>;

  /** Update edit instructions text */
  setEditInstructions: (instructions: string) => void;

  /** Reset visualization state (e.g., when room image changes) */
  resetVisualization: () => void;

  /** Initialize from existing visualization (e.g., curated look) */
  initializeFromExisting: (
    image: string,
    products: VisualizationProduct[],
    history?: VisualizationHistoryEntry[]
  ) => void;
}

/**
 * Internal setters exposed for admin page legacy handlers
 * These should be used sparingly and ideally removed in future refactoring
 */
export interface VisualizationInternalSetters {
  setVisualizationImage: (image: string | null) => void;
  setIsVisualizing: (value: boolean) => void;
  setVisualizationProgress: (value: string) => void;
  setVisualizedProductIds: (ids: Set<string>) => void;
  setVisualizedProducts: (products: VisualizationProduct[]) => void;
  setVisualizedQuantities: (quantities: Map<string, number>) => void;
  setNeedsRevisualization: (value: boolean) => void;
  setIsEditingPositions: (value: boolean) => void;
  setCurrentAngle: (angle: ViewingAngle) => void;
  setAngleImages: (images: Record<ViewingAngle, string | null>) => void;
  historyHook: any;  // UseVisualizationHistoryReturn - avoid circular dependency
}

/**
 * Return type of useVisualization hook
 */
export interface UseVisualizationReturn extends VisualizationState, VisualizationActions {
  /** Internal setters for admin page legacy handlers */
  _internal: VisualizationInternalSetters;
}

// ============================================================================
// Callback Types
// ============================================================================

export interface VisualizationCallbacks {
  /** Called when products should be updated (e.g., from undo) */
  onSetProducts: (products: VisualizationProduct[]) => void;

  /** Called when visualization image changes */
  onVisualizationImageChange?: (image: string | null) => void;

  /** Called when history changes (for persistence) */
  onVisualizationHistoryChange?: (history: SerializableHistoryEntry[]) => void;
}

// ============================================================================
// Helper Type Guards
// ============================================================================

/**
 * Check if a product ID is a string (normalize)
 */
export function normalizeProductId(id: string | number): string {
  return String(id);
}

/**
 * Convert history entry to serializable format
 */
export function serializeHistoryEntry(entry: VisualizationHistoryEntry): SerializableHistoryEntry {
  return {
    image: entry.image,
    products: entry.products,
    productIds: Array.from(entry.productIds),
    visualizedQuantities: Object.fromEntries(entry.visualizedQuantities),
    wallColor: entry.wallColor,
  };
}

/**
 * Convert serializable format back to history entry
 */
export function deserializeHistoryEntry(entry: SerializableHistoryEntry): VisualizationHistoryEntry {
  return {
    image: entry.image,
    products: entry.products,
    productIds: new Set(entry.productIds),
    visualizedQuantities: new Map(Object.entries(entry.visualizedQuantities).map(
      ([k, v]) => [k, typeof v === 'number' ? v : Number(v)]
    )),
    wallColor: entry.wallColor,
  };
}
