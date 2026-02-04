'use client';

import { FloorTile } from '@/types/floor-tiles';

interface FloorTileDetailModalProps {
  tile: FloorTile;
  isOpen: boolean;
  onClose: () => void;
  onAddToCanvas?: () => void;
  inCanvas?: boolean;
}

/**
 * FloorTileDetailModal Component
 *
 * Shows detailed view of a floor tile including:
 * - Large tile image
 * - Tile name, vendor, product code
 * - Properties: size, finish, look, color, material
 * - Description
 * - Link to product website
 * - Add to Canvas button
 *
 * Mirrors TextureDetailModal layout (2-column grid, same close button, same action button).
 */
export function FloorTileDetailModal({
  tile,
  isOpen,
  onClose,
  onAddToCanvas,
  inCanvas = false,
}: FloorTileDetailModalProps) {
  if (!isOpen) return null;

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const imageUrl = tile.image_data
    ? (tile.image_data.startsWith('data:')
      ? tile.image_data
      : `data:image/jpeg;base64,${tile.image_data}`)
    : tile.image_url || tile.swatch_url || `${apiBase}/api/floor-tiles/${tile.id}/image`;

  const properties = [
    { label: 'Size', value: tile.size },
    { label: 'Finish', value: tile.finish },
    { label: 'Look', value: tile.look },
    { label: 'Color', value: tile.color },
    { label: 'Material', value: tile.material },
  ].filter((p) => p.value);

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
            {/* Left: Tile Image */}
            <div>
              <div className="relative aspect-square bg-gray-100 dark:bg-neutral-800 rounded-xl overflow-hidden">
                <img
                  src={imageUrl}
                  alt={tile.name}
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Product Code */}
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                Code: {tile.product_code}
              </p>
            </div>

            {/* Right: Details */}
            <div className="flex flex-col">
              {/* Vendor */}
              <p className="text-sm text-gray-500 dark:text-gray-400 font-medium mb-2">
                {tile.vendor}
              </p>

              {/* Name */}
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                {tile.name}
              </h2>

              {/* Properties */}
              {properties.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                    Properties
                  </h3>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                    {properties.map((p) => (
                      <div key={p.label} className="flex items-baseline gap-1.5">
                        <span className="text-xs text-gray-500 dark:text-gray-400">{p.label}:</span>
                        <span className="text-sm text-gray-800 dark:text-gray-200">{p.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Description */}
              {tile.description && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                    Description
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                    {tile.description}
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
                    {tile.vendor}
                  </span>
                  {tile.product_url && (
                    <a
                      href={tile.product_url}
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

export default FloorTileDetailModal;
