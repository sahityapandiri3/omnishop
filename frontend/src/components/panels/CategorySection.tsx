'use client';

import { useState, useMemo, useCallback, useEffect } from 'react';
import Image from 'next/image';
import { Product, PaginationCursor } from '@/types';
import { formatCurrency } from '@/utils/format';
import { ProductDetailModal } from '../ProductDetailModal';
import InfiniteScrollTrigger from '../InfiniteScrollTrigger';
import { usePaginatedProducts, flattenPaginatedProducts } from '@/hooks/usePaginatedProducts';
import { getCategorizedStores, StoreCategory } from '@/utils/api';

// Product style options (matches Product.primary_style values) - same as admin curation page
const PRODUCT_STYLES = [
  { value: 'modern', label: 'Modern' },
  { value: 'modern_luxury', label: 'Modern Luxury' },
  { value: 'indian_contemporary', label: 'Indian Contemporary' },
  { value: 'minimalist', label: 'Minimalist' },
  { value: 'japandi', label: 'Japandi' },
  { value: 'scandinavian', label: 'Scandinavian' },
  { value: 'mid_century_modern', label: 'Mid-Century Modern' },
  { value: 'boho', label: 'Boho' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'contemporary', label: 'Contemporary' },
  { value: 'eclectic', label: 'Eclectic' },
];

// Types for category recommendations from API
export interface BudgetAllocation {
  min: number;
  max: number;
}

export interface CategoryRecommendation {
  category_id: string;
  display_name: string;
  budget_allocation?: BudgetAllocation | null;
  priority: number;
  product_count?: number;
}

interface CategoryFilterState {
  selectedStores: string[];
  selectedStyles: string[];
  priceMin: number;
  priceMax: number;
  sortBy: 'relevance' | 'price-low' | 'price-high';
}

interface CategorySectionProps {
  category: CategoryRecommendation;
  products: any[];
  onAddToCanvas: (product: any) => void;
  canvasProducts: any[];
  isExpanded: boolean;
  onToggleExpand: () => void;
  // Pagination props (optional for backward compatibility)
  sessionId?: string;
  hasMore?: boolean;
  totalEstimated?: number;
  nextCursor?: PaginationCursor | null;
  styleAttributes?: {
    style_keywords?: string[];
    colors?: string[];
    materials?: string[];
    size_keywords?: string[];
  };
}

/**
 * CategorySection Component
 * Renders a collapsible category with header, filter bar, and product grid
 */
