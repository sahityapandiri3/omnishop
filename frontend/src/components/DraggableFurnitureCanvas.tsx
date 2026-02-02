'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Rect, Transformer, Group, Text, Circle } from 'react-konva';
import type Konva from 'konva';
import type { KonvaEventObject } from 'konva/lib/Node';
import useImage from 'use-image';
import { furniturePositionAPI } from '@/utils/api';

/**
 * Magic Grab Layer - represents a segmented object from SAM
 */
export interface MagicGrabLayer {
  id: string;
  productId?: string | null;
  productName?: string;
  cutout: string;  // Base64 PNG with transparency
  x: number;       // Normalized position (0-1)
  y: number;
  width: number;   // Normalized width
  height: number;  // Normalized height
  scale: number;
  rotation?: number;
  zIndex?: number;
}

/**
 * Legacy interface for backward compatibility
 */
export interface FurniturePosition {
  productId: string;
  x: number;
  y: number;
  label: string;
  width?: number;
  height?: number;
  layerImage?: string;
  fromX?: number;
  fromY?: number;
}

interface Product {
  id: string;
  name: string;
  price: number;
  quantity?: number;
}

// Product info for matching
interface CuratedProduct {
  id: number;
  name: string;
  image_url?: string;
}

// Pending move data for Re-visualize button
export interface PendingMoveData {
  originalImage: string;
  mask: string;
  cutout: string;
  originalPosition: { x: number; y: number };
  newPosition: { x: number; y: number };
  scale: number;
  inpaintedBackground?: string;
  matchedProductId?: number | null;
}

interface DraggableFurnitureCanvasProps {
  // Legacy props (for backward compatibility)
  visualizationImage?: string;
  baseRoomLayer?: string | null;  // Legacy prop - not used but kept for compatibility
  furnitureLayers?: any[];  // Legacy prop - not used but kept for compatibility
  furniturePositions?: FurniturePosition[];
  onPositionsChange?: (positions: FurniturePosition[]) => void;
  products?: Product[];

  // Magic Grab props (new)
  background?: string;  // Clean background image (base64)
  layers?: MagicGrabLayer[];  // Extracted object layers
  onLayersChange?: (layers: MagicGrabLayer[]) => void;

  // Click-to-select props
  sessionId?: string;  // Required for click-to-select mode
  onFinalImage?: (image: string) => void;  // Called with final image after Done
  onPendingMoveChange?: (hasPending: boolean, moveData?: PendingMoveData) => void;  // Called when pending move changes
  curatedProducts?: CuratedProduct[];  // Products in visualization for matching
  curatedLookId?: number;  // For curated looks cache optimization

  // Common props
  containerWidth?: number;
  containerHeight?: number;
  mode?: 'legacy' | 'magic-grab' | 'click-to-select';
}

/**
 * Background image component - loads and displays the clean room background
 * Shows the FULL image (fit mode) - same view as normal display
 */
interface BackgroundImageProps {
  src: string;
  containerWidth: number;
  containerHeight: number;
  onDimensionsCalculated?: (dims: { displayWidth: number; displayHeight: number; offsetX: number; offsetY: number; scale: number }) => void;
}

const BackgroundImage: React.FC<BackgroundImageProps> = ({ src, containerWidth, containerHeight, onDimensionsCalculated }) => {
  const [image] = useImage(src);
  const prevDimensionsRef = React.useRef<{ displayWidth: number; displayHeight: number; offsetX: number; offsetY: number; scale: number } | null>(null);

  // Calculate dimensions - show the FULL image (fit mode)
  const dimensions = React.useMemo(() => {
    if (!image) return { displayWidth: containerWidth, displayHeight: containerHeight, offsetX: 0, offsetY: 0, scale: 1 };

    const naturalWidth = image.naturalWidth || image.width;
    const naturalHeight = image.naturalHeight || image.height;

    // Scale to FIT the container - show entire image
    const scaleX = containerWidth / naturalWidth;
    const scaleY = containerHeight / naturalHeight;
    const scale = Math.min(scaleX, scaleY);

    const displayWidth = naturalWidth * scale;
    const displayHeight = naturalHeight * scale;

    // Center the image within container
    const offsetX = (containerWidth - displayWidth) / 2;
    const offsetY = (containerHeight - displayHeight) / 2;

    return { displayWidth, displayHeight, offsetX, offsetY, scale };
  }, [image, containerWidth, containerHeight]);

  // Notify parent of calculated dimensions - only when values actually change
  React.useEffect(() => {
    if (image && onDimensionsCalculated) {
      const prev = prevDimensionsRef.current;
      // Only call if values actually changed
      if (!prev ||
          prev.displayWidth !== dimensions.displayWidth ||
          prev.displayHeight !== dimensions.displayHeight ||
          prev.offsetX !== dimensions.offsetX ||
          prev.offsetY !== dimensions.offsetY ||
          prev.scale !== dimensions.scale) {
        prevDimensionsRef.current = dimensions;
        onDimensionsCalculated(dimensions);
      }
    }
  }, [image, dimensions, onDimensionsCalculated]);

  if (!image) return null;

  return (
    <KonvaImage
      image={image}
      x={dimensions.offsetX}
      y={dimensions.offsetY}
      width={dimensions.displayWidth}
      height={dimensions.displayHeight}
    />
  );
};

