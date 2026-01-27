'use client';

import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import { ProductDetailModal } from '../ProductDetailModal';
import { Product } from '@/types';
import { formatCurrency } from '@/utils/format';
import CategorySection, { CategoryRecommendation } from './CategorySection';
import CategoryCarousel from './CategoryCarousel';
// Shared utilities
import {
  transformProduct as transformProductUtil,
  ExtendedProduct,
  getProductImageUrl,
  isProductInCanvas,
  getCanvasQuantity as getCanvasQuantityUtil,
  calculateDiscountPercentage,
} from '@/utils/product-transforms';
// Shared product search components
import { ProductResultsGrid } from '../products/ProductResultsGrid';

type SearchMode = 'ai' | 'keyword';

// Keyword search results from Panel 1
interface KeywordSearchResults {
  products: ExtendedProduct[];
  totalProducts: number;
  totalPrimary: number;
  totalRelated: number;
  hasMore: boolean;
  isSearching: boolean;
}

interface ProductDiscoveryPanelProps {
  products: any[];  // Raw products from API (legacy flat list)
  onAddToCanvas: (product: any) => void;
  canvasProducts: any[];
  // NEW: Category-based recommendations
  selectedCategories?: CategoryRecommendation[] | null;
  productsByCategory?: Record<string, any[]> | null;
  totalBudget?: number | null;
  // Session ID for pagination/infinite scroll
  sessionId?: string | null;
  // Search mode toggle
  enableModeToggle?: boolean;
  defaultSearchMode?: SearchMode;
  // Keyword search results from Panel 1 (when in keyword mode)
  keywordSearchResults?: KeywordSearchResults | null;
  // Callback for loading more keyword search results
  onLoadMoreKeywordResults?: () => void;
  // Whether we're currently in keyword search mode
  isKeywordSearchMode?: boolean;
}

/**
 * Panel 2: Product Discovery & Selection
 * Displays products with modal details and Add to Canvas functionality
 */
