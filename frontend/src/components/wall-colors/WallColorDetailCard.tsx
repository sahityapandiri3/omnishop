'use client';

import { WallColor, WALL_COLOR_FAMILY_LABELS, isLightColor, getContrastColor } from '@/types/wall-colors';

interface WallColorDetailCardProps {
  color: WallColor;
  onAddToCanvas: () => void;
  /** Whether the color is already added to canvas */
  isAddedToCanvas?: boolean;
}

/**
 * WallColorDetailCard Component
 *
 * Shows selected color details with large preview and "Add to Canvas" button.
 * Displays color name, code, hex value, and family.
 * The actual wall color is applied when user clicks "Visualize Room".
 */
export function WallColorDetailCard({
  color,
  onAddToCanvas,
  isAddedToCanvas = false,
}: WallColorDetailCardProps) {
  const needsBorder = isLightColor(color.hex_value);
  const textColor = getContrastColor(color.hex_value);

  return (
    <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 shadow-sm">
      <div className="flex gap-4">
        {/* Color Preview */}
        <div
          className={`
            w-20 h-20 rounded-lg flex-shrink-0 flex items-center justify-center
            ${needsBorder ? 'border border-neutral-200 dark:border-neutral-600' : ''}
          `}
          style={{ backgroundColor: color.hex_value }}
        >
          {/* Show hex inside the preview box */}
          <span
            className="text-xs font-mono opacity-70"
            style={{ color: textColor }}
          >
            {color.hex_value}
          </span>
        </div>

        {/* Color Info */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-neutral-900 dark:text-white text-lg truncate">
            {color.name}
          </h3>
          <div className="mt-1 space-y-0.5">
            <p className="text-sm text-neutral-600 dark:text-neutral-300">
              Code: <span className="font-mono">{color.code}</span>
            </p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {WALL_COLOR_FAMILY_LABELS[color.family]}
            </p>
            <p className="text-xs text-neutral-400 dark:text-neutral-500">
              {color.brand}
            </p>
          </div>
        </div>
      </div>

      {/* Add to Canvas Button */}
      <button
        onClick={onAddToCanvas}
        disabled={isAddedToCanvas}
        className={`
          mt-4 w-full py-2.5 px-4 rounded-lg font-medium text-sm
          transition-all duration-200
          ${isAddedToCanvas
            ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 cursor-default border border-green-200 dark:border-green-800'
            : 'bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 hover:bg-neutral-800 dark:hover:bg-neutral-200 active:scale-[0.98]'
          }
        `}
      >
        {isAddedToCanvas ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Added to Canvas
          </span>
        ) : (
          'Add to Canvas'
        )}
      </button>

      {/* Info note */}
      <p className="mt-2 text-[10px] text-neutral-400 dark:text-neutral-500 text-center">
        Click "Visualize Room" to apply wall color
      </p>
    </div>
  );
}
