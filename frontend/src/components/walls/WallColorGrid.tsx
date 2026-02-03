'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { WallColor, WallColorFamily, WALL_COLOR_FAMILY_ORDER, WALL_COLOR_FAMILY_LABELS } from '@/types/wall-colors';
import { wallColorsAPI } from '@/utils/api';
import { WallColorSwatch } from '@/components/wall-colors/WallColorSwatch';
import { WallColorFamilyGroup } from '@/components/wall-colors/WallColorFamilyGroup';

interface WallColorGridProps {
  /** Filter by color families */
  familyFilter?: WallColorFamily[];
  /** Currently selected color */
  selectedColor: WallColor | null;
  /** Callback when color is selected */
  onSelectColor: (color: WallColor) => void;
  /** Whether to show as flat grid (no family grouping) */
  flatGrid?: boolean;
}

/**
 * WallColorGrid Component
 *
 * Displays wall colors in ProductDiscoveryPanel (Panel 2).
 * Shows colors grouped by family with collapsible headers.
 * Supports optional family filtering from Panel 1.
 */
export function WallColorGrid({
  familyFilter = [],
  selectedColor,
  onSelectColor,
  flatGrid = false,
}: WallColorGridProps) {
  const [colors, setColors] = useState<Record<string, WallColor[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedFamily, setExpandedFamily] = useState<WallColorFamily | null>(null);

  // Fetch colors on mount
  useEffect(() => {
    async function fetchColors() {
      try {
        setIsLoading(true);
        setError(null);
        const response = await wallColorsAPI.getGrouped();
        setColors(response.colors);
      } catch (err) {
        console.error('Failed to fetch wall colors:', err);
        setError('Failed to load wall colors');
      } finally {
        setIsLoading(false);
      }
    }

    fetchColors();
  }, []);

  // Filter families based on filter selection
  const visibleFamilies = useMemo(() => {
    if (familyFilter.length === 0) {
      return WALL_COLOR_FAMILY_ORDER;
    }
    return WALL_COLOR_FAMILY_ORDER.filter((family) => familyFilter.includes(family));
  }, [familyFilter]);

  // Toggle family expansion (accordion behavior)
  const handleToggleExpand = useCallback((family: WallColorFamily) => {
    setExpandedFamily((current) => (current === family ? null : family));
  }, []);

  // Flat grid of all visible colors
  const allVisibleColors = useMemo(() => {
    return visibleFamilies.flatMap((family) => colors[family] || []);
  }, [visibleFamilies, colors]);

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
            Loading colors...
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

  if (flatGrid) {
    // Render as flat grid without family grouping
    return (
      <div className="p-3">
        <div className="grid grid-cols-6 sm:grid-cols-8 gap-1.5">
          {allVisibleColors.map((color) => (
            <WallColorSwatch
              key={color.id}
              color={color}
              isSelected={selectedColor?.id === color.id}
              onClick={() => onSelectColor(color)}
              size="md"
            />
          ))}
        </div>
        {allVisibleColors.length === 0 && (
          <p className="text-sm text-neutral-500 dark:text-neutral-400 text-center py-4">
            No colors match the selected filters
          </p>
        )}
      </div>
    );
  }

  // Render as grouped by family with collapsible headers
  return (
    <div className="px-3 py-2">
      {visibleFamilies.map((family) => (
        <WallColorFamilyGroup
          key={family}
          family={family}
          colors={colors[family] || []}
          selectedColorId={selectedColor?.id ?? null}
          onSelectColor={onSelectColor}
          isExpanded={expandedFamily === family}
          onToggleExpand={() => handleToggleExpand(family)}
        />
      ))}

      {visibleFamilies.length === 0 && (
        <p className="text-sm text-neutral-500 dark:text-neutral-400 text-center py-4">
          No color families selected
        </p>
      )}
    </div>
  );
}
