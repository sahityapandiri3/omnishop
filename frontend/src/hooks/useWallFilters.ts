'use client';

import { useState, useCallback, useMemo } from 'react';
import {
  WallType,
  WallFilterState,
  DEFAULT_WALL_FILTER_STATE,
} from '@/types/wall-textures';
import { WallColorFamily } from '@/types/wall-colors';

interface UseWallFiltersReturn {
  /** Current filter state */
  filters: WallFilterState;
  /** Current wall type (color or textured) */
  wallType: WallType;
  /** Set wall type */
  setWallType: (type: WallType) => void;
  /** Selected color families for filtering colors */
  selectedFamilies: WallColorFamily[];
  /** Toggle a color family filter */
  toggleFamily: (family: WallColorFamily) => void;
  /** Set all selected families */
  setSelectedFamilies: (families: WallColorFamily[]) => void;
  /** Clear all family filters */
  clearFamilies: () => void;
  /** Selected brands for filtering textures */
  selectedBrands: string[];
  /** Toggle a brand filter */
  toggleBrand: (brand: string) => void;
  /** Set all selected brands */
  setSelectedBrands: (brands: string[]) => void;
  /** Clear all brand filters */
  clearBrands: () => void;
  /** Clear all filters */
  clearAllFilters: () => void;
  /** Check if any filters are active */
  hasActiveFilters: boolean;
  /** Count of active filters */
  activeFilterCount: number;
}

/**
 * Hook for managing wall filter state.
 *
 * Provides unified state management for:
 * - Wall type toggle (color vs textured)
 * - Color family filters (for color mode)
 * - Brand filters (for texture mode)
 *
 * Usage:
 * ```tsx
 * const {
 *   wallType,
 *   setWallType,
 *   selectedBrands,
 *   toggleBrand,
 * } = useWallFilters();
 *
 * // In filter panel
 * <WallTypeToggle value={wallType} onChange={setWallType} />
 * <BrandFilter selected={selectedBrands} onToggle={toggleBrand} />
 * ```
 */
export function useWallFilters(
  initialState: Partial<WallFilterState> = {}
): UseWallFiltersReturn {
  const [filters, setFilters] = useState<WallFilterState>({
    ...DEFAULT_WALL_FILTER_STATE,
    ...initialState,
  });

  // Wall type
  const setWallType = useCallback((type: WallType) => {
    setFilters((prev) => ({ ...prev, wallType: type }));
  }, []);

  // Color families
  const toggleFamily = useCallback((family: WallColorFamily) => {
    setFilters((prev) => {
      const families = prev.selectedFamilies.includes(family)
        ? prev.selectedFamilies.filter((f) => f !== family)
        : [...prev.selectedFamilies, family];
      return { ...prev, selectedFamilies: families };
    });
  }, []);

  const setSelectedFamilies = useCallback((families: WallColorFamily[]) => {
    setFilters((prev) => ({ ...prev, selectedFamilies: families }));
  }, []);

  const clearFamilies = useCallback(() => {
    setFilters((prev) => ({ ...prev, selectedFamilies: [] }));
  }, []);

  // Brands
  const toggleBrand = useCallback((brand: string) => {
    setFilters((prev) => {
      const brands = prev.selectedBrands.includes(brand)
        ? prev.selectedBrands.filter((b) => b !== brand)
        : [...prev.selectedBrands, brand];
      return { ...prev, selectedBrands: brands };
    });
  }, []);

  const setSelectedBrands = useCallback((brands: string[]) => {
    setFilters((prev) => ({ ...prev, selectedBrands: brands }));
  }, []);

  const clearBrands = useCallback(() => {
    setFilters((prev) => ({ ...prev, selectedBrands: [] }));
  }, []);

  // Clear all
  const clearAllFilters = useCallback(() => {
    setFilters(DEFAULT_WALL_FILTER_STATE);
  }, []);

  // Computed values
  const hasActiveFilters = useMemo(() => {
    return (
      filters.selectedFamilies.length > 0 ||
      filters.selectedBrands.length > 0
    );
  }, [filters]);

  const activeFilterCount = useMemo(() => {
    return (
      filters.selectedFamilies.length +
      filters.selectedBrands.length
    );
  }, [filters]);

  return {
    filters,
    wallType: filters.wallType,
    setWallType,
    selectedFamilies: filters.selectedFamilies,
    toggleFamily,
    setSelectedFamilies,
    clearFamilies,
    selectedBrands: filters.selectedBrands,
    toggleBrand,
    setSelectedBrands,
    clearBrands,
    clearAllFilters,
    hasActiveFilters,
    activeFilterCount,
  };
}
