'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Product } from '@/types'
import { formatCurrency } from '@/utils/format'

interface ProductCardProps {
  product: Product
  className?: string
}

export function ProductCard({ product, className = '' }: ProductCardProps) {
  const primaryImage = product.images?.find(img => img.is_primary) || product.images?.[0]
  const discountPercentage = product.original_price && product.price < product.original_price
    ? Math.round(((product.original_price - product.price) / product.original_price) * 100)
    : null

  return (
    <Link href={`/products/${product.id}`} className={`group block ${className}`}>
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden transition-all duration-300 hover:shadow-lg hover:border-gray-200 hover:-translate-y-1">
        {/* Image Container */}
        <div className="relative aspect-square bg-gray-50 overflow-hidden">
          {primaryImage ? (
            <Image
              src={primaryImage.large_url || primaryImage.medium_url || primaryImage.original_url}
              alt={primaryImage.alt_text || product.name}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}

          {/* Badges */}
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

          {/* Source Website Badge */}
          <div className="absolute top-3 right-3">
            <span className="inline-block bg-black/70 text-white text-xs font-medium px-2 py-1 rounded backdrop-blur-sm">
              {product.source_website}
            </span>
          </div>
        </div>

        {/* Product Info */}
        <div className="p-4">
          {/* Brand */}
          {product.brand && (
            <p className="text-sm text-gray-500 font-medium mb-1">{product.brand}</p>
          )}

          {/* Name */}
          <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2 group-hover:text-blue-600 transition-colors">
            {product.name}
          </h3>

          {/* Category */}
          {product.category && (
            <p className="text-xs text-gray-400 mb-3">{product.category.name}</p>
          )}

          {/* Price */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="text-lg font-bold text-gray-900">
                {formatCurrency(product.price, product.currency)}
              </span>
              {product.original_price && product.price < product.original_price && (
                <span className="text-sm text-gray-400 line-through">
                  {formatCurrency(product.original_price, product.currency)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}

export default ProductCard