'use client';

import { useRef, useState, useMemo } from 'react';
import Image from 'next/image';
import { Product } from '@/types';
import { formatCurrency } from '@/utils/format';
import { ProductDetailModal } from '../ProductDetailModal';
import { CategoryRecommendation } from './CategorySection';
// Shared utilities
import {
  transformProduct as transformProductUtil,
  separateProductMatches,
  ExtendedProduct,
  getProductImageUrl,
  isProductInCanvas,
  getCanvasQuantity as getCanvasQuantityUtil,
} from '@/utils/product-transforms';

interface CategoryCarouselProps {
  category: CategoryRecommendation;
  products: any[];
  onAddToCanvas: (product: any) => void;
  canvasProducts: any[];
  onViewAll: () => void;
}

/**
 * CategoryCarousel Component
 * Horizontal scrolling carousel for a category (Netflix-style)
 */
export default function CategoryCarousel({
  category,
  products,
  onAddToCanvas,
  canvasProducts,
  onViewAll,
}: CategoryCarouselProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selectedProduct, setSelectedProduct] = useState<ExtendedProduct | null>(null);

  // Transform raw product to Product type (using shared utility)
  const transformProduct = (rawProduct: any): ExtendedProduct => {
    return transformProductUtil(rawProduct);
  };

  // Check if product is in canvas (using shared utility)
  const isInCanvas = (productId: string | number) => {
    return isProductInCanvas(productId, canvasProducts);
  };

  // Get quantity of product in canvas (using shared utility)
  const getCanvasQuantity = (productId: string | number) => {
    return getCanvasQuantityUtil(productId, canvasProducts);
  };

  // Get image URL helper (using shared utility)
  const getImageUrl = (product: Product | ExtendedProduct) => {
    return getProductImageUrl(product);
  };

  // Scroll handlers
  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = 280; // Card width + gap
      scrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  // Transform products
  const transformedProducts = products.map(transformProduct);

  // Separate Best Matches from More Products (using shared utility)
  const { bestMatches, moreProducts } = useMemo(() => {
    return separateProductMatches(transformedProducts);
  }, [transformedProducts]);

  // Format budget hint
  const budgetHint = category.budget_allocation
    ? `${Math.round(category.budget_allocation.min / 1000)}K - ${Math.round(category.budget_allocation.max / 1000)}K`
    : null;

  // Handle add to canvas from modal
  const handleAddToCanvasFromModal = () => {
    if (selectedProduct) {
      onAddToCanvas(selectedProduct);
      setSelectedProduct(null);
    }
  };

  if (products.length === 0) {
    return null;
  }

  // Helper to render a single product card
  const renderProductCard = (product: ExtendedProduct, isBestMatch: boolean = false) => {
    const productInCanvas = isInCanvas(product.id);
    const imageUrl = getImageUrl(product);
    const discountPercentage = product.original_price && product.price < product.original_price
      ? Math.round(((product.original_price - product.price) / product.original_price) * 100)
      : null;

    return (
      <div
        key={product.id}
        className={`flex-shrink-0 w-[140px] border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer ${
          productInCanvas
            ? 'bg-neutral-100 dark:bg-neutral-800/30 border-neutral-400 dark:border-neutral-600'
            : isBestMatch
              ? 'bg-neutral-100 dark:bg-neutral-800/10 border-neutral-300 dark:border-neutral-700 hover:border-neutral-400 dark:hover:border-neutral-600 hover:shadow-md'
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
              className="object-cover"
              sizes="140px"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-neutral-200 dark:bg-neutral-600">
              <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}

          {/* Best Match Badge */}
          {isBestMatch && !productInCanvas && (
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

          {productInCanvas && (
            <span className="absolute top-1 right-1 bg-neutral-700 text-white text-[9px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
              <svg className="w-2 h-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              {getCanvasQuantity(product.id) > 1 && getCanvasQuantity(product.id)}
            </span>
          )}

          {product.source_website && (
            <span className="absolute bottom-1 right-1 bg-black/70 text-white text-[8px] px-1 py-0.5 rounded backdrop-blur-sm">
              {product.source_website}
            </span>
          )}
        </div>

        {/* Product Info */}
        <div className="p-2">
          <h4 className="font-medium text-[10px] text-neutral-900 dark:text-white line-clamp-2 mb-1 h-[28px]">
            {product.name}
          </h4>
          <div className="flex items-center gap-1 mb-1.5">
            <span className="text-xs font-bold text-neutral-900 dark:text-white">
              {formatCurrency(product.price, product.currency)}
            </span>
          </div>

          {/* Add to Canvas Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAddToCanvas(product);
            }}
            className={`w-full py-1 text-[9px] font-medium rounded transition-colors ${
              productInCanvas
                ? 'bg-neutral-700 hover:bg-neutral-800 text-white'
                : 'bg-neutral-800 hover:bg-neutral-900 text-white'
            }`}
          >
            {productInCanvas ? `Add +1 (${getCanvasQuantity(product.id)})` : 'Add'}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="py-4 border-b border-neutral-100 dark:border-neutral-800">
      {/* Category Header */}
      <div className="px-4 mb-3 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-neutral-900 dark:text-white text-sm">
            {category.display_name}
          </h3>
          <div className="flex items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
            <span>{products.length} items</span>
            {bestMatches.length > 0 && (
              <>
                <span>•</span>
                <span className="text-neutral-700 dark:text-neutral-400">{bestMatches.length} best matches</span>
              </>
            )}
            {budgetHint && (
              <>
                <span>•</span>
                <span className="text-neutral-500 dark:text-neutral-400">Budget: {budgetHint}</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={onViewAll}
          className="text-xs text-neutral-700 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-300 font-medium flex items-center gap-1"
        >
          View All
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Best Matches Section */}
      {bestMatches.length > 0 && (
        <div className="mb-2">
          <div className="px-4 mb-2 flex items-center gap-2">
            <span className="text-[10px] font-semibold text-neutral-700 dark:text-neutral-400 uppercase tracking-wide">
              Best Matches
            </span>
            <div className="flex-1 h-px bg-neutral-300 dark:bg-neutral-700"></div>
          </div>
          <div className="relative group">
            <div
              ref={scrollRef}
              className="flex gap-3 overflow-x-auto scrollbar-hide px-4 pb-2 scroll-smooth"
              style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
            >
              {bestMatches.map((product) => renderProductCard(product, true))}
            </div>
          </div>
        </div>
      )}

      {/* More Products Section */}
      {moreProducts.length > 0 && (
        <div>
          {bestMatches.length > 0 && (
            <div className="px-4 mb-2 flex items-center gap-2">
              <span className="text-[10px] font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">
                More Options
              </span>
              <div className="flex-1 h-px bg-neutral-200 dark:bg-neutral-700"></div>
            </div>
          )}
          <div className="relative group">
            {/* Left Scroll Button */}
            <button
              onClick={() => scroll('left')}
              className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-8 h-8 bg-white dark:bg-neutral-800 rounded-full shadow-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-neutral-50 dark:hover:bg-neutral-700"
            >
              <svg className="w-4 h-4 text-neutral-600 dark:text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            {/* Products Scroll Container */}
            <div
              className="flex gap-3 overflow-x-auto scrollbar-hide px-4 pb-2 scroll-smooth"
              style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
            >
              {moreProducts.map((product) => renderProductCard(product, false))}
            </div>

            {/* Right Scroll Button */}
            <button
              onClick={() => scroll('right')}
              className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-8 h-8 bg-white dark:bg-neutral-800 rounded-full shadow-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-neutral-50 dark:hover:bg-neutral-700"
            >
              <svg className="w-4 h-4 text-neutral-600 dark:text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
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
