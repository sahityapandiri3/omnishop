'use client';

import { useState, useEffect, useCallback, useRef, useImperativeHandle, forwardRef } from 'react';
import { adminCuratedAPI, searchProducts, getCategorizedStores, StoreCategory } from '@/utils/api';
import { PRODUCT_STYLES, FURNITURE_COLORS, PRODUCT_MATERIALS } from '@/constants/products';
import { transformProduct, ExtendedProduct } from '@/utils/product-transforms';
import { ProductResultsGrid } from './ProductResultsGrid';
import { ProductFilterPanel, FilterToggleButton } from './ProductFilterPanel';
import { ProductFilters, useProductFilters } from '@/hooks/useProductFilters';
import { ProductDetailModal } from '../ProductDetailModal';

// Ref handle interface for parent to call loadMore
export interface KeywordSearchPanelRef {
  loadMore: () => void;
}

// Filter state interface for external control
export interface SearchFilters {
  selectedStores: string[];
  selectedStyles: string[];
  selectedColors: string[];
  selectedMaterials: string[];
  priceMin: number;
  priceMax: number;
}

interface KeywordSearchPanelProps {
  /** Callback when product is added to canvas */
  onAddProduct: (product: ExtendedProduct) => void;
  /** Products currently in canvas */
  canvasProducts: Array<{ id: string | number; quantity?: number }>;
  /** Initial search query */
  initialQuery?: string;
  /** Whether to show the search input */
  showSearchInput?: boolean;
  /** Placeholder text for search input */
  searchPlaceholder?: string;
  /** Compact mode for smaller panels */
  compact?: boolean;
  /** Whether to show results inline (false = results via callback only) */
  showResultsInline?: boolean;
  /** Callback when search results are available (for external display) */
  onSearchResults?: (results: {
    products: ExtendedProduct[];
    totalProducts: number;
    totalPrimary: number;
    totalRelated: number;
    hasMore: boolean;
    isSearching: boolean;
    isLoadingMore: boolean;
  }) => void;
  /** Callback for loading more results */
  onLoadMore?: () => void;
  /** External filter state (for persistence across mode switches) */
  filters?: SearchFilters;
  /** Callback when filters change */
  onFiltersChange?: (filters: SearchFilters) => void;
  /** Whether to show filters (for external control) */
  showFilters?: boolean;
  /** Callback when filter visibility changes */
  onShowFiltersChange?: (show: boolean) => void;
}

/**
 * KeywordSearchPanel Component
 *
 * Provides keyword-based product search with integrated filters.
 * Used for direct product discovery without AI assistant.
 *
 * Exposes a `loadMore` function via ref for parent to trigger pagination.
 */
