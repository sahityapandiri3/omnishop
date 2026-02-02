'use client';

/**
 * ProductCanvas Component
 *
 * Shared component for displaying products in the canvas:
 * - Grid/List view toggle
 * - Product cards with quantity controls
 * - Remove/View details actions
 * - Total price calculation
 *
 * Used by both CanvasPanel and Admin Curation page.
 */

import React from 'react';
import Image from 'next/image';
import { VisualizationProduct } from '@/types/visualization';
import { getProductImageUrl, calculateTotalPrice, calculateTotalItems, isBase64Image, formatImageSrc } from '@/utils/visualization-helpers';

interface ProductCanvasProps {
  products: VisualizationProduct[];
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  onRemoveProduct: (productId: string, removeAll?: boolean) => void;
  onIncrementQuantity?: (productId: string) => void;
  onViewProductDetails?: (product: VisualizationProduct) => void;
  onClearCanvas: () => void;
  showTotals?: boolean;
  disabled?: boolean;
}

export function ProductCanvas({
  products,
  viewMode,
  onViewModeChange,
  onRemoveProduct,
  onIncrementQuantity,
  onViewProductDetails,
  onClearCanvas,
  showTotals = true,
  disabled = false,
}: ProductCanvasProps) {
  const totalPrice = calculateTotalPrice(products);
  const totalItems = calculateTotalItems(products);

  if (products.length === 0) {
    return (
      <div className="p-6 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-neutral-100 dark:bg-neutral-800 flex items-center justify-center">
          <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <h3 className="text-sm font-medium text-neutral-900 dark:text-white mb-1">
          No products added yet
        </h3>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          Add products from the catalog to see them here
        </p>
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* Header with view mode toggle and totals */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
            Canvas Products
          </h3>
          {showTotals && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              ({totalItems} items)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex items-center border border-neutral-300 dark:border-neutral-600 rounded-lg overflow-hidden">
            <button
              onClick={() => onViewModeChange('grid')}
              className={`p-1.5 ${viewMode === 'grid' ? 'bg-neutral-100 dark:bg-neutral-700' : 'hover:bg-neutral-50 dark:hover:bg-neutral-800'}`}
              title="Grid view"
            >
              <svg className="w-4 h-4 text-neutral-600 dark:text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => onViewModeChange('list')}
              className={`p-1.5 ${viewMode === 'list' ? 'bg-neutral-100 dark:bg-neutral-700' : 'hover:bg-neutral-50 dark:hover:bg-neutral-800'}`}
              title="List view"
            >
              <svg className="w-4 h-4 text-neutral-600 dark:text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
            </button>
          </div>
          {/* Clear all button */}
          <button
            onClick={onClearCanvas}
            disabled={disabled}
            className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Product grid/list */}
      <div className={viewMode === 'grid'
        ? 'grid grid-cols-2 gap-3'
        : 'space-y-2'
      }>
        {products.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            viewMode={viewMode}
            onRemove={() => onRemoveProduct(String(product.id))}
            onRemoveAll={() => onRemoveProduct(String(product.id), true)}
            onIncrement={onIncrementQuantity ? () => onIncrementQuantity(String(product.id)) : undefined}
            onViewDetails={onViewProductDetails ? () => onViewProductDetails(product) : undefined}
            disabled={disabled}
          />
        ))}
      </div>

      {/* Total price */}
      {showTotals && totalPrice > 0 && (
        <div className="mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
              Total
            </span>
            <span className="text-lg font-semibold text-neutral-900 dark:text-white">
              {new Intl.NumberFormat('en-IN', {
                style: 'currency',
                currency: 'INR',
                maximumFractionDigits: 0,
              }).format(totalPrice)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// ProductCard Component
// ============================================================================

interface ProductCardProps {
  product: VisualizationProduct;
  viewMode: 'grid' | 'list';
  onRemove: () => void;
  onRemoveAll?: () => void;
  onIncrement?: () => void;
  onViewDetails?: () => void;
  disabled?: boolean;
}

function ProductCard({
  product,
  viewMode,
  onRemove,
  onRemoveAll,
  onIncrement,
  onViewDetails,
  disabled = false,
}: ProductCardProps) {
  const imageUrl = getProductImageUrl(product);
  const quantity = product.quantity || 1;
  const hasMultiple = quantity > 1;

  if (viewMode === 'list') {
    return (
      <div className="flex items-center gap-3 p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
        {/* Image */}
        <div
          className="relative w-16 h-16 bg-white dark:bg-neutral-700 rounded-lg overflow-hidden flex-shrink-0 cursor-pointer"
          onClick={onViewDetails}
        >
          {imageUrl ? (
            isBase64Image(imageUrl) ? (
              <img
                src={formatImageSrc(imageUrl)}
                alt={product.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <Image
                src={imageUrl}
                alt={product.name}
                fill
                className="object-cover"
                unoptimized
              />
            )
          ) : (
            <div className="w-full h-full flex items-center justify-center text-neutral-400">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-neutral-900 dark:text-white truncate">
            {product.name}
          </h4>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            {new Intl.NumberFormat('en-IN', {
              style: 'currency',
              currency: 'INR',
              maximumFractionDigits: 0,
            }).format(product.price * quantity)}
            {hasMultiple && ` (${quantity}x)`}
          </p>
        </div>

        {/* Quantity controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={onRemove}
            disabled={disabled}
            className="p-1 text-neutral-400 hover:text-red-500 transition-colors disabled:opacity-50"
            title={hasMultiple ? 'Remove one' : 'Remove'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>
          <span className="w-6 text-center text-sm font-medium text-neutral-700 dark:text-neutral-300">
            {quantity}
          </span>
          {onIncrement && (
            <button
              onClick={onIncrement}
              disabled={disabled}
              className="p-1 text-neutral-400 hover:text-neutral-700 transition-colors disabled:opacity-50"
              title="Add one more"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          )}
        </div>
      </div>
    );
  }

  // Grid view
  return (
    <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg overflow-hidden">
      {/* Image */}
      <div
        className="relative aspect-square bg-white dark:bg-neutral-700 cursor-pointer"
        onClick={onViewDetails}
      >
        {imageUrl ? (
          isBase64Image(imageUrl) ? (
            <img
              src={formatImageSrc(imageUrl)}
              alt={product.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <Image
              src={imageUrl}
              alt={product.name}
              fill
              className="object-cover"
              unoptimized
            />
          )
        ) : (
          <div className="w-full h-full flex items-center justify-center text-neutral-400">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
        {/* Quantity badge */}
        {hasMultiple && (
          <div className="absolute top-1 right-1 bg-neutral-800 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">
            x{quantity}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-2">
        <h4 className="text-xs font-medium text-neutral-900 dark:text-white truncate mb-1">
          {product.name}
        </h4>
        <div className="flex items-center justify-between">
          <span className="text-xs text-neutral-500 dark:text-neutral-400">
            {new Intl.NumberFormat('en-IN', {
              style: 'currency',
              currency: 'INR',
              maximumFractionDigits: 0,
            }).format(product.price * quantity)}
          </span>
          <div className="flex items-center gap-0.5">
            <button
              onClick={onRemove}
              disabled={disabled}
              className="p-1 text-neutral-400 hover:text-red-500 transition-colors disabled:opacity-50"
              title={hasMultiple ? 'Remove one' : 'Remove'}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
            </button>
            {onIncrement && (
              <button
                onClick={onIncrement}
                disabled={disabled}
                className="p-1 text-neutral-400 hover:text-neutral-700 transition-colors disabled:opacity-50"
                title="Add one more"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
