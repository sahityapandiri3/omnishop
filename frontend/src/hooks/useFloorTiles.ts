'use client';

import { useState, useCallback, useRef } from 'react';
import { floorTilesAPI } from '@/utils/api';
import {
  FloorTile,
  FloorTileFilterOptions,
  FloorTileFilterState,
  DEFAULT_FLOOR_TILE_FILTER_STATE,
} from '@/types/floor-tiles';

interface UseFloorTilesReturn {
  /** All tiles matching current filters */
  tiles: FloorTile[];
  /** Available filter values */
  filterOptions: FloorTileFilterOptions;
  /** Total count of tiles */
  totalCount: number;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;
  /** Fetch tiles with optional filters */
  fetchTiles: (filters?: Partial<FloorTileFilterState>) => Promise<void>;
  /** Currently selected tile (for preview) */
  selectedTile: FloorTile | null;
  /** Set selected tile */
  setSelectedTile: (tile: FloorTile | null) => void;
  /** Tile added to canvas (will be applied during visualization) */
  canvasTile: FloorTile | null;
  /** Set canvas tile directly (used for undo/redo) */
  setCanvasTile: (tile: FloorTile | null) => void;
  /** Add selected tile to canvas */
  addToCanvas: (tile: FloorTile) => void;
  /** Remove tile from canvas */
  removeFromCanvas: () => void;
}

/**
 * Hook for fetching and managing floor tile data.
 *
 * Mirrors useWallTextures pattern. Fetches tiles from API,
 * manages selection state and canvas state.
 * Lazy-loads when flooring tab is first selected.
 */
export function useFloorTiles(): UseFloorTilesReturn {
  const [tiles, setTiles] = useState<FloorTile[]>([]);
  const [filterOptions, setFilterOptions] = useState<FloorTileFilterOptions>({
    vendors: [],
    sizes: [],
    finishes: [],
    looks: [],
    colors: [],
  });
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);

  // Selection state
  const [selectedTile, setSelectedTile] = useState<FloorTile | null>(null);

  // Canvas state
  const [canvasTile, setCanvasTileState] = useState<FloorTile | null>(null);

  const fetchTiles = useCallback(async (filters?: Partial<FloorTileFilterState>) => {
    // Skip if already fetched with no filters (initial load dedup)
    const hasFilters = filters && Object.values(filters).some(v => Array.isArray(v) ? v.length > 0 : v != null);
    if (!hasFilters && hasFetchedRef.current && tiles.length > 0) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await floorTilesAPI.getAll(
        filters?.selectedVendors?.length ? filters.selectedVendors : undefined,
        filters?.selectedSizes?.length ? filters.selectedSizes : undefined,
        filters?.selectedFinishes?.length ? filters.selectedFinishes : undefined,
        filters?.selectedLooks?.length ? filters.selectedLooks : undefined,
        filters?.selectedColors?.length ? filters.selectedColors : undefined,
      );
      setTiles(response.tiles);
      setFilterOptions(response.filters);
      setTotalCount(response.total_count);
      if (!hasFilters) {
        hasFetchedRef.current = true;
      }
    } catch (err) {
      console.error('[useFloorTiles] Error fetching tiles:', err);
      setError(err instanceof Error ? err.message : 'Failed to load floor tiles');
    } finally {
      setIsLoading(false);
    }
  }, [tiles.length]);

  const setCanvasTile = useCallback((tile: FloorTile | null) => {
    setCanvasTileState(tile);
  }, []);

  const addToCanvas = useCallback((tile: FloorTile) => {
    console.log(`[useFloorTiles] Adding tile to canvas: ${tile.name} (${tile.size})`);
    setCanvasTileState(tile);
    setSelectedTile(tile);
  }, []);

  const removeFromCanvas = useCallback(() => {
    console.log('[useFloorTiles] Removing tile from canvas');
    setCanvasTileState(null);
    setSelectedTile(null);
  }, []);

  return {
    tiles,
    filterOptions,
    totalCount,
    isLoading,
    error,
    fetchTiles,
    selectedTile,
    setSelectedTile,
    canvasTile,
    setCanvasTile,
    addToCanvas,
    removeFromCanvas,
  };
}