export const KeywordSearchPanel = forwardRef<KeywordSearchPanelRef, KeywordSearchPanelProps>(function KeywordSearchPanel({
  onAddProduct,
  canvasProducts,
  initialQuery = '',
  showSearchInput = true,
  searchPlaceholder = 'Search furniture...',
  compact = false,
  showResultsInline = true,
  onSearchResults,
  filters: externalFilters,
  onFiltersChange,
  showFilters: externalShowFilters,
  onShowFiltersChange,
}, ref) {
  // Search state
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Products state
  const [products, setProducts] = useState<ExtendedProduct[]>([]);
  const [totalProducts, setTotalProducts] = useState(0);
  const [totalPrimary, setTotalPrimary] = useState(0);
  const [totalRelated, setTotalRelated] = useState(0);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Internal filter state (used when no external filters provided)
  const [internalShowFilters, setInternalShowFilters] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [internalSelectedStores, setInternalSelectedStores] = useState<string[]>([]);
  const [internalSelectedStyles, setInternalSelectedStyles] = useState<string[]>([]);
  const [internalSelectedColors, setInternalSelectedColors] = useState<string[]>([]);
  const [internalSelectedMaterials, setInternalSelectedMaterials] = useState<string[]>([]);
  const [internalPriceMin, setInternalPriceMin] = useState<number>(0);
  const [internalPriceMax, setInternalPriceMax] = useState<number>(Infinity);
  const [sortBy, setSortBy] = useState<'relevance' | 'price-low' | 'price-high'>('relevance');

  // Use external or internal filter state
  const isExternallyControlled = !!onFiltersChange;
  const showFilters = externalShowFilters !== undefined ? externalShowFilters : internalShowFilters;
  const selectedStores = externalFilters?.selectedStores ?? internalSelectedStores;
  const selectedStyles = externalFilters?.selectedStyles ?? internalSelectedStyles;
  const selectedColors = externalFilters?.selectedColors ?? internalSelectedColors;
  const selectedMaterials = externalFilters?.selectedMaterials ?? internalSelectedMaterials;
  const priceMin = externalFilters?.priceMin ?? internalPriceMin;
  const priceMax = externalFilters?.priceMax ?? internalPriceMax;

  // Store categories for grouped filtering
  const [storeCategories, setStoreCategories] = useState<StoreCategory[]>([]);
  const [allStores, setAllStores] = useState<string[]>([]);

  // Product detail modal
  const [selectedProduct, setSelectedProduct] = useState<ExtendedProduct | null>(null);

  // Ref for debouncing
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Load store categories on mount
  useEffect(() => {
    const fetchStoreCategories = async () => {
      try {
        const response = await getCategorizedStores();
        setStoreCategories(response.categories);
        setAllStores(response.all_stores.map(s => s.name));
      } catch (error) {
        console.error('Failed to fetch store categories:', error);
      }
    };
    fetchStoreCategories();
  }, []);

  // Build search params
  const buildSearchParams = useCallback((page: number = 1) => ({
    query: searchQuery || undefined,
    categoryId: selectedCategory || undefined,
    sourceWebsite: selectedStores.length > 0 ? selectedStores.join(',') : undefined,
    minPrice: priceMin > 0 ? priceMin : undefined,
    maxPrice: priceMax < Infinity && priceMax !== 999999 ? priceMax : undefined,
    colors: selectedColors.length > 0 ? selectedColors.join(',') : undefined,
    styles: selectedStyles.length > 0 ? selectedStyles.join(',') : undefined,
    materials: selectedMaterials.length > 0 ? selectedMaterials.join(',') : undefined,
    page,
    pageSize: 50,
  }), [searchQuery, selectedCategory, selectedStores, priceMin, priceMax, selectedColors, selectedStyles, selectedMaterials]);

  // Search products
  const handleSearch = useCallback(async (resetPage: boolean = true) => {
    const hasAnyFilter = selectedStores.length > 0 || selectedStyles.length > 0 ||
      selectedColors.length > 0 || selectedMaterials.length > 0 ||
      priceMin > 0 || (priceMax < Infinity && priceMax !== 999999);
    if (!searchQuery.trim() && !hasAnyFilter) {
      // Don't search if no query or filters
      return;
    }

    try {
      setIsSearching(true);
      setSearchError(null);

      if (resetPage) {
        setCurrentPage(1);
        setProducts([]);
      }

      const response = await searchProducts(buildSearchParams(resetPage ? 1 : currentPage));

      const transformedProducts = response.products.map(transformProduct);

      if (resetPage) {
        setProducts(transformedProducts);
      } else {
        setProducts(prev => [...prev, ...transformedProducts]);
      }

      setTotalProducts(response.total);
      setTotalPrimary(response.total_primary || 0);
      setTotalRelated(response.total_related || 0);
      setHasMore(response.has_more);
    } catch (error) {
      console.error('Error searching products:', error);
      setSearchError('Failed to search products. Please try again.');
    } finally {
      setIsSearching(false);
    }
  }, [searchQuery, buildSearchParams, currentPage, selectedStores, selectedStyles, selectedColors, selectedMaterials, priceMin, priceMax]);

  // Load more products
  // IMPORTANT: Products from page 2+ are marked as non-primary to always append
  // to "More Products" section, avoiding confusing scroll jumps when new "Best Matches"
  // would otherwise be inserted above the user's scroll position.
  const handleLoadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return;

    try {
      setIsLoadingMore(true);
      const nextPage = currentPage + 1;

      const response = await searchProducts(buildSearchParams(nextPage));

      // Mark all products from page 2+ as non-primary so they append to "More Products"
      const transformedProducts = response.products.map(p => ({
        ...transformProduct(p),
        is_primary_match: false, // Force to More Products section
      }));
      setProducts(prev => [...prev, ...transformedProducts]);
      setCurrentPage(nextPage);
      setHasMore(response.has_more);
    } catch (error) {
      console.error('Error loading more products:', error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, hasMore, currentPage, buildSearchParams]);

  // Expose loadMore function to parent via ref
  useImperativeHandle(ref, () => ({
    loadMore: handleLoadMore,
  }), [handleLoadMore]);

  // Notify parent when search results change (for external display in Panel 2)
  useEffect(() => {
    if (onSearchResults) {
      onSearchResults({
        products,
        totalProducts,
        totalPrimary,
        totalRelated,
        hasMore,
        isSearching,
        isLoadingMore,
      });
    }
  }, [products, totalProducts, totalPrimary, totalRelated, hasMore, isSearching, isLoadingMore, onSearchResults]);

  // Handle search form submit
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(true);
  };

  // Helper to update filters (either external or internal)
  const updateFilters = useCallback((updates: Partial<SearchFilters>) => {
    if (isExternallyControlled && onFiltersChange) {
      onFiltersChange({
        selectedStores,
        selectedStyles,
        selectedColors,
        selectedMaterials,
        priceMin,
        priceMax,
        ...updates,
      });
    } else {
      // Update internal state
      if (updates.selectedStores !== undefined) setInternalSelectedStores(updates.selectedStores);
      if (updates.selectedStyles !== undefined) setInternalSelectedStyles(updates.selectedStyles);
      if (updates.selectedColors !== undefined) setInternalSelectedColors(updates.selectedColors);
      if (updates.selectedMaterials !== undefined) setInternalSelectedMaterials(updates.selectedMaterials);
      if (updates.priceMin !== undefined) setInternalPriceMin(updates.priceMin);
      if (updates.priceMax !== undefined) setInternalPriceMax(updates.priceMax);
    }
  }, [isExternallyControlled, onFiltersChange, selectedStores, selectedStyles, selectedColors, selectedMaterials, priceMin, priceMax]);

  // Toggle filter visibility
  const handleToggleFilters = () => {
    if (onShowFiltersChange) {
      onShowFiltersChange(!showFilters);
    } else {
      setInternalShowFilters(!showFilters);
    }
  };

  // Toggle store filter
  const toggleStore = (store: string) => {
    const newStores = selectedStores.includes(store)
      ? selectedStores.filter(s => s !== store)
      : [...selectedStores, store];
    updateFilters({ selectedStores: newStores });
  };

  // Toggle style filter
  const toggleStyle = (style: string) => {
    const newStyles = selectedStyles.includes(style)
      ? selectedStyles.filter(s => s !== style)
      : [...selectedStyles, style];
    updateFilters({ selectedStyles: newStyles });
  };

  // Toggle color filter
  const toggleColor = (color: string) => {
    const newColors = selectedColors.includes(color)
      ? selectedColors.filter(c => c !== color)
      : [...selectedColors, color];
    updateFilters({ selectedColors: newColors });
  };

  // Toggle material filter
  const toggleMaterial = (material: string) => {
    const newMaterials = selectedMaterials.includes(material)
      ? selectedMaterials.filter(m => m !== material)
      : [...selectedMaterials, material];
    updateFilters({ selectedMaterials: newMaterials });
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedCategory(null);
    updateFilters({
      selectedStores: [],
      selectedStyles: [],
      selectedColors: [],
      selectedMaterials: [],
      priceMin: 0,
      priceMax: Infinity,
    });
  };

  // Check if any filters are active
  const hasActiveFilters = selectedStores.length > 0 ||
    selectedStyles.length > 0 ||
    selectedColors.length > 0 ||
    selectedMaterials.length > 0 ||
    priceMin > 0 ||
    (priceMax < Infinity && priceMax !== 999999);

  // Handle add to canvas from modal
  const handleAddFromModal = () => {
    if (selectedProduct) {
      onAddProduct(selectedProduct);
      setSelectedProduct(null);
    }
  };

  // Render filter panel content (shared between both modes)
  const renderFilterContent = () => (
    <>
      {/* Store Categories */}
      {storeCategories.length > 0 && (
        <div className="mb-3">
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs text-neutral-600 dark:text-neutral-400 font-medium">Stores</label>
            {selectedStores.length > 0 && (
              <button
                type="button"
                onClick={() => updateFilters({ selectedStores: [] })}
                className="text-xs text-neutral-700 hover:text-neutral-800"
              >
                Clear ({selectedStores.length})
              </button>
            )}
          </div>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {storeCategories.map((category) => (
              <div key={category.tier}>
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">
                    {category.label}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 pl-2 border-l-2 border-neutral-200 dark:border-neutral-600">
                  {category.stores.map((store) => (
                    <button
                      type="button"
                      key={store.name}
                      onClick={() => toggleStore(store.name)}
                      className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                        selectedStores.includes(store.name)
                          ? 'bg-neutral-800 text-white'
                          : 'bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600'
                      }`}
                    >
                      {store.display_name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Style Filter */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1.5">
          <label className="text-xs text-neutral-600 dark:text-neutral-400 font-medium">Style</label>
          {selectedStyles.length > 0 && (
            <button
              type="button"
              onClick={() => updateFilters({ selectedStyles: [] })}
              className="text-xs text-neutral-700 hover:text-neutral-800"
            >
              Clear ({selectedStyles.length})
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {PRODUCT_STYLES.map((style) => (
            <button
              type="button"
              key={style.value}
              onClick={() => toggleStyle(style.value)}
              className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                selectedStyles.includes(style.value)
                  ? 'bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 border border-neutral-400 dark:border-neutral-600'
                  : 'bg-white dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-600'
              }`}
            >
              {selectedStyles.includes(style.value) && (
                <svg className="w-2.5 h-2.5 inline mr-0.5 -ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
              {style.label}
            </button>
          ))}
        </div>
      </div>

      {/* Color Filter */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1.5">
          <label className="text-xs text-neutral-600 dark:text-neutral-400 font-medium">Color</label>
          {selectedColors.length > 0 && (
            <button
              type="button"
              onClick={() => updateFilters({ selectedColors: [] })}
              className="text-xs text-neutral-700 hover:text-neutral-800"
            >
              Clear ({selectedColors.length})
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FURNITURE_COLORS.map((color) => (
            <button
              type="button"
              key={color.value}
              onClick={() => toggleColor(color.value)}
              title={color.name}
              className={`w-6 h-6 rounded-full transition-all ${
                selectedColors.includes(color.value)
                  ? 'ring-2 ring-neutral-800 ring-offset-2 dark:ring-offset-neutral-800'
                  : color.border
                    ? 'border border-neutral-300 dark:border-neutral-600'
                    : ''
              }`}
              style={{ backgroundColor: color.color }}
            />
          ))}
        </div>
      </div>

      {/* Material Filter */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1.5">
          <label className="text-xs text-neutral-600 dark:text-neutral-400 font-medium">Material</label>
          {selectedMaterials.length > 0 && (
            <button
              type="button"
              onClick={() => updateFilters({ selectedMaterials: [] })}
              className="text-xs text-neutral-700 hover:text-neutral-800"
            >
              Clear ({selectedMaterials.length})
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {PRODUCT_MATERIALS.map((material) => (
            <button
              type="button"
              key={material.value}
              onClick={() => toggleMaterial(material.value)}
              className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                selectedMaterials.includes(material.value)
                  ? 'bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 border border-neutral-400 dark:border-neutral-600'
                  : 'bg-white dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-600'
              }`}
            >
              {material.label}
            </button>
          ))}
        </div>
      </div>

      {/* Price Range */}
      <div className="mb-3">
        <label className="text-xs text-neutral-600 dark:text-neutral-400 font-medium mb-1.5 block">
          Price Range
        </label>
        <div className="flex gap-2 items-center">
          <input
            type="number"
            placeholder="Min"
            value={priceMin === 0 ? '' : priceMin}
            onChange={(e) => updateFilters({ priceMin: Number(e.target.value) || 0 })}
            className="flex-1 text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-neutral-500"
          />
          <span className="text-neutral-400 text-xs">-</span>
          <input
            type="number"
            placeholder="Max"
            value={priceMax >= 999999 || priceMax === Infinity ? '' : priceMax}
            onChange={(e) => updateFilters({ priceMax: Number(e.target.value) || Infinity })}
            className="flex-1 text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-neutral-500"
          />
        </div>
      </div>

      {/* Sort & Clear */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <label className="text-xs text-neutral-600 dark:text-neutral-400">Sort:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="text-xs px-2 py-1 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded focus:outline-none focus:ring-1 focus:ring-neutral-500"
          >
            <option value="relevance">Relevance</option>
            <option value="price-low">Price: Low to High</option>
            <option value="price-high">Price: High to Low</option>
          </select>
        </div>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-xs text-neutral-700 hover:text-neutral-800 dark:text-neutral-400 font-medium"
          >
            Clear all filters
          </button>
        )}
      </div>
    </>
  );

  // =============================================
  // KEYWORD SEARCH MODE - Search input + filters + results in scrollable layout
  // =============================================
  if (showSearchInput) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        {/* Search Input - Fixed at top */}
        <div className={`flex-shrink-0 ${compact ? 'p-3' : 'p-4'} pb-0`}>
          <form onSubmit={handleSearchSubmit}>
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSearch(true);
                  }
                }}
                placeholder={searchPlaceholder}
                className="w-full px-4 py-2 pl-10 text-sm border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-transparent"
              />
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
          </form>
        </div>

        {/* Scrollable Content Area - Filters + Results */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {/* Collapsible Filters Section */}
          <div className={`${compact ? 'px-3' : 'px-4'} py-3 border-b border-neutral-200 dark:border-neutral-700`}>
            {/* Filter Toggle Header */}
            <button
              type="button"
              onClick={handleToggleFilters}
              className="w-full flex items-center justify-between text-sm font-medium text-neutral-700 dark:text-neutral-300 hover:text-neutral-900 dark:hover:text-white"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                Filters
                {hasActiveFilters && (
                  <span className="px-1.5 py-0.5 text-xs bg-neutral-200 text-neutral-800 dark:bg-neutral-700 dark:text-neutral-200 rounded">
                    Active
                  </span>
                )}
              </span>
              <svg
                className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Expanded Filters */}
            {showFilters && (
              <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700">
                {renderFilterContent()}
              </div>
            )}
          </div>

          {/* Search Button */}
          <div className={`${compact ? 'px-3 py-2' : 'px-4 py-3'} border-b border-neutral-200 dark:border-neutral-700`}>
            {/* Search Results Info */}
            {products.length > 0 && (
              <div className="text-xs text-neutral-600 dark:text-neutral-400 mb-2 text-center">
                {totalPrimary > 0 && (
                  <span className="text-neutral-800 dark:text-neutral-200 font-medium">{totalPrimary} best matches</span>
                )}
                {totalPrimary > 0 && totalRelated > 0 && <span> + </span>}
                {totalRelated > 0 && <span>{totalRelated} more</span>}
                {totalPrimary === 0 && totalRelated === 0 && <span>{totalProducts} products</span>}
              </div>
            )}

            <button
              type="button"
              onClick={() => handleSearch(true)}
              disabled={isSearching || (!searchQuery.trim() && !hasActiveFilters)}
              className="w-full py-2.5 bg-neutral-800 hover:bg-neutral-900 disabled:bg-neutral-300 dark:disabled:bg-neutral-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {isSearching ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  Search Products
                </>
              )}
            </button>
          </div>

          {/* Search Results */}
          {showResultsInline && (
            <div className={`${compact ? 'p-3' : 'p-4'}`}>
              {searchError ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <svg className="w-12 h-12 text-red-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-red-500 dark:text-red-400">{searchError}</p>
                  <button
                    onClick={() => handleSearch(true)}
                    className="mt-3 text-sm text-neutral-700 hover:text-neutral-800"
                  >
                    Try again
                  </button>
                </div>
              ) : (
                <ProductResultsGrid
                  products={products}
                  onAddProduct={onAddProduct}
                  canvasProducts={canvasProducts}
                  onViewDetails={setSelectedProduct}
                  showSeparation={true}
                  enableInfiniteScroll={true}
                  onLoadMore={handleLoadMore}
                  hasMore={hasMore}
                  isLoadingMore={isLoadingMore}
                  totalCount={totalProducts}
                  isLoading={isSearching && products.length === 0}
                  emptyMessage={searchQuery ? 'No products found for your search' : 'Enter a search term or select filters to find products'}
                  gridClassName={compact ? 'grid grid-cols-2 gap-2' : 'grid grid-cols-2 md:grid-cols-3 gap-2'}
                  cardSize={compact ? 'small' : 'medium'}
                />
              )}
            </div>
          )}
        </div>

        {/* Product Detail Modal */}
        {selectedProduct && (
          <ProductDetailModal
            product={selectedProduct}
            isOpen={true}
            onClose={() => setSelectedProduct(null)}
            onAddToCanvas={handleAddFromModal}
            inCanvas={canvasProducts.some(p => p.id?.toString() === selectedProduct.id?.toString())}
            canvasQuantity={canvasProducts.find(p => p.id?.toString() === selectedProduct.id?.toString())?.quantity || 0}
          />
        )}
      </div>
    );
  }

  // =============================================
  // AI STYLIST MODE - Collapsible filter panel only
  // =============================================
  return (
    <div className={`flex flex-col ${showResultsInline ? 'h-full' : ''}`}>
      {/* Filter Toggle Header */}
      <div className={`${compact ? 'p-3' : 'p-4'} ${showResultsInline ? 'border-b border-neutral-200 dark:border-neutral-700' : ''}`}>
        {/* Filter Toggle */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-neutral-600 dark:text-neutral-400">
            {hasActiveFilters ? (
              <span className="text-neutral-800 dark:text-neutral-200 font-medium">Filters active</span>
            ) : (
              <span>Filter recommendations</span>
            )}
          </div>
          <FilterToggleButton
            isOpen={showFilters}
            onClick={handleToggleFilters}
            hasActiveFilters={hasActiveFilters}
          />
        </div>

        {/* Collapsible Filter Panel */}
        {showFilters && (
          <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700 max-h-[60vh] overflow-y-auto">
            {renderFilterContent()}
          </div>
        )}
      </div>

      {/* Search Results - Only show inline if showResultsInline is true */}
      {showResultsInline && (
        <div className="flex-1 overflow-y-auto p-4">
          {searchError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <svg className="w-12 h-12 text-red-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-red-500 dark:text-red-400">{searchError}</p>
              <button
                onClick={() => handleSearch(true)}
                className="mt-3 text-sm text-neutral-700 hover:text-neutral-800"
              >
                Try again
              </button>
            </div>
          ) : (
            <ProductResultsGrid
              products={products}
              onAddProduct={onAddProduct}
              canvasProducts={canvasProducts}
              onViewDetails={setSelectedProduct}
              showSeparation={true}
              enableInfiniteScroll={true}
              onLoadMore={handleLoadMore}
              hasMore={hasMore}
              isLoadingMore={isLoadingMore}
              totalCount={totalProducts}
              isLoading={isSearching && products.length === 0}
              emptyMessage="Chat with AI Stylist to get personalized recommendations"
              gridClassName={compact ? 'grid grid-cols-2 gap-2' : 'grid grid-cols-2 md:grid-cols-3 gap-2'}
              cardSize={compact ? 'small' : 'medium'}
            />
          )}
        </div>
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          isOpen={true}
          onClose={() => setSelectedProduct(null)}
          onAddToCanvas={handleAddFromModal}
          inCanvas={canvasProducts.some(p => p.id?.toString() === selectedProduct.id?.toString())}
          canvasQuantity={canvasProducts.find(p => p.id?.toString() === selectedProduct.id?.toString())?.quantity || 0}
        />
      )}
    </div>
  );
});
