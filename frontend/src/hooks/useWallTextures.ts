'use client';

import { useState, useCallback, useRef } from 'react';
import { wallTexturesAPI } from '@/utils/api';
import {
  WallTextureWithVariants,
  WallTextureVariant,
  TextureBrandInfo,
  TextureTypeInfo,
  TextureType,
} from '@/types/wall-textures';

interface UseWallTexturesReturn {
  /** All textures with their variants */
  textures: WallTextureWithVariants[];
  /** Available brands for filtering */
  brands: TextureBrandInfo[];
  /** Available texture types for filtering */
  textureTypes: TextureTypeInfo[];
  /** Total count of textures */
  totalCount: number;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;
  /** Reload textures with optional filters */
  fetchTextures: (brand?: string, textureType?: TextureType, collection?: string) => Promise<void>;
  /** Currently selected texture variant (for preview) */
  selectedVariant: WallTextureVariant | null;
  /** Parent texture of selected variant */
  selectedTexture: WallTextureWithVariants | null;
  /** Set selected variant */
  setSelectedVariant: (variant: WallTextureVariant | null, texture?: WallTextureWithVariants | null) => void;
  /** Texture variant added to canvas (will be applied during visualization) */
  canvasTextureVariant: WallTextureVariant | null;
  /** Parent texture of canvas variant */
  canvasTexture: WallTextureWithVariants | null;
  /** Set canvas texture variant directly (used for undo/redo) */
  setCanvasTextureVariant: (variant: WallTextureVariant | null, texture?: WallTextureWithVariants | null) => void;
  /** Add selected texture to canvas */
  addToCanvas: (variant: WallTextureVariant, texture: WallTextureWithVariants) => void;
  /** Remove texture from canvas */
  removeFromCanvas: () => void;
}

/**
 * Hook for fetching and managing wall texture data.
 *
 * Provides:
 * - Texture data fetching with caching
 * - Selection state for preview
 * - Canvas state for visualization
 *
 * Usage:
 * ```tsx
 * const {
 *   textures,
 *   brands,
 *   textureTypes,
 *   isLoading,
 *   selectedVariant,
 *   setSelectedVariant,
 *   canvasTextureVariant,
 *   addToCanvas,
 * } = useWallTextures();
 *
 * // Fetch with filters
 * fetchTextures('Asian Paints', 'marble');
 * ```
 */
export function useWallTextures(): UseWallTexturesReturn {
  const [textures, setTextures] = useState<WallTextureWithVariants[]>([]);
  const [brands, setBrands] = useState<TextureBrandInfo[]>([]);
  const [textureTypes, setTextureTypes] = useState<TextureTypeInfo[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);

  // Selection state
  const [selectedVariant, setSelectedVariantState] = useState<WallTextureVariant | null>(null);
  const [selectedTexture, setSelectedTexture] = useState<WallTextureWithVariants | null>(null);

  // Canvas state
  const [canvasTextureVariant, setCanvasVariantState] = useState<WallTextureVariant | null>(null);
  const [canvasTexture, setCanvasTextureState] = useState<WallTextureWithVariants | null>(null);

  const fetchTextures = useCallback(async (
    brand?: string,
    textureType?: TextureType,
    collection?: string
  ) => {
    // Skip if already fetched with no filters (initial load dedup)
    const hasFilters = brand || textureType || collection;
    if (!hasFilters && hasFetchedRef.current && textures.length > 0) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await wallTexturesAPI.getAll(brand, textureType, collection);
      setTextures(response.textures);
      setBrands(response.brands);
      setTextureTypes(response.texture_types);
      setTotalCount(response.total_count);
      if (!hasFilters) {
        hasFetchedRef.current = true;
      }
    } catch (err) {
      console.error('[useWallTextures] Error fetching textures:', err);
      setError(err instanceof Error ? err.message : 'Failed to load textures');
    } finally {
      setIsLoading(false);
    }
  }, [textures.length]);

  const setSelectedVariant = useCallback((
    variant: WallTextureVariant | null,
    texture?: WallTextureWithVariants | null
  ) => {
    setSelectedVariantState(variant);
    setSelectedTexture(texture ?? null);
  }, []);

  const setCanvasTextureVariant = useCallback((
    variant: WallTextureVariant | null,
    texture?: WallTextureWithVariants | null
  ) => {
    setCanvasVariantState(variant);
    setCanvasTextureState(texture ?? null);
  }, []);

  const addToCanvas = useCallback((
    variant: WallTextureVariant,
    texture: WallTextureWithVariants
  ) => {
    console.log(`[useWallTextures] Adding texture to canvas: ${texture.name} - ${variant.code}`);
    setCanvasVariantState(variant);
    setCanvasTextureState(texture);
    // Keep selected in sync
    setSelectedVariantState(variant);
    setSelectedTexture(texture);
  }, []);

  const removeFromCanvas = useCallback(() => {
    console.log('[useWallTextures] Removing texture from canvas');
    setCanvasVariantState(null);
    setCanvasTextureState(null);
    setSelectedVariantState(null);
    setSelectedTexture(null);
  }, []);

  return {
    textures,
    brands,
    textureTypes,
    totalCount,
    isLoading,
    error,
    fetchTextures,
    selectedVariant,
    selectedTexture,
    setSelectedVariant,
    canvasTextureVariant,
    canvasTexture,
    setCanvasTextureVariant,
    addToCanvas,
    removeFromCanvas,
  };
}
