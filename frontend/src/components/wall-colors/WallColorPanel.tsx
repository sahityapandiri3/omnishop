'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  WallColor,
  WallColorFamily,
  WallColorsGroupedResponse,
  WALL_COLOR_FAMILY_ORDER,
} from '@/types/wall-colors';
import { WallColorFamilyGroup } from './WallColorFamilyGroup';
import { WallColorDetailCard } from './WallColorDetailCard';
import { wallColorsAPI } from '@/utils/api';

interface WallColorPanelProps {
  /** Callback when user clicks "Add to Canvas" */
  onAddToCanvas: (color: WallColor) => void;
  /** The wall color currently added to canvas (if any) */
  canvasWallColor?: WallColor | null;
  /** Optional: currently selected/previewing color from parent state */
  selectedColor?: WallColor | null;
  /** Optional: callback when color is selected (for preview) */
  onSelectColor?: (color: WallColor) => void;
  /** Whether to show the header (default: true) */
  showHeader?: boolean;
}

/**
 * WallColorPanel Component
 *
 * Main wall color selection panel with:
 * - Scrollable list of colors grouped by family
 * - Collapsible family headers
 * - Color swatches in grid layout
 * - Sticky detail card at bottom when color is selected
 * - "Apply to Walls" action button
 */
export function WallColorPanel({
  onAddToCanvas,
  canvasWallColor,
  selectedColor: externalSelectedColor,
  onSelectColor: externalOnSelectColor,
  showHeader = true,
}: WallColorPanelProps) {
  const [colors, setColors] = useState<Record<string, WallColor[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [internalSelectedColor, setInternalSelectedColor] = useState<WallColor | null>(null);
  // Track which family is expanded (accordion behavior - only one at a time)
  const [expandedFamily, setExpandedFamily] = useState<WallColorFamily | null>(
    WALL_COLOR_FAMILY_ORDER[0] // Default to first family expanded
  );

  // Use external state if provided, otherwise use internal state
  const selectedColor = externalSelectedColor !== undefined ? externalSelectedColor : internalSelectedColor;
  const handleSelectColor = (color: WallColor) => {
    if (externalOnSelectColor) {
      externalOnSelectColor(color);
    } else {
      setInternalSelectedColor(color);
    }
  };

  // Toggle family expansion (accordion behavior - clicking expands that family, collapses others)
  const handleToggleExpand = useCallback((family: WallColorFamily) => {
    setExpandedFamily((current) => (current === family ? null : family));
  }, []);

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
        setError('Failed to load wall colors. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }

    fetchColors();
  }, []);

  const handleAddToCanvas = () => {
    if (selectedColor) {
      onAddToCanvas(selectedColor);
    }
  };

  // Check if the currently selected color is already added to canvas
  const isSelectedColorOnCanvas = selectedColor && canvasWallColor && selectedColor.id === canvasWallColor.id;

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center">
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
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-red-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-3 text-xs text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200 underline"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header - optional */}
      {showHeader && (
        <div className="flex-shrink-0 px-4 py-3 border-b border-neutral-200 dark:border-neutral-700">
          <h2 className="font-semibold text-neutral-900 dark:text-white">
            Wall Colors
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Asian Paints Collection
          </p>
        </div>
      )}

      {/* Scrollable Color List */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {WALL_COLOR_FAMILY_ORDER.map((family) => (
          <WallColorFamilyGroup
            key={family}
            family={family}
            colors={colors[family] || []}
            selectedColorId={selectedColor?.id ?? null}
            onSelectColor={handleSelectColor}
            isExpanded={expandedFamily === family}
            onToggleExpand={() => handleToggleExpand(family)}
          />
        ))}

        {/* Empty state if no colors */}
        {Object.values(colors).flat().length === 0 && (
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-neutral-500 dark:text-neutral-400">
              No colors available
            </p>
          </div>
        )}
      </div>

      {/* Sticky Detail Card at Bottom */}
      {selectedColor && (
        <div className="flex-shrink-0 border-t border-neutral-200 dark:border-neutral-700 p-3 bg-neutral-50 dark:bg-neutral-800/50">
          <WallColorDetailCard
            color={selectedColor}
            onAddToCanvas={handleAddToCanvas}
            isAddedToCanvas={!!isSelectedColorOnCanvas}
          />
        </div>
      )}
    </div>
  );
}
