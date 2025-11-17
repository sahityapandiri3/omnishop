'use client';

import { useState } from 'react';
import Image from 'next/image';
import { Product } from '@/types';
import { formatCurrency } from '@/utils/format';

interface ProductDetailModalProps {
  product: Product;
  isOpen: boolean;
  onClose: () => void;
  onAddToCanvas?: () => void;
  inCanvas?: boolean;
}

export function ProductDetailModal({
  product,
  isOpen,
  onClose,
  onAddToCanvas,
  inCanvas = false,
}: ProductDetailModalProps) {
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);

  if (!isOpen) return null;

  const images = product.images || [];
  const currentImage = images[selectedImageIndex] || images[0];
  const discountPercentage =
    product.original_price && product.price < product.original_price
      ? Math.round(
          ((product.original_price - product.price) / product.original_price) *
            100
        )
      : null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-2xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-10 bg-white rounded-full p-2 shadow-lg hover:bg-gray-100 transition-colors"
          >
            <svg
              className="w-6 h-6 text-gray-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>

          <div className="grid md:grid-cols-2 gap-6 p-6 overflow-y-auto max-h-[90vh]">
            {/* Left: Images */}
            <div>
              {/* Main Image */}
              <div className="relative aspect-square bg-gray-100 rounded-xl overflow-hidden mb-4">
                {currentImage ? (
                  <Image
                    src={
                      currentImage.large_url ||
                      currentImage.medium_url ||
                      currentImage.original_url
                    }
                    alt={currentImage.alt_text || product.name}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 100vw, 50vw"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400">
                    <svg
                      className="w-16 h-16"
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
                  </div>
                )}

                {/* Badges on main image */}
                <div className="absolute top-3 left-3 space-y-1">
                  {product.is_on_sale && discountPercentage && (
                    <span className="inline-block bg-red-500 text-white text-xs font-semibold px-2 py-1 rounded-full">
                      -{discountPercentage}%
                    </span>
                  )}
                  {!product.is_available && (
                    <span className="inline-block bg-gray-500 text-white text-xs font-semibold px-2 py-1 rounded-full">
                      Out of Stock
                    </span>
                  )}
                </div>
              </div>

              {/* Thumbnail Gallery */}
              {images.length > 1 && (
                <div className="grid grid-cols-4 gap-2 overflow-x-auto">
                  {images.map((image, index) => (
                    <button
                      key={image.id || index}
                      onClick={() => setSelectedImageIndex(index)}
                      className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                        selectedImageIndex === index
                          ? 'border-blue-500 ring-2 ring-blue-200'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <Image
                        src={
                          image.thumbnail_url ||
                          image.medium_url ||
                          image.original_url
                        }
                        alt={image.alt_text || `Product image ${index + 1}`}
                        fill
                        className="object-cover"
                        sizes="100px"
                      />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Right: Product Details */}
            <div className="flex flex-col">
              {/* Brand */}
              {product.brand && (
                <p className="text-sm text-gray-500 font-medium mb-2">
                  {product.brand}
                </p>
              )}

              {/* Name */}
              <h2 className="text-2xl font-bold text-gray-900 mb-3">
                {product.name}
              </h2>

              {/* Category */}
              {product.category && (
                <p className="text-sm text-gray-500 mb-4">
                  {product.category.name}
                </p>
              )}

              {/* Price */}
              <div className="flex items-center space-x-3 mb-6">
                <span className="text-3xl font-bold text-gray-900">
                  {formatCurrency(product.price, product.currency)}
                </span>
                {product.original_price &&
                  product.price < product.original_price && (
                    <span className="text-lg text-gray-400 line-through">
                      {formatCurrency(product.original_price, product.currency)}
                    </span>
                  )}
              </div>

              {/* Description */}
              {product.description && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">
                    Description
                  </h3>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    {product.description}
                  </p>
                </div>
              )}

              {/* Source */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">
                  Source
                </h3>
                <div className="flex items-center space-x-2">
                  <span className="inline-block bg-gray-100 text-gray-700 text-sm px-3 py-1 rounded-full">
                    {product.source_website}
                  </span>
                  {product.source_url && (
                    <a
                      href={product.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-700 underline"
                    >
                      View on website
                    </a>
                  )}
                </div>
              </div>

              {/* SKU */}
              {product.sku && (
                <p className="text-xs text-gray-400 mb-6">SKU: {product.sku}</p>
              )}

              {/* Action Button */}
              <div className="mt-auto">
                {onAddToCanvas && !inCanvas && (
                  <button
                    onClick={onAddToCanvas}
                    disabled={!product.is_available}
                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-xl transition-colors disabled:cursor-not-allowed"
                  >
                    {product.is_available ? 'Add to Canvas' : 'Out of Stock'}
                  </button>
                )}
                {inCanvas && (
                  <div className="bg-green-50 border border-green-200 text-green-700 text-center py-3 px-6 rounded-xl font-medium">
                    ✓ Added to Canvas
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProductDetailModal;
