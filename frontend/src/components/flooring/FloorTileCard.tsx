'use client';

import { useState } from 'react';
import { FloorTile } from '@/types/floor-tiles';

interface FloorTileCardProps {
  tile: FloorTile;
  isSelected: boolean;
  onSelect: (tile: FloorTile) => void;
  onViewDetails?: () => void;
}

/**
 * Build the image URL for a floor tile.
 * Uses the API image endpoint for lazy browser loading.
 */
function getTileImageUrl(tile: FloorTile): string | null {
  if (tile.image_url) return tile.image_url;
  if (tile.swatch_url) return tile.swatch_url;
  // Fall back to API endpoint
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  return `${apiBase}/api/floor-tiles/${tile.id}/image`;
}

/**
 * FloorTileCard Component
 *
 * Displays a single floor tile as a card with image, name, size, finish.
 * Matches the TextureVariantCard pattern with hover overlay for "Add to Canvas".
 */
export function FloorTileCard({
  tile,
  isSelected,
  onSelect,
  onViewDetails,
}: FloorTileCardProps) {
  const [imageError, setImageError] = useState(false);

  const imageUrl = getTileImageUrl(tile);

  return (
    <div
      className={`group border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer ${
        isSelected
          ? 'bg-neutral-100 dark:bg-neutral-800/30 border-neutral-400 dark:border-neutral-600'
          : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-md'
      }`}
    >
      {/* Tile Image */}
      <div className="relative aspect-square bg-neutral-100 dark:bg-neutral-700">
        {imageError || !imageUrl ? (
          <div className="w-full h-full flex items-center justify-center bg-neutral-200 dark:bg-neutral-600">
            <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        ) : (
          <img
            src={imageUrl}
            alt={tile.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={() => setImageError(true)}
          />
        )}

        {/* In Canvas Badge */}
        {isSelected && (
          <span className="absolute top-1 right-1 bg-neutral-700 text-white text-[9px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
            <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </span>
        )}

        {/* Hover overlay with View Details and Add to Canvas */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1.5">
          {onViewDetails && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onViewDetails();
              }}
              className="px-2.5 py-1 bg-white/90 hover:bg-white text-neutral-800 text-[10px] font-medium rounded flex items-center gap-1 transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              View Details
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect(tile);
            }}
            className={`px-2.5 py-1 text-[10px] font-medium rounded flex items-center gap-1 transition-colors ${
              isSelected
                ? 'bg-red-500/90 hover:bg-red-500 text-white'
                : 'bg-white/90 hover:bg-white text-neutral-800'
            }`}
          >
            {isSelected ? (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Remove
              </>
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add to Canvas
              </>
            )}
          </button>
        </div>
      </div>

      {/* Tile Info */}
      <div className="p-2">
        <h4 className="text-[11px] font-medium text-neutral-900 dark:text-white line-clamp-1 mb-0.5">
          {tile.name}
        </h4>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] text-neutral-500 dark:text-neutral-400">
            {tile.size}
          </span>
          {tile.finish && (
            <>
              <span className="text-[10px] text-neutral-300 dark:text-neutral-600">|</span>
              <span className="text-[10px] text-neutral-500 dark:text-neutral-400">
                {tile.finish}
              </span>
            </>
          )}
          {tile.look && (
            <>
              <span className="text-[10px] text-neutral-300 dark:text-neutral-600">|</span>
              <span className="text-[10px] text-neutral-500 dark:text-neutral-400">
                {tile.look}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
