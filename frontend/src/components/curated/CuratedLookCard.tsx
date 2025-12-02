'use client';

import Image from 'next/image';
import { CuratedLook } from '@/utils/api';

interface CuratedLookCardProps {
  look: CuratedLook;
  onViewDetails: (look: CuratedLook) => void;
  onStyleThisLook: (look: CuratedLook) => void;
  isLoading?: boolean;
}

export function CuratedLookCard({
  look,
  onViewDetails,
  onStyleThisLook,
  isLoading = false,
}: CuratedLookCardProps) {
  const formatPrice = (price: number) => {
    if (price >= 100000) {
      return `₹${(price / 100000).toFixed(1)}L`;
    } else if (price >= 1000) {
      return `₹${(price / 1000).toFixed(0)}K`;
    }
    return `₹${price.toFixed(0)}`;
  };

  // Loading skeleton
  if (isLoading || look.generation_status === 'pending' || look.generation_status === 'generating') {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-white/20 overflow-hidden animate-pulse">
        <div className="aspect-[4/3] bg-gradient-to-br from-gray-200 to-gray-300 relative">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="relative mb-4">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 mx-auto"></div>
                <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-purple-600 mx-auto absolute top-0 left-1/2 -translate-x-1/2"></div>
              </div>
              <p className="text-gray-600 font-medium">Creating your look...</p>
              <p className="text-gray-500 text-sm mt-1">AI is designing your space</p>
            </div>
          </div>
        </div>
        <div className="p-5">
          <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="flex gap-2">
            <div className="h-10 bg-gray-200 rounded-xl flex-1"></div>
            <div className="h-10 bg-gray-200 rounded-xl flex-1"></div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (look.generation_status === 'failed') {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-red-200 overflow-hidden">
        <div className="aspect-[4/3] bg-gradient-to-br from-red-50 to-red-100 flex items-center justify-center">
          <div className="text-center p-6">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-red-700 font-medium">Generation Failed</p>
            <p className="text-red-500 text-sm mt-1">{look.error_message || 'Unable to create this look'}</p>
          </div>
        </div>
        <div className="p-5">
          <h3 className="text-lg font-bold text-gray-800 mb-1">{look.style_theme}</h3>
          <p className="text-gray-500 text-sm">{look.style_description}</p>
        </div>
      </div>
    );
  }

  // Completed look
  return (
    <div className="group bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-white/20 overflow-hidden hover:shadow-2xl hover:scale-[1.02] transition-all duration-300">
      {/* Visualization Image */}
      <div className="aspect-[4/3] relative overflow-hidden bg-gradient-to-br from-gray-100 to-gray-200">
        {look.visualization_image ? (
          <Image
            src={look.visualization_image.startsWith('data:') ? look.visualization_image : `data:image/png;base64,${look.visualization_image}`}
            alt={look.style_theme}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-500"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            unoptimized
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <svg className="w-16 h-16 text-gray-300 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <p className="text-gray-400 text-sm mt-2">Visualization unavailable</p>
            </div>
          </div>
        )}

        {/* Price badge */}
        <div className="absolute top-4 right-4">
          <div className="bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-lg">
            <span className="text-lg font-bold text-purple-600">{formatPrice(look.total_price)}</span>
          </div>
        </div>

        {/* Product count badge */}
        <div className="absolute bottom-4 left-4">
          <div className="bg-black/60 backdrop-blur-sm text-white px-3 py-1 rounded-full text-sm flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            {look.products.length} items
          </div>
        </div>

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end justify-center pb-8">
          <button
            onClick={() => onViewDetails(look)}
            className="bg-white text-gray-800 px-6 py-2.5 rounded-full font-semibold shadow-lg hover:bg-gray-100 transition-colors transform translate-y-4 group-hover:translate-y-0 transition-transform duration-300"
          >
            View Products
          </button>
        </div>
      </div>

      {/* Card content */}
      <div className="p-5">
        <h3 className="text-xl font-bold text-gray-800 mb-1">{look.style_theme}</h3>
        <p className="text-gray-500 text-sm mb-4 line-clamp-2">{look.style_description}</p>

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => onViewDetails(look)}
            className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 py-2.5 px-4 rounded-xl font-medium transition-colors text-sm flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            View Details
          </button>
          <button
            onClick={() => onStyleThisLook(look)}
            className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white py-2.5 px-4 rounded-xl font-medium transition-all shadow-md hover:shadow-lg text-sm flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
            Use Style
          </button>
        </div>
      </div>
    </div>
  );
}

export default CuratedLookCard;