/**
 * Draggable layer component - represents a single draggable furniture object
 */
interface DraggableLayerProps {
  layer: MagicGrabLayer;
  stageWidth: number;
  stageHeight: number;
  isSelected: boolean;
  onSelect: () => void;
  onDragEnd: (newPos: { x: number; y: number }) => void;
  onTransformEnd?: (newScale: number, newRotation: number) => void;
}

const DraggableLayer: React.FC<DraggableLayerProps> = ({
  layer,
  stageWidth,
  stageHeight,
  isSelected,
  onSelect,
  onDragEnd,
  onTransformEnd,
}) => {
  const [image] = useImage(layer.cutout);
  const shapeRef = useRef<any>(null);
  const transformerRef = useRef<any>(null);

  // Calculate pixel dimensions
  const pixelX = layer.x * stageWidth;
  const pixelY = layer.y * stageHeight;
  const pixelWidth = layer.width * stageWidth;
  const pixelHeight = layer.height * stageHeight;

  // Attach transformer when selected
  useEffect(() => {
    if (isSelected && transformerRef.current && shapeRef.current) {
      transformerRef.current.nodes([shapeRef.current]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [isSelected]);

  if (!image) return null;

  return (
    <>
      <Group
        ref={shapeRef}
        x={pixelX}
        y={pixelY}
        draggable
        onClick={onSelect}
        onTap={onSelect}
        onDragStart={onSelect}
        onDragEnd={(e: KonvaEventObject<DragEvent>) => {
          const node = e.target;
          onDragEnd({
            x: node.x() / stageWidth,
            y: node.y() / stageHeight,
          });
        }}
        onTransformEnd={(e: KonvaEventObject<Event>) => {
          const node = shapeRef.current;
          if (node && onTransformEnd) {
            const scaleX = node.scaleX();
            const rotation = node.rotation();
            // Reset scale to 1 and adjust size instead
            node.scaleX(1);
            node.scaleY(1);
            onTransformEnd(scaleX * layer.scale, rotation);
          }
        }}
      >
        <KonvaImage
          image={image}
          width={pixelWidth * layer.scale}
          height={pixelHeight * layer.scale}
          offsetX={(pixelWidth * layer.scale) / 2}
          offsetY={(pixelHeight * layer.scale) / 2}
          rotation={layer.rotation || 0}
        />

        {/* Selection indicator */}
        {isSelected && (
          <Rect
            x={-(pixelWidth * layer.scale) / 2 - 2}
            y={-(pixelHeight * layer.scale) / 2 - 2}
            width={pixelWidth * layer.scale + 4}
            height={pixelHeight * layer.scale + 4}
            stroke="#3B82F6"
            strokeWidth={2}
            dash={[5, 5]}
            listening={false}
          />
        )}
      </Group>

      {/* Transformer for scaling (when selected) */}
      {isSelected && (
        <Transformer
          ref={transformerRef}
          boundBoxFunc={(oldBox, newBox) => {
            // Limit minimum size
            if (newBox.width < 20 || newBox.height < 20) {
              return oldBox;
            }
            return newBox;
          }}
          enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right']}
          rotateEnabled={false}
        />
      )}
    </>
  );
};

/**
 * Draggable layer component with offset support for aspect-ratio-preserved backgrounds
 */
interface DraggableLayerWithOffsetProps {
  layer: MagicGrabLayer;
  imageDimensions: {
    displayWidth: number;
    displayHeight: number;
    offsetX: number;
    offsetY: number;
    scale: number;
  };
  isSelected: boolean;
  onSelect: () => void;
  onDragEnd: (newPos: { x: number; y: number }) => void;
  onTransformEnd?: (newScale: number, newRotation: number) => void;
}

const DraggableLayerWithOffset: React.FC<DraggableLayerWithOffsetProps> = ({
  layer,
  imageDimensions,
  isSelected,
  onSelect,
  onDragEnd,
  onTransformEnd,
}) => {
  const [image] = useImage(layer.cutout);
  const shapeRef = useRef<any>(null);
  const transformerRef = useRef<any>(null);

  // Calculate pixel dimensions relative to the actual displayed image
  const pixelX = imageDimensions.offsetX + layer.x * imageDimensions.displayWidth;
  const pixelY = imageDimensions.offsetY + layer.y * imageDimensions.displayHeight;
  const pixelWidth = layer.width * imageDimensions.displayWidth;
  const pixelHeight = layer.height * imageDimensions.displayHeight;

  // Attach transformer when selected
  useEffect(() => {
    if (isSelected && transformerRef.current && shapeRef.current) {
      transformerRef.current.nodes([shapeRef.current]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [isSelected]);

  if (!image) return null;

  return (
    <>
      <Group
        ref={shapeRef}
        x={pixelX}
        y={pixelY}
        draggable
        onClick={onSelect}
        onTap={onSelect}
        onDragStart={onSelect}
        onDragEnd={(e: KonvaEventObject<DragEvent>) => {
          const node = e.target;
          // Convert back to normalized coordinates relative to the image
          const newX = (node.x() - imageDimensions.offsetX) / imageDimensions.displayWidth;
          const newY = (node.y() - imageDimensions.offsetY) / imageDimensions.displayHeight;
          console.log('[DraggableLayer] Drag end - node position:', node.x(), node.y());
          console.log('[DraggableLayer] Normalized position:', { x: newX, y: newY });
          onDragEnd({ x: newX, y: newY });
        }}
        onTransformEnd={(e: KonvaEventObject<Event>) => {
          const node = shapeRef.current;
          if (node && onTransformEnd) {
            const scaleX = node.scaleX();
            const rotation = node.rotation();
            node.scaleX(1);
            node.scaleY(1);
            onTransformEnd(scaleX * layer.scale, rotation);
          }
        }}
      >
        <KonvaImage
          image={image}
          width={pixelWidth * layer.scale}
          height={pixelHeight * layer.scale}
          offsetX={(pixelWidth * layer.scale) / 2}
          offsetY={(pixelHeight * layer.scale) / 2}
          rotation={layer.rotation || 0}
        />

        {/* Selection indicator */}
        {isSelected && (
          <Rect
            x={-(pixelWidth * layer.scale) / 2 - 2}
            y={-(pixelHeight * layer.scale) / 2 - 2}
            width={pixelWidth * layer.scale + 4}
            height={pixelHeight * layer.scale + 4}
            stroke="#3B82F6"
            strokeWidth={2}
            dash={[5, 5]}
            listening={false}
          />
        )}
      </Group>

      {/* Transformer for scaling (when selected) */}
      {isSelected && (
        <Transformer
          ref={transformerRef}
          boundBoxFunc={(oldBox, newBox) => {
            if (newBox.width < 20 || newBox.height < 20) {
              return oldBox;
            }
            return newBox;
          }}
          enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right']}
          rotateEnabled={false}
        />
      )}
    </>
  );
};

/**
 * Magic Grab Canvas - Canva-style drag-and-drop furniture editing
 *
 * Features:
 * - Click any object to select it
 * - Drag objects to reposition them
 * - Corner handles for scaling
 * - Real-time updates (no API calls during interaction)
 *
 * Modes:
 * - 'legacy': Original from/to click mode
 * - 'magic-grab': Pre-extracted layers for dragging
 * - 'click-to-select': Click to select, Drag button creates layer, Done finalizes
 */
export const DraggableFurnitureCanvas: React.FC<DraggableFurnitureCanvasProps> = ({
  // Legacy props
  visualizationImage,
  furniturePositions = [],
  onPositionsChange,
  products = [],

  // Magic Grab props
  background,
  layers: initialLayers,
  onLayersChange,

  // Click-to-select props
  sessionId,
  onFinalImage,
  onPendingMoveChange,
  curatedProducts,
  curatedLookId,

  // Common props
  containerWidth = 800,
  containerHeight = 600,
  mode = 'magic-grab',
}) => {
  // Magic Grab state
  const [layers, setLayers] = useState<MagicGrabLayer[]>(initialLayers || []);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);

  // Legacy state (for backward compatibility)
  const [positions, setPositions] = useState<FurniturePosition[]>(furniturePositions);
  const [selectedProduct, setSelectedProduct] = useState<string>('');
  const [clickStep, setClickStep] = useState<'select' | 'from' | 'to'>('select');
  const [tempFrom, setTempFrom] = useState<{ x: number; y: number } | null>(null);

  // Click-to-select state
  const [clickSelectPhase, setClickSelectPhase] = useState<'idle' | 'selected' | 'segmenting' | 'dragging' | 'finalizing'>('idle');
  const [clickPoint, setClickPoint] = useState<{ x: number; y: number } | null>(null);
  const [activeLayer, setActiveLayer] = useState<MagicGrabLayer | null>(null);
  const [originalImage, setOriginalImage] = useState<string | null>(null);
  const [inpaintedBackground, setInpaintedBackground] = useState<string | null>(null);  // Clean background with object removed
  const [activeMask, setActiveMask] = useState<string | null>(null);
  const [matchedProductId, setMatchedProductId] = useState<number | null>(null);  // Matched product from DB
  const [originalPosition, setOriginalPosition] = useState<{ x: number; y: number } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Image dimension state for aspect ratio handling
  const [imageDimensions, setImageDimensions] = useState<{
    displayWidth: number;
    displayHeight: number;
    offsetX: number;
    offsetY: number;
    scale: number;
  } | null>(null);

  const stageRef = useRef<any>(null);

  // Sync with prop changes
  useEffect(() => {
    if (initialLayers) {
      // Only update if values actually changed (prevent infinite loops from new array references)
      setLayers(prev => {
        if (JSON.stringify(prev) === JSON.stringify(initialLayers)) {
          return prev;
        }
        return initialLayers;
      });
    }
  }, [initialLayers]);

  useEffect(() => {
    // Only update if values actually changed (prevent infinite loops from new array references)
    setPositions(prev => {
      if (JSON.stringify(prev) === JSON.stringify(furniturePositions)) {
        return prev;
      }
      return furniturePositions;
    });
  }, [furniturePositions]);

  // Track previous visualization image to detect changes
  const prevVisualizationImageRef = React.useRef<string | null | undefined>(null);

  // Reset click-to-select state when visualizationImage changes (e.g., after parent calls Re-visualize)
  useEffect(() => {
    if (mode === 'click-to-select' && visualizationImage) {
      const prevImage = prevVisualizationImageRef.current;

      // If the image changed and we were in dragging/finalizing phase, reset state
      if (prevImage && prevImage !== visualizationImage && (clickSelectPhase === 'dragging' || clickSelectPhase === 'finalizing')) {
        console.log('[DraggableCanvas] Visualization image changed, resetting click-to-select state');
        setActiveLayer(null);
        setActiveMask(null);
        setOriginalImage(null);
        setInpaintedBackground(null);
        setMatchedProductId(null);
        setOriginalPosition(null);
        setClickSelectPhase('idle');
        setClickPoint(null);

        // Notify parent that pending move is cleared
        onPendingMoveChange?.(false);
      }

      prevVisualizationImageRef.current = visualizationImage;
    }
  }, [visualizationImage, mode, clickSelectPhase, onPendingMoveChange]);

  // Handle layer selection
  const handleSelectLayer = useCallback((layerId: string) => {
    setSelectedLayerId(layerId);
  }, []);

  // Handle click on empty space (deselect)
  const handleStageClick = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    // Check if we clicked on empty space
    const clickedOnEmpty = e.target === e.target.getStage();
    if (clickedOnEmpty) {
      setSelectedLayerId(null);
    }

    // Legacy mode handling
    if (mode === 'legacy' && selectedProduct && clickStep !== 'select') {
      const stage = e.target.getStage();
      if (!stage) return;

      const pos = stage.getPointerPosition();
      if (!pos) return;

      const x = pos.x / containerWidth;
      const y = pos.y / containerHeight;

      if (clickStep === 'from') {
        setTempFrom({ x, y });
        setClickStep('to');
      } else if (clickStep === 'to' && tempFrom) {
        const product = products.find(p => String(p.id) === selectedProduct);
        const newPosition: FurniturePosition = {
          productId: selectedProduct,
          label: product?.name || 'Product',
          x,
          y,
          fromX: tempFrom.x,
          fromY: tempFrom.y,
        };

        const existingIndex = positions.findIndex(p => p.productId === selectedProduct);
        let updatedPositions;
        if (existingIndex >= 0) {
          updatedPositions = [...positions];
          updatedPositions[existingIndex] = newPosition;
        } else {
          updatedPositions = [...positions, newPosition];
        }

        setPositions(updatedPositions);
        onPositionsChange?.(updatedPositions);

        setSelectedProduct('');
        setClickStep('select');
        setTempFrom(null);
      }
    }
  }, [mode, selectedProduct, clickStep, tempFrom, positions, products, containerWidth, containerHeight, onPositionsChange]);

  // Handle layer position change
  const handleLayerDragEnd = useCallback((layerId: string, newPos: { x: number; y: number }) => {
    setLayers(prevLayers => {
      const updatedLayers = prevLayers.map(layer =>
        layer.id === layerId
          ? { ...layer, x: newPos.x, y: newPos.y }
          : layer
      );
      onLayersChange?.(updatedLayers);
      return updatedLayers;
    });
  }, [onLayersChange]);

  // Handle layer scale change
  const handleLayerTransformEnd = useCallback((layerId: string, newScale: number, newRotation: number) => {
    setLayers(prevLayers => {
      const updatedLayers = prevLayers.map(layer =>
        layer.id === layerId
          ? { ...layer, scale: newScale, rotation: newRotation }
          : layer
      );
      onLayersChange?.(updatedLayers);
      return updatedLayers;
    });
  }, [onLayersChange]);

  // ============================================================================
  // CLICK-TO-SELECT MODE HANDLERS
  // ============================================================================

  // Handle image dimensions being calculated (for aspect ratio preservation)
  const handleDimensionsCalculated = useCallback((dims: {
    displayWidth: number;
    displayHeight: number;
    offsetX: number;
    offsetY: number;
    scale: number;
  }) => {
    // Only update if values actually changed to prevent infinite loops
    setImageDimensions(prev => {
      if (prev &&
          prev.displayWidth === dims.displayWidth &&
          prev.displayHeight === dims.displayHeight &&
          prev.offsetX === dims.offsetX &&
          prev.offsetY === dims.offsetY &&
          prev.scale === dims.scale) {
        return prev; // No change, keep same reference
      }
      return dims;
    });
  }, []);

  // Handle click on canvas to select a point
  const handleClickToSelect = useCallback((e: KonvaEventObject<MouseEvent>) => {
    if (mode !== 'click-to-select' || clickSelectPhase === 'segmenting' || clickSelectPhase === 'finalizing') {
      return;
    }

    // If already dragging, clicking on empty space does nothing
    if (clickSelectPhase === 'dragging') {
      const clickedOnEmpty = e.target === e.target.getStage();
      if (clickedOnEmpty) {
        // Don't deselect during dragging - user must click Done or Cancel
        return;
      }
    }

    const stage = e.target.getStage();
    if (!stage) return;

    const pos = stage.getPointerPosition();
    if (!pos) return;

    // DEBUG: Log raw and calculated coordinates
    console.log('[DraggableCanvas] Raw click position:', pos);
    console.log('[DraggableCanvas] imageDimensions:', imageDimensions);
    console.log('[DraggableCanvas] containerWidth:', containerWidth, 'containerHeight:', containerHeight);

    // Calculate normalized coordinates relative to the actual image (accounting for offset and aspect ratio)
    let normalizedX: number;
    let normalizedY: number;

    if (imageDimensions) {
      // Check if click is within the image bounds
      const imgX = pos.x - imageDimensions.offsetX;
      const imgY = pos.y - imageDimensions.offsetY;

      console.log('[DraggableCanvas] imgX:', imgX, 'imgY:', imgY);

      if (imgX < 0 || imgY < 0 || imgX > imageDimensions.displayWidth || imgY > imageDimensions.displayHeight) {
        // Click is outside the image area
        console.log('[DraggableCanvas] Click outside image bounds, ignoring');
        return;
      }

      // Normalize relative to the actual image dimensions
      normalizedX = imgX / imageDimensions.displayWidth;
      normalizedY = imgY / imageDimensions.displayHeight;
      console.log('[DraggableCanvas] Normalized (with dimensions):', normalizedX, normalizedY);
    } else {
      // Fallback to container dimensions
      normalizedX = pos.x / containerWidth;
      normalizedY = pos.y / containerHeight;
      console.log('[DraggableCanvas] Normalized (fallback):', normalizedX, normalizedY);
    }

    // Set the click point and move to selected phase
    console.log('[DraggableCanvas] Setting clickPoint to:', { x: normalizedX, y: normalizedY });
    setClickPoint({ x: normalizedX, y: normalizedY });
    setClickSelectPhase('selected');
    setErrorMessage(null);
  }, [mode, clickSelectPhase, containerWidth, containerHeight, imageDimensions]);

  // Handle "Drag" button click - segment the object
  const handleDragButtonClick = useCallback(async () => {
    if (!clickPoint || !sessionId || !visualizationImage) {
      setErrorMessage('Missing required data for segmentation');
      return;
    }

    setClickSelectPhase('segmenting');
    setErrorMessage(null);

    try {
      // Store original image for finalization
      setOriginalImage(visualizationImage);

      // Call SAM 2 to segment at the click point, passing products for matching
      console.log('[DraggableCanvas] Calling segmentAtPoint with products:', curatedProducts?.length || 0, 'curatedLookId:', curatedLookId);
      const result = await furniturePositionAPI.segmentAtPoint(
        sessionId,
        visualizationImage,
        clickPoint,
        'object',
        curatedProducts,  // Pass products for Gemini to match
        curatedLookId  // Pass curated look ID for cache lookup
      );

      // Create the active layer from result
      const layer: MagicGrabLayer = {
        id: result.layer.id,
        cutout: result.layer.cutout,
        x: result.layer.x,
        y: result.layer.y,
        width: result.layer.width,
        height: result.layer.height,
        scale: 1.0,
      };

      setActiveLayer(layer);
      setActiveMask(result.layer.mask);
      setOriginalPosition({ x: result.layer.x, y: result.layer.y });

      // Store matched product ID from Gemini matching
      if (result.matched_product_id) {
        setMatchedProductId(result.matched_product_id);
        console.log('[DraggableCanvas] Matched product ID:', result.matched_product_id);
      }

      // Store the inpainted background (with object removed) for cleaner dragging experience
      if (result.inpainted_background) {
        setInpaintedBackground(result.inpainted_background);
      }

      setClickSelectPhase('dragging');
    } catch (error: any) {
      console.error('Segmentation failed:', error);
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Failed to segment object');
      setClickSelectPhase('selected');
    }
  }, [clickPoint, sessionId, visualizationImage, curatedProducts]);

  // Handle layer drag in click-to-select mode
  const handleActiveLayerDrag = useCallback((newPos: { x: number; y: number }) => {
    if (activeLayer) {
      setActiveLayer(prev => prev ? { ...prev, x: newPos.x, y: newPos.y } : null);

      // Notify parent of pending move for Re-visualize button
      if (onPendingMoveChange && originalImage && activeMask && originalPosition) {
        onPendingMoveChange(true, {
          originalImage,
          mask: activeMask,
          cutout: activeLayer.cutout,
          originalPosition,
          newPosition: newPos,
          scale: activeLayer.scale,
          inpaintedBackground: inpaintedBackground || undefined,
          matchedProductId: matchedProductId,
        });
      }
    }
  }, [activeLayer, onPendingMoveChange, originalImage, activeMask, originalPosition, inpaintedBackground, matchedProductId]);

  // Handle "Done" button click - finalize the move
  const handleDoneButtonClick = useCallback(async () => {
    if (!activeLayer || !originalImage || !activeMask || !originalPosition || !sessionId) {
      setErrorMessage('Missing required data for finalization');
      return;
    }

    setClickSelectPhase('finalizing');
    setErrorMessage(null);

    try {
      console.log('[DraggableCanvas] Finalizing move:');
      console.log('  Original position:', originalPosition);
      console.log('  New position:', { x: activeLayer.x, y: activeLayer.y });
      console.log('  Scale:', activeLayer.scale);
      console.log('  Layer dimensions:', { width: activeLayer.width, height: activeLayer.height });

      const result = await furniturePositionAPI.finalizeMove(
        sessionId,
        originalImage,
        activeMask,
        activeLayer.cutout,
        originalPosition,
        { x: activeLayer.x, y: activeLayer.y },
        activeLayer.scale,
        inpaintedBackground,  // Pass the inpainted background for better results
        matchedProductId  // Pass matched product ID to fetch clean image from DB
      );

      // Call the callback with the final image
      onFinalImage?.(result.image);

      // Reset state for next selection
      setActiveLayer(null);
      setActiveMask(null);
      setOriginalImage(null);
      setInpaintedBackground(null);
      setMatchedProductId(null);
      setOriginalPosition(null);
      setClickPoint(null);
      setClickSelectPhase('idle');
    } catch (error: any) {
      console.error('Finalization failed:', error);
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Failed to finalize move');
      setClickSelectPhase('dragging');
    }
  }, [activeLayer, originalImage, activeMask, originalPosition, sessionId, onFinalImage, inpaintedBackground, matchedProductId]);

  // Handle "Cancel" button click
  const handleCancelClick = useCallback(() => {
    setClickPoint(null);
    setActiveLayer(null);
    setActiveMask(null);
    setOriginalImage(null);
    setInpaintedBackground(null);
    setMatchedProductId(null);
    setOriginalPosition(null);
    setClickSelectPhase('idle');
    setErrorMessage(null);
    // Notify parent that there's no pending move
    onPendingMoveChange?.(false);
  }, [onPendingMoveChange]);

  // ============================================================================
  // RENDER CLICK-TO-SELECT MODE
  // ============================================================================
  if (mode === 'click-to-select' && visualizationImage) {
    return (
      <div className="relative w-full h-full flex flex-col items-center">
        {/* Loading overlay */}
        {(clickSelectPhase === 'segmenting' || clickSelectPhase === 'finalizing') && (
          <div className="absolute inset-0 bg-black/30 flex items-center justify-center z-50 rounded-lg">
            <div className="bg-white rounded-lg p-4 shadow-lg flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-purple-600 border-t-transparent" />
              <span className="text-gray-700">
                {clickSelectPhase === 'segmenting' ? 'Creating movable layer...' : 'Blending changes...'}
              </span>
            </div>
          </div>
        )}

        {/* Canvas */}
        <div
          className="border-2 border-purple-300 rounded-lg overflow-hidden bg-gray-100"
          style={{ width: containerWidth, height: containerHeight, flexShrink: 0 }}
        >
          <Stage
            width={containerWidth}
            height={containerHeight}
            ref={stageRef}
            onClick={handleClickToSelect}
            onTap={handleClickToSelect}
            style={{
              cursor: clickSelectPhase === 'idle' || clickSelectPhase === 'selected'
                ? 'crosshair'
                : clickSelectPhase === 'dragging'
                  ? 'move'
                  : 'wait'
            }}
          >
            {/* Background: Use inpainted background when dragging (object removed), otherwise original */}
            <Layer>
              <BackgroundImage
                src={clickSelectPhase === 'dragging' && inpaintedBackground ? inpaintedBackground : visualizationImage}
                containerWidth={containerWidth}
                containerHeight={containerHeight}
                onDimensionsCalculated={handleDimensionsCalculated}
              />
            </Layer>

            {/* Click point indicator (when selected but not yet dragging) */}
            {clickPoint && clickSelectPhase === 'selected' && imageDimensions && (
              <Layer>
                <Circle
                  x={imageDimensions.offsetX + clickPoint.x * imageDimensions.displayWidth}
                  y={imageDimensions.offsetY + clickPoint.y * imageDimensions.displayHeight}
                  radius={20}
                  stroke="#8B5CF6"
                  strokeWidth={3}
                  dash={[5, 5]}
                  fill="rgba(139, 92, 246, 0.1)"
                />
                <Circle
                  x={imageDimensions.offsetX + clickPoint.x * imageDimensions.displayWidth}
                  y={imageDimensions.offsetY + clickPoint.y * imageDimensions.displayHeight}
                  radius={4}
                  fill="#8B5CF6"
                />
              </Layer>
            )}

            {/* Draggable layer (when in dragging phase) */}
            {activeLayer && clickSelectPhase === 'dragging' && imageDimensions && (
              <Layer>
                {/* Ghost outline at original position */}
                <Rect
                  x={originalPosition
                    ? imageDimensions.offsetX + originalPosition.x * imageDimensions.displayWidth - (activeLayer.width * imageDimensions.displayWidth * activeLayer.scale) / 2
                    : 0}
                  y={originalPosition
                    ? imageDimensions.offsetY + originalPosition.y * imageDimensions.displayHeight - (activeLayer.height * imageDimensions.displayHeight * activeLayer.scale) / 2
                    : 0}
                  width={activeLayer.width * imageDimensions.displayWidth * activeLayer.scale}
                  height={activeLayer.height * imageDimensions.displayHeight * activeLayer.scale}
                  stroke="#9CA3AF"
                  strokeWidth={1}
                  dash={[4, 4]}
                  opacity={0.5}
                />
                <DraggableLayerWithOffset
                  layer={activeLayer}
                  imageDimensions={imageDimensions}
                  isSelected={true}
                  onSelect={() => {}}
                  onDragEnd={handleActiveLayerDrag}
                  onTransformEnd={(newScale) => {
                    if (activeLayer) {
                      setActiveLayer(prev => prev ? { ...prev, scale: newScale } : null);
                    }
                  }}
                />
              </Layer>
            )}
          </Stage>
        </div>

        {/* Control bar */}
        <div
          className="mt-3 flex items-center justify-between bg-gray-50 rounded-lg p-3 border"
          style={{ width: containerWidth, maxWidth: '100%' }}
        >
          {/* Status/Instructions */}
          <div className="text-sm text-gray-600 flex-1">
            {clickSelectPhase === 'idle' && (
              <span>Click on an object you want to move</span>
            )}
            {clickSelectPhase === 'selected' && (
              <span className="text-purple-600 font-medium">
                Object selected - Click &quot;Drag&quot; to make it movable
              </span>
            )}
            {clickSelectPhase === 'segmenting' && (
              <span className="text-purple-600">Creating movable layer...</span>
            )}
            {clickSelectPhase === 'dragging' && (
              <span className="text-purple-600 font-medium">
                Drag to reposition • Click &quot;Re-visualize&quot; below when done
              </span>
            )}
            {clickSelectPhase === 'finalizing' && (
              <span className="text-purple-600">Blending changes...</span>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {clickSelectPhase === 'selected' && (
              <>
                <button
                  onClick={handleDragButtonClick}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium text-sm"
                >
                  Drag
                </button>
                <button
                  onClick={handleCancelClick}
                  className="px-3 py-2 text-gray-600 hover:text-gray-800 text-sm"
                >
                  Cancel
                </button>
              </>
            )}
            {clickSelectPhase === 'dragging' && (
              <button
                onClick={handleCancelClick}
                className="px-3 py-2 text-gray-600 hover:text-gray-800 text-sm border border-gray-300 rounded-lg"
              >
                Cancel Move
              </button>
            )}
          </div>
        </div>

        {/* Error message */}
        {errorMessage && (
          <div className="mt-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg" style={{ width: containerWidth, maxWidth: '100%' }}>
            {errorMessage}
          </div>
        )}
      </div>
    );
  }

  // Render Magic Grab mode
  if (mode === 'magic-grab' && background) {
    // Sort layers by zIndex
    const sortedLayers = [...layers].sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0));

    return (
      <div className="relative w-full h-full flex flex-col items-center">
        {/* Canvas */}
        <div
          className="border-2 border-purple-300 rounded-lg overflow-hidden bg-gray-100"
          style={{ width: containerWidth, height: containerHeight, flexShrink: 0 }}
        >
          <Stage
            width={containerWidth}
            height={containerHeight}
            ref={stageRef}
            onClick={handleStageClick}
            onTap={handleStageClick}
            style={{ cursor: selectedLayerId ? 'move' : 'default' }}
          >
            {/* Background layer */}
            <Layer>
              <BackgroundImage
                src={background}
                containerWidth={containerWidth}
                containerHeight={containerHeight}
              />
            </Layer>

            {/* Draggable furniture layers */}
            <Layer>
              {sortedLayers.map((layer) => (
                <DraggableLayer
                  key={layer.id}
                  layer={layer}
                  stageWidth={containerWidth}
                  stageHeight={containerHeight}
                  isSelected={selectedLayerId === layer.id}
                  onSelect={() => handleSelectLayer(layer.id)}
                  onDragEnd={(newPos) => handleLayerDragEnd(layer.id, newPos)}
                  onTransformEnd={(newScale, newRotation) =>
                    handleLayerTransformEnd(layer.id, newScale, newRotation)
                  }
                />
              ))}
            </Layer>
          </Stage>
        </div>

        {/* Info bar */}
        <div
          className="mt-3 flex items-center justify-between bg-gray-50 rounded-lg p-3 border"
          style={{ width: containerWidth, maxWidth: '100%' }}
        >
          <div className="text-sm text-gray-600">
            {selectedLayerId ? (
              <span className="text-purple-600 font-medium">
                Drag to move • Use corners to resize
              </span>
            ) : (
              <span>Click any object to select and move it</span>
            )}
          </div>

          <div className="text-xs text-gray-500">
            {layers.length} object{layers.length !== 1 ? 's' : ''} detected
          </div>
        </div>

        {/* Selected layer info */}
        {selectedLayerId && (
          <div className="mt-2 flex items-center gap-3 text-xs">
            <span className="text-gray-600">
              Selected: {layers.find(l => l.id === selectedLayerId)?.productName || selectedLayerId}
            </span>
            <button
              onClick={() => setSelectedLayerId(null)}
              className="text-gray-500 hover:text-gray-700"
            >
              Deselect
            </button>
          </div>
        )}
      </div>
    );
  }

  // Fallback to legacy mode (original implementation)
  const getProductName = (productId: string) => {
    const product = products.find(p => String(p.id) === productId);
    return product?.name || 'Product';
  };

  return (
    <div className="relative w-full h-full flex flex-col items-center">
      {/* Canvas - fixed size to prevent stretching */}
      <div
        className="border-2 border-purple-300 rounded-lg overflow-hidden"
        style={{ width: containerWidth, height: containerHeight, flexShrink: 0 }}
      >
        <Stage
          width={containerWidth}
          height={containerHeight}
          ref={stageRef}
          onClick={handleStageClick}
          onTap={handleStageClick}
          style={{ cursor: clickStep !== 'select' ? 'crosshair' : 'default' }}
        >
          <Layer>
            <BackgroundImage
              src={visualizationImage || ''}
              containerWidth={containerWidth}
              containerHeight={containerHeight}
            />
          </Layer>

          <Layer>
            {/* Show "from" marker when placing */}
            {tempFrom && (
              <Group x={tempFrom.x * containerWidth} y={tempFrom.y * containerHeight}>
                <Rect
                  width={16}
                  height={16}
                  offsetX={8}
                  offsetY={8}
                  fill="#EF4444"
                  stroke="white"
                  strokeWidth={2}
                  cornerRadius={8}
                />
                <Text text="FROM" fontSize={10} fill="white" offsetX={14} y={12} />
              </Group>
            )}

            {/* Show move arrows for completed moves */}
            {positions.map((pos) => (
              <Group key={pos.productId}>
                {pos.fromX !== undefined && pos.fromY !== undefined && (
                  <>
                    {/* From point (red) */}
                    <Rect
                      x={pos.fromX * containerWidth - 6}
                      y={pos.fromY * containerHeight - 6}
                      width={12}
                      height={12}
                      fill="#EF4444"
                      stroke="white"
                      strokeWidth={2}
                      cornerRadius={6}
                    />
                    {/* To point (green) */}
                    <Rect
                      x={pos.x * containerWidth - 6}
                      y={pos.y * containerHeight - 6}
                      width={12}
                      height={12}
                      fill="#10B981"
                      stroke="white"
                      strokeWidth={2}
                      cornerRadius={6}
                    />
                  </>
                )}
              </Group>
            ))}
          </Layer>
        </Stage>
      </div>

      {/* Minimal control bar at bottom */}
      <div
        className="mt-3 flex items-center gap-4 bg-gray-50 rounded-lg p-3 border"
        style={{ width: containerWidth, maxWidth: '100%' }}
      >
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Move:</label>
          <select
            value={selectedProduct}
            onChange={(e) => {
              setSelectedProduct(e.target.value);
              setClickStep(e.target.value ? 'from' : 'select');
              setTempFrom(null);
            }}
            className="text-sm border rounded-md px-2 py-1.5 bg-white min-w-[200px]"
          >
            <option value="">Select a product...</option>
            {products.map((product) => (
              <option key={product.id} value={String(product.id)}>
                {product.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 text-sm text-gray-600">
          {clickStep === 'select' && 'Select a product to move'}
          {clickStep === 'from' && (
            <span className="text-red-600 font-medium">
              Click on the image where "{getProductName(selectedProduct)}" currently is
            </span>
          )}
          {clickStep === 'to' && (
            <span className="text-neutral-700 font-medium">
              Now click where you want it moved to
            </span>
          )}
        </div>

        {clickStep !== 'select' && (
          <button
            onClick={() => {
              setSelectedProduct('');
              setClickStep('select');
              setTempFrom(null);
            }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        )}
      </div>

      {positions.length > 0 && (
        <div className="mt-2 text-xs text-gray-500">
          {positions.length} move{positions.length !== 1 ? 's' : ''} marked
          <button
            onClick={() => {
              setPositions([]);
              onPositionsChange?.([]);
            }}
            className="ml-2 text-red-500 hover:text-red-700 underline"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
};
