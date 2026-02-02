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
import {
  useVisualizationHistory,
  UseVisualizationHistoryReturn,
} from './useVisualizationHistory';
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

  /** Callback to update products (e.g., from undo/redo) */
  onSetProducts: (products: VisualizationProduct[]) => void;

  /** Callback to update wall color (e.g., from undo/redo) */
  onSetWallColor?: (wallColor: WallColor | null) => void;

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
  products,
  roomImage,
  cleanRoomImage,
  wallColor,
  onSetProducts,
  onSetWallColor,
  onVisualizationImageChange,
  onVisualizationHistoryChange,
  initialVisualizationImage,
  initialVisualizationHistory = [],
  config = {},
}: UseVisualizationProps): UseVisualizationReturn {
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
    if (visualizedProductIds.size === 0 && !visualizationImage && !visualizedWallColor) {
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
    // Note: wallColor can be undefined (optional prop) or null (explicitly cleared)
    // IMPORTANT: Only consider wall color "changed" if we have already done at least one visualization
    // with products. This prevents triggering re-visualization when setting wall color for the first time.
    const currentWallColor = wallColor ?? null;
    const hasExistingVisualization = visualizedProductIds.size > 0 || visualizationImage;
    const wallColorChanged = hasExistingVisualization && (
      (currentWallColor === null && visualizedWallColor !== null) ||
      (currentWallColor !== null && visualizedWallColor === null) ||
      (currentWallColor !== null && visualizedWallColor !== null && currentWallColor.id !== visualizedWallColor.id)
    );

    if (productsChanged || quantitiesChanged || wallColorChanged) {
      setNeedsRevisualization(true);
      if (wallColorChanged) {
        console.log('[useVisualization] Wall color changed, needs re-visualization');
      } else if (quantitiesChanged && !productsChanged) {
        console.log('[useVisualization] Quantity changed, needs re-visualization');
      }
    }
  }, [products, visualizedProductIds, visualizedQuantities, visualizationImage, wallColor, visualizedWallColor]);

  // ============================================================================
  // Sync Effect: Keep visualizedProducts in sync when products change
  // ============================================================================

  useEffect(() => {
    // If we have a visualization but visualizedProductIds is empty, sync from products
    if (visualizationImage && products.length > 0 && visualizedProductIds.size === 0) {
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

    // Track the room image used for this visualization
    const baseImage = cleanRoomImage || roomImage;
    if (baseImage) {
      setVisualizedRoomImage(baseImage);
    }

    // Add to history (including wall color if present)
    historyHook.pushState({
      image: formattedImage,
      products: [...products],
      wallColor: wallColor || null,
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
    if (!baseImage || products.length === 0) return;

    console.log('[useVisualization] handleVisualize called with', products.length, 'products');

    setIsVisualizing(true);
    setVisualizationStartTime(Date.now());
    setVisualizationProgress('Preparing visualization...');

    try {
      // Check for wall color changes
      const currentWallColor = wallColor ?? null;
      const wallColorChanged = (
        (currentWallColor === null && visualizedWallColor !== null) ||
        (currentWallColor !== null && visualizedWallColor === null) ||
        (currentWallColor !== null && visualizedWallColor !== null && currentWallColor.id !== visualizedWallColor.id)
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

      console.log('[useVisualization] Change detection result:', changeInfo.type, changeInfo.reason, 'wallColorChanged:', wallColorChanged, 'roomImageChanged:', roomImageChanged);

      if (changeInfo.type === 'no_change' && !wallColorChanged && !roomImageChanged) {
        console.log('[useVisualization] No changes detected, skipping');
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
      } else if (changeInfo.type === 'no_change' && wallColorChanged) {
        // Wall color changed but products didn't - apply wall color to existing visualization
        imageToUse = visualizationImage!;
        productsToVisualize = [];  // No products to add, just wall color change
        console.log('[useVisualization] Wall color only change');
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
            wall_color: wallColor ? {
              name: wallColor.name,
              code: wallColor.code,
              hex_value: wallColor.hex_value,
            } : undefined,
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

      // Update state with new visualization
      const newImage = data.visualization.rendered_image;
      const newProductIds = buildProductIdSet(products);
      const newQuantities = buildQuantityMap(products);

      setVisualizationImage(newImage);
      setVisualizedProductIds(newProductIds);
      setVisualizedProducts([...products]);
      setVisualizedQuantities(newQuantities);
      setVisualizedWallColor(wallColor || null);
      setVisualizedRoomImage(baseImage);  // CRITICAL: Track which room image was used
      setNeedsRevisualization(false);

      // Push to history (including wall color)
      historyHook.pushState({
        image: newImage,
        products: [...products],
        wallColor: wallColor || null,
      });

      console.log('[useVisualization] Visualization successful, tracked room image');

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
    config.curatedLookId, config.projectId, historyHook
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
      onSetProducts(previousState.products);
      // Notify parent to update wall color state
      if (onSetWallColor) {
        onSetWallColor(previousState.wallColor || null);
      }
    } else {
      // No previous state - clear visualization
      console.log('[useVisualization] No previous state - clearing visualization');
      setVisualizationImage(null);
      setVisualizedProductIds(new Set());
      setVisualizedProducts([]);
      setVisualizedQuantities(new Map());
      setVisualizedWallColor(null);
      onSetProducts([]);
      // Clear wall color in parent
      if (onSetWallColor) {
        onSetWallColor(null);
      }
    }

    console.log('[useVisualization] Undo complete');
  }, [historyHook, onSetProducts, onSetWallColor]);

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
      onSetProducts(stateToRestore.products);
      // Notify parent to update wall color state
      if (onSetWallColor) {
        onSetWallColor(stateToRestore.wallColor || null);
      }
    }

    console.log('[useVisualization] Redo complete');
  }, [historyHook, onSetProducts, onSetWallColor]);

  // ============================================================================
  // Handle Improve Quality
  // ============================================================================

  const handleImproveQuality = useCallback(async () => {
    const baseImage = cleanRoomImage || roomImage;
    if (!baseImage || products.length === 0) {
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

      const newImage = data.visualization.rendered_image;
      console.log('[useVisualization] Quality improvement success');

      // Update visualization
      setVisualizationImage(newImage);

      // Reset history with new state (including wall color)
      historyHook.reset();
      historyHook.pushState({
        image: newImage,
        products: [...products],
        wallColor: wallColor || null,
      });

      // Update visualized state
      setVisualizedProductIds(buildProductIdSet(products));
      setVisualizedProducts([...products]);
      setVisualizedQuantities(buildQuantityMap(products));
      setVisualizedWallColor(wallColor || null);
      setVisualizedRoomImage(baseImage);  // CRITICAL: Track which room image was used
      setNeedsRevisualization(false);

    } catch (error) {
      console.error('[useVisualization] Quality improvement error:', error);
      alert(`Failed to improve quality: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsImprovingQuality(false);
    }
  }, [products, roomImage, cleanRoomImage, config.curatedLookId, config.projectId, historyHook]);

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

      // Add to history (including wall color)
      historyHook.pushState({
        image: data.image,
        products: [...visualizedProducts],
        wallColor: visualizedWallColor,
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
