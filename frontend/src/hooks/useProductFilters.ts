/**
 * useProductFilters Hook
 *
 * Reusable hook for product filtering logic.
 * Used across CategorySection, ProductDiscoveryPanel, and Admin Curation pages
 * to ensure consistent filter behavior.
 */

import { useState, useMemo, useCallback } from 'react';
import { PRODUCT_STYLES, PRICE_RANGES } from '@/constants/products';
import { ExtendedProduct, getStoreCategory } from '@/utils/product-transforms';

export interface ProductFilters {
  stores: string[];
  styles: string[];
  priceRange: { min: number; max: number } | null;
  storeCategory: 'all' | 'luxury' | 'budget' | 'marketplace' | 'indian_luxury' | 'indian_budget';
  sortBy: 'relevance' | 'price-low' | 'price-high';
}

export interface UseProductFiltersOptions {
  /** Initial filter values */
  initialFilters?: Partial<ProductFilters>;
}

export interface UseProductFiltersResult {
  /** Current filter state */
  filters: ProductFilters;
  /** Products after applying filters */
  filteredProducts: ExtendedProduct[];
  /** Unique stores from products */
  availableStores: string[];
  /** Available style options */
  availableStyles: typeof PRODUCT_STYLES;
  /** Available price range options */
  priceRanges: typeof PRICE_RANGES;
  /** Check if any filters are active */
  hasActiveFilters: boolean;
  /** Set store filter */
  setStoreFilter: (stores: string[]) => void;
  /** Toggle a single store */
  toggleStore: (store: string) => void;
  /** Set style filter */
  setStyleFilter: (styles: string[]) => void;
  /** Toggle a single style */
  toggleStyle: (style: string) => void;
  /** Set price range filter */
  setPriceRangeFilter: (priceRange: { min: number; max: number } | null) => void;
  /** Set store category filter */
  setStoreCategoryFilter: (storeCategory: ProductFilters['storeCategory']) => void;
  /** Set sort order */
  setSortBy: (sortBy: ProductFilters['sortBy']) => void;
  /** Clear all filters */
  clearFilters: () => void;
  /** Update entire filter state */
  setFilters: React.Dispatch<React.SetStateAction<ProductFilters>>;
}

const DEFAULT_FILTERS: ProductFilters = {
  stores: [],
  styles: [],
  priceRange: null,
  storeCategory: 'all',
  sortBy: 'relevance',
};

/**
 * Hook for managing product filters with memoized computations.
 *
 * @param products - Array of products to filter
 * @param options - Optional configuration
 * @returns Filter state and handlers
 */
export function useProductFilters(
  products: ExtendedProduct[],
  options: UseProductFiltersOptions = {}
): UseProductFiltersResult {
  const { initialFilters } = options;

  const [filters, setFilters] = useState<ProductFilters>({
    ...DEFAULT_FILTERS,
    ...initialFilters,
  });

  // Get unique stores from products
  const availableStores = useMemo(() => {
    const stores = new Set(
      products.map(p => p.source_website).filter(Boolean) as string[]
    );
    return Array.from(stores).sort();
  }, [products]);

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return (
      filters.stores.length > 0 ||
      filters.styles.length > 0 ||
      filters.priceRange !== null ||
      filters.storeCategory !== 'all'
    );
  }, [filters]);

  // Apply filters and sorting to products
  const filteredProducts = useMemo(() => {
    let result = products.filter(product => {
      // Store filter
      if (filters.stores.length > 0 && !filters.stores.includes(product.source_website || '')) {
        return false;
      }

      // Style filter
      if (filters.styles.length > 0) {
        const productStyle = product.primary_style?.toLowerCase();
        if (!productStyle || !filters.styles.includes(productStyle)) {
          return false;
        }
      }

      // Price range filter
      if (filters.priceRange) {
        const price = product.price || 0;
        if (price < filters.priceRange.min || price > filters.priceRange.max) {
          return false;
        }
      }

      // Store category filter
      if (filters.storeCategory !== 'all') {
        if (getStoreCategory(product.source_website) !== filters.storeCategory) {
          return false;
        }
      }

      return true;
    });

    // Apply sorting
    switch (filters.sortBy) {
      case 'price-low':
        result = [...result].sort((a, b) => (a.price || 0) - (b.price || 0));
        break;
      case 'price-high':
        result = [...result].sort((a, b) => (b.price || 0) - (a.price || 0));
        break;
      default:
        // 'relevance' - keep original order (usually by similarity_score)
        break;
    }

    return result;
  }, [products, filters]);

  // Filter handlers
  const setStoreFilter = useCallback((stores: string[]) => {
    setFilters(prev => ({ ...prev, stores }));
  }, []);

  const toggleStore = useCallback((store: string) => {
    setFilters(prev => ({
      ...prev,
      stores: prev.stores.includes(store)
        ? prev.stores.filter(s => s !== store)
        : [...prev.stores, store],
    }));
  }, []);

  const setStyleFilter = useCallback((styles: string[]) => {
    setFilters(prev => ({ ...prev, styles }));
  }, []);

  const toggleStyle = useCallback((style: string) => {
    setFilters(prev => ({
      ...prev,
      styles: prev.styles.includes(style)
        ? prev.styles.filter(s => s !== style)
        : [...prev.styles, style],
    }));
  }, []);

  const setPriceRangeFilter = useCallback((priceRange: { min: number; max: number } | null) => {
    setFilters(prev => ({ ...prev, priceRange }));
  }, []);

  const setStoreCategoryFilter = useCallback((storeCategory: ProductFilters['storeCategory']) => {
    setFilters(prev => ({ ...prev, storeCategory }));
  }, []);

  const setSortBy = useCallback((sortBy: ProductFilters['sortBy']) => {
    setFilters(prev => ({ ...prev, sortBy }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  return {
    filters,
    filteredProducts,
    availableStores,
    availableStyles: PRODUCT_STYLES,
    priceRanges: PRICE_RANGES,
    hasActiveFilters,
    setStoreFilter,
    toggleStore,
    setStyleFilter,
    toggleStyle,
    setPriceRangeFilter,
    setStoreCategoryFilter,
    setSortBy,
    clearFilters,
    setFilters,
  };
}
