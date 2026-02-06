/**
 * useVisualization Hook
 *
 * Core visualization hook that manages:
 * - Visualization state and API calls
 * - Smart change detection (additive, removal, reset)
 * - Undo/redo with proper quantity restoration
 * - Multi-angle viewing
 * - Text-based position editing
 * - Improve quality feature
 *
 * This hook is designed to be used by both:
 * - CanvasPanel (design page)
 * - Admin Curation page
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ViewingAngle } from '@/components/AngleSelector';
import { generateAngleView } from '@/utils/api';
import {
  VisualizationProduct,
  VisualizationConfig,
  VisualizationState,
  VisualizationActions,
  UseVisualizationReturn,
  VisualizationHistoryEntry,
  SerializableHistoryEntry,
  normalizeProductId,
} from '@/types/visualization';
import { WallColor } from '@/types/wall-colors';
import { WallTextureVariant } from '@/types/wall-textures';
import { FloorTile } from '@/types/floor-tiles';
import {
  useVisualizationHistory,
  UseVisualizationHistoryReturn,
} from './useVisualizationHistory';
import type { CanvasItem } from '@/hooks/useCanvas';
import { extractProducts, extractWallColor, extractTextureVariant, extractFloorTile } from '@/hooks/useCanvas';
import {
  detectChangeType,
  formatProductForApi,
  fetchWithRetry,
  getProgressMessage,
  buildQuantityMap,
  buildProductIdSet,
  formatImageSrc,
} from '@/utils/visualization-helpers';

// ============================================================================
// Hook Props
// ============================================================================

export interface UseVisualizationProps {
  /** Products currently in the canvas */
  products: VisualizationProduct[];

  /** Room image (may include baked-in products from curated looks) */
  roomImage: string | null;

  /** Clean room image without products (used for reset visualization) */
  cleanRoomImage?: string | null;

  /** Wall color to apply during visualization */
  wallColor?: WallColor | null;

  /** Wall texture variant to apply during visualization */
  textureVariant?: WallTextureVariant | null;

  /** Floor tile to apply during visualization */
  floorTile?: FloorTile | null;

  /** Callback to update products (e.g., from undo/redo) */
  onSetProducts: (products: VisualizationProduct[]) => void;

  /** Callback to update wall color (e.g., from undo/redo) */
  onSetWallColor?: (wallColor: WallColor | null) => void;

  /** Callback to update texture (e.g., from undo/redo) */
  onSetTexture?: (texture: WallTextureVariant | null) => void;

  /** Callback to update floor tile (e.g., from undo/redo) */
  onSetFloorTile?: (floorTile: FloorTile | null) => void;

  /** Unified canvas items (if using useCanvas hook) */
  canvasItems?: CanvasItem[];

  /** Callback to restore canvas items on undo/redo */
  onSetCanvasItems?: (items: CanvasItem[]) => void;

  /** Callback when visualization image changes */
  onVisualizationImageChange?: (image: string | null) => void;

  /** Callback when history changes (for persistence) */
  onVisualizationHistoryChange?: (history: SerializableHistoryEntry[]) => void;

  /** Initial visualization image (from curated look) */
  initialVisualizationImage?: string | null;

  /** Initial history (from saved project) */
  initialVisualizationHistory?: SerializableHistoryEntry[];

  /** Configuration options */
  config?: VisualizationConfig;

  /** Optional analytics callback for tracking visualization events */
  onTrackEvent?: (eventType: string, stepName?: string, eventData?: Record<string, unknown>) => void;
}

// ============================================================================
// API URL Helper
// ============================================================================

