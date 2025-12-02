'use client';

import Image from 'next/image';
import { CuratedLook } from '@/utils/api';

interface LookDetailModalProps {
  look: CuratedLook;
  isOpen: boolean;
  onClose: () => void;
  onStyleThisLook: (look: CuratedLook) => void;
}

export function LookDetailModal({
  look,
  isOpen,
  onClose,
  onStyleThisLook,
}: LookDetailModalProps) {
  if (!isOpen) return null;

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-3xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-10 bg-white/90 backdrop-blur-sm rounded-full p-2.5 shadow-lg hover:bg-gray-100 transition-colors"
          >
            <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {/* Header - Theme info */}
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-2xl font-bold text-gray-800">{look.style_theme}</h2>
            <p className="text-gray-500 mt-1">{look.style_description}</p>
          </div>

          {/* Two-column layout */}
          <div className="flex flex-col lg:flex-row max-h-[calc(90vh-180px)]">
            {/* Left Side - Curated Visualization Image */}
            <div className="lg:w-1/2 p-6 flex flex-col">
              <div className="relative flex-1 min-h-[300px] lg:min-h-[400px] bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl overflow-hidden">
                {look.visualization_image ? (
                  <Image
                    src={look.visualization_image.startsWith('data:') ? look.visualization_image : `data:image/png;base64,${look.visualization_image}`}
                    alt={look.style_theme}
                    fill
                    className="object-cover"
                    sizes="50vw"
                    priority
                    unoptimized
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="text-center">
                      <svg className="w-16 h-16 text-gray-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <p className="text-gray-400">Visualization not available</p>
                    </div>
                  </div>
                )}

                {/* Price badge on image */}
                <div className="absolute top-4 right-4">
                  <div className="bg-white/95 backdrop-blur-sm px-4 py-2 rounded-full shadow-lg">
                    <span className="text-lg font-bold text-purple-600">{formatPrice(look.total_price)}</span>
                  </div>
                </div>

                {/* Product count badge */}
                <div className="absolute bottom-4 left-4">
                  <div className="bg-black/60 backdrop-blur-sm text-white px-3 py-1.5 rounded-full text-sm flex items-center gap-1.5">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    {look.products.length} items in this look
                  </div>
                </div>
              </div>

              {/* Use Style button - Desktop */}
              <button
                onClick={() => onStyleThisLook(look)}
                className="hidden lg:flex mt-4 w-full py-4 px-6 rounded-xl font-semibold transition-all items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white shadow-lg hover:shadow-xl"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Use Style in Studio
              </button>
            </div>

            {/* Right Side - Products */}
            <div className="lg:w-1/2 border-t lg:border-t-0 lg:border-l border-gray-100 flex flex-col">
              <div className="p-4 border-b border-gray-100 bg-gray-50/50">
                <h3 className="text-lg font-bold text-gray-800">Products in this Look</h3>
                <p className="text-sm text-gray-500">{look.products.length} items totaling {formatPrice(look.total_price)}</p>
              </div>

              {/* Scrollable Products Grid */}
              <div className="flex-1 overflow-y-auto p-4">
                <div className="grid grid-cols-2 gap-3">
                  {look.products.map((product) => (
                    <div
                      key={product.id}
                      className="bg-white rounded-xl overflow-hidden border border-gray-100 hover:shadow-lg transition-shadow"
                    >
                      {/* Product Image */}
                      <div className="aspect-square relative bg-gray-50">
                        {product.image_url ? (
                          <Image
                            src={product.image_url}
                            alt={product.name}
                            fill
                            className="object-cover"
                            sizes="(max-width: 768px) 50vw, 25vw"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <svg className="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                        )}

                        {/* Store badge */}
                        <div className="absolute top-2 left-2">
                          <span className="bg-white/90 backdrop-blur-sm text-gray-700 text-[10px] px-2 py-0.5 rounded-full font-medium capitalize">
                            {product.source_website}
                          </span>
                        </div>
                      </div>

                      {/* Product Info */}
                      <div className="p-3">
                        <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">{product.product_type}</p>
                        <h4 className="font-semibold text-gray-800 text-xs mb-1.5 line-clamp-2">{product.name}</h4>
                        <p className="text-purple-600 font-bold text-sm mb-2">{formatPrice(product.price)}</p>

                        {product.source_url && (
                          <a
                            href={product.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-1.5 px-2 rounded-lg text-[10px] font-medium transition-colors text-center flex items-center justify-center gap-1"
                          >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                            View Product
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Action Bar - Mobile */}
          <div className="lg:hidden p-4 border-t border-gray-200 bg-gray-50/80">
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 px-4 rounded-xl font-semibold transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => onStyleThisLook(look)}
                className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white py-3 px-4 rounded-xl font-semibold transition-all shadow-lg flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Use Style
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LookDetailModal;
