'use client';

import { useState, useCallback, useMemo } from 'react';
import {
  FloorTileFilterState,
  DEFAULT_FLOOR_TILE_FILTER_STATE,
} from '@/types/floor-tiles';

/** Toggle a value in an array (add if absent, remove if present) */
function toggleValue(arr: string[], value: string): string[] {
  return arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value];
}

interface UseFloorTileFiltersReturn {
  /** Current filter state */
  filters: FloorTileFilterState;
  /** Selected vendors */
  selectedVendors: string[];
  toggleVendor: (vendor: string) => void;
  /** Selected sizes */
  selectedSizes: string[];
  toggleSize: (size: string) => void;
  /** Selected finishes */
  selectedFinishes: string[];
  toggleFinish: (finish: string) => void;
  /** Selected looks */
  selectedLooks: string[];
  toggleLook: (look: string) => void;
  /** Selected colors */
  selectedColors: string[];
  toggleColor: (color: string) => void;
  /** Clear all filters */
  clearAllFilters: () => void;
  /** Check if any filters are active */
  hasActiveFilters: boolean;
  /** Count of active filter values */
  activeFilterCount: number;
}

/**
 * Hook for managing floor tile multi-select filter state.
 */
export function useFloorTileFilters(
  initialState: Partial<FloorTileFilterState> = {}
): UseFloorTileFiltersReturn {
  const [filters, setFilters] = useState<FloorTileFilterState>({
    ...DEFAULT_FLOOR_TILE_FILTER_STATE,
    ...initialState,
  });

  const toggleVendor = useCallback((vendor: string) => {
    setFilters((prev) => ({ ...prev, selectedVendors: toggleValue(prev.selectedVendors, vendor) }));
  }, []);

  const toggleSize = useCallback((size: string) => {
    setFilters((prev) => ({ ...prev, selectedSizes: toggleValue(prev.selectedSizes, size) }));
  }, []);

  const toggleFinish = useCallback((finish: string) => {
    setFilters((prev) => ({ ...prev, selectedFinishes: toggleValue(prev.selectedFinishes, finish) }));
  }, []);

  const toggleLook = useCallback((look: string) => {
    setFilters((prev) => ({ ...prev, selectedLooks: toggleValue(prev.selectedLooks, look) }));
  }, []);

  const toggleColor = useCallback((color: string) => {
    setFilters((prev) => ({ ...prev, selectedColors: toggleValue(prev.selectedColors, color) }));
  }, []);

  const clearAllFilters = useCallback(() => {
    setFilters(DEFAULT_FLOOR_TILE_FILTER_STATE);
  }, []);

  const hasActiveFilters = useMemo(() => {
    return Object.values(filters).some(arr => arr.length > 0);
  }, [filters]);

  const activeFilterCount = useMemo(() => {
    return Object.values(filters).reduce((sum, arr) => sum + arr.length, 0);
  }, [filters]);

  return {
    filters,
    selectedVendors: filters.selectedVendors,
    toggleVendor,
    selectedSizes: filters.selectedSizes,
    toggleSize,
    selectedFinishes: filters.selectedFinishes,
    toggleFinish,
    selectedLooks: filters.selectedLooks,
    toggleLook,
    selectedColors: filters.selectedColors,
    toggleColor,
    clearAllFilters,
    hasActiveFilters,
    activeFilterCount,
  };
}
