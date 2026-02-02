'use client';

import { PRODUCT_STYLES, PRICE_RANGES } from '@/constants/products';
import { ProductFilters } from '@/hooks/useProductFilters';
import { StoreCategory } from '@/utils/api';

interface ProductFilterPanelProps {
  /** Current filter state */
  filters: ProductFilters;
  /** Unique stores available for filtering */
  availableStores: string[];
  /** Store categories for grouped filtering (optional) */
  storeCategories?: StoreCategory[];
  /** Callback when store filter changes */
  onStoreChange: (stores: string[]) => void;
  /** Callback to toggle a single store */
  onToggleStore: (store: string) => void;
  /** Callback when style filter changes */
  onStyleChange: (styles: string[]) => void;
  /** Callback to toggle a single style */
  onToggleStyle: (style: string) => void;
  /** Callback when price range changes */
  onPriceRangeChange: (range: { min: number; max: number } | null) => void;
  /** Callback when price inputs change (for custom range) */
  onPriceInputChange?: (priceMin: number, priceMax: number) => void;
  /** Callback when sort order changes */
  onSortByChange: (sortBy: ProductFilters['sortBy']) => void;
  /** Callback when store category changes */
  onStoreCategoryChange?: (category: ProductFilters['storeCategory']) => void;
  /** Callback to clear all filters */
  onClearFilters: () => void;
  /** Whether to show store category tabs */
  showStoreCategory?: boolean;
  /** Whether to show style filter */
  showStyleFilter?: boolean;
  /** Whether to show price filter */
  showPriceFilter?: boolean;
  /** Whether to show sort dropdown */
  showSortBy?: boolean;
  /** Use compact mode (inline) */
  compact?: boolean;
  /** Custom price min value for inputs */
  priceMin?: number;
  /** Custom price max value for inputs */
  priceMax?: number;
}

/**
 * ProductFilterPanel Component
 *
 * Shared filter panel UI for product discovery.
 * Supports stores (grouped by category), styles, price ranges, and sorting.
 */