function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useVisualization({
  products: productsProp,
  roomImage,
  cleanRoomImage,
  wallColor: wallColorProp,
  textureVariant: textureVariantProp,
  floorTile: floorTileProp,
  onSetProducts,
  onSetWallColor,
  onSetTexture,
  onSetFloorTile,
  canvasItems: canvasItemsProp,
  onSetCanvasItems,
  onVisualizationImageChange,
  onVisualizationHistoryChange,
  initialVisualizationImage,
  initialVisualizationHistory = [],
  config = {},
  onTrackEvent,
}: UseVisualizationProps): UseVisualizationReturn {
  // Derive products/wallColor/textureVariant from canvasItems if provided
  const products = canvasItemsProp ? extractProducts(canvasItemsProp) : productsProp;
  const wallColor = canvasItemsProp ? extractWallColor(canvasItemsProp) : (wallColorProp ?? null);
  const textureVariant = canvasItemsProp ? extractTextureVariant(canvasItemsProp) : (textureVariantProp ?? null);
  // For floor tile, prefer canvasItems extraction but fall back to explicit prop
  // This handles timing issues where canvasItems may not yet contain the tile
  const floorTileFromCanvas = canvasItemsProp ? extractFloorTile(canvasItemsProp) : null;
  const floorTile = floorTileFromCanvas ?? (floorTileProp ?? null);
  // ============================================================================
  // History Hook
  // ============================================================================

  const historyHook = useVisualizationHistory({
    initialHistory: initialVisualizationHistory,
    onHistoryChange: onVisualizationHistoryChange,
  });

  // ============================================================================
  // Core State
  // ============================================================================

  const [visualizationImage, setVisualizationImage] = useState<string | null>(null);
  const [isVisualizing, setIsVisualizing] = useState(false);
  const [visualizationProgress, setVisualizationProgress] = useState('');
  const [visualizationStartTime, setVisualizationStartTime] = useState<number | null>(null);

  // Product tracking
  const [visualizedProductIds, setVisualizedProductIds] = useState<Set<string>>(new Set());
  const [visualizedProducts, setVisualizedProducts] = useState<VisualizationProduct[]>([]);
  const [visualizedQuantities, setVisualizedQuantities] = useState<Map<string, number>>(new Map());
  const [visualizedWallColor, setVisualizedWallColor] = useState<WallColor | null>(null);
  const [visualizedTextureVariant, setVisualizedTextureVariant] = useState<WallTextureVariant | null>(null);
  const [visualizedFloorTile, setVisualizedFloorTile] = useState<FloorTile | null>(null);
  const [visualizedRoomImage, setVisualizedRoomImage] = useState<string | null>(null);  // Track which room image was visualized
  const [needsRevisualization, setNeedsRevisualization] = useState(false);

  // Edit mode
  const [isEditingPositions, setIsEditingPositions] = useState(false);
  const [editInstructions, setEditInstructions] = useState('');
  const [preEditVisualization, setPreEditVisualization] = useState<string | null>(null);

  // Multi-angle
  const [currentAngle, setCurrentAngle] = useState<ViewingAngle>('front');
  const [angleImages, setAngleImages] = useState<Record<ViewingAngle, string | null>>({
    front: null, left: null, right: null, back: null
  });
  const [loadingAngle, setLoadingAngle] = useState<ViewingAngle | null>(null);

  // Quality improvement
  const [isImprovingQuality, setIsImprovingQuality] = useState(false);

  // Initialization flag
  const initializationRef = useRef(false);

  // ============================================================================
  // Progress Timer Effect
  // ============================================================================

  useEffect(() => {
    if (!isVisualizing || !visualizationStartTime) return;

    const updateProgress = () => {
      const elapsed = Math.floor((Date.now() - visualizationStartTime) / 1000);
      setVisualizationProgress(getProgressMessage(elapsed));
    };

    updateProgress();
    const interval = setInterval(updateProgress, 1000);
    return () => clearInterval(interval);
  }, [isVisualizing, visualizationStartTime]);

  // ============================================================================
  // Change Detection Effect
  // ============================================================================

  useEffect(() => {
    // Don't trigger on initial load or if never visualized
    if (visualizedProductIds.size === 0 && !visualizationImage && !visualizedWallColor && !visualizedTextureVariant && !visualizedFloorTile) {
      return;
    }

    // Compare current products with last visualized products
    const currentIds = new Set(products.map(p => normalizeProductId(p.id)));
    const productsChanged =
      products.length !== visualizedProductIds.size ||
      products.some(p => !visualizedProductIds.has(normalizeProductId(p.id)));

    // Check if any quantities have changed
    const quantitiesChanged = products.some(p => {
      const currentQty = p.quantity || 1;
      const visualizedQty = visualizedQuantities.get(normalizeProductId(p.id)) || 0;
      return currentQty !== visualizedQty;
    });

    // Check if wall color has changed
    const currentWallColor = wallColor ?? null;
    const hasExistingVisualization = visualizedProductIds.size > 0 || visualizationImage;
    const wallColorChanged = hasExistingVisualization && (
      (currentWallColor === null && visualizedWallColor !== null) ||
      (currentWallColor !== null && visualizedWallColor === null) ||
      (currentWallColor !== null && visualizedWallColor !== null && currentWallColor.id !== visualizedWallColor.id)
    );

    // Check if texture variant has changed
    const currentTexture = textureVariant ?? null;
    const textureChanged = hasExistingVisualization && (
      (currentTexture === null && visualizedTextureVariant !== null) ||
      (currentTexture !== null && visualizedTextureVariant === null) ||
      (currentTexture !== null && visualizedTextureVariant !== null && currentTexture.id !== visualizedTextureVariant.id)
    );

    // Check if floor tile has changed
    const currentFloorTile = floorTile ?? null;
    const floorTileChanged = hasExistingVisualization && (
      (currentFloorTile === null && visualizedFloorTile !== null) ||
      (currentFloorTile !== null && visualizedFloorTile === null) ||
      (currentFloorTile !== null && visualizedFloorTile !== null && currentFloorTile.id !== visualizedFloorTile.id)
    );

    if (productsChanged || quantitiesChanged || wallColorChanged || textureChanged || floorTileChanged) {
      setNeedsRevisualization(true);
      if (floorTileChanged) {
        console.log('[useVisualization] Floor tile changed, needs re-visualization');
      } else if (textureChanged) {
        console.log('[useVisualization] Texture changed, needs re-visualization');
      } else if (wallColorChanged) {
        console.log('[useVisualization] Wall color changed, needs re-visualization');
      } else if (quantitiesChanged && !productsChanged) {
        console.log('[useVisualization] Quantity changed, needs re-visualization');
      }
    }
  }, [products, visualizedProductIds, visualizedQuantities, visualizationImage, wallColor, visualizedWallColor, textureVariant, visualizedTextureVariant, floorTile, visualizedFloorTile]);

  // ============================================================================
  // Sync Effect: Keep visualizedProducts in sync when products change
  // ============================================================================
  // Track whether products have ever been part of a visualization
  // This prevents the sync effect from incorrectly claiming new products
  // were already visualized after a surface-only visualization (texture/tile/color).
  const hasVisualizedProductsRef = useRef(false);

  useEffect(() => {
    // If we have a visualization but visualizedProductIds is empty, sync from products.
    // BUT only if products were actually visualized before (not after surface-only viz).
    if (visualizationImage && products.length > 0 && visualizedProductIds.size === 0 && hasVisualizedProductsRef.current) {
      console.log('[useVisualization] CRITICAL SYNC: syncing visualizedProductIds from products');
      setVisualizedProducts([...products]);
      setVisualizedProductIds(buildProductIdSet(products));
      setVisualizedQuantities(buildQuantityMap(products));
    }
  }, [products, visualizationImage, visualizedProductIds.size]);

  // ============================================================================
  // Initialize from curated look
  // ============================================================================

  useEffect(() => {
    if (initializationRef.current) return;
    if (!initialVisualizationImage || visualizationImage) return;

    console.log('[useVisualization] Initializing from curated look image');
    initializationRef.current = true;

    const formattedImage = formatImageSrc(initialVisualizationImage);
    setVisualizationImage(formattedImage);

    // Track initial products as visualized
    const productIds = buildProductIdSet(products);
    setVisualizedProductIds(productIds);
    setVisualizedProducts([...products]);
    setVisualizedQuantities(buildQuantityMap(products));
    if (products.length > 0) {
      hasVisualizedProductsRef.current = true;
    }

    // Track the room image used for this visualization
    const baseImage = cleanRoomImage || roomImage;
    if (baseImage) {
      setVisualizedRoomImage(baseImage);
    }

    // Add to history (including wall color and canvas items if present)
    historyHook.pushState({
      image: formattedImage,
      products: [...products],
      wallColor: wallColor || null,
      canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
    });

    console.log('[useVisualization] Curated visualization initialized successfully');
  }, [initialVisualizationImage, visualizationImage, products, cleanRoomImage, roomImage]);

  // ============================================================================
  // Notify parent when visualization image changes
  // ============================================================================

  useEffect(() => {
    if (onVisualizationImageChange) {
      onVisualizationImageChange(visualizationImage);
    }
  }, [visualizationImage, onVisualizationImageChange]);

  // ============================================================================
  // Reset angle state when visualization changes
  // ============================================================================

  useEffect(() => {
    if (visualizationImage) {
      setCurrentAngle('front');
      setAngleImages({ front: visualizationImage, left: null, right: null, back: null });
    }
  }, [visualizationImage]);

  // ============================================================================
  // Get or Create Session
  // ============================================================================

  const getOrCreateSession = async (): Promise<string> => {
    let sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId) {
      const response = await fetch(`${getApiUrl()}/api/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error('Failed to create session');
      }

      const data = await response.json();
      sessionId = data.session_id;
      if (sessionId) {
        sessionStorage.setItem('design_session_id', sessionId);
      }
    }
    return sessionId!;
  };

  // ============================================================================
  // Handle Visualize
  // ============================================================================

  const handleVisualize = useCallback(async () => {
    const baseImage = cleanRoomImage || roomImage;
    if (!baseImage) return;

    // Allow visualization with products, wall color, texture, or floor tile
    const hasProducts = products.length > 0;
    const hasWallColor = !!(wallColor);
    const hasTexture = !!(textureVariant);
    const hasFloorTile = !!(floorTile);

    if (!hasProducts && !hasWallColor && !hasTexture && !hasFloorTile) return;

    console.log('[useVisualization] handleVisualize called:', {
      products: products.length,
      wallColorId: wallColor?.id ?? null,
      textureVariantId: textureVariant?.id ?? null,
      floorTileId: floorTile?.id ?? null,
      baseImage: baseImage ? 'exists' : 'null',
    });

    const vizStartTime = Date.now();

    // Track API method used for analytics
    let vizMethod = 'unknown';

    // Build comprehensive tracking data for analytics
    const trackingData: Record<string, unknown> = {
      product_count: products.length,
      products: products.map(p => ({
        id: p.id,
        name: p.name,
        category: p.productType || p.product_type,
      })),
    };
    if (wallColor) {
      trackingData.wall_color = {
        id: wallColor.id,
        name: wallColor.name,
        code: wallColor.code,
        hex: wallColor.hex_value,
      };
    }
    if (textureVariant) {
      trackingData.wall_texture = {
        id: textureVariant.id,
        name: textureVariant.name,
      };
    }
    if (floorTile) {
      trackingData.floor_tile = {
        id: floorTile.id,
        name: floorTile.name,
      };
    }

    // Note: visualize_start tracking removed - only track complete events for cleaner analytics

    setIsVisualizing(true);
    setVisualizationStartTime(Date.now());
    setVisualizationProgress('Preparing visualization...');

    try {
      // ================================================================
      // Wall-only / Texture-only / Floor-tile-only visualization (no furniture products)
      // Apply all surface changes in a single combined Gemini call
      // ================================================================
      if (!hasProducts) {
        // Use existing visualization image if available (preserves previously rendered furniture)
        // Fall back to baseImage only if there's no existing visualization
        const startImage = visualizationImage || baseImage;
        console.log('[useVisualization] No products in canvas - applying surface changes via combined call', {
          usingExistingVisualization: !!visualizationImage,
          hasWallColor, hasTexture, hasFloorTile,
        });

        const sessionId = await getOrCreateSession();
        setVisualizationProgress('Applying surface changes...');

        // Build combined surface request
        const surfaceRequest: Record<string, unknown> = {
          room_image: startImage,
          session_id: sessionId,
        };
        if (hasWallColor && wallColor) {
          surfaceRequest.wall_color_name = wallColor.name;
          surfaceRequest.wall_color_code = wallColor.code;
          surfaceRequest.wall_color_hex = wallColor.hex_value;
        }
        if (hasTexture && textureVariant) {
          surfaceRequest.texture_variant_id = textureVariant.id;
        }
        if (hasFloorTile && floorTile) {
          surfaceRequest.tile_id = floorTile.id;
        }

        let newImage: string | null = null;

        try {
          // Combined surface call — single Gemini API call for all surface changes
          const response = await fetchWithRetry(
            `${getApiUrl()}/api/visualization/apply-surfaces`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(surfaceRequest),
            },
            { maxRetries: 2, retryDelayMs: 3000, timeoutMs: 300000 }
          );

          if (response.ok) {
            const surfaceData = await response.json();
            if (surfaceData.success && surfaceData.rendered_image) {
              newImage = surfaceData.rendered_image;
              vizMethod = 'apply_surfaces';
              console.log('[useVisualization] Combined surface call succeeded:', surfaceData.surfaces_applied);
            } else {
              console.warn('[useVisualization] Combined surface call returned failure:', surfaceData.error_message);
            }
          } else {
            console.warn('[useVisualization] Combined surface call HTTP error:', response.status);
          }
        } catch (combinedError) {
          console.warn('[useVisualization] Combined surface call failed, falling back to sequential:', combinedError);
        }

        // Fallback: sequential calls if combined call failed
        if (!newImage) {
          console.log('[useVisualization] Falling back to sequential surface calls');
          vizMethod = 'sequential_surfaces';
          newImage = startImage;

          if (hasWallColor && wallColor) {
            setVisualizationProgress('Applying wall color...');
            const colorResponse = await fetch(
              `${getApiUrl()}/api/visualization/change-wall-color`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  room_image: newImage,
                  color_name: wallColor.name,
                  color_code: wallColor.code,
                  color_hex: wallColor.hex_value,
                  session_id: sessionId,
                }),
              }
            );
            if (colorResponse.ok) {
              const colorData = await colorResponse.json();
              if (colorData.success && colorData.rendered_image) {
                newImage = colorData.rendered_image;
              }
            }
          }

          if (hasTexture && textureVariant) {
            setVisualizationProgress('Applying wall texture...');
            const textureResponse = await fetch(
              `${getApiUrl()}/api/visualization/change-wall-texture`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  room_image: newImage,
                  texture_variant_id: textureVariant.id,
                }),
              }
            );
            if (textureResponse.ok) {
              const textureData = await textureResponse.json();
              if (textureData.success && textureData.rendered_image) {
                newImage = textureData.rendered_image;
              }
            }
          }

          if (hasFloorTile && floorTile) {
            setVisualizationProgress('Applying floor tile...');
            const floorTileResponse = await fetch(
              `${getApiUrl()}/api/visualization/change-floor-tile`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  room_image: newImage,
                  tile_id: floorTile.id,
                }),
              }
            );
            if (floorTileResponse.ok) {
              const floorTileData = await floorTileResponse.json();
              if (floorTileData.success && floorTileData.rendered_image) {
                newImage = floorTileData.rendered_image;
              }
            }
          }
        }

        // Only update visualization if we actually got a new image
        if (!newImage || newImage === startImage) {
          throw new Error('Visualization produced no changes. Please try again.');
        }

        // Update state
        setVisualizationImage(newImage);
        // Preserve existing visualized products if we started from a visualization image
        if (!visualizationImage) {
          setVisualizedProductIds(new Set());
          setVisualizedProducts([]);
          setVisualizedQuantities(new Map());
        }
        setVisualizedWallColor(wallColor || null);
        setVisualizedTextureVariant(textureVariant || null);
        setVisualizedFloorTile(floorTile || null);
        setVisualizedRoomImage(baseImage);
        setNeedsRevisualization(false);

        historyHook.pushState({
          image: newImage,
          products: [],
          wallColor: wallColor || null,
          canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
        });

        console.log('[useVisualization] Surface-only visualization complete');
        return;
      }

      // ================================================================
      // Product visualization (with optional wall color / texture overlay)
      // ================================================================

      // Check for wall color changes
      const currentWallColor = wallColor ?? null;
      const wallColorChanged = (
        (currentWallColor === null && visualizedWallColor !== null) ||
        (currentWallColor !== null && visualizedWallColor === null) ||
        (currentWallColor !== null && visualizedWallColor !== null && currentWallColor.id !== visualizedWallColor.id)
      );

      // Check for texture changes
      const currentTexture = textureVariant ?? null;
      const textureChanged = (
        (currentTexture === null && visualizedTextureVariant !== null) ||
        (currentTexture !== null && visualizedTextureVariant === null) ||
        (currentTexture !== null && visualizedTextureVariant !== null && currentTexture.id !== visualizedTextureVariant.id)
      );

      // Check for floor tile changes
      const currentFloorTile = floorTile ?? null;
      const floorTileChanged = (
        (currentFloorTile === null && visualizedFloorTile !== null) ||
        (currentFloorTile !== null && visualizedFloorTile === null) ||
        (currentFloorTile !== null && visualizedFloorTile !== null && currentFloorTile.id !== visualizedFloorTile.id)
      );

      // Check for room image changes - compare current base image with the one used in last visualization
      const roomImageChanged = visualizedRoomImage !== null && baseImage !== visualizedRoomImage;
      if (roomImageChanged) {
        console.log('[useVisualization] Room image changed - will force reset visualization');
      }

      // Detect change type for products
      const changeInfo = detectChangeType({
        products,
        visualizedProductIds,
        visualizedProducts,
        visualizedQuantities,
        visualizationResult: visualizationImage,
      });

      console.log('[useVisualization] Change detection result:', changeInfo.type, changeInfo.reason, 'wallColorChanged:', wallColorChanged, 'textureChanged:', textureChanged, 'floorTileChanged:', floorTileChanged, 'roomImageChanged:', roomImageChanged);

      if (changeInfo.type === 'no_change' && !wallColorChanged && !textureChanged && !floorTileChanged && !roomImageChanged) {
        console.log('[useVisualization] No changes detected, skipping');
        setIsVisualizing(false);
        setVisualizationStartTime(null);
        setVisualizationProgress('');
        return;
      }

      // Handle floor-tile-only change (products unchanged, just apply tile to existing visualization)
      if (changeInfo.type === 'no_change' && floorTileChanged && !textureChanged && !wallColorChanged && !roomImageChanged && visualizationImage) {
        console.log('[useVisualization] Floor-tile-only change on existing visualization');
        let newImage = visualizationImage;

        if (currentFloorTile && currentFloorTile.id) {
          setVisualizationProgress('Applying floor tile...');
          const tileResponse = await fetch(
            `${getApiUrl()}/api/visualization/change-floor-tile`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                room_image: newImage,
                tile_id: currentFloorTile.id,
              }),
            }
          );
          if (tileResponse.ok) {
            const tileData = await tileResponse.json();
            if (tileData.success && tileData.rendered_image) {
              newImage = tileData.rendered_image;
              console.log('[useVisualization] Floor tile applied to existing visualization successfully');
            } else {
              const errorMsg = tileData.error_message || 'Floor tile visualization returned no image';
              console.error('[useVisualization] Floor tile API returned failure:', errorMsg);
              throw new Error(errorMsg);
            }
          } else {
            console.error('[useVisualization] Floor tile API HTTP error:', tileResponse.status);
            throw new Error(`Floor tile API failed with status ${tileResponse.status}`);
          }
        }

        setVisualizationImage(newImage);
        setVisualizedFloorTile(currentFloorTile);
        setNeedsRevisualization(false);

        historyHook.pushState({
          image: newImage,
          products: [...products],
          wallColor: wallColor || null,
          canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
        });

        console.log('[useVisualization] Floor-tile-only visualization complete');
        setIsVisualizing(false);
        setVisualizationStartTime(null);
        setVisualizationProgress('');
        return;
      }

      // Handle texture-only change (products unchanged, just apply texture to existing visualization)
      if (changeInfo.type === 'no_change' && textureChanged && !wallColorChanged && !roomImageChanged && visualizationImage) {
        console.log('[useVisualization] Texture-only change on existing visualization');
        let newImage = visualizationImage;

        if (currentTexture && currentTexture.id) {
          setVisualizationProgress('Applying wall texture...');
          const textureResponse = await fetch(
            `${getApiUrl()}/api/visualization/change-wall-texture`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                room_image: newImage,
                texture_variant_id: currentTexture.id,
              }),
            }
          );
          if (textureResponse.ok) {
            const textureData = await textureResponse.json();
            if (textureData.success && textureData.rendered_image) {
              newImage = textureData.rendered_image;
              console.log('[useVisualization] Texture applied to existing visualization successfully');
            } else {
              const errorMsg = textureData.error_message || 'Texture visualization returned no image';
              console.error('[useVisualization] Texture API returned failure:', errorMsg);
              throw new Error(errorMsg);
            }
          } else {
            console.error('[useVisualization] Texture API HTTP error:', textureResponse.status);
            throw new Error(`Texture API failed with status ${textureResponse.status}`);
          }
        }

        setVisualizationImage(newImage);
        setVisualizedTextureVariant(currentTexture);
        setNeedsRevisualization(false);

        historyHook.pushState({
          image: newImage,
          products: [...products],
          wallColor: wallColor || null,
          canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
        });

        console.log('[useVisualization] Texture-only visualization complete');
        setIsVisualizing(false);
        setVisualizationStartTime(null);
        setVisualizationProgress('');
        return;
      }

      const sessionId = await getOrCreateSession();

      // Prepare API request based on change type
      let imageToUse: string;
      let productsToVisualize: VisualizationProduct[];
      let isIncremental = false;
      let forceReset = false;
      let removalMode = false;
      let productsToRemove: VisualizationProduct[] = [];
      let productsToAdd: VisualizationProduct[] = [];

      // CRITICAL: If room image changed, force a complete reset regardless of product changes
      // This ensures the new room image is used as the base
      if (roomImageChanged) {
        imageToUse = baseImage;
        productsToVisualize = products;
        forceReset = true;
        console.log('[useVisualization] Room image changed: re-visualizing all products on NEW room image');
      } else if (changeInfo.type === 'additive') {
        imageToUse = visualizationImage!;
        productsToVisualize = changeInfo.newProducts!;
        isIncremental = true;
        console.log(`[useVisualization] Incremental: adding ${productsToVisualize.length} products`);
      } else if (changeInfo.type === 'remove_and_add') {
        imageToUse = visualizationImage!;
        productsToVisualize = products;
        productsToRemove = changeInfo.removedProducts || [];
        productsToAdd = changeInfo.newProducts || [];
        removalMode = true;
        console.log(`[useVisualization] Remove and add: -${productsToRemove.length}, +${productsToAdd.length}`);
      } else if (changeInfo.type === 'removal') {
        imageToUse = visualizationImage!;
        productsToVisualize = products;
        productsToRemove = changeInfo.removedProducts || [];
        removalMode = true;
        console.log(`[useVisualization] Removal: removing ${productsToRemove.length} products`);
      } else if (changeInfo.type === 'quantity_decrease') {
        imageToUse = visualizationImage!;
        removalMode = true;
        productsToVisualize = products;
        productsToRemove = (changeInfo.quantityDeltas || []).map(qd => ({
          ...qd.product,
          name: qd.product.name,
        }));
        console.log(`[useVisualization] Quantity decrease: removing copies from ${productsToRemove.length} types`);
      } else if (changeInfo.type === 'reset') {
        imageToUse = cleanRoomImage || roomImage!;
        productsToVisualize = products;
        forceReset = true;
        console.log('[useVisualization] Reset: re-visualizing all products');
      } else if (changeInfo.type === 'no_change' && (wallColorChanged || textureChanged || floorTileChanged)) {
        // Wall color, texture, and/or floor tile changed but products didn't - apply changes to existing visualization
        imageToUse = visualizationImage!;
        productsToVisualize = [];  // No products to add, just surface changes
        console.log('[useVisualization] Surface change only (wall color/texture/tile)');
      } else {
        // Initial
        imageToUse = cleanRoomImage || roomImage!;
        productsToVisualize = products;
        console.log('[useVisualization] Initial visualization');
      }

      // Prepare products for API
      const productDetails = productsToVisualize.map(formatProductForApi);
      const allProductDetails = products.map(formatProductForApi);
      const visualizedProductDetails = (visualizedProducts.length > 0 ? visualizedProducts : products)
        .map(formatProductForApi);

      // Log what we're sending to help debug duplicates
      console.log('[useVisualization] API Request Summary:', {
        changeType: changeInfo.type,
        isIncremental,
        forceReset,
        removalMode,
        productsToSend: productDetails.map(p => ({ id: p.id, name: p.name, qty: p.quantity })),
        allProducts: allProductDetails.map(p => ({ id: p.id, name: p.name, qty: p.quantity })),
        visualizedProducts: isIncremental ? visualizedProductDetails.map(p => ({ id: p.id, name: p.name, qty: p.quantity })) : [],
      });

      // Make API request
      const response = await fetchWithRetry(
        `${getApiUrl()}/api/chat/sessions/${sessionId}/visualize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: imageToUse,
            products: productDetails,
            all_products: allProductDetails,
            visualized_products: isIncremental ? visualizedProductDetails : [],
            analysis: {
              design_style: 'modern',
              color_palette: [],
              room_type: 'living_room',
            },
            is_incremental: isIncremental,
            force_reset: forceReset,
            removal_mode: removalMode,
            products_to_remove: removalMode ? productsToRemove.map(formatProductForApi) : undefined,
            products_to_add: removalMode ? productsToAdd.map(formatProductForApi) : undefined,
            user_uploaded_new_image: changeInfo.type === 'initial',
            curated_look_id: config.curatedLookId,
            project_id: config.projectId,
            // Wall color to apply during visualization
            // For incremental adds, only send wall color if it actually changed
            wall_color: ((!isIncremental || wallColorChanged) && wallColor) ? {
              name: wallColor.name,
              code: wallColor.code,
              hex_value: wallColor.hex_value,
            } : undefined,
            // Surface changes to apply in same Gemini call (unified visualization)
            // For incremental adds, only send surface IDs if the surface actually changed
            // (otherwise it's already applied on the base image)
            texture_variant_id: (!isIncremental || textureChanged) ? (textureVariant?.id || undefined) : undefined,
            tile_id: (!isIncremental || floorTileChanged) ? (floorTile?.id || undefined) : undefined,
          }),
        },
        { maxRetries: 2, timeoutMs: 300000, retryDelayMs: 3000 }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Visualization failed');
      }

      const data = await response.json();

      if (!data.visualization?.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      // Capture the visualization mode/method from the API response
      vizMethod = data.mode || 'visualize';

      // Update state with new visualization
      // Texture and floor tile are now handled in the same Gemini call (unified visualization)
      const newImage = data.visualization.rendered_image;
      const newProductIds = buildProductIdSet(products);
      const newQuantities = buildQuantityMap(products);

      setVisualizationImage(newImage);
      setVisualizedProductIds(newProductIds);
      setVisualizedProducts([...products]);
      setVisualizedQuantities(newQuantities);
      setVisualizedWallColor(wallColor || null);
      setVisualizedTextureVariant(textureVariant || null);
      setVisualizedFloorTile(floorTile || null);
      setVisualizedRoomImage(baseImage);  // CRITICAL: Track which room image was used
      setNeedsRevisualization(false);

      // Push to history (including wall color and canvas items)
      historyHook.pushState({
        image: newImage,
        products: [...products],
        wallColor: wallColor || null,
        canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
      });

      console.log('[useVisualization] Visualization successful, tracked room image');
      onTrackEvent?.('design.visualize_complete', undefined, {
        ...trackingData,
        method: vizMethod,
        success: true,
        duration_ms: Date.now() - vizStartTime,
      });

    } catch (error: unknown) {
      console.error('[useVisualization] Visualization error:', error);

      let errorMessage = 'Failed to generate visualization. Please try again.';
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          errorMessage = 'Request timed out. Please try with fewer products.';
        } else if (error.message) {
          errorMessage = error.message;
        }
      }
      alert(errorMessage);
    } finally {
      setIsVisualizing(false);
      setVisualizationStartTime(null);
      setVisualizationProgress('');
    }
  }, [
    products, roomImage, cleanRoomImage, visualizationImage,
    visualizedProductIds, visualizedProducts, visualizedQuantities,
    wallColor, visualizedWallColor, visualizedRoomImage,
    textureVariant, visualizedTextureVariant,
    floorTile, visualizedFloorTile,
    config.curatedLookId, config.projectId, historyHook,
    canvasItemsProp,
  ]);

  // ============================================================================
  // Handle Undo
  // ============================================================================

  const handleUndo = useCallback(() => {
    const previousState = historyHook.undo();

    if (previousState) {
      console.log('[useVisualization] Restoring previous state with', previousState.products.length, 'products', 'wallColor:', previousState.wallColor?.name || 'none');
      setVisualizationImage(previousState.image);
      setVisualizedProductIds(previousState.productIds);
      setVisualizedProducts(previousState.products);
      setVisualizedQuantities(previousState.visualizedQuantities);  // CRITICAL: Restore quantities
      setVisualizedWallColor(previousState.wallColor || null);  // Restore wall color
      setVisualizedTextureVariant(null);  // Texture restored via canvasItems
      // Restore floor tile from canvasItems to keep change detection in sync
      setVisualizedFloorTile(previousState.canvasItems ? extractFloorTile(previousState.canvasItems) : null);

      // Restore full canvas state if available (unified canvas mode)
      if (previousState.canvasItems && onSetCanvasItems) {
        onSetCanvasItems(previousState.canvasItems);
      } else {
        onSetProducts(previousState.products);
        if (onSetWallColor) {
          onSetWallColor(previousState.wallColor || null);
        }
      }
    } else {
      // No previous state - clear visualization
      console.log('[useVisualization] No previous state - clearing visualization');
      setVisualizationImage(null);
      setVisualizedProductIds(new Set());
      setVisualizedProducts([]);
      setVisualizedQuantities(new Map());
      setVisualizedWallColor(null);
      setVisualizedTextureVariant(null);
      setVisualizedFloorTile(null);

      if (onSetCanvasItems) {
        onSetCanvasItems([]);
      } else {
        onSetProducts([]);
        if (onSetWallColor) {
          onSetWallColor(null);
        }
      }
    }

    console.log('[useVisualization] Undo complete');
  }, [historyHook, onSetProducts, onSetWallColor, onSetCanvasItems]);

  // ============================================================================
  // Handle Redo
  // ============================================================================

  const handleRedo = useCallback(() => {
    const stateToRestore = historyHook.redo();

    if (stateToRestore) {
      console.log('[useVisualization] Restoring state with', stateToRestore.products.length, 'products', 'wallColor:', stateToRestore.wallColor?.name || 'none');
      setVisualizationImage(stateToRestore.image);
      setVisualizedProductIds(stateToRestore.productIds);
      setVisualizedProducts(stateToRestore.products);
      setVisualizedQuantities(stateToRestore.visualizedQuantities);  // CRITICAL: Restore quantities
      setVisualizedWallColor(stateToRestore.wallColor || null);  // Restore wall color
      setVisualizedTextureVariant(null);  // Texture restored via canvasItems
      // Restore floor tile from canvasItems to keep change detection in sync
      setVisualizedFloorTile(stateToRestore.canvasItems ? extractFloorTile(stateToRestore.canvasItems) : null);

      // Restore full canvas state if available (unified canvas mode)
      if (stateToRestore.canvasItems && onSetCanvasItems) {
        onSetCanvasItems(stateToRestore.canvasItems);
      } else {
        onSetProducts(stateToRestore.products);
        if (onSetWallColor) {
          onSetWallColor(stateToRestore.wallColor || null);
        }
      }
    }

    console.log('[useVisualization] Redo complete');
  }, [historyHook, onSetProducts, onSetWallColor, onSetCanvasItems]);

  // ============================================================================
  // Handle Improve Quality
  // ============================================================================

  const handleImproveQuality = useCallback(async () => {
    const baseImage = cleanRoomImage || roomImage;
    if (!baseImage || (products.length === 0 && !wallColor && !textureVariant && !floorTile)) {
      console.log('[useVisualization] Improve quality: missing requirements');
      return;
    }

    const confirmed = window.confirm(
      'Improve Quality will re-visualize all products on the original room image.\n\n' +
      'WARNING: This will reset your undo/redo history.\n\n' +
      'Continue?'
    );
    if (!confirmed) return;

    setIsImprovingQuality(true);
    console.log('[useVisualization] Starting quality improvement with', products.length, 'products');

    // Debug: Log all products being sent
    products.forEach((p, i) => {
      console.log(`[useVisualization] Product ${i + 1}:`, {
        id: p.id,
        name: p.name,
        productType: p.productType || p.product_type,
        hasImageUrl: !!p.image_url,
        quantity: p.quantity || 1,
      });
    });

    try {
      const sessionId = await getOrCreateSession();
      const productDetails = products.map(formatProductForApi);

      // Debug: Log formatted products
      console.log('[useVisualization] Formatted products for API:', productDetails.map(p => ({
        id: p.id,
        name: p.name,
        product_type: p.product_type,
        hasImageUrl: !!p.image_url,
        quantity: p.quantity,
      })));

      const response = await fetch(
        `${getApiUrl()}/api/chat/sessions/${sessionId}/visualize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: baseImage,
            products: productDetails,
            analysis: { design_style: 'modern', color_palette: [], room_type: 'living_room' },
            is_incremental: false,
            force_reset: true,
            user_uploaded_new_image: false,
            action: 'add',
            curated_look_id: config.curatedLookId,
            project_id: config.projectId,
            // Wall color to apply during visualization
            wall_color: wallColor ? {
              name: wallColor.name,
              code: wallColor.code,
              hex_value: wallColor.hex_value,
            } : undefined,
            // Surface changes to apply in same Gemini call (unified visualization)
            texture_variant_id: textureVariant?.id || undefined,
            tile_id: floorTile?.id || undefined,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Quality improvement failed');
      }

      const data = await response.json();

      if (!data.visualization?.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      // Texture and floor tile are now handled in the same Gemini call (unified visualization)
      const newImage = data.visualization.rendered_image;
      console.log('[useVisualization] Quality improvement success (unified call)');

      // Update visualization
      setVisualizationImage(newImage);

      // Reset history with new state (including wall color and canvas items)
      historyHook.reset();
      historyHook.pushState({
        image: newImage,
        products: [...products],
        wallColor: wallColor || null,
        canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
      });

      // Update visualized state
      setVisualizedProductIds(buildProductIdSet(products));
      setVisualizedProducts([...products]);
      setVisualizedQuantities(buildQuantityMap(products));
      hasVisualizedProductsRef.current = true;
      setVisualizedWallColor(wallColor || null);
      setVisualizedTextureVariant(textureVariant || null);
      setVisualizedFloorTile(floorTile || null);
      setVisualizedRoomImage(baseImage);  // CRITICAL: Track which room image was used
      setNeedsRevisualization(false);

    } catch (error) {
      console.error('[useVisualization] Quality improvement error:', error);
      alert(`Failed to improve quality: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsImprovingQuality(false);
    }
  }, [products, roomImage, cleanRoomImage, wallColor, textureVariant, floorTile,
    config.curatedLookId, config.projectId, historyHook, canvasItemsProp]);

  // ============================================================================
  // Handle Angle Select
  // ============================================================================

  const handleAngleSelect = useCallback(async (angle: ViewingAngle) => {
    if (angle === 'front') {
      setCurrentAngle('front');
      return;
    }

    // Check if we already have this angle cached
    if (angleImages[angle]) {
      setCurrentAngle(angle);
      return;
    }

    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId || !visualizationImage) {
      console.error('[useVisualization] Cannot generate angle: no session or visualization');
      return;
    }

    setLoadingAngle(angle);
    try {
      const result = await generateAngleView(sessionId, {
        visualization_image: visualizationImage,
        target_angle: angle,
        products_description: products.map(p => p.name).join(', ')
      });

      const formattedImage = result.image.startsWith('data:')
        ? result.image
        : `data:image/png;base64,${result.image}`;

      setAngleImages(prev => ({ ...prev, [angle]: formattedImage }));
      setCurrentAngle(angle);
    } catch (error) {
      console.error('[useVisualization] Failed to generate angle view:', error);
      alert('Failed to generate angle view. Please try again.');
    } finally {
      setLoadingAngle(null);
    }
  }, [visualizationImage, products, angleImages]);

  // ============================================================================
  // Edit Mode Handlers
  // ============================================================================

  const enterEditMode = useCallback(() => {
    console.log('[useVisualization] enterEditMode called, visualizationImage exists:', !!visualizationImage);

    if (!visualizationImage) {
      alert('Please create a visualization first.');
      return;
    }

    console.log('[useVisualization] Entering text-based edit mode');
    setPreEditVisualization(visualizationImage);
    setIsEditingPositions(true);
    setEditInstructions('');
    console.log('[useVisualization] isEditingPositions set to true');
  }, [visualizationImage]);

  const exitEditMode = useCallback(() => {
    // Revert to pre-edit visualization
    if (preEditVisualization) {
      setVisualizationImage(preEditVisualization);
    }
    setIsEditingPositions(false);
    setEditInstructions('');
    setPreEditVisualization(null);
  }, [preEditVisualization]);

  const applyEditInstructions = useCallback(async (instructions: string) => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId || !visualizationImage) {
      throw new Error('No session or visualization image found.');
    }

    if (!instructions.trim()) {
      throw new Error('Please enter instructions for how to reposition items.');
    }

    setIsVisualizing(true);
    try {
      const productInfos = products.map(p => ({
        id: p.id,
        name: p.name,
        quantity: p.quantity || 1,
        image_url: p.image_url || (p.images?.[0]?.large_url || p.images?.[0]?.medium_url || p.images?.[0]?.original_url),
      }));

      const response = await fetch(
        `${getApiUrl()}/api/visualization/sessions/${sessionId}/edit-with-instructions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: visualizationImage,
            instructions: instructions.trim(),
            products: productInfos,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to apply edit instructions');
      }

      const data = await response.json();

      if (!data.image) {
        throw new Error('No edited image was generated');
      }

      setVisualizationImage(data.image);

      // Add to history (including wall color and canvas items)
      historyHook.pushState({
        image: data.image,
        products: [...visualizedProducts],
        wallColor: visualizedWallColor,
        canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
      });

      setNeedsRevisualization(false);
      setIsEditingPositions(false);
      setEditInstructions('');

      console.log('[useVisualization] Edit instructions applied successfully');

    } catch (error) {
      throw error;  // Re-throw for caller to handle
    } finally {
      setIsVisualizing(false);
    }
  }, [visualizationImage, products, visualizedProducts, historyHook]);

  // ============================================================================
  // Reset Visualization
  // ============================================================================

  const resetVisualization = useCallback(() => {
    console.log('[useVisualization] Resetting visualization');
    setVisualizationImage(null);
    setVisualizedProductIds(new Set());
    setVisualizedProducts([]);
    setVisualizedQuantities(new Map());
    setVisualizedWallColor(null);
    setVisualizedTextureVariant(null);
    setVisualizedFloorTile(null);
    setVisualizedRoomImage(null);  // Reset room image tracking
    setNeedsRevisualization(false);
    historyHook.reset();
    initializationRef.current = false;
  }, [historyHook]);

  // ============================================================================
  // Initialize from Existing
  // ============================================================================

  const initializeFromExisting = useCallback((
    image: string,
    existingProducts: VisualizationProduct[],
    existingHistory?: VisualizationHistoryEntry[]
  ) => {
    console.log('[useVisualization] Initializing from existing:', existingProducts.length, 'products');

    const formattedImage = formatImageSrc(image);
    setVisualizationImage(formattedImage);
    setVisualizedProductIds(buildProductIdSet(existingProducts));
    setVisualizedProducts([...existingProducts]);
    setVisualizedQuantities(buildQuantityMap(existingProducts));
    if (existingProducts.length > 0) {
      hasVisualizedProductsRef.current = true;
    }
    setNeedsRevisualization(false);

    if (existingHistory && existingHistory.length > 0) {
      // Initialize history from serializable format
      historyHook.initializeFromExisting(existingHistory.map(entry => ({
        image: entry.image,
        products: entry.products,
        productIds: Array.from(entry.productIds),
        visualizedQuantities: Object.fromEntries(entry.visualizedQuantities),
      })));
    } else {
      // Just add current state to history
      historyHook.pushState({
        image: formattedImage,
        products: [...existingProducts],
        wallColor: null,  // No wall color when initializing from existing
        canvasItems: canvasItemsProp ? [...canvasItemsProp] : undefined,
      });
    }

    initializationRef.current = true;
  }, [historyHook]);

  // ============================================================================
  // Return Value
  // ============================================================================

  return {
    // State
    visualizationImage,
    isVisualizing,
    visualizationProgress,
    visualizedProductIds,
    visualizedProducts,
    visualizedQuantities,
    needsRevisualization,
    canUndo: historyHook.canUndo,
    canRedo: historyHook.canRedo,
    isEditingPositions,
    editInstructions,
    currentAngle,
    angleImages,
    loadingAngle,
    isImprovingQuality,

    // Actions
    handleVisualize,
    handleUndo,
    handleRedo,
    handleImproveQuality,
    handleAngleSelect,
    enterEditMode,
    exitEditMode,
    applyEditInstructions,
    setEditInstructions,
    resetVisualization,
    initializeFromExisting,

    // Internal setters (exposed for admin page legacy handlers)
    // These should be used sparingly and ideally removed in future refactoring
    _internal: {
      setVisualizationImage,
      setIsVisualizing,
      setVisualizationProgress,
      setVisualizedProductIds,
      setVisualizedProducts,
      setVisualizedQuantities,
      setNeedsRevisualization,
      setIsEditingPositions,
      setCurrentAngle,
      setAngleImages,
      historyHook,
    },
  };
}
