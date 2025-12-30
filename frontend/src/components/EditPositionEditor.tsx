'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { DraggableFurnitureCanvas, FurniturePosition } from './DraggableFurnitureCanvas';
import { furniturePositionAPI } from '@/utils/api';

interface Product {
  id: number | string;
  name: string;
  price?: number;
  image_url?: string;
  images?: Array<{
    original_url?: string;
    medium_url?: string;
    large_url?: string;
    is_primary?: boolean;
  }>;
  quantity?: number;
}

interface EditPositionEditorProps {
  visualizationImage: string;
  products: Product[];
  sessionId: string;
  containerWidth?: number;
  containerHeight?: number;
  onCancel: () => void;
  onRevisualize: (positions: FurniturePosition[]) => Promise<void>;
  onPositionsChange?: (positions: FurniturePosition[]) => void;
}

export const EditPositionEditor: React.FC<EditPositionEditorProps> = ({
  visualizationImage,
  products,
  sessionId,
  containerWidth = 800,
  containerHeight = 600,
  onCancel,
  onRevisualize,
  onPositionsChange,
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState('Extracting furniture layers...');
  const [error, setError] = useState<string | null>(null);
  const [baseRoomLayer, setBaseRoomLayer] = useState<string | null>(null);
  const [furniturePositions, setFurniturePositions] = useState<FurniturePosition[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isRevisualizing, setIsRevisualizing] = useState(false);

  // Load layers on mount
  useEffect(() => {
    loadLayers();
  }, []);

  const loadLayers = async () => {
    setIsLoading(true);
    setError(null);
    setLoadingMessage('Detecting furniture positions...');

    try {
      // Prepare products data for API
      const productsForApi = products.map(p => ({
        id: String(p.id),
        name: p.name,
      }));

      console.log('[EditPositionEditor] Extracting layers for products:', productsForApi);

      // Call the extract layers API
      const result = await furniturePositionAPI.extractLayers(
        sessionId,
        visualizationImage,
        productsForApi
      );

      console.log('[EditPositionEditor] Extraction result:', {
        hasCleanBackground: !!result.clean_background,
        layersCount: result.layers?.length || 0,
      });

      // Set clean background
      setBaseRoomLayer(result.clean_background || visualizationImage);

      // Convert API layers to FurniturePosition format
      const layers = result.layers || [];
      const positions: FurniturePosition[] = layers.map((layer: any) => ({
        productId: String(layer.product_id),
        x: layer.center?.x || 0.5,
        y: layer.center?.y || 0.5,
        width: layer.bounding_box?.width || 0.15,
        height: layer.bounding_box?.height || 0.15,
        label: layer.product_name || 'Product',
        layerImage: layer.layer_image || null,
      }));

      // If no layers detected, fall back to default grid layout
      if (positions.length === 0) {
        console.log('[EditPositionEditor] No layers detected, using default grid layout');
        const defaultPositions = createDefaultPositions(products);
        setFurniturePositions(defaultPositions);
      } else {
        setFurniturePositions(positions);
      }

      setLoadingMessage('');
    } catch (err: any) {
      console.error('[EditPositionEditor] Error extracting layers:', err);
      setError(err.message || 'Failed to extract layers');

      // Fall back to default positions on error
      const defaultPositions = createDefaultPositions(products);
      setFurniturePositions(defaultPositions);
      setBaseRoomLayer(visualizationImage);
    } finally {
      setIsLoading(false);
    }
  };

  // Create default grid positions when layer extraction fails
  const createDefaultPositions = (prods: Product[]): FurniturePosition[] => {
    // Expand products by quantity
    const expandedProducts: Array<{ product: Product; instanceIndex: number; totalInstances: number }> = [];
    prods.forEach(product => {
      const qty = product.quantity || 1;
      for (let i = 1; i <= qty; i++) {
        expandedProducts.push({
          product,
          instanceIndex: i,
          totalInstances: qty
        });
      }
    });

    const numProducts = expandedProducts.length;
    const cols = Math.ceil(Math.sqrt(numProducts));

    return expandedProducts.map((item, index) => {
      const row = Math.floor(index / cols);
      const col = index % cols;
      const spacingX = 0.6 / (cols + 1);
      const spacingY = 0.6 / (Math.ceil(numProducts / cols) + 1);

      const instanceId = item.totalInstances > 1
        ? `${item.product.id}-${item.instanceIndex}`
        : String(item.product.id);

      const label = item.totalInstances > 1
        ? `${item.product.name} (${item.instanceIndex} of ${item.totalInstances})`
        : item.product.name;

      return {
        productId: instanceId,
        x: 0.2 + (col + 1) * spacingX,
        y: 0.2 + (row + 1) * spacingY,
        label: label,
        width: 0.15,
        height: 0.15,
      };
    });
  };

  const handlePositionsChange = useCallback((newPositions: FurniturePosition[]) => {
    setFurniturePositions(newPositions);
    setHasUnsavedChanges(true);
    onPositionsChange?.(newPositions);
  }, [onPositionsChange]);

  const handleCancel = () => {
    if (hasUnsavedChanges) {
      const confirmExit = window.confirm('You have unsaved position changes. Exit anyway?');
      if (!confirmExit) return;
    }
    onCancel();
  };

  const handleRevisualize = async () => {
    setIsRevisualizing(true);
    try {
      await onRevisualize(furniturePositions);
    } catch (err: any) {
      console.error('[EditPositionEditor] Revisualize error:', err);
      alert('Failed to re-visualize. Please try again.');
    } finally {
      setIsRevisualizing(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-neutral-100 dark:bg-neutral-800 rounded-lg p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-500 border-t-transparent mb-4"></div>
        <p className="text-neutral-600 dark:text-neutral-300 text-center">
          {loadingMessage}
        </p>
        <p className="text-neutral-400 dark:text-neutral-500 text-sm mt-2">
          This may take a few seconds...
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Error banner */}
      {error && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-4 py-2 mb-3">
          <p className="text-amber-700 dark:text-amber-300 text-sm">
            <span className="font-medium">Note:</span> Using simplified edit mode. {error}
          </p>
        </div>
      )}

      {/* Canvas */}
      <div className="flex-1 relative">
        <DraggableFurnitureCanvas
          visualizationImage={visualizationImage}
          baseRoomLayer={baseRoomLayer}
          furniturePositions={furniturePositions}
          onPositionsChange={handlePositionsChange}
          products={products.map(p => ({
            id: String(p.id),
            name: p.name,
            price: p.price || 0,
            image_url: p.image_url,
            images: p.images,
          }))}
          containerWidth={containerWidth}
          containerHeight={containerHeight}
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center gap-2">
          {hasUnsavedChanges && (
            <span className="text-amber-600 dark:text-amber-400 text-sm">
              • Unsaved changes
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleCancel}
            disabled={isRevisualizing}
            className="px-4 py-2 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleRevisualize}
            disabled={isRevisualizing || !hasUnsavedChanges}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isRevisualizing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                Re-visualizing...
              </>
            ) : (
              'Re-visualize with New Positions'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EditPositionEditor;
