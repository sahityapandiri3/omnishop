'use client';

import { useState, useMemo } from 'react';
import Image from 'next/image';
import { formatCurrency } from '@/utils/format';
import {
  ExtendedProduct,
  separateProductMatches,
  getProductImageUrl,
  calculateDiscountPercentage,
  isProductInCanvas,
  getCanvasQuantity,
} from '@/utils/product-transforms';
import InfiniteScrollTrigger from '../InfiniteScrollTrigger';

interface ProductCardProps {
  product: ExtendedProduct;
  onAddProduct: (product: ExtendedProduct) => void;
  onViewDetails?: (product: ExtendedProduct) => void;
  inCanvas: boolean;
  canvasQuantity: number;
  isBestMatch?: boolean;
  size?: 'small' | 'medium' | 'large';
}

/**
 * Individual product card component.
 */
function ProductCard({
  product,
  onAddProduct,
  onViewDetails,
  inCanvas,
  canvasQuantity,
  isBestMatch = false,
  size = 'medium',
}: ProductCardProps) {
  const imageUrl = getProductImageUrl(product);
  const discountPercentage = calculateDiscountPercentage(product.price, product.original_price);

  const sizeClasses = {
    small: 'w-[120px]',
    medium: '',
    large: '',
  };

  const textSizes = {
    small: { name: 'text-[10px] h-[24px]', price: 'text-[10px]', button: 'text-[8px] py-0.5' },
    medium: { name: 'text-[11px]', price: 'text-xs', button: 'text-[10px] py-1' },
    large: { name: 'text-sm', price: 'text-sm', button: 'text-xs py-1.5' },
  };

  return (
    <div
      className={`group border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer ${sizeClasses[size]} ${
        inCanvas
          ? 'bg-green-50 dark:bg-green-900/10 border-green-300 dark:border-green-700'
          : isBestMatch
            ? 'bg-primary-50 dark:bg-primary-900/10 border-primary-200 dark:border-primary-800 hover:border-primary-300 dark:hover:border-primary-700 hover:shadow-md'
            : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-md'
      }`}
      onClick={() => onViewDetails?.(product)}
    >
      {/* Product Image */}
      <div className="relative aspect-square bg-neutral-100 dark:bg-neutral-700">
        {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
          <Image
            src={imageUrl}
            alt={product.name}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes={size === 'small' ? '120px' : '(max-width: 768px) 50vw, 33vw'}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-neutral-200 dark:bg-neutral-600">
            <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}

        {/* Best Match Badge */}
        {isBestMatch && !inCanvas && (
          <span className="absolute top-1 left-1 bg-primary-600 text-white text-[8px] font-semibold px-1.5 py-0.5 rounded-full">
            Best Match
          </span>
        )}

        {/* Discount Badge */}
        {discountPercentage && !isBestMatch && (
          <span className="absolute top-1 left-1 bg-red-500 text-white text-[9px] font-semibold px-1.5 py-0.5 rounded-full">
            -{discountPercentage}%
          </span>
        )}

        {/* In Canvas Badge */}
        {inCanvas && (
          <span className="absolute top-1 right-1 bg-green-500 text-white text-[9px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
            <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            {canvasQuantity > 1 && canvasQuantity}
          </span>
        )}

        {/* Source Badge */}
        {product.source_website && (
          <span className="absolute bottom-1 right-1 bg-black/70 text-white text-[8px] px-1 py-0.5 rounded backdrop-blur-sm">
            {product.source_website}
          </span>
        )}
      </div>

      {/* Product Info */}
      <div className="p-2">
        <h4 className={`font-medium text-neutral-900 dark:text-white line-clamp-2 mb-1 ${textSizes[size].name}`}>
          {product.name}
        </h4>
        <div className="flex items-center gap-1 mb-1.5">
          <span className={`font-bold text-neutral-900 dark:text-white ${textSizes[size].price}`}>
            {formatCurrency(product.price, product.currency)}
          </span>
          {product.original_price && product.price < product.original_price && (
            <span className="text-[10px] text-neutral-400 line-through">
              {formatCurrency(product.original_price, product.currency)}
            </span>
          )}
        </div>

        {/* Add to Canvas Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAddProduct(product);
          }}
          className={`w-full font-medium rounded transition-colors ${textSizes[size].button} ${
            inCanvas
              ? 'bg-green-600 hover:bg-green-700 text-white'
              : 'bg-primary-600 hover:bg-primary-700 text-white'
          }`}
        >
          {inCanvas ? `Add +1 (${canvasQuantity})` : size === 'small' ? 'Add' : 'Add to Canvas'}
        </button>
      </div>
    </div>
  );
}

interface ProductResultsGridProps {
  /** Products to display */
  products: ExtendedProduct[];
  /** Callback when product is added to canvas */
  onAddProduct: (product: ExtendedProduct) => void;
  /** Products currently in canvas */
  canvasProducts: Array<{ id: string | number; quantity?: number }>;
  /** Callback when product card is clicked for details */
  onViewDetails?: (product: ExtendedProduct) => void;
  /** Whether to show Best Matches / More Products separation */
  showSeparation?: boolean;
  /** Group products by category */
  groupByCategory?: boolean;
  /** Categories for grouping (if groupByCategory is true) */
  categories?: Array<{ category_id: string; display_name: string }>;
  /** Products grouped by category */
  productsByCategory?: Record<string, ExtendedProduct[]>;
  /** Enable infinite scroll */
  enableInfiniteScroll?: boolean;
  /** Callback when more products need to be loaded */
  onLoadMore?: () => void;
  /** Whether there are more products to load */
  hasMore?: boolean;
  /** Whether currently loading more products */
  isLoadingMore?: boolean;
  /** Total product count for display */
  totalCount?: number;
  /** Grid columns class */
  gridClassName?: string;
  /** Card size */
  cardSize?: 'small' | 'medium' | 'large';
  /** Loading state */
  isLoading?: boolean;
  /** Empty state message */
  emptyMessage?: string;
}

/**
 * ProductResultsGrid Component
 *
 * Displays products in a grid with optional:
 * - Best Matches / More Products separation
 * - Category grouping
 * - Infinite scroll
 */
export function ProductResultsGrid({
  products,
  onAddProduct,
  canvasProducts,
  onViewDetails,
  showSeparation = true,
  groupByCategory = false,
  categories,
  productsByCategory,
  enableInfiniteScroll = false,
  onLoadMore,
  hasMore = false,
  isLoadingMore = false,
  totalCount,
  gridClassName = 'grid grid-cols-2 md:grid-cols-3 gap-2',
  cardSize = 'medium',
  isLoading = false,
  emptyMessage = 'No products found',
}: ProductResultsGridProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Separate products into Best Matches and More Products
  const { bestMatches, moreProducts } = useMemo(() => {
    if (!showSeparation) {
      return { bestMatches: [], moreProducts: products };
    }
    return separateProductMatches(products);
  }, [products, showSeparation]);

  // Toggle category expansion
  const toggleCategory = (categoryId: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  };

  // Render a product card
  const renderProductCard = (product: ExtendedProduct, isBestMatch: boolean = false) => (
    <ProductCard
      key={product.id}
      product={product}
      onAddProduct={onAddProduct}
      onViewDetails={onViewDetails}
      inCanvas={isProductInCanvas(product.id, canvasProducts)}
      canvasQuantity={getCanvasQuantity(product.id, canvasProducts)}
      isBestMatch={isBestMatch}
      size={cardSize}
    />
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading products...</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (products.length === 0 && !groupByCategory) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <svg className="w-12 h-12 text-neutral-300 dark:text-neutral-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
        <p className="text-neutral-500 dark:text-neutral-400">{emptyMessage}</p>
      </div>
    );
  }

  // Category-grouped display
  if (groupByCategory && categories && productsByCategory) {
    return (
      <div className="space-y-4">
        {categories.map(category => {
          const categoryProducts = productsByCategory[category.category_id] || [];
          if (categoryProducts.length === 0) return null;

          const isExpanded = expandedCategories.has(category.category_id);
          const { bestMatches: catBest, moreProducts: catMore } = separateProductMatches(categoryProducts);

          return (
            <div key={category.category_id} className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden">
              {/* Category Header */}
              <button
                onClick={() => toggleCategory(category.category_id)}
                className="w-full px-4 py-3 flex items-center justify-between bg-neutral-50 dark:bg-neutral-800/50 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
                    <svg className="w-4 h-4 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </span>
                  <span className="font-medium text-neutral-900 dark:text-white">{category.display_name}</span>
                  <span className="text-xs text-neutral-500">({categoryProducts.length})</span>
                  {catBest.length > 0 && (
                    <span className="text-xs text-primary-600 dark:text-primary-400">
                      {catBest.length} best matches
                    </span>
                  )}
                </div>
              </button>

              {/* Category Products */}
              {isExpanded && (
                <div className="p-4">
                  {/* Best Matches */}
                  {catBest.length > 0 && (
                    <>
                      <div className="mb-2">
                        <span className="text-xs font-semibold text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded">
                          Best Matches ({catBest.length})
                        </span>
                      </div>
                      <div className={gridClassName}>
                        {catBest.map(product => renderProductCard(product, true))}
                      </div>
                    </>
                  )}

                  {/* More Products */}
                  {catMore.length > 0 && (
                    <>
                      <div className={`mb-2 ${catBest.length > 0 ? 'mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700' : ''}`}>
                        <span className="text-xs font-semibold text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
                          More Products ({catMore.length})
                        </span>
                      </div>
                      <div className={gridClassName}>
                        {catMore.map(product => renderProductCard(product, false))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // Standard grid display with optional separation
  return (
    <div>
      {/* Best Matches Section */}
      {bestMatches.length > 0 && (
        <>
          <div className="mb-2">
            <span className="text-xs font-semibold text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded">
              Best Matches ({bestMatches.length})
            </span>
          </div>
          <div className={gridClassName}>
            {bestMatches.map(product => renderProductCard(product, true))}
          </div>
        </>
      )}

      {/* More Products Section */}
      {moreProducts.length > 0 && (
        <>
          <div className={`mb-2 ${bestMatches.length > 0 ? 'mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700' : ''}`}>
            <span className="text-xs font-semibold text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
              {bestMatches.length > 0 ? 'More Products' : 'Products'} ({moreProducts.length})
              {totalCount && totalCount > products.length && (
                <span className="ml-1 text-neutral-400">of {totalCount}</span>
              )}
            </span>
          </div>
          <div className={gridClassName}>
            {moreProducts.map(product => renderProductCard(product, false))}
          </div>
        </>
      )}

      {/* Infinite Scroll Trigger */}
      {enableInfiniteScroll && onLoadMore && (
        <InfiniteScrollTrigger
          onLoadMore={onLoadMore}
          hasMore={hasMore}
          isLoading={isLoadingMore}
          loadedCount={products.length}
          totalCount={totalCount}
        />
      )}
    </div>
  );
}

export { ProductCard };
