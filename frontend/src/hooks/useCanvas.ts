'use client';

/**
 * useCanvas Hook — Unified Canvas State Management
 *
 * Manages all canvas items (products, wall colors, textures) through
 * a single interface. Replaces the previous approach where each item type
 * had its own separate state management.
 *
 * Key behaviors:
 * - Products: multiple allowed, support quantity > 1
 * - Wall colors: only one at a time (new replaces old)
 * - Textures: only one at a time (new replaces old)
 * - Wall colors and textures can coexist
 * - Undo/redo tracks the full canvas state
 */

import { useState, useCallback, useRef } from 'react';
import { VisualizationProduct } from '@/types/visualization';
import { WallColor } from '@/types/wall-colors';
import { WallTexture, WallTextureVariant, WallTextureWithVariants } from '@/types/wall-textures';
import { FloorTile } from '@/types/floor-tiles';

// ============================================================================
// Types
// ============================================================================

export type CanvasItemType = 'product' | 'wall_color' | 'wall_texture' | 'floor_tile';

/** Data specific to a product canvas item */
export interface ProductCanvasData {
  product: VisualizationProduct;
}

/** Data specific to a wall color canvas item */
export interface WallColorCanvasData {
  wallColor: WallColor;
}

/** Data specific to a wall texture canvas item */
export interface WallTextureCanvasData {
  textureVariant: WallTextureVariant;
  texture: WallTextureWithVariants;
}

/** Data specific to a floor tile canvas item */
export interface FloorTileCanvasData {
  floorTile: FloorTile;
}

export type CanvasItemData = ProductCanvasData | WallColorCanvasData | WallTextureCanvasData | FloorTileCanvasData;

export interface CanvasItem {
  /** Unique identifier: `product-{id}`, `wall_color-{id}`, `wall_texture-{id}` */
  id: string;
  /** Item type */
  type: CanvasItemType;
  /** Products can have quantity > 1; others always 1 */
  quantity: number;
  /** Type-specific data */
  data: CanvasItemData;
  /** Timestamp for ordering */
  addedAt: number;
}

// ============================================================================
// Type Guards
// ============================================================================

export function isProductData(data: CanvasItemData): data is ProductCanvasData {
  return 'product' in data;
}

export function isWallColorData(data: CanvasItemData): data is WallColorCanvasData {
  return 'wallColor' in data;
}

export function isWallTextureData(data: CanvasItemData): data is WallTextureCanvasData {
  return 'textureVariant' in data;
}

export function isFloorTileData(data: CanvasItemData): data is FloorTileCanvasData {
  return 'floorTile' in data;
}

// ============================================================================
// Helpers to extract typed data from items
// ============================================================================

export function getProductItems(items: CanvasItem[]): CanvasItem[] {
  return items.filter(item => item.type === 'product');
}

export function getWallColorItem(items: CanvasItem[]): CanvasItem | null {
  return items.find(item => item.type === 'wall_color') ?? null;
}

export function getWallTextureItem(items: CanvasItem[]): CanvasItem | null {
  return items.find(item => item.type === 'wall_texture') ?? null;
}

export function getFloorTileItem(items: CanvasItem[]): CanvasItem | null {
  return items.find(item => item.type === 'floor_tile') ?? null;
}

/** Extract VisualizationProduct[] from canvas items (for API calls) */
export function extractProducts(items: CanvasItem[]): VisualizationProduct[] {
  return getProductItems(items).map(item => {
    const data = item.data as ProductCanvasData;
    return { ...data.product, quantity: item.quantity };
  });
}

/** Extract WallColor from canvas items */
export function extractWallColor(items: CanvasItem[]): WallColor | null {
  const wallColorItem = getWallColorItem(items);
  if (!wallColorItem) return null;
  return (wallColorItem.data as WallColorCanvasData).wallColor;
}

/** Extract WallTextureVariant from canvas items */
export function extractTextureVariant(items: CanvasItem[]): WallTextureVariant | null {
  const textureItem = getWallTextureItem(items);
  if (!textureItem) return null;
  return (textureItem.data as WallTextureCanvasData).textureVariant;
}