export function ProductFilterPanel({
  filters,
  availableStores,
  storeCategories,
  onStoreChange,
  onToggleStore,
  onStyleChange,
  onToggleStyle,
  onPriceRangeChange,
  onPriceInputChange,
  onSortByChange,
  onStoreCategoryChange,
  onClearFilters,
  showStoreCategory = false,
  showStyleFilter = true,
  showPriceFilter = true,
  showSortBy = true,
  compact = false,
  priceMin = 0,
  priceMax = Infinity,
}: ProductFilterPanelProps) {
  // Handle price input changes
  const handlePriceMinChange = (value: string) => {
    const numValue = Number(value) || 0;
    if (onPriceInputChange) {
      onPriceInputChange(numValue, priceMax);
    } else {
      onPriceRangeChange({ min: numValue, max: priceMax === Infinity ? 999999 : priceMax });
    }
  };

  const handlePriceMaxChange = (value: string) => {
    const numValue = Number(value) || Infinity;
    if (onPriceInputChange) {
      onPriceInputChange(priceMin, numValue);
    } else {
      onPriceRangeChange({ min: priceMin, max: numValue });
    }
  };

  // Toggle all stores
  const toggleAllStores = () => {
    const allStoreNames = storeCategories
      ? storeCategories.flatMap(c => c.stores.map(s => s.name))
      : availableStores;

    if (filters.stores.length === allStoreNames.length) {
      onStoreChange([]);
    } else {
      onStoreChange([...allStoreNames]);
    }
  };

  const hasActiveFilters = filters.stores.length > 0 ||
    filters.styles.length > 0 ||
    (filters.priceRange !== null) ||
    filters.storeCategory !== 'all';

  return (
    <div className={`space-y-3 ${compact ? '' : 'bg-neutral-50 dark:bg-neutral-800/50 rounded-lg p-3'}`}>
      {/* Store Category Tabs */}
      {showStoreCategory && onStoreCategoryChange && (
        <div className="flex gap-2 flex-wrap">
          {(['all', 'luxury', 'budget', 'marketplace'] as const).map((category) => (
            <button
              key={category}
              onClick={() => onStoreCategoryChange(category)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                filters.storeCategory === category
                  ? 'bg-neutral-800 text-white'
                  : 'bg-white dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-600'
              }`}
            >
              {category === 'all' ? 'All Stores' : category.charAt(0).toUpperCase() + category.slice(1)}
            </button>
          ))}
        </div>
      )}

      {/* Store Filter - Categorized by Budget Tier */}
      {storeCategories && storeCategories.length > 0 && (
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs text-neutral-600 dark:text-neutral-400">
              Stores
            </label>
            <button
              onClick={toggleAllStores}
              className="text-xs text-neutral-700 hover:text-neutral-800"
            >
              {filters.stores.length === storeCategories.flatMap(c => c.stores).length
                ? 'Deselect all'
                : 'Select all'}
            </button>
          </div>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {storeCategories.map((category) => (
              <div key={category.tier}>
                {/* Category Header */}
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">
                    {category.label}
                  </span>
                  <span className="text-[10px] text-neutral-400">({category.stores.length})</span>
                </div>
                {/* Stores in this category */}
                <div className="flex flex-wrap gap-1 pl-2 border-l-2 border-neutral-200 dark:border-neutral-600">
                  {category.stores.map((store) => (
                    <button
                      key={store.name}
                      onClick={() => onToggleStore(store.name)}
                      className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                        filters.stores.includes(store.name)
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

      {/* Simple Store Filter (fallback when no categories) */}
      {(!storeCategories || storeCategories.length === 0) && availableStores.length > 0 && (
        <div>
          <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block">
            Store
          </label>
          <div className="flex flex-wrap gap-1.5">
            {availableStores.map(store => (
              <button
                key={store}
                onClick={() => onToggleStore(store)}
                className={`text-[10px] px-2 py-1 rounded-full transition-colors ${
                  filters.stores.includes(store)
                    ? 'bg-neutral-800 text-white'
                    : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                }`}
              >
                {store}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Style Filter */}
      {showStyleFilter && (
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs text-neutral-600 dark:text-neutral-400">
              Style
            </label>
            {filters.styles.length > 0 && (
              <button
                onClick={() => onStyleChange([])}
                className="text-xs text-neutral-700 hover:text-neutral-800"
              >
                Clear ({filters.styles.length})
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {PRODUCT_STYLES.map((style) => (
              <button
                key={style.value}
                onClick={() => onToggleStyle(style.value)}
                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                  filters.styles.includes(style.value)
                    ? 'bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 border border-neutral-400 dark:border-neutral-600'
                    : 'bg-white dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-600'
                }`}
              >
                {filters.styles.includes(style.value) && (
                  <svg className="w-2.5 h-2.5 inline mr-0.5 -ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
                {style.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Price Range */}
      {showPriceFilter && (
        <div>
          <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block">
            Price Range
          </label>
          <div className="flex gap-2 items-center">
            <input
              type="number"
              placeholder="Min"
              value={priceMin === 0 ? '' : priceMin}
              onChange={(e) => handlePriceMinChange(e.target.value)}
              className="flex-1 text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-neutral-500"
            />
            <span className="text-neutral-400 text-xs">-</span>
            <input
              type="number"
              placeholder="Max"
              value={priceMax >= 999999 || priceMax === Infinity ? '' : priceMax}
              onChange={(e) => handlePriceMaxChange(e.target.value)}
              className="flex-1 text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-neutral-500"
            />
          </div>
        </div>
      )}

      {/* Sort */}
      {showSortBy && (
        <div>
          <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block">
            Sort By
          </label>
          <select
            value={filters.sortBy}
            onChange={(e) => onSortByChange(e.target.value as ProductFilters['sortBy'])}
            className="w-full text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-neutral-500"
          >
            <option value="relevance">Relevance</option>
            <option value="price-low">Price: Low to High</option>
            <option value="price-high">Price: High to Low</option>
          </select>
        </div>
      )}

      {/* Clear Filters */}
      {hasActiveFilters && (
        <button
          onClick={onClearFilters}
          className="text-xs text-neutral-700 hover:text-neutral-800 dark:text-neutral-400 font-medium"
        >
          Clear all filters
        </button>
      )}
    </div>
  );
}

/**
 * FilterToggleButton Component
 *
 * Button to show/hide filter panel.
 */
interface FilterToggleButtonProps {
  isOpen: boolean;
  onClick: () => void;
  hasActiveFilters: boolean;
}

export function FilterToggleButton({
  isOpen,
  onClick,
  hasActiveFilters,
}: FilterToggleButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
        hasActiveFilters
          ? 'bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 border border-neutral-400 dark:border-neutral-600'
          : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
      }`}
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
      </svg>
      Filter
      {hasActiveFilters && (
        <span className="w-1.5 h-1.5 bg-neutral-800 rounded-full"></span>
      )}
    </button>
  );
}

/**
 * ActiveFiltersSummary Component
 *
 * Shows active filters as removable chips.
 */
interface ActiveFiltersSummaryProps {
  filters: ProductFilters;
  onRemoveStore: (store: string) => void;
  onClearPriceRange: () => void;
  priceMin?: number;
  priceMax?: number;
}

export function ActiveFiltersSummary({
  filters,
  onRemoveStore,
  onClearPriceRange,
  priceMin = 0,
  priceMax = Infinity,
}: ActiveFiltersSummaryProps) {
  const hasFilters = filters.stores.length > 0 ||
    (priceMin > 0 || (priceMax < Infinity && priceMax !== 999999));

  if (!hasFilters) return null;

  return (
    <div className="flex items-center gap-2 mt-2 flex-wrap">
      {filters.stores.map(store => (
        <span
          key={store}
          className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 rounded-full"
        >
          {store}
          <button
            onClick={() => onRemoveStore(store)}
            className="hover:text-neutral-900 dark:hover:text-neutral-100"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </span>
      ))}
      {(priceMin > 0 || (priceMax < Infinity && priceMax !== 999999)) && (
        <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 rounded-full">
          {'\u20B9'}{priceMin > 0 ? priceMin : '0'} - {'\u20B9'}{priceMax < Infinity && priceMax !== 999999 ? priceMax : '\u221E'}
          <button
            onClick={onClearPriceRange}
            className="hover:text-neutral-900 dark:hover:text-neutral-100"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </span>
      )}
    </div>
  );
}
