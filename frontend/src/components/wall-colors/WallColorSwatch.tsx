'use client';

import { WallColor, isLightColor } from '@/types/wall-colors';

interface WallColorSwatchProps {
  color: WallColor;
  isSelected: boolean;
  onClick: () => void;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * WallColorSwatch Component
 *
 * Individual color swatch with selection state.
 * Shows color preview with optional checkmark when selected.
 * Hover shows tooltip with color name and code.
 */
export function WallColorSwatch({
  color,
  isSelected,
  onClick,
  size = 'md',
}: WallColorSwatchProps) {
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
  };

  const needsBorder = isLightColor(color.hex_value);

  return (
    <button
      onClick={onClick}
      className={`
        relative rounded-md transition-all duration-150
        ${sizeClasses[size]}
        ${isSelected ? 'ring-2 ring-offset-2 ring-neutral-800 dark:ring-neutral-200' : ''}
        ${needsBorder ? 'border border-neutral-200 dark:border-neutral-600' : ''}
        hover:scale-110 hover:shadow-lg
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-neutral-500
        group
      `}
      style={{ backgroundColor: color.hex_value }}
      title={`${color.name} (${color.code})`}
      aria-label={`Select ${color.name} color`}
      aria-pressed={isSelected}
    >
      {/* Checkmark when selected */}
      {isSelected && (
        <div className="absolute inset-0 flex items-center justify-center">
          <svg
            className={`w-5 h-5 ${isLightColor(color.hex_value) ? 'text-neutral-800' : 'text-white'}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={3}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
      )}

      {/* Tooltip on hover */}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
        <div className="bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-xs px-2 py-1 rounded whitespace-nowrap shadow-lg">
          <div className="font-medium">{color.name}</div>
          <div className="text-neutral-300 dark:text-neutral-600 text-[10px]">{color.code}</div>
        </div>
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-neutral-900 dark:border-t-neutral-100" />
      </div>
    </button>
  );
}