/** Extract parent WallTexture from canvas items */
export function extractTexture(items: CanvasItem[]): WallTextureWithVariants | null {
  const textureItem = getWallTextureItem(items);
  if (!textureItem) return null;
  return (textureItem.data as WallTextureCanvasData).texture;
}

/** Extract FloorTile from canvas items */
export function extractFloorTile(items: CanvasItem[]): FloorTile | null {
  const floorTileItem = getFloorTileItem(items);
  if (!floorTileItem) return null;
  return (floorTileItem.data as FloorTileCanvasData).floorTile;
}

// ============================================================================
// Serializable types for persistence / history
// ============================================================================

export interface SerializableCanvasItem {
  id: string;
  type: CanvasItemType;
  quantity: number;
  data: CanvasItemData;
  addedAt: number;
}

export function serializeCanvasItems(items: CanvasItem[]): SerializableCanvasItem[] {
  return items.map(item => ({
    id: item.id,
    type: item.type,
    quantity: item.quantity,
    data: item.data,
    addedAt: item.addedAt,
  }));
}

export function deserializeCanvasItems(items: SerializableCanvasItem[]): CanvasItem[] {
  return items.map(item => ({
    id: item.id,
    type: item.type,
    quantity: item.quantity,
    data: item.data,
    addedAt: item.addedAt,
  }));
}

// ============================================================================
// Hook Return Type
// ============================================================================

export interface UseCanvasReturn {
  /** All canvas items */
  items: CanvasItem[];

  /** Convenience: product items only */
  productItems: CanvasItem[];
  /** Convenience: wall color item (or null) */
  wallColorItem: CanvasItem | null;
  /** Convenience: texture item (or null) */
  textureItem: CanvasItem | null;
  /** Convenience: floor tile item (or null) */
  floorTileItem: CanvasItem | null;

  /** Whether the canvas has any content */
  hasContent: boolean;

  /** Extracted products for API/visualization use */
  products: VisualizationProduct[];
  /** Extracted wall color for API/visualization use */
  wallColor: WallColor | null;
  /** Extracted texture variant for API/visualization use */
  textureVariant: WallTextureVariant | null;
  /** Extracted parent texture for display */
  texture: WallTextureWithVariants | null;
  /** Extracted floor tile for API/visualization use */
  floorTile: FloorTile | null;

  // === Actions ===

  /** Add a product to canvas (increments quantity if already present) */
  addProduct: (product: VisualizationProduct) => void;
  /** Add a wall color to canvas (replaces existing) */
  addWallColor: (color: WallColor) => void;
  /** Add a texture to canvas (replaces existing) */
  addTexture: (variant: WallTextureVariant, texture: WallTextureWithVariants) => void;
  /** Add a floor tile to canvas (replaces existing) */
  addFloorTile: (tile: FloorTile) => void;

  /** Remove an item by its canvas ID */
  removeItem: (id: string) => void;
  /** Update quantity of a product (+1 or -1). Removes if quantity reaches 0. */
  updateQuantity: (id: string, delta: number) => void;
  /** Remove all items of a specific product (regardless of quantity) */
  removeProduct: (productId: string | number, removeAll?: boolean) => void;

  /** Clear all canvas items */
  clearAll: () => void;

  /** Set items directly (used by undo/redo to restore state) */
  setItems: (items: CanvasItem[]) => void;
  /** Set products directly (used by undo/redo legacy) */
  setProducts: (products: VisualizationProduct[]) => void;
  /** Set wall color directly (used by undo/redo) */
  setWallColor: (color: WallColor | null) => void;
  /** Set texture variant directly (used by undo/redo) */
  setTextureVariant: (variant: WallTextureVariant | null, texture?: WallTextureWithVariants | null) => void;
  /** Set floor tile directly (used by undo/redo) */
  setFloorTile: (tile: FloorTile | null) => void;

  // === Computed values ===

