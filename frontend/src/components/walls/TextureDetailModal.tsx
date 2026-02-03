'use client';

import { WallTextureVariant, WallTextureWithVariants } from '@/types/wall-textures';

interface TextureDetailModalProps {
  /** The parent texture */
  texture: WallTextureWithVariants;
  /** The specific variant being viewed */
  variant: WallTextureVariant;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Callback to add to canvas */
  onAddToCanvas?: () => void;
  /** Whether this variant is already on canvas */
  inCanvas?: boolean;
}

/**
 * Get the product page URL for a variant
 */
function getProductPageUrl(variant: WallTextureVariant, textureName: string): string | null {
  // Use stored product URL if available
  if (variant.product_url) {
    return variant.product_url;
  }

  // Fallback: construct URL from texture name and variant code
  if (!variant.code) return null;

  const nameSlug = textureName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  const code = variant.code.toLowerCase();

  return `https://www.asianpaints.com/interior-textures/${nameSlug}-${code}.html`;
}

/**
 * TextureDetailModal Component
 *
 * Shows detailed view of a texture variant including:
 * - Large swatch image
 * - Texture name and variant code
 * - Description and type
 * - Link to product website
 * - Add to Canvas button
 */
export function TextureDetailModal({
  texture,
  variant,
  isOpen,
  onClose,
  onAddToCanvas,
  inCanvas = false,
}: TextureDetailModalProps) {
  if (!isOpen) return null;

  // Use API image endpoint, or fall back to inline base64 if available
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const imageUrl = variant.image_data
    ? (variant.image_data.startsWith('data:')
      ? variant.image_data
      : `data:image/jpeg;base64,${variant.image_data}`)
    : `${apiBase}/api/wall-textures/variant/${variant.id}/image`;

  const productUrl = getProductPageUrl(variant, texture.name);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white dark:bg-neutral-900 rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-10 bg-white dark:bg-neutral-800 rounded-full p-2 shadow-lg hover:bg-gray-100 dark:hover:bg-neutral-700 transition-colors"
          >
            <svg
              className="w-6 h-6 text-gray-600 dark:text-gray-300"
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
            {/* Left: Swatch Image */}
            <div>
              {/* Main Image */}
              <div className="relative aspect-square bg-gray-100 dark:bg-neutral-800 rounded-xl overflow-hidden">
                <img
                  src={imageUrl}
                  alt={variant.name || variant.code}
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Variant Code */}
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                Code: {variant.code}
              </p>
            </div>

            {/* Right: Details */}
            <div className="flex flex-col">
              {/* Brand */}
              <p className="text-sm text-gray-500 dark:text-gray-400 font-medium mb-2">
                {texture.brand}
              </p>

              {/* Name */}
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                {texture.name}
              </h2>

              {/* Variant Name */}
              {variant.name && variant.name !== variant.code && (
                <p className="text-lg text-gray-700 dark:text-gray-300 mb-3">
                  {variant.name}
                </p>
              )}

              {/* Description */}
              {texture.description && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                    Description
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                    {texture.description}
                  </p>
                </div>
              )}

              {/* Source Link */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                  Source
                </h3>
                <div className="flex items-center space-x-2">
                  <span className="inline-block bg-gray-100 dark:bg-neutral-800 text-gray-700 dark:text-gray-300 text-sm px-3 py-1 rounded-full">
                    {texture.brand}
                  </span>
                  {productUrl && (
                    <a
                      href={productUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 underline flex items-center gap-1"
                    >
                      View on website
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  )}
                </div>
              </div>

              {/* Action Button */}
              <div className="mt-auto">
                {onAddToCanvas && (
                  <button
                    onClick={onAddToCanvas}
                    className={`w-full font-semibold py-3 px-6 rounded-xl transition-colors ${
                      inCanvas
                        ? 'bg-green-600 hover:bg-green-700 text-white'
                        : 'bg-neutral-800 hover:bg-neutral-900 dark:bg-white dark:hover:bg-neutral-100 text-white dark:text-neutral-900'
                    }`}
                  >
                    {inCanvas ? 'On Canvas' : 'Add to Canvas'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TextureDetailModal;
