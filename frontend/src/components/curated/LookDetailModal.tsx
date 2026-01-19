'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { CuratedLook, getCuratedLookById } from '@/utils/api';

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
  const [fullLook, setFullLook] = useState<CuratedLook | null>(null);
  const [loadingFullImage, setLoadingFullImage] = useState(false);

  // Fetch full-resolution image when modal opens
  useEffect(() => {
    if (isOpen && look.look_id) {
      setLoadingFullImage(true);
      getCuratedLookById(look.look_id)
        .then((fullData) => {
          setFullLook(fullData);
        })
        .catch((err) => {
          console.error('Failed to fetch full look:', err);
        })
        .finally(() => {
          setLoadingFullImage(false);
        });
    } else {
      setFullLook(null);
    }
  }, [isOpen, look.look_id]);

  if (!isOpen) return null;

  // Use full-resolution image if loaded, otherwise fall back to thumbnail
  const displayImage = fullLook?.visualization_image || look.visualization_image;

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
        className="fixed inset-0 bg-neutral-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-2xl shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-3 right-3 z-10 bg-white/90 backdrop-blur-sm rounded-full p-2 shadow-sm hover:bg-neutral-100 transition-colors"
          >
            <svg className="w-5 h-5 text-neutral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {/* Header - Theme info */}
          <div className="p-4 border-b border-neutral-100">
            <h2 className="text-lg font-bold text-neutral-800">{look.title || look.style_theme}</h2>
            <p className="text-neutral-500 text-sm mt-0.5">{look.style_description}</p>
          </div>

          {/* Two-column layout */}
          <div className="flex flex-col lg:flex-row max-h-[calc(90vh-140px)]">
            {/* Left Side - Curated Visualization Image */}
            <div className="lg:w-1/2 p-4 flex flex-col">
              <div className="relative flex-1 min-h-[250px] lg:min-h-[350px] bg-gradient-to-br from-neutral-100 to-neutral-200 rounded-xl overflow-hidden">
                {/* Loading indicator for full image */}
                {loadingFullImage && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-neutral-100/50">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary-600 border-t-transparent"></div>
                  </div>
                )}
                {displayImage ? (
                  <Image
                    src={displayImage.startsWith('data:') ? displayImage : `data:image/png;base64,${displayImage}`}
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
                      <svg className="w-12 h-12 text-neutral-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <p className="text-neutral-400 text-sm">Visualization not available</p>
                    </div>
                  </div>
                )}

                {/* Price badge on image */}
                <div className="absolute top-3 right-3">
                  <div className="bg-white/95 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm">
                    <span className="text-sm font-bold text-primary-600">{formatPrice(look.total_price)}</span>
                  </div>
                </div>

                {/* Product count badge */}
                <div className="absolute bottom-3 left-3">
                  <div className="bg-neutral-800/70 backdrop-blur-sm text-white px-2 py-1 rounded-full text-xs flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    {look.products.length} items
                  </div>
                </div>
              </div>

              {/* Action buttons - Desktop */}
              <div className="hidden lg:flex mt-3 gap-2">
                <button
                  onClick={() => onStyleThisLook(look)}
                  className="flex-1 py-3 px-4 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                  Use Style in Studio
                </button>
                <a
                  href="/app"
                  className="flex-1 py-3 px-4 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2 bg-white border border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                  </svg>
                  Build Your Own
                </a>
              </div>
            </div>

            {/* Right Side - Products */}
            <div className="lg:w-1/2 border-t lg:border-t-0 lg:border-l border-neutral-100 flex flex-col">
              <div className="p-3 border-b border-neutral-100 bg-neutral-50/50">
                <h3 className="text-sm font-semibold text-neutral-800">Products in this Look</h3>
                <p className="text-xs text-neutral-500">{look.products.length} items totaling {formatPrice(look.total_price)}</p>
              </div>

              {/* Scrollable Products Grid */}
              <div className="flex-1 overflow-y-auto p-3">
                <div className="grid grid-cols-2 gap-2">
                  {look.products.map((product) => (
                    <div
                      key={product.id}
                      className="bg-white rounded-lg overflow-hidden border border-neutral-100 hover:shadow-md transition-shadow"
                    >
                      {/* Product Image */}
                      <div className="aspect-square relative bg-neutral-50">
                        {product.image_url ? (
                          <Image
                            src={product.image_url}
                            alt={product.name}
                            fill
                            className="object-cover"
                            sizes="(max-width: 768px) 50vw, 25vw"
                            unoptimized
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <svg className="w-8 h-8 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                        )}

                        {/* Store badge */}
                        <div className="absolute top-1.5 left-1.5">
                          <span className="bg-white/90 backdrop-blur-sm text-neutral-600 text-[9px] px-1.5 py-0.5 rounded-full font-medium capitalize">
                            {product.source_website}
                          </span>
                        </div>
                      </div>

                      {/* Product Info */}
                      <div className="p-2">
                        <p className="text-[9px] text-neutral-400 uppercase tracking-wide mb-0.5">{product.product_type}</p>
                        <h4 className="font-medium text-neutral-800 text-[11px] mb-1 line-clamp-2">{product.name}</h4>
                        <p className="text-primary-600 font-bold text-xs mb-1.5">{formatPrice(product.price)}</p>

                        {product.source_url && (
                          <a
                            href={product.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-full bg-neutral-100 hover:bg-neutral-200 text-neutral-700 py-1 px-2 rounded text-[9px] font-medium transition-colors text-center flex items-center justify-center gap-1"
                          >
                            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                            View
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
          <div className="lg:hidden p-3 border-t border-neutral-200 bg-neutral-50/80">
            <div className="flex gap-2">
              <button
                onClick={() => onStyleThisLook(look)}
                className="flex-1 bg-primary-600 hover:bg-primary-700 text-white py-2.5 px-3 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Use Style
              </button>
              <a
                href="/app"
                className="flex-1 bg-white border border-neutral-200 hover:bg-neutral-50 text-neutral-700 py-2.5 px-3 rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                Build Your Own
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LookDetailModal;
