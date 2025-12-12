'use client';

import { useState, useMemo } from 'react';
import Image from 'next/image';
import { Product } from '@/types';
import { formatCurrency } from '@/utils/format';
import { ProductDetailModal } from '../ProductDetailModal';

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
}: CategorySectionProps) {
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [filters, setFilters] = useState<CategoryFilterState>({
    selectedStores: [],
    priceMin: category.budget_allocation?.min || 0,
    priceMax: category.budget_allocation?.max || Infinity,
    sortBy: 'relevance',
  });
  const [showFilters, setShowFilters] = useState(false);

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
    } as Product;
  };

  // Get unique stores from products
  const uniqueStores = useMemo(() => {
    return Array.from(
      new Set(products.map(p => p.source_website || p.source).filter(Boolean))
    ).sort();
  }, [products]);

  // Transform and filter products
  const filteredProducts = useMemo(() => {
    const transformed = products.map(transformProduct);

    return transformed.filter(product => {
      const price = product.price || 0;
      const store = product.source_website;

      // Price filter
      if (price < filters.priceMin) return false;
      if (filters.priceMax < 999999 && price > filters.priceMax) return false;

      // Store filter
      if (filters.selectedStores.length > 0 && !filters.selectedStores.includes(store)) return false;

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
              showFilters || filters.selectedStores.length > 0
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
              {/* Store Filter */}
              {uniqueStores.length > 0 && (
                <div>
                  <label className="text-xs text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                    Store
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {uniqueStores.map(store => (
                      <button
                        key={store}
                        onClick={() => toggleStore(store)}
                        className={`text-xs px-2 py-1 rounded-full transition-colors ${
                          filters.selectedStores.includes(store)
                            ? 'bg-primary-600 text-white'
                            : 'bg-white dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-600'
                        }`}
                      >
                        {store}
                      </button>
                    ))}
                  </div>
                </div>
              )}

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

          {/* Products Grid */}
          {filteredProducts.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {filteredProducts.map((product) => {
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
