'use client';

import { useState, useCallback } from 'react';
import { WallColor } from '@/types/wall-colors';

interface UseWallColorReturn {
  /** Wall color currently added to canvas (will be applied during visualization) */
  canvasWallColor: WallColor | null;
  /** Currently selected/previewing wall color (before adding to canvas) */
  selectedColor: WallColor | null;
  /** Set selected wall color for preview */
  setSelectedColor: (color: WallColor | null) => void;
  /** Add selected wall color to canvas */
  addToCanvas: (color: WallColor) => void;
  /** Remove wall color from canvas */
  removeFromCanvas: () => void;
  /** Handle color selection (for preview in WallColorPanel) */
  handleSelectColor: (color: WallColor) => void;
  /** Handle add to canvas action (from WallColorPanel) */
  handleAddToCanvas: (color: WallColor) => void;
}

/**
 * Hook for managing wall color selection and canvas state.
 *
 * The flow is:
 * 1. User browses and selects a color (preview)
 * 2. User clicks "Add to Canvas" - color is stored in canvasWallColor
 * 3. User clicks "Visualize Room" - the canvasWallColor is applied to walls
 *
 * Usage in design page:
 * ```tsx
 * const {
 *   canvasWallColor,
 *   selectedColor,
 *   handleSelectColor,
 *   handleAddToCanvas,
 * } = useWallColor();
 *
 * // Pass to ProductSearchPanel:
 * <ProductSearchPanel
 *   enableWallColors={true}
 *   onAddWallColorToCanvas={handleAddToCanvas}
 *   canvasWallColor={canvasWallColor}
 *   selectedWallColor={selectedColor}
 *   onSelectWallColor={handleSelectColor}
 *   ...
 * />
 *
 * // When visualizing, include canvasWallColor in the request
 * ```
 */
export function useWallColor(): UseWallColorReturn {
  const [canvasWallColor, setCanvasWallColor] = useState<WallColor | null>(null);
  const [selectedColor, setSelectedColor] = useState<WallColor | null>(null);

  const addToCanvas = useCallback((color: WallColor) => {
    console.log(`[useWallColor] Adding wall color to canvas: ${color.name} (${color.hex_value})`);
    setCanvasWallColor(color);
    // Keep selected color in sync
    setSelectedColor(color);
  }, []);

  const removeFromCanvas = useCallback(() => {
    console.log('[useWallColor] Removing wall color from canvas');
    setCanvasWallColor(null);
    // Also clear the selected color so the checkmark disappears from the swatch
    setSelectedColor(null);
  }, []);

  const handleSelectColor = useCallback((color: WallColor) => {
    setSelectedColor(color);
  }, []);

  const handleAddToCanvas = useCallback((color: WallColor) => {
    addToCanvas(color);
  }, [addToCanvas]);

  return {
    canvasWallColor,
    selectedColor,
    setSelectedColor,
    addToCanvas,
    removeFromCanvas,
    handleSelectColor,
    handleAddToCanvas,
  };
}