export default function ProductDiscoveryPanel({
  products,
  onAddToCanvas,
  canvasProducts,
  selectedCategories,
  productsByCategory,
  totalBudget,
  sessionId,
  enableModeToggle = true,
  defaultSearchMode = 'ai',
  keywordSearchResults,
  onLoadMoreKeywordResults,
  isKeywordSearchMode = false,
}: ProductDiscoveryPanelProps) {
  console.log('[ProductDiscoveryPanel] Received products:', products.length, 'products');
  console.log('[ProductDiscoveryPanel] Category mode:', selectedCategories ? 'YES' : 'NO');
  console.log('[ProductDiscoveryPanel] productsByCategory exists:', !!productsByCategory);
  if (productsByCategory) {
    const categoryKeys = Object.keys(productsByCategory);
    const totalProducts = Object.values(productsByCategory).reduce((sum, prods) => sum + (prods?.length || 0), 0);
    console.log('[ProductDiscoveryPanel] Categories in productsByCategory:', categoryKeys, 'Total products:', totalProducts);
  }
  if (selectedCategories) {
    console.log('[ProductDiscoveryPanel] selectedCategories:', selectedCategories.map(c => c.category_id));
  }

  const [selectedProduct, setSelectedProduct] = useState<ExtendedProduct | null>(null);
  const [sortBy, setSortBy] = useState<'relevance' | 'price-low' | 'price-high'>(
    'relevance'
  );

  // Filter states
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState<{ min: number; max: number }>({ min: 0, max: Infinity });
  const [showFilters, setShowFilters] = useState(false);

  // Ref for the scrollable products container
  const productsContainerRef = useRef<HTMLDivElement>(null);

  // NEW: State for "View All" mode - which category to show in full grid (null = carousel view)
  const [viewAllCategory, setViewAllCategory] = useState<string | null>(null);

  // Store scroll positions for each view layer to persist scroll when navigating back
  const scrollPositionsRef = useRef<Record<string, number>>({
    carousel: 0,  // Main carousel/all-categories view
    // category_id: scroll position for each category's view all mode
  });

  // Save current scroll position for the current view
  const saveScrollPosition = (viewKey: string) => {
    if (productsContainerRef.current) {
      scrollPositionsRef.current[viewKey] = productsContainerRef.current.scrollTop;
      console.log(`[ProductDiscoveryPanel] Saved scroll position for "${viewKey}":`, scrollPositionsRef.current[viewKey]);
    }
  };

  // Restore scroll position for a view (called after render via useEffect)
  const restoreScrollPosition = (viewKey: string) => {
    if (productsContainerRef.current && scrollPositionsRef.current[viewKey] !== undefined) {
      const savedPosition = scrollPositionsRef.current[viewKey];
      productsContainerRef.current.scrollTop = savedPosition;
      console.log(`[ProductDiscoveryPanel] Restored scroll position for "${viewKey}":`, savedPosition);
    }
  };

  // Handle entering "View All" mode for a category
  const handleViewAll = (categoryId: string) => {
    // Save carousel scroll position before navigating
    saveScrollPosition('carousel');
    setViewAllCategory(categoryId);
  };

  // Handle going back to carousel view from category view
  const handleBackToCarousel = () => {
    // Save current category's scroll position (in case user returns)
    if (viewAllCategory) {
      saveScrollPosition(viewAllCategory);
    }
    setViewAllCategory(null);
  };

  // Restore scroll position when view changes
  useEffect(() => {
    // Use requestAnimationFrame to ensure DOM has updated
    requestAnimationFrame(() => {
      if (viewAllCategory) {
        // Entering a category - restore that category's scroll position (or start at top)
        restoreScrollPosition(viewAllCategory);
      } else {
        // Returning to carousel - restore carousel scroll position
        restoreScrollPosition('carousel');
      }
    });
  }, [viewAllCategory]);

  // Reset viewAllCategory when categories change (new search/recommendation)
  // This ensures we don't show an old category when new results come in
  useEffect(() => {
    if (selectedCategories) {
      const categoryIds = selectedCategories.map(c => c.category_id);
      // If current viewAllCategory doesn't exist in new categories, reset to carousel view
      if (viewAllCategory && !categoryIds.includes(viewAllCategory)) {
        console.log('[ProductDiscoveryPanel] Resetting viewAllCategory - category no longer exists');
        setViewAllCategory(null);
      }
      console.log('[ProductDiscoveryPanel] New categories received:', categoryIds);

      // Reset all scroll positions when new categories arrive (fresh start)
      scrollPositionsRef.current = { carousel: 0 };

      // Scroll to top when new categories arrive
      if (productsContainerRef.current) {
        productsContainerRef.current.scrollTo({
          top: 0,
          behavior: 'smooth'
        });
        console.log('[ProductDiscoveryPanel] Scrolling to top - new categories loaded');
      }
    }
  }, [selectedCategories]);

  // Scroll to top when new products arrive
  useEffect(() => {
    if (products.length > 0 && productsContainerRef.current) {
      productsContainerRef.current.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
      console.log('[ProductDiscoveryPanel] Scrolling to top - new products loaded');
    }
  }, [products]);

  // Transform raw product to Product type (using shared utility)
  const transformProduct = (rawProduct: any): ExtendedProduct => {
    return transformProductUtil(rawProduct);
  };

  // Check if product is in canvas and get quantity (using shared utility)
  const isInCanvas = (productId: string | number) => {
    return isProductInCanvas(productId, canvasProducts);
  };

  // Get quantity of product in canvas (using shared utility)
  const getCanvasQuantity = (productId: string | number) => {
    return getCanvasQuantityUtil(productId, canvasProducts);
  };

  // Handle product click (open modal)
  const handleProductClick = (product: ExtendedProduct) => {
    setSelectedProduct(product);
  };

  // Handle add to canvas from modal
  const handleAddToCanvasFromModal = () => {
    if (selectedProduct) {
      onAddToCanvas(selectedProduct);
      setSelectedProduct(null); // Close modal after adding
    }
  };

  // Get unique store names
  const uniqueStores = Array.from(
    new Set(products.map(p => p.source_website || p.source).filter(Boolean))
  ).sort();

  // Transform all products first
  const transformedProducts = products.map(transformProduct);

  // Apply filters
  const filteredProducts = transformedProducts.filter(product => {
    const price = product.price || 0;
    const store = product.source_website;

    // Price filter
    if (price < priceRange.min || price > priceRange.max) return false;

    // Store filter
    if (selectedStores.length > 0 && !selectedStores.includes(store)) return false;

    return true;
  });

  // Sort products
  const sortedProducts = [...filteredProducts].sort((a, b) => {
    switch (sortBy) {
      case 'price-low':
        return (a.price || 0) - (b.price || 0);
      case 'price-high':
        return (b.price || 0) - (a.price || 0);
      default:
        return 0;
    }
  });

  // Toggle store filter
  const toggleStore = (store: string) => {
    setSelectedStores(prev =>
      prev.includes(store)
        ? prev.filter(s => s !== store)
        : [...prev, store]
    );
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedStores([]);
    setPriceRange({ min: 0, max: Infinity });
  };

  // Check if we have category-based products
  const hasCategoryProducts = selectedCategories && productsByCategory &&
    selectedCategories.length > 0 &&
    Object.values(productsByCategory).some(prods => prods && prods.length > 0);

  // Get all products across all categories for filter options
  const allCategoryProducts = hasCategoryProducts
    ? Object.values(productsByCategory!).flat().filter(Boolean)
    : [];

  // Calculate total products across all categories
  const totalCategoryProducts = allCategoryProducts.length;

  // Get unique stores from category products
  const uniqueCategoryStores = Array.from(
    new Set(allCategoryProducts.map((p: any) => p.source_website || p.source).filter(Boolean))
  ).sort() as string[];

  // Filter products in a category based on selected filters
  const filterCategoryProducts = (categoryProducts: any[]) => {
    if (selectedStores.length === 0 && priceRange.min === 0 && priceRange.max === Infinity) {
      return categoryProducts; // No filters applied
    }
    return categoryProducts.filter((product: any) => {
      const price = parseFloat(product.price) || 0;
      const store = product.source_website || product.source;

      // Price filter
      if (price < priceRange.min || price > priceRange.max) return false;

      // Store filter
      if (selectedStores.length > 0 && !selectedStores.includes(store)) return false;

      return true;
    });
  };

  // Check if any filters are active
  const hasActiveFilters = selectedStores.length > 0 || priceRange.min > 0 || priceRange.max < Infinity;

  // If in keyword search mode, display keyword search results from Panel 1
  if (isKeywordSearchMode) {
    const hasKeywordResults = keywordSearchResults && keywordSearchResults.products.length > 0;
    const isLoading = keywordSearchResults?.isSearching && !hasKeywordResults;

    return (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-700">
          <h2 className="font-semibold text-neutral-900 dark:text-white">
            Search Results
          </h2>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            {hasKeywordResults
              ? `${keywordSearchResults.totalProducts} products found`
              : 'Use the search panel to find products'}
          </p>
        </div>

        {/* Results */}
        <div ref={productsContainerRef} className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
              <p className="text-sm text-neutral-500 dark:text-neutral-400">Searching products...</p>
            </div>
          ) : hasKeywordResults ? (
            <ProductResultsGrid
              products={keywordSearchResults.products}
              onAddProduct={(product) => onAddToCanvas(product)}
              canvasProducts={canvasProducts.map(p => ({ id: p.id, quantity: p.quantity }))}
              onViewDetails={setSelectedProduct}
              showSeparation={true}
              enableInfiniteScroll={true}
              onLoadMore={onLoadMoreKeywordResults}
              hasMore={keywordSearchResults.hasMore}
              isLoadingMore={keywordSearchResults.isSearching && keywordSearchResults.products.length > 0}
              totalCount={keywordSearchResults.totalProducts}
              totalPrimaryCount={keywordSearchResults.totalPrimary}
              totalRelatedCount={keywordSearchResults.totalRelated}
              isLoading={false}
              emptyMessage="No products found"
              gridClassName="grid grid-cols-2 md:grid-cols-3 gap-3"
              cardSize="medium"
            />
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-20 h-20 bg-neutral-100 dark:bg-neutral-700 rounded-full flex items-center justify-center mb-4">
                <svg className="w-10 h-10 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-2">
                Ready to Search
              </h3>
              <p className="text-sm text-neutral-600 dark:text-neutral-400 max-w-sm">
                Enter a search term in the search panel and click Search to find products.
              </p>
            </div>
          )}
        </div>

        {/* Product Detail Modal */}
        {selectedProduct && (
          <ProductDetailModal
            product={selectedProduct}
            isOpen={true}
            onClose={() => setSelectedProduct(null)}
            onAddToCanvas={handleAddToCanvasFromModal}
            inCanvas={isInCanvas(selectedProduct.id)}
            canvasQuantity={getCanvasQuantity(selectedProduct.id)}
          />
        )}
      </div>
    );
  }

  // Empty state - show if no products in AI mode
  if (products.length === 0 && !hasCategoryProducts) {
    return (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-700">
          <h2 className="font-semibold text-neutral-900 dark:text-white">
            AI Recommendations
          </h2>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            Products curated for your room
          </p>
        </div>
        <div className="flex flex-col items-center justify-center flex-1 p-8 text-center">
          <div className="w-24 h-24 bg-neutral-100 dark:bg-neutral-700 rounded-full flex items-center justify-center mb-4">
            <svg
              className="w-12 h-12 text-neutral-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-2">
            No Recommendations Yet
          </h3>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 max-w-sm">
            Start chatting with the AI Stylist to get personalized furniture
            recommendations for your room.
          </p>
        </div>
      </div>
    );
  }

  // ====================
  // CATEGORY-BASED VIEW
  // ====================
  if (hasCategoryProducts && selectedCategories) {
    // Get the expanded category if in "View All" mode
    const expandedCategoryData = viewAllCategory
      ? selectedCategories.find(c => c.category_id === viewAllCategory)
      : null;

    // VIEW ALL MODE - Show single category with full grid and filters
    if (viewAllCategory && expandedCategoryData) {
      return (
        <div className="flex flex-col h-full">
          {/* Header with Back Button */}
          <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
            <button
              onClick={handleBackToCarousel}
              className="flex items-center gap-2 text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 mb-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to all categories
            </button>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-neutral-900 dark:text-white">
                  {expandedCategoryData.display_name}
                </h2>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">
                  {productsByCategory![viewAllCategory]?.length || 0} items
                  {expandedCategoryData.budget_allocation && (
                    <span className="ml-2 text-primary-600 dark:text-primary-400">
                      • Budget: ₹{Math.round(expandedCategoryData.budget_allocation.min / 1000)}K - ₹{Math.round(expandedCategoryData.budget_allocation.max / 1000)}K
                    </span>
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Full Category Section with filters */}
          <div ref={productsContainerRef} className="flex-1 overflow-y-auto">
            <CategorySection
              category={expandedCategoryData}
              products={productsByCategory![viewAllCategory] || []}
              onAddToCanvas={onAddToCanvas}
              canvasProducts={canvasProducts}
              isExpanded={true}
              onToggleExpand={() => {}}
              sessionId={sessionId || undefined}
              hasMore={true}
            />
          </div>
        </div>
      );
    }

    // CAROUSEL MODE - Default view with horizontal scrolling carousels
    return (
      <div className="flex flex-col h-full">
        {/* Header with Filter Toggle */}
        <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="font-semibold text-neutral-900 dark:text-white">
                Curated for You
              </h2>
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                {selectedCategories.length} categories • {totalCategoryProducts} items
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* Filter Toggle Button */}
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  hasActiveFilters
                    ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 border border-primary-300 dark:border-primary-700'
                    : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                Filter
                {hasActiveFilters && (
                  <span className="w-1.5 h-1.5 bg-primary-500 rounded-full"></span>
                )}
              </button>
              {totalBudget && (
                <div className="text-right">
                  <p className="text-[10px] text-neutral-500 dark:text-neutral-400">Budget</p>
                  <p className="text-sm font-semibold text-primary-600 dark:text-primary-400">
                    ₹{(totalBudget / 1000).toFixed(0)}K
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Collapsible Filter Panel */}
          {showFilters && (
            <div className="pt-3 mt-3 border-t border-neutral-200 dark:border-neutral-700 space-y-3">
              {/* Store Filter */}
              {uniqueCategoryStores.length > 0 && (
                <div>
                  <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block font-medium">
                    Store
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {uniqueCategoryStores.map(store => (
                      <button
                        key={store}
                        onClick={() => toggleStore(store)}
                        className={`text-[10px] px-2 py-1 rounded-full transition-colors ${
                          selectedStores.includes(store)
                            ? 'bg-primary-600 text-white'
                            : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                        }`}
                      >
                        {store}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Price Range Filter */}
              <div>
                <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block font-medium">
                  Price Range
                </label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    placeholder="Min"
                    value={priceRange.min === 0 ? '' : priceRange.min}
                    onChange={(e) => setPriceRange({ ...priceRange, min: Number(e.target.value) || 0 })}
                    className="w-20 text-xs px-2 py-1.5 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                  <span className="text-neutral-400 text-xs">-</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={priceRange.max === Infinity ? '' : priceRange.max}
                    onChange={(e) => setPriceRange({ ...priceRange, max: Number(e.target.value) || Infinity })}
                    className="w-20 text-xs px-2 py-1.5 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              {/* Clear Filters */}
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}

          {/* Active Filters Summary (shown when filter panel is collapsed) */}
          {!showFilters && hasActiveFilters && (
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {selectedStores.map(store => (
                <span
                  key={store}
                  className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-full"
                >
                  {store}
                  <button
                    onClick={() => toggleStore(store)}
                    className="hover:text-primary-900 dark:hover:text-primary-100"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </span>
              ))}
              {(priceRange.min > 0 || priceRange.max < Infinity) && (
                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-full">
                  ₹{priceRange.min > 0 ? priceRange.min : '0'} - ₹{priceRange.max < Infinity ? priceRange.max : '∞'}
                  <button
                    onClick={() => setPriceRange({ min: 0, max: Infinity })}
                    className="hover:text-primary-900 dark:hover:text-primary-100"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Category Carousels */}
        <div ref={productsContainerRef} className="flex-1 overflow-y-auto">
          {selectedCategories.sort((a, b) => a.priority - b.priority).map((category) => {
            const filteredProducts = filterCategoryProducts(productsByCategory![category.category_id] || []);
            // Skip categories with no products after filtering
            if (filteredProducts.length === 0) return null;
            return (
              <CategoryCarousel
                key={category.category_id}
                category={category}
                products={filteredProducts}
                onAddToCanvas={onAddToCanvas}
                canvasProducts={canvasProducts}
                onViewAll={() => handleViewAll(category.category_id)}
              />
            );
          })}
        </div>
      </div>
    );
  }

  // ====================
  // LEGACY FLAT GRID VIEW (original behavior)
  // ====================

  return (
    <>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-neutral-900 dark:text-white">
              Product Discovery
            </h2>
            <span className="text-sm text-neutral-600 dark:text-neutral-400">
              {sortedProducts.length} / {products.length} results
            </span>
          </div>

          {/* Filters & Sort */}
          <div className="space-y-3">
            {/* Sort */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-neutral-600 dark:text-neutral-400">
                Sort:
              </label>
              <select
                value={sortBy}
                onChange={(e) =>
                  setSortBy(e.target.value as 'relevance' | 'price-low' | 'price-high')
                }
                className="flex-1 text-sm px-3 py-1.5 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="relevance">Relevance</option>
                <option value="price-low">Price: Low to High</option>
                <option value="price-high">Price: High to Low</option>
              </select>
            </div>

            {/* Store Filter */}
            {uniqueStores.length > 0 && (
              <div>
                <label className="text-sm text-neutral-600 dark:text-neutral-400 mb-2 block">
                  Store:
                </label>
                <div className="flex flex-wrap gap-2">
                  {uniqueStores.map(store => (
                    <button
                      key={store}
                      onClick={() => toggleStore(store)}
                      className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                        selectedStores.includes(store)
                          ? 'bg-primary-600 text-white'
                          : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                      }`}
                    >
                      {store}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Price Filter */}
            <div>
              <label className="text-sm text-neutral-600 dark:text-neutral-400 mb-2 block">
                Price Range:
              </label>
              <div className="flex gap-2 items-center">
                <input
                  type="number"
                  placeholder="Min"
                  value={priceRange.min === 0 ? '' : priceRange.min}
                  onChange={(e) => setPriceRange({ ...priceRange, min: Number(e.target.value) || 0 })}
                  className="flex-1 text-sm px-3 py-1.5 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <span className="text-neutral-500">-</span>
                <input
                  type="number"
                  placeholder="Max"
                  value={priceRange.max === Infinity ? '' : priceRange.max}
                  onChange={(e) => setPriceRange({ ...priceRange, max: Number(e.target.value) || Infinity })}
                  className="flex-1 text-sm px-3 py-1.5 border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>

            {/* Clear Filters */}
            {(selectedStores.length > 0 || priceRange.min > 0 || priceRange.max < Infinity) && (
              <button
                onClick={clearFilters}
                className="text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium"
              >
                Clear all filters
              </button>
            )}
          </div>
        </div>

        {/* Products Grid */}
        <div ref={productsContainerRef} className="flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
            {sortedProducts.map((product) => {
              const productInCanvas = isInCanvas(product.id);

              // Get primary image or first image
              const getImageUrl = () => {
                if (product.images && Array.isArray(product.images) && product.images.length > 0) {
                  const primaryImage = product.images.find((img: any) => img.is_primary);
                  const image = primaryImage || product.images[0];
                  return image.large_url || image.medium_url || image.original_url;
                }
                return (product as any).image_url || '/placeholder-product.jpg';
              };

              const imageUrl = getImageUrl();
              const discountPercentage =
                product.original_price && product.price < product.original_price
                  ? Math.round(
                      ((product.original_price - product.price) / product.original_price) * 100
                    )
                  : null;

              return (
                <div
                  key={product.id}
                  className={`group border rounded-xl overflow-hidden transition-all duration-200 cursor-pointer ${
                    productInCanvas
                      ? 'bg-green-50 dark:bg-green-900/10 border-green-300 dark:border-green-700'
                      : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-lg'
                  }`}
                  onClick={() => handleProductClick(product)}
                >
                  {/* Product Image */}
                  <div className="relative aspect-[4/3] bg-neutral-100 dark:bg-neutral-700">
                    {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
                      <Image
                        src={imageUrl}
                        alt={product.name}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-300"
                        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                        onError={(e) => {
                          console.error('[ProductDiscoveryPanel] Image failed to load:', imageUrl);
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-neutral-200 dark:bg-neutral-600">
                        <svg
                          className="w-16 h-16 text-neutral-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={1.5}
                            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                          />
                        </svg>
                        {!imageUrl && (
                          <p className="text-xs text-neutral-400 mt-2">No image</p>
                        )}
                      </div>
                    )}

                    {/* Badges */}
                    <div className="absolute top-1.5 left-1.5 space-y-0.5">
                      {discountPercentage && (
                        <span className="inline-block bg-red-500 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
                          -{discountPercentage}%
                        </span>
                      )}
                      {product.is_available === false && (
                        <span className="inline-block bg-gray-500 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
                          Out of Stock
                        </span>
                      )}
                    </div>

                    {/* In Canvas Badge with Quantity */}
                    {productInCanvas && (
                      <div className="absolute top-1.5 right-1.5">
                        <span className="px-1.5 py-0.5 bg-green-500 text-white text-[10px] font-bold rounded-full flex items-center gap-0.5 shadow-lg">
                          <svg
                            className="w-2.5 h-2.5"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                          {getCanvasQuantity(product.id) > 1 ? `${getCanvasQuantity(product.id)} in Canvas` : 'In Canvas'}
                        </span>
                      </div>
                    )}

                    {/* Source Badge */}
                    {product.source_website && (
                      <div className="absolute bottom-1.5 right-1.5">
                        <span className="inline-block bg-black/70 text-white text-[10px] font-medium px-1.5 py-0.5 rounded backdrop-blur-sm">
                          {product.source_website}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Product Info */}
                  <div className="p-2">
                    {/* Brand */}
                    {product.brand && (
                      <p className="text-[10px] text-neutral-500 dark:text-neutral-400 mb-0.5">
                        {product.brand}
                      </p>
                    )}

                    {/* Name */}
                    <h3 className="font-medium text-xs text-neutral-900 dark:text-white mb-1.5 line-clamp-2 group-hover:text-primary-600 transition-colors">
                      {product.name}
                    </h3>

                    {/* Price */}
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-sm font-bold text-neutral-900 dark:text-white">
                        {formatCurrency(product.price, product.currency)}
                      </span>
                      {product.original_price && product.price < product.original_price && (
                        <span className="text-xs text-neutral-400 line-through">
                          {formatCurrency(product.original_price, product.currency)}
                        </span>
                      )}
                    </div>

                    {/* Add to Canvas Button - always enabled (allows adding multiple) */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAddToCanvas(product);
                      }}
                      disabled={product.is_available === false}
                      className={`w-full py-1.5 px-2 rounded-lg text-xs font-medium transition-colors ${
                        productInCanvas
                          ? 'bg-green-600 hover:bg-green-700 disabled:bg-neutral-300 dark:disabled:bg-neutral-700 text-white'
                          : 'bg-primary-600 hover:bg-primary-700 disabled:bg-neutral-300 dark:disabled:bg-neutral-700 text-white'
                      } disabled:cursor-not-allowed`}
                    >
                      {product.is_available === false
                        ? 'Out of Stock'
                        : productInCanvas
                          ? `Add Another (${getCanvasQuantity(product.id)} in cart)`
                          : 'Add to Canvas'}
                    </button>

                    {/* Click to view details hint */}
                    <p className="text-[10px] text-neutral-400 text-center mt-1">
                      Click for details
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          isOpen={true}
          onClose={() => setSelectedProduct(null)}
          onAddToCanvas={handleAddToCanvasFromModal}
          inCanvas={isInCanvas(selectedProduct.id)}
          canvasQuantity={getCanvasQuantity(selectedProduct.id)}
        />
      )}
    </>
  );
}