export default function CategorySection({
  category,
  products,
  onAddToCanvas,
  canvasProducts,
  isExpanded,
  onToggleExpand,
  // Pagination props
  sessionId,
  hasMore: initialHasMore = false,
  totalEstimated: initialTotalEstimated,
  nextCursor,
  styleAttributes,
}: CategorySectionProps) {
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  // NOTE: Don't initialize price filters to budget allocation values
  // All products should be shown by default (sorted by relevance/score)
  // Users can manually apply budget filters if they want
  const [filters, setFilters] = useState<CategoryFilterState>({
    selectedStores: [],
    selectedStyles: [],
    priceMin: 0,
    priceMax: Infinity,
    sortBy: 'relevance',
  });
  const [showFilters, setShowFilters] = useState(false);

  // Store categories for grouped store filtering (same as admin curation page)
  const [storeCategories, setStoreCategories] = useState<StoreCategory[]>([]);
  const [allStores, setAllStores] = useState<string[]>([]);

  // Fetch store categories on mount
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

  // Use pagination hook for infinite scroll (only active when expanded and sessionId is provided)
  // NOTE: Don't pass budget constraints - all products should be shown, sorted by score
  // Budget is used for scoring (products within budget ranked higher), not filtering
  const paginationEnabled = isExpanded && !!sessionId && initialHasMore;

  // Derive semantic query from category display name for vector search consistency
  // This ensures pagination uses the same vector search as initial load
  // e.g., "Accent Chairs" → "accent chairs" for semantic search
  const semanticQuery = category.display_name?.toLowerCase() || category.category_id.replace(/_/g, ' ');

  const {
    data: paginatedData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = usePaginatedProducts({
    sessionId: sessionId || '',
    categoryId: category.category_id,
    styleAttributes,
    // Don't pass budget constraints - show all products, ranked by score
    enabled: paginationEnabled,
    // Use semantic query for vector search ranking (same as initial load)
    semanticQuery: semanticQuery,
  });

  // Combine initial products with paginated products
  const allProducts = useMemo(() => {
    const paginatedProducts = flattenPaginatedProducts(paginatedData);
    if (paginatedProducts.length === 0) {
      return products;
    }
    // Deduplicate by product ID (initial products may overlap with paginated)
    const seenIds = new Set(products.map((p: any) => p.id));
    const additionalProducts = paginatedProducts.filter((p: any) => !seenIds.has(p.id));
    return [...products, ...additionalProducts];
  }, [products, paginatedData]);

  // Calculate pagination state
  const currentHasMore = hasNextPage ?? initialHasMore;
  const currentTotalEstimated = paginatedData?.pages[0]?.total_estimated ?? initialTotalEstimated ?? products.length;

  // Memoize fetchNextPage callback
  const handleLoadMore = useCallback(() => {
    if (!isFetchingNextPage && hasNextPage) {
      fetchNextPage();
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  // Transform raw product to Product type
  const transformProduct = (rawProduct: any): Product => {
    let images = [];
    if (rawProduct.primary_image && rawProduct.primary_image.url) {
      images = [{
        id: 1,
        original_url: rawProduct.primary_image.url,
        is_primary: true,
        alt_text: rawProduct.primary_image.alt_text || rawProduct.name
      }];
    } else if (rawProduct.images && Array.isArray(rawProduct.images)) {
      images = rawProduct.images;
    } else if (rawProduct.image_url) {
      images = [{
        id: 1,
        original_url: rawProduct.image_url,
        is_primary: true,
        alt_text: rawProduct.name
      }];
    }

    return {
      id: parseInt(rawProduct.id) || rawProduct.id,
      name: rawProduct.name,
      description: rawProduct.description,
      price: parseFloat(rawProduct.price) || 0,
      original_price: rawProduct.original_price ? parseFloat(rawProduct.original_price) : undefined,
      currency: rawProduct.currency || 'INR',
      brand: rawProduct.brand,
      source_website: rawProduct.source || rawProduct.source_website,
      source_url: rawProduct.source_url,
      is_available: rawProduct.is_available !== false,
      is_on_sale: rawProduct.is_on_sale || false,
      images: images,
      category: rawProduct.category,
      sku: rawProduct.sku,
      // Preserve these for Best Matches vs More Products separation and style filtering
      is_primary_match: rawProduct.is_primary_match,
      primary_style: rawProduct.primary_style,
      similarity_score: rawProduct.similarity_score,
    } as Product & { is_primary_match?: boolean; primary_style?: string; similarity_score?: number };
  };

  // Get unique stores from products (use allProducts to include paginated)
  const uniqueStores = useMemo(() => {
    return Array.from(
      new Set(allProducts.map(p => p.source_website || p.source).filter(Boolean))
    ).sort();
  }, [allProducts]);

  // Transform and filter products (use allProducts to include paginated)
  const filteredProducts = useMemo(() => {
    const transformed = allProducts.map(transformProduct);

    return transformed.filter(product => {
      const price = product.price || 0;
      const store = product.source_website;
      const extProduct = product as Product & { primary_style?: string };

      // Price filter
      if (price < filters.priceMin) return false;
      if (filters.priceMax < 999999 && price > filters.priceMax) return false;

      // Store filter
      if (filters.selectedStores.length > 0 && !filters.selectedStores.includes(store)) return false;

      // Style filter
      if (filters.selectedStyles.length > 0) {
        const productStyle = extProduct.primary_style?.toLowerCase();
        if (!productStyle || !filters.selectedStyles.includes(productStyle)) return false;
      }

      return true;
    }).sort((a, b) => {
      switch (filters.sortBy) {
        case 'price-low':
          return (a.price || 0) - (b.price || 0);
        case 'price-high':
          return (b.price || 0) - (a.price || 0);
        default:
          return 0;
      }
    });
  }, [products, filters]);

  // Check if product is in canvas
  const isInCanvas = (productId: string | number) => {
    return canvasProducts.some((p) => p.id?.toString() === productId?.toString());
  };

  // Get quantity of product in canvas
  const getCanvasQuantity = (productId: string | number) => {
    const product = canvasProducts.find((p) => p.id?.toString() === productId?.toString());
    return product?.quantity || 0;
  };

  // Toggle store filter
  const toggleStore = (store: string) => {
    setFilters(prev => ({
      ...prev,
      selectedStores: prev.selectedStores.includes(store)
        ? prev.selectedStores.filter(s => s !== store)
        : [...prev.selectedStores, store]
    }));
  };

  // Toggle all stores
  const toggleAllStores = () => {
    if (filters.selectedStores.length === allStores.length) {
      setFilters(prev => ({ ...prev, selectedStores: [] }));
    } else {
      setFilters(prev => ({ ...prev, selectedStores: [...allStores] }));
    }
  };

  // Toggle style filter
  const toggleStyle = (style: string) => {
    setFilters(prev => ({
      ...prev,
      selectedStyles: prev.selectedStyles.includes(style)
        ? prev.selectedStyles.filter(s => s !== style)
        : [...prev.selectedStyles, style]
    }));
  };

  // Separate products into Best Matches and More Products (same as admin curation page)
  const { primaryProducts, relatedProducts } = useMemo(() => {
    type ExtendedProduct = Product & { is_primary_match?: boolean };
    const primary = filteredProducts.filter((p: ExtendedProduct) => p.is_primary_match === true);
    const related = filteredProducts.filter((p: ExtendedProduct) => p.is_primary_match !== true);
    return { primaryProducts: primary, relatedProducts: related };
  }, [filteredProducts]);

  // Handle add to canvas from modal
  const handleAddToCanvasFromModal = () => {
    if (selectedProduct) {
      onAddToCanvas(selectedProduct);
      setSelectedProduct(null);
    }
  };

  // Get image URL helper
  const getImageUrl = (product: Product) => {
    if (product.images && Array.isArray(product.images) && product.images.length > 0) {
      const primaryImage = product.images.find((img: any) => img.is_primary);
      const image = primaryImage || product.images[0];
      return image.large_url || image.medium_url || image.original_url;
    }
    return (product as any).image_url || '/placeholder-product.jpg';
  };

  // Format budget hint
  const budgetHint = category.budget_allocation
    ? `₹${Math.round(category.budget_allocation.min / 1000)}K - ₹${Math.round(category.budget_allocation.max / 1000)}K`
    : null;

  return (
    <div className="border-b border-neutral-200 dark:border-neutral-700">
      {/* Category Header */}
      <button
        onClick={onToggleExpand}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
            <svg className="w-4 h-4 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </span>
          <div className="text-left">
            <h3 className="font-semibold text-neutral-900 dark:text-white text-sm">
              {category.display_name}
            </h3>
            <div className="flex items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
              <span>{filteredProducts.length} items</span>
              {budgetHint && (
                <>
                  <span>•</span>
                  <span className="text-primary-600 dark:text-primary-400">{budgetHint}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Filter toggle button */}
        {isExpanded && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowFilters(!showFilters);
            }}
            className={`p-1.5 rounded-lg transition-colors ${
              showFilters || filters.selectedStores.length > 0 || filters.selectedStyles.length > 0
                ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-600'
                : 'hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-500'
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
          </button>
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4">
          {/* Filter Bar */}
          {showFilters && (
            <div className="bg-neutral-50 dark:bg-neutral-800/50 rounded-lg p-3 mb-4 space-y-3">
              {/* Store Filter - Categorized by Budget Tier (same as admin curation page) */}
              {storeCategories.length > 0 && (
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-xs text-neutral-600 dark:text-neutral-400">
                      Stores
                    </label>
                    <button
                      onClick={toggleAllStores}
                      className="text-xs text-primary-600 hover:text-primary-700"
                    >
                      {filters.selectedStores.length === allStores.length ? 'Deselect all' : 'Select all'}
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
                              onClick={() => toggleStore(store.name)}
                              className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                filters.selectedStores.includes(store.name)
                                  ? 'bg-primary-600 text-white'
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
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-xs text-neutral-600 dark:text-neutral-400">
                    Style
                  </label>
                  {filters.selectedStyles.length > 0 && (
                    <button
                      onClick={() => setFilters(prev => ({ ...prev, selectedStyles: [] }))}
                      className="text-xs text-primary-600 hover:text-primary-700"
                    >
                      Clear ({filters.selectedStyles.length})
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {PRODUCT_STYLES.map((style) => (
                    <button
                      key={style.value}
                      onClick={() => toggleStyle(style.value)}
                      className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                        filters.selectedStyles.includes(style.value)
                          ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 border border-primary-300 dark:border-primary-700'
                          : 'bg-white dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-600'
                      }`}
                    >
                      {filters.selectedStyles.includes(style.value) && (
                        <svg className="w-2.5 h-2.5 inline mr-0.5 -ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      )}
                      {style.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Price Range */}
              <div>
                <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Price Range
                </label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    placeholder="Min"
                    value={filters.priceMin === 0 ? '' : filters.priceMin}
                    onChange={(e) => setFilters({ ...filters, priceMin: Number(e.target.value) || 0 })}
                    className="flex-1 text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <span className="text-neutral-400 text-xs">-</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={filters.priceMax >= 999999 ? '' : filters.priceMax}
                    onChange={(e) => setFilters({ ...filters, priceMax: Number(e.target.value) || Infinity })}
                    className="flex-1 text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
              </div>

              {/* Sort */}
              <div>
                <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Sort By
                </label>
                <select
                  value={filters.sortBy}
                  onChange={(e) => setFilters({ ...filters, sortBy: e.target.value as any })}
                  className="w-full text-xs px-2 py-1.5 border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="relevance">Relevance</option>
                  <option value="price-low">Price: Low to High</option>
                  <option value="price-high">Price: High to Low</option>
                </select>
              </div>
            </div>
          )}

          {/* Products Grid - Separated into Best Matches and More Products (same as admin curation page) */}
          {filteredProducts.length > 0 ? (
            <>
              {/* Render helper for product grid */}
              {(() => {
                const renderProductGrid = (productsToRender: typeof filteredProducts) => (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {productsToRender.map((product) => {
                      const productInCanvas = isInCanvas(product.id);
                      const imageUrl = getImageUrl(product);
                      const discountPercentage = product.original_price && product.price < product.original_price
                        ? Math.round(((product.original_price - product.price) / product.original_price) * 100)
                        : null;

                      return (
                        <div
                          key={product.id}
                          className={`group border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer ${
                            productInCanvas
                              ? 'bg-green-50 dark:bg-green-900/10 border-green-300 dark:border-green-700'
                              : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-md'
                          }`}
                          onClick={() => setSelectedProduct(product)}
                        >
                          {/* Product Image */}
                          <div className="relative aspect-square bg-neutral-100 dark:bg-neutral-700">
                            {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
                              <Image
                                src={imageUrl}
                                alt={product.name}
                                fill
                                className="object-cover group-hover:scale-105 transition-transform duration-300"
                                sizes="(max-width: 768px) 50vw, 33vw"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center bg-neutral-200 dark:bg-neutral-600">
                                <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                              </div>
                            )}

                            {/* Badges */}
                            {discountPercentage && (
                              <span className="absolute top-1 left-1 bg-red-500 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
                                -{discountPercentage}%
                              </span>
                            )}

                            {productInCanvas && (
                              <span className="absolute top-1 right-1 bg-green-500 text-white text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
                                <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                </svg>
                                {getCanvasQuantity(product.id) > 1 && getCanvasQuantity(product.id)}
                              </span>
                            )}

                            {product.source_website && (
                              <span className="absolute bottom-1 right-1 bg-black/70 text-white text-[9px] px-1 py-0.5 rounded backdrop-blur-sm">
                                {product.source_website}
                              </span>
                            )}
                          </div>

                          {/* Product Info */}
                          <div className="p-2">
                            <h4 className="font-medium text-[11px] text-neutral-900 dark:text-white line-clamp-2 mb-1">
                              {product.name}
                            </h4>
                            <div className="flex items-center gap-1">
                              <span className="text-xs font-bold text-neutral-900 dark:text-white">
                                {formatCurrency(product.price, product.currency)}
                              </span>
                              {product.original_price && product.price < product.original_price && (
                                <span className="text-[10px] text-neutral-400 line-through">
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
                              className={`w-full mt-1.5 py-1 text-[10px] font-medium rounded transition-colors ${
                                productInCanvas
                                  ? 'bg-green-600 hover:bg-green-700 text-white'
                                  : 'bg-primary-600 hover:bg-primary-700 text-white'
                              }`}
                            >
                              {productInCanvas ? `Add +1 (${getCanvasQuantity(product.id)})` : 'Add to Canvas'}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );

                return (
                  <>
                    {/* Best Matches Section */}
                    {primaryProducts.length > 0 && (
                      <>
                        <div className="mb-2">
                          <span className="text-xs font-semibold text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded">
                            Best Matches ({primaryProducts.length})
                          </span>
                        </div>
                        {renderProductGrid(primaryProducts)}
                      </>
                    )}

                    {/* More Products Section */}
                    {relatedProducts.length > 0 && (
                      <>
                        <div className={`mb-2 ${primaryProducts.length > 0 ? 'mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700' : ''}`}>
                          <span className="text-xs font-semibold text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
                            {primaryProducts.length > 0 ? 'More Products' : 'Products'} ({relatedProducts.length})
                          </span>
                        </div>
                        {renderProductGrid(relatedProducts)}
                      </>
                    )}

                    {/* Fallback if no is_primary_match flag (all products treated equally) */}
                    {primaryProducts.length === 0 && relatedProducts.length === 0 && filteredProducts.length > 0 && (
                      renderProductGrid(filteredProducts)
                    )}
                  </>
                );
              })()}

              {/* Infinite Scroll Trigger */}
              {sessionId && (
                <InfiniteScrollTrigger
                  onLoadMore={handleLoadMore}
                  hasMore={currentHasMore}
                  isLoading={isFetchingNextPage}
                  loadedCount={filteredProducts.length}
                  totalCount={currentTotalEstimated}
                />
              )}
            </>
          ) : (
            <div className="text-center py-8 text-neutral-500 dark:text-neutral-400 text-sm">
              No products match your filters
            </div>
          )}
        </div>
      )}

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
