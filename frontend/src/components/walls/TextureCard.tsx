'use client';

import { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';
import {
  WallTextureWithVariants,
  WallTextureVariant,
  TEXTURE_TYPE_LABELS,
} from '@/types/wall-textures';
import { TextureDetailModal } from './TextureDetailModal';

interface TextureCardProps {
  /** The texture with its variants */
  texture: WallTextureWithVariants;
  /** Currently selected variant */
  selectedVariantId: number | null;
  /** Callback when variant is selected */
  onSelectVariant: (variant: WallTextureVariant, texture: WallTextureWithVariants) => void;
  /** Whether the card is expanded by default */
  defaultExpanded?: boolean;
}

/**
 * Get the product page URL for a variant
 * Uses the stored product_url if available, otherwise constructs from texture name and code
 */
function getProductPageUrl(variant: WallTextureVariant, textureName: string): string | null {
  // Use stored product URL if available
  if (variant.product_url) {
    return variant.product_url;
  }

  // Fallback: construct URL from texture name and variant code
  if (!variant.code) return null;

  // Convert texture name to URL slug: "Metallics Bandhej" -> "metallics-bandhej"
  const nameSlug = textureName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  const code = variant.code.toLowerCase();

  // Asian Paints texture product page pattern
  return `https://www.asianpaints.com/interior-textures/${nameSlug}-${code}.html`;
}

/**
 * TextureVariantCard Component
 *
 * Individual texture variant displayed as a card matching the furniture product card pattern.
 * Shows aspect-square image, variant code, and hover overlay with "View Details" and "Add to Canvas".
 */
/**
 * Build the image URL for a texture variant.
 * Prefers the API image endpoint (lazy loaded by browser).
 * Falls back to inline base64 if available.
 */
function getVariantImageUrl(variant: WallTextureVariant): string {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  // Use the dedicated image endpoint — browser lazy-loads and caches automatically
  return `${apiBase}/api/wall-textures/variant/${variant.id}/image`;
}

function TextureVariantCard({
  variant,
  textureName,
  isSelected,
  onClick,
  onViewDetails,
}: {
  variant: WallTextureVariant;
  textureName: string;
  isSelected: boolean;
  onClick: () => void;
  onViewDetails?: () => void;
}) {
  const [imageError, setImageError] = useState(false);

  const imageUrl = getVariantImageUrl(variant);

  return (
    <div
      className={`group border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer ${
        isSelected
          ? 'bg-neutral-100 dark:bg-neutral-800/30 border-neutral-400 dark:border-neutral-600'
          : 'bg-white dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-md'
      }`}
    >
      {/* Variant Image */}
      <div className="relative aspect-square bg-neutral-100 dark:bg-neutral-700">
        {imageError ? (
          <div className="w-full h-full flex items-center justify-center bg-neutral-200 dark:bg-neutral-600">
            <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        ) : (
          <img
            src={imageUrl}
            alt={variant.name || variant.code}
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
              onClick();
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

      {/* Variant Info */}
      <div className="p-2">
        <h4 className="text-[11px] font-medium text-neutral-900 dark:text-white line-clamp-1 mb-0.5">
          {variant.name || textureName}
        </h4>
        <p className="text-[10px] text-neutral-500 dark:text-neutral-400">
          {variant.code}
        </p>
      </div>
    </div>
  );
}

/**
 * TextureCard Component
 *
 * Displays a base texture with its color variants in a grid layout matching furniture cards.
 * Variants use aspect-square images with hover overlays for "View Details" and "Add to Canvas".
 */
export function TextureCard({
  texture,
  selectedVariantId,
  onSelectVariant,
  defaultExpanded = false,
}: TextureCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [detailModalVariant, setDetailModalVariant] = useState<WallTextureVariant | null>(null);

  const hasMultipleVariants = texture.variants.length > 1;

  // Check if any variant in this texture is selected
  const hasSelectedVariant = texture.variants.some((v) => v.id === selectedVariantId);

  // Product page URL - use first variant's URL
  const previewVariant = texture.variants[0];
  const productPageUrl = previewVariant ? getProductPageUrl(previewVariant, texture.name) : null;

  if (!previewVariant) {
    return null;
  }

  const visibleVariants = isExpanded || !hasMultipleVariants
    ? texture.variants
    : texture.variants.slice(0, 4);

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-all ${
        hasSelectedVariant
          ? 'border-neutral-900 dark:border-white bg-neutral-50 dark:bg-neutral-800'
          : 'border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800'
      }`}
    >
      {/* Header with texture name */}
      <div className="flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <h4 className="font-medium text-neutral-900 dark:text-white text-sm truncate">
            {texture.name}
          </h4>
          {texture.texture_type && (
            <span className="flex-shrink-0 inline-block px-1.5 py-0.5 text-[10px] bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 rounded">
              {TEXTURE_TYPE_LABELS[texture.texture_type]}
            </span>
          )}
          <span className="flex-shrink-0 text-[10px] text-neutral-400">
            {texture.variants.length} {texture.variants.length === 1 ? 'variant' : 'variants'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {/* Product page link */}
          {productPageUrl && (
            <a
              href={productPageUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 p-1 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors"
              title="View on Asian Paints"
              onClick={(e) => e.stopPropagation()}
            >
              <ArrowTopRightOnSquareIcon className="w-4 h-4" />
            </a>
          )}
          {/* Expand toggle for multiple variants */}
          {hasMultipleVariants && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors p-1"
            >
              {isExpanded ? (
                <ChevronDownIcon className="w-4 h-4" />
              ) : (
                <ChevronRightIcon className="w-4 h-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Variant grid - matching furniture product grid layout */}
      <div className="px-3 pb-3">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {visibleVariants.map((variant) => (
            <TextureVariantCard
              key={variant.id}
              variant={variant}
              textureName={texture.name}
              isSelected={variant.id === selectedVariantId}
              onClick={() => onSelectVariant(variant, texture)}
              onViewDetails={() => setDetailModalVariant(variant)}
            />
          ))}
          {!isExpanded && hasMultipleVariants && texture.variants.length > 4 && (
            <button
              onClick={() => setIsExpanded(true)}
              className="aspect-square rounded-lg border-2 border-dashed border-neutral-300 dark:border-neutral-600 flex items-center justify-center text-neutral-400 hover:border-neutral-400 hover:text-neutral-500 transition-colors"
            >
              <span className="text-sm font-medium">+{texture.variants.length - 4}</span>
            </button>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {detailModalVariant && (
        <TextureDetailModal
          texture={texture}
          variant={detailModalVariant}
          isOpen={!!detailModalVariant}
          onClose={() => setDetailModalVariant(null)}
          onAddToCanvas={() => {
            onSelectVariant(detailModalVariant, texture);
            setDetailModalVariant(null);
          }}
          inCanvas={detailModalVariant.id === selectedVariantId}
        />
      )}
    </div>
  );
}

export { TextureVariantCard };
