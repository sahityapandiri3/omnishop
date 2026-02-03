'use client';

import { useMemo } from 'react';
import {
  WallTextureWithVariants,
  WallTextureVariant,
} from '@/types/wall-textures';
import { TextureCard } from './TextureCard';

interface WallTextureGridProps {
  /** All textures with variants */
  textures: WallTextureWithVariants[];
  /** Filter by brands */
  brandFilter?: string[];
  /** Currently selected variant ID */
  selectedVariantId: number | null;
  /** Callback when variant is selected */
  onSelectVariant: (variant: WallTextureVariant, texture: WallTextureWithVariants) => void;
  /** Loading state */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
}

/**
 * WallTextureGrid Component
 *
 * Displays wall textures in ProductDiscoveryPanel (Panel 2).
 * Shows textures as cards with expandable variant thumbnails.
 * Supports filtering by brand.
 */
export function WallTextureGrid({
  textures,
  brandFilter = [],
  selectedVariantId,
  onSelectVariant,
  isLoading = false,
  error = null,
}: WallTextureGridProps) {
  // Filter textures based on brand filter
  const filteredTextures = useMemo(() => {
    return textures.filter((texture) => {
      // Brand filter
      if (brandFilter.length > 0 && !brandFilter.includes(texture.brand)) {
        return false;
      }
      return true;
    });
  }, [textures, brandFilter]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <svg
            className="animate-spin h-8 w-8 text-neutral-400 mx-auto"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
            Loading textures...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (filteredTextures.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            {textures.length === 0
              ? 'No textures available'
              : 'No textures match the selected filters'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-3">
      {filteredTextures.map((texture) => (
        <TextureCard
          key={texture.id}
          texture={texture}
          selectedVariantId={selectedVariantId}
          onSelectVariant={onSelectVariant}
          defaultExpanded={texture.variants.length <= 4}
        />
      ))}
    </div>
  );
}
