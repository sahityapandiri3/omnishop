'use client';

import { useState } from 'react';
import Image from 'next/image';
import { ProductDetailModal } from '../ProductDetailModal';
import { Product } from '@/types';
import { formatCurrency } from '@/utils/format';

interface ProductDiscoveryPanelProps {
  products: any[];  // Raw products from API
  onAddToCanvas: (product: any) => void;
  canvasProducts: any[];
}

/**
 * Panel 2: Product Discovery & Selection
 * Displays products with modal details and Add to Canvas functionality
 */
export default function ProductDiscoveryPanel({
  products,
  onAddToCanvas,
  canvasProducts,
}: ProductDiscoveryPanelProps) {
  console.log('[ProductDiscoveryPanel] Received products:', products.length, 'products');
  console.log('[ProductDiscoveryPanel] First product:', products[0]);

  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [sortBy, setSortBy] = useState<'relevance' | 'price-low' | 'price-high'>(
    'relevance'
  );

  // Filter states
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState<{ min: number; max: number }>({ min: 0, max: Infinity });

  // Transform raw product to Product type
  const transformProduct = (rawProduct: any): Product => {
    // Handle different image formats from API
    let images = [];

    // Backend returns primary_image.url from chat API
    if (rawProduct.primary_image && rawProduct.primary_image.url) {
      images = [{
        id: 1,
        original_url: rawProduct.primary_image.url,
        is_primary: true,
        alt_text: rawProduct.primary_image.alt_text || rawProduct.name
      }];
    }
    // Fallback: Check for images array
    else if (rawProduct.images && Array.isArray(rawProduct.images)) {
      images = rawProduct.images;
    }
    // Fallback: Check for image_url
    else if (rawProduct.image_url) {
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

  // Check if product is in canvas
  const isInCanvas = (productId: string | number) => {
    return canvasProducts.some((p) => p.id.toString() === productId.toString());
  };

  // Handle product click (open modal)
  const handleProductClick = (product: Product) => {
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

  // Empty state
  if (products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
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
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-2">
          No Products Yet
        </h3>
        <p className="text-sm text-neutral-600 dark:text-neutral-400 max-w-sm">
          Start chatting with the AI assistant to get personalized furniture
          recommendations for your space.
        </p>
      </div>
    );
  }

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
        <div className="flex-1 overflow-y-auto p-4">
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

                    {/* In Canvas Badge */}
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
                          In Canvas
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

                    {/* Add to Canvas Button */}
                    {!productInCanvas ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onAddToCanvas(product);
                        }}
                        disabled={product.is_available === false}
                        className="w-full py-1.5 px-2 bg-primary-600 hover:bg-primary-700 disabled:bg-neutral-300 dark:disabled:bg-neutral-700 disabled:cursor-not-allowed text-white rounded-lg text-xs font-medium transition-colors"
                      >
                        {product.is_available === false ? 'Out of Stock' : 'Add to Canvas'}
                      </button>
                    ) : (
                      <div className="w-full py-1.5 px-2 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded-lg text-xs font-medium text-center">
                        Added to Canvas ✓
                      </div>
                    )}

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
        />
      )}
    </>
  );
}
