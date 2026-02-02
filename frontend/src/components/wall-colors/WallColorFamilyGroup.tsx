'use client';

import { useState } from 'react';
import { WallColor, WallColorFamily, WALL_COLOR_FAMILY_LABELS } from '@/types/wall-colors';
import { WallColorSwatch } from './WallColorSwatch';

interface WallColorFamilyGroupProps {
  family: WallColorFamily;
  colors: WallColor[];
  selectedColorId: number | null;
  onSelectColor: (color: WallColor) => void;
  defaultExpanded?: boolean;
}

/**
 * WallColorFamilyGroup Component
 *
 * Collapsible group header with color swatches for one family.
 * Shows family name with color count and expandable swatch grid.
 */
export function WallColorFamilyGroup({
  family,
  colors,
  selectedColorId,
  onSelectColor,
  defaultExpanded = true,
}: WallColorFamilyGroupProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (colors.length === 0) {
    return null;
  }

  return (
    <div className="border-b border-neutral-100 dark:border-neutral-700 last:border-b-0">
      {/* Family Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between py-3 px-1 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-4 h-4 text-neutral-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="font-medium text-sm text-neutral-700 dark:text-neutral-200">
            {WALL_COLOR_FAMILY_LABELS[family]}
          </span>
        </div>
        <span className="text-xs text-neutral-400 dark:text-neutral-500">
          {colors.length} colors
        </span>
      </button>

      {/* Color Swatches Grid */}
      {isExpanded && (
        <div className="pb-3 px-1">
          <div className="grid grid-cols-6 gap-2">
            {colors.map((color) => (
              <WallColorSwatch
                key={color.id}
                color={color}
                isSelected={selectedColorId === color.id}
                onClick={() => onSelectColor(color)}
                size="md"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
