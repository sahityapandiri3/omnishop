'use client';

import { PlusIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { WallColor } from '@/types/wall-colors';
import {
  WallTextureWithVariants,
  WallTextureVariant,
  TEXTURE_TYPE_LABELS,
} from '@/types/wall-textures';

interface WallSelectionCardProps {
  /** Selected wall color (if in color mode) */
  selectedColor?: WallColor | null;
  /** Selected texture variant (if in texture mode) */
  selectedVariant?: WallTextureVariant | null;
  /** Parent texture of selected variant */
  selectedTexture?: WallTextureWithVariants | null;
  /** Whether the selection is already on canvas */
  isOnCanvas?: boolean;
  /** Callback to add selection to canvas */
  onAddToCanvas: () => void;
  /** Callback to remove from canvas */
  onRemoveFromCanvas?: () => void;
  /** Callback to clear selection */
  onClearSelection?: () => void;
}

/**
 * WallSelectionCard Component
 *
 * Unified selection card for both colors and textures.
 * Shows preview, details, and add-to-canvas action.
 * Displayed as sticky footer in Panel 2.
 */
export function WallSelectionCard({
  selectedColor,
  selectedVariant,
  selectedTexture,
  isOnCanvas = false,
  onAddToCanvas,
  onRemoveFromCanvas,
  onClearSelection,
}: WallSelectionCardProps) {
  // Determine what's selected
  const hasColorSelection = !!selectedColor;
  const hasTextureSelection = !!selectedVariant && !!selectedTexture;
  const hasSelection = hasColorSelection || hasTextureSelection;

  if (!hasSelection) {
    return null;
  }

  // Color selection card
  if (hasColorSelection && selectedColor) {
    return (
      <div className="flex items-center gap-3">
        {/* Color swatch */}
        <div
          className="w-14 h-14 rounded-lg border border-neutral-200 dark:border-neutral-700 flex-shrink-0"
          style={{ backgroundColor: selectedColor.hex_value }}
        />

        {/* Color info */}
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-neutral-900 dark:text-white text-sm truncate">
            {selectedColor.name}
          </h4>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            {selectedColor.code} • {selectedColor.hex_value}
          </p>
          <p className="text-xs text-neutral-400 dark:text-neutral-500">
            {selectedColor.brand}
          </p>
        </div>

        {/* Action button */}
        {isOnCanvas ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
              <CheckIcon className="w-3 h-3" />
              On Canvas
            </span>
            {onRemoveFromCanvas && (
              <button
                onClick={onRemoveFromCanvas}
                className="p-1.5 text-neutral-400 hover:text-red-500 transition-colors"
                title="Remove from canvas"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={onAddToCanvas}
            className="flex items-center gap-1.5 px-3 py-2 bg-neutral-900 hover:bg-neutral-800 text-white dark:bg-white dark:hover:bg-neutral-100 dark:text-neutral-900 text-sm font-medium rounded-lg transition-colors"
          >
            <PlusIcon className="w-4 h-4" />
            Add to Canvas
          </button>
        )}
      </div>
    );
  }

  // Texture selection card
  if (hasTextureSelection && selectedVariant && selectedTexture) {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const imageUrl = selectedVariant.image_data
      ? (selectedVariant.image_data.startsWith('data:')
        ? selectedVariant.image_data
        : `data:image/jpeg;base64,${selectedVariant.image_data}`)
      : `${apiBase}/api/wall-textures/variant/${selectedVariant.id}/image`;

    return (
      <div className="flex items-center gap-3">
        {/* Texture preview */}
        <div className="w-14 h-14 rounded-lg overflow-hidden border border-neutral-200 dark:border-neutral-700 flex-shrink-0">
          <img
            src={imageUrl}
            alt={selectedTexture.name}
            className="w-full h-full object-cover"
          />
        </div>

        {/* Texture info */}
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-neutral-900 dark:text-white text-sm truncate">
            {selectedTexture.name}
          </h4>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">
            {selectedVariant.name || selectedVariant.code}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            {selectedTexture.texture_type && (
              <span className="text-xs text-neutral-400">
                {TEXTURE_TYPE_LABELS[selectedTexture.texture_type]}
              </span>
            )}
            {selectedTexture.collection && (
              <span className="text-xs text-neutral-400">
                • {selectedTexture.collection}
              </span>
            )}
          </div>
        </div>

        {/* Action button */}
        {isOnCanvas ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
              <CheckIcon className="w-3 h-3" />
              On Canvas
            </span>
            {onRemoveFromCanvas && (
              <button
                onClick={onRemoveFromCanvas}
                className="p-1.5 text-neutral-400 hover:text-red-500 transition-colors"
                title="Remove from canvas"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={onAddToCanvas}
            className="flex items-center gap-1.5 px-3 py-2 bg-neutral-900 hover:bg-neutral-800 text-white dark:bg-white dark:hover:bg-neutral-100 dark:text-neutral-900 text-sm font-medium rounded-lg transition-colors"
          >
            <PlusIcon className="w-4 h-4" />
            Add to Canvas
          </button>
        )}
      </div>
    );
  }

  return null;
}
