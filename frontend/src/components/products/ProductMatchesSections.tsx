'use client';

import { ReactNode, useState } from 'react';
import Image from 'next/image';
import { formatCurrency } from '@/utils/format';
import {
  ExtendedProduct,
  getProductImageUrl,
  calculateDiscountPercentage,
  isProductInCanvas,
  getCanvasQuantity,
} from '@/utils/product-transforms';

interface ProductCardProps {
  product: ExtendedProduct;
  onAddToCanvas: (product: ExtendedProduct) => void;
  onClick?: (product: ExtendedProduct) => void;
  inCanvas: boolean;
  canvasQuantity: number;
  isBestMatch?: boolean;
  compact?: boolean;
}

/**
 * Product card component used within ProductMatchesSections.
 * Displays product image, name, price, and add-to-canvas button.
 */
function ProductCard({
  product,
  onAddToCanvas,
  onClick,
  inCanvas,
  canvasQuantity,
  isBestMatch = false,
  compact = false,
}: ProductCardProps) {
  const imageUrl = getProductImageUrl(product);
  const discountPercentage = calculateDiscountPercentage(product.price, product.original_price);

  return (
    <div
      className={`group border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer ${
        inCanvas
          ? 'bg-neutral-100 dark:bg-neutral-800/30 border-neutral-400 dark:border-neutral-600'
          : isBestMatch
            ? 'bg-neutral-100 dark:bg-neutral-800/10 border-neutral-300 dark:border-neutral-700 hover:border-neutral-400 dark:hover:border-neutral-600 hover:shadow-md'
            : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-md'
      }`}
      onClick={() => onClick?.(product)}
    >
      {/* Product Image */}
      <div className={`relative ${compact ? 'aspect-square' : 'aspect-square'} bg-neutral-100 dark:bg-neutral-700`}>
        {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
          <Image
            src={imageUrl}
            alt={product.name}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes={compact ? '140px' : '(max-width: 768px) 50vw, 33vw'}
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
          <span className="absolute top-1 left-1 bg-neutral-800 text-white text-[8px] font-semibold px-1.5 py-0.5 rounded-full">
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
          <span className="absolute top-1 right-1 bg-neutral-700 text-white text-[9px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
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
        <h4 className={`font-medium text-neutral-900 dark:text-white line-clamp-2 mb-1 ${compact ? 'text-[10px] h-[28px]' : 'text-[11px]'}`}>
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

        {/* Add to Canvas Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAddToCanvas(product);
          }}
          className={`w-full mt-1.5 py-1 text-[10px] font-medium rounded transition-colors ${
            inCanvas
              ? 'bg-neutral-700 hover:bg-neutral-800 text-white'
              : 'bg-neutral-800 hover:bg-neutral-900 text-white'
          }`}
        >
          {inCanvas ? `Add +1 (${canvasQuantity})` : compact ? 'Add' : 'Add to Canvas'}
        </button>
      </div>
    </div>
  );
}

interface ProductMatchesSectionsProps {
  /** Products marked as best matches (is_primary_match === true) */
  bestMatches: ExtendedProduct[];
  /** Products that are not best matches */
  moreProducts: ExtendedProduct[];
  /** Callback when product is added to canvas */
  onAddProduct: (product: ExtendedProduct) => void;
  /** Products currently in canvas (for highlighting) */
  canvasProducts: Array<{ id: string | number; quantity?: number }>;
  /** Callback when product card is clicked (for details modal) */
  onViewDetails?: (product: ExtendedProduct) => void;
  /** Custom renderer for product card */
  renderProduct?: (product: ExtendedProduct, isBestMatch: boolean) => ReactNode;
  /** Title for best matches section */
  bestMatchesTitle?: string;
  /** Title for more products section */
  moreProductsTitle?: string;
  /** Whether more products section starts collapsed */
  showMoreProductsCollapsed?: boolean;
  /** Use compact card style */
  compact?: boolean;
  /** Grid columns class */
  gridClassName?: string;
}

/**
 * ProductMatchesSections Component
 *
 * Displays products separated into "Best Matches" and "More Products" sections.
 * Used across CategorySection, CategoryCarousel, and Admin Curation pages.
 */
export function ProductMatchesSections({
  bestMatches,
  moreProducts,
  onAddProduct,
  canvasProducts,
  onViewDetails,
  renderProduct,
  bestMatchesTitle = 'Best Matches',
  moreProductsTitle = 'More Products',
  showMoreProductsCollapsed = false,
  compact = false,
  gridClassName = 'grid grid-cols-2 md:grid-cols-3 gap-2',
}: ProductMatchesSectionsProps) {
  const [moreProductsExpanded, setMoreProductsExpanded] = useState(!showMoreProductsCollapsed);

  // Check if we have any products at all
  if (bestMatches.length === 0 && moreProducts.length === 0) {
    return (
      <div className="text-center py-8 text-neutral-500 dark:text-neutral-400 text-sm">
        No products found
      </div>
    );
  }

  // Default product card renderer
  const defaultRenderProduct = (product: ExtendedProduct, isBestMatch: boolean) => (
    <ProductCard
      key={product.id}
      product={product}
      onAddToCanvas={onAddProduct}
      onClick={onViewDetails}
      inCanvas={isProductInCanvas(product.id, canvasProducts)}
      canvasQuantity={getCanvasQuantity(product.id, canvasProducts)}
      isBestMatch={isBestMatch}
      compact={compact}
    />
  );

  const renderProductFn = renderProduct || defaultRenderProduct;

  return (
    <>
      {/* Best Matches Section */}
      {bestMatches.length > 0 && (
        <>
          <div className="mb-2">
            <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 bg-neutral-200 dark:bg-neutral-700/50 px-2 py-1 rounded">
              {bestMatchesTitle} ({bestMatches.length})
            </span>
          </div>
          <div className={gridClassName}>
            {bestMatches.map(product => renderProductFn(product, true))}
          </div>
        </>
      )}

      {/* More Products Section */}
      {moreProducts.length > 0 && (
        <>
          <div className={`mb-2 ${bestMatches.length > 0 ? 'mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700' : ''}`}>
            <button
              onClick={() => setMoreProductsExpanded(!moreProductsExpanded)}
              className="flex items-center gap-2 text-xs font-semibold text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors"
            >
              <span className={`transform transition-transform ${moreProductsExpanded ? 'rotate-90' : ''}`}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </span>
              {bestMatches.length > 0 ? moreProductsTitle : 'Products'} ({moreProducts.length})
            </button>
          </div>
          {moreProductsExpanded && (
            <div className={gridClassName}>
              {moreProducts.map(product => renderProductFn(product, false))}
            </div>
          )}
        </>
      )}

      {/* Fallback: All products if no separation */}
      {bestMatches.length === 0 && moreProducts.length === 0 && (
        <div className="text-center py-8 text-neutral-500 dark:text-neutral-400 text-sm">
          No products match your filters
        </div>
      )}
    </>
  );
}

// Export ProductCard for use elsewhere
export { ProductCard };