  /** Total number of items (accounting for product quantities) */
  totalItemCount: number;
  /** Total price of all products */
  totalPrice: number;
  /** Number of unique products */
  uniqueProductCount: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

function makeCanvasId(type: CanvasItemType, id: string | number): string {
  return `${type}-${id}`;
}

export function useCanvas(): UseCanvasReturn {
  const [items, setItems] = useState<CanvasItem[]>([]);

  // Convenience getters
  const productItems = getProductItems(items);
  const wallColorItem = getWallColorItem(items);
  const textureItem = getWallTextureItem(items);
  const floorTileItem = getFloorTileItem(items);
  const hasContent = items.length > 0;

  // Extracted values for visualization
  const products = extractProducts(items);
  const wallColor = extractWallColor(items);
  const textureVariant = extractTextureVariant(items);
  const texture = extractTexture(items);
  const floorTile = extractFloorTile(items);

  // Computed values
  const totalItemCount = productItems.reduce((sum, item) => sum + item.quantity, 0)
    + (wallColorItem ? 1 : 0) + (textureItem ? 1 : 0) + (floorTileItem ? 1 : 0);
  const totalPrice = productItems.reduce((sum, item) => {
    const data = item.data as ProductCanvasData;
    return sum + (data.product.price || 0) * item.quantity;
  }, 0);
  const uniqueProductCount = productItems.length;

  // === Actions ===

  const addProduct = useCallback((product: VisualizationProduct) => {
    const canvasId = makeCanvasId('product', product.id);
    setItems(prev => {
      const existingIdx = prev.findIndex(item => item.id === canvasId);
      if (existingIdx >= 0) {
        // Increment quantity
        const updated = [...prev];
        updated[existingIdx] = {
          ...updated[existingIdx],
          quantity: updated[existingIdx].quantity + 1,
        };
        console.log(`[useCanvas] Incremented quantity for: ${product.name} to ${updated[existingIdx].quantity}`);
        return updated;
      }
      // Add new product
      console.log(`[useCanvas] Added product: ${product.name}`);
      return [...prev, {
        id: canvasId,
        type: 'product' as CanvasItemType,
        quantity: 1,
        data: { product: { ...product, quantity: 1 } },
        addedAt: Date.now(),
      }];
    });
  }, []);

  const addWallColor = useCallback((color: WallColor) => {
    const canvasId = makeCanvasId('wall_color', color.id);
    setItems(prev => {
      // Remove any existing wall color
      const filtered = prev.filter(item => item.type !== 'wall_color');
      console.log(`[useCanvas] Added wall color: ${color.name} (${color.hex_value})`);
      return [...filtered, {
        id: canvasId,
        type: 'wall_color' as CanvasItemType,
        quantity: 1,
        data: { wallColor: color },
        addedAt: Date.now(),
      }];
    });
  }, []);

  const addTexture = useCallback((variant: WallTextureVariant, parentTexture: WallTextureWithVariants) => {
    const canvasId = makeCanvasId('wall_texture', variant.id);
    setItems(prev => {
      // Remove any existing texture
      const filtered = prev.filter(item => item.type !== 'wall_texture');
      console.log(`[useCanvas] Added texture: ${parentTexture.name} - ${variant.code}`);
      return [...filtered, {
        id: canvasId,
        type: 'wall_texture' as CanvasItemType,
        quantity: 1,
        data: { textureVariant: variant, texture: parentTexture },
        addedAt: Date.now(),
      }];
    });
  }, []);

  const addFloorTile = useCallback((tile: FloorTile) => {
    const canvasId = makeCanvasId('floor_tile', tile.id);
    setItems(prev => {
      // Remove any existing floor tile (only one at a time)
      const filtered = prev.filter(item => item.type !== 'floor_tile');
      console.log(`[useCanvas] Added floor tile: ${tile.name} (${tile.size})`);
      return [...filtered, {
        id: canvasId,
        type: 'floor_tile' as CanvasItemType,
        quantity: 1,
        data: { floorTile: tile },
        addedAt: Date.now(),
      }];
    });
  }, []);

  const removeItem = useCallback((id: string) => {
    setItems(prev => prev.filter(item => item.id !== id));
  }, []);

  const updateQuantity = useCallback((id: string, delta: number) => {
    setItems(prev => {
      const idx = prev.findIndex(item => item.id === id);
      if (idx < 0) return prev;

      const item = prev[idx];
      const newQty = item.quantity + delta;

      if (newQty <= 0) {
        // Remove item
        return prev.filter((_, i) => i !== idx);
      }

      const updated = [...prev];
      updated[idx] = { ...updated[idx], quantity: newQty };
      return updated;
    });
  }, []);

  const removeProduct = useCallback((productId: string | number, removeAll: boolean = false) => {
    const canvasId = makeCanvasId('product', productId);
    if (removeAll) {
      setItems(prev => prev.filter(item => item.id !== canvasId));
    } else {
      // Decrement quantity, remove if reaches 0
      updateQuantity(canvasId, -1);
    }
  }, [updateQuantity]);

  const clearAll = useCallback(() => {
    setItems([]);
  }, []);

  // Set products from external source (undo/redo, curated looks)
  const setProducts = useCallback((newProducts: VisualizationProduct[]) => {
    setItems(prev => {
      // Keep non-product items
      const nonProducts = prev.filter(item => item.type !== 'product');
      // Create product items from the array
      const productCanvasItems: CanvasItem[] = newProducts.map(p => ({
        id: makeCanvasId('product', p.id),
        type: 'product' as CanvasItemType,
        quantity: p.quantity || 1,
        data: { product: p },
        addedAt: Date.now(),
      }));
      return [...nonProducts, ...productCanvasItems];
    });
  }, []);

  // Set wall color directly (undo/redo)
  const setWallColor = useCallback((color: WallColor | null) => {
    setItems(prev => {
      const filtered = prev.filter(item => item.type !== 'wall_color');
      if (!color) return filtered;
      return [...filtered, {
        id: makeCanvasId('wall_color', color.id),
        type: 'wall_color' as CanvasItemType,
        quantity: 1,
        data: { wallColor: color },
        addedAt: Date.now(),
      }];
    });
  }, []);

  // Set texture variant directly (undo/redo)
  const setTextureVariant = useCallback((
    variant: WallTextureVariant | null,
    parentTexture?: WallTextureWithVariants | null
  ) => {
    setItems(prev => {
      const filtered = prev.filter(item => item.type !== 'wall_texture');
      if (!variant) return filtered;
      // If no parent texture provided, create a minimal one
      const tex = parentTexture ?? {
        id: 0,
        name: variant.name || variant.code,
        brand: '',
        is_active: true,
        display_order: 0,
        variants: [variant],
      };
      return [...filtered, {
        id: makeCanvasId('wall_texture', variant.id),
        type: 'wall_texture' as CanvasItemType,
        quantity: 1,
        data: { textureVariant: variant, texture: tex },
        addedAt: Date.now(),
      }];
    });
  }, []);

  // Set floor tile directly (undo/redo)
  const setFloorTile = useCallback((tile: FloorTile | null) => {
    setItems(prev => {
      const filtered = prev.filter(item => item.type !== 'floor_tile');
      if (!tile) return filtered;
      return [...filtered, {
        id: makeCanvasId('floor_tile', tile.id),
        type: 'floor_tile' as CanvasItemType,
        quantity: 1,
        data: { floorTile: tile },
        addedAt: Date.now(),
      }];
    });
  }, []);

  return {
    items,
    productItems,
    wallColorItem,
    textureItem,
    floorTileItem,
    hasContent,
    products,
    wallColor,
    textureVariant,
    texture,
    floorTile,

    addProduct,
    addWallColor,
    addTexture,
    addFloorTile,
    removeItem,
    updateQuantity,
    removeProduct,
    clearAll,
    setItems,
    setProducts,
    setWallColor,
    setTextureVariant,
    setFloorTile,

    totalItemCount,
    totalPrice,
    uniqueProductCount,
  };
}
