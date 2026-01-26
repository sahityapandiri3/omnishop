'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { FurniturePosition, MagicGrabLayer } from '../DraggableFurnitureCanvas';
import { furniturePositionAPI, generateAngleView } from '@/utils/api';
import { AngleSelector, ViewingAngle } from '../AngleSelector';
import { useVisualization } from '@/hooks/useVisualization';
import { VisualizationProduct, VisualizationHistoryEntry } from '@/types/visualization';
import { fetchWithRetry } from '@/utils/visualization-helpers';

const DraggableFurnitureCanvas = dynamic(
  () => import('../DraggableFurnitureCanvas').then(mod => ({ default: mod.DraggableFurnitureCanvas })),
  { ssr: false }
);

// Helper to format image source - handles base64 and URLs
const formatImageSrc = (src: string | null | undefined): string => {
  if (!src) return '';
  // If it's already a URL or data URI, return as-is
  if (src.startsWith('http') || src.startsWith('data:')) return src;
  // If it's base64 data (starts with /9j/ for JPEG or iVBOR for PNG), add data URI prefix
  if (src.startsWith('/9j/') || src.startsWith('iVBOR')) {
    const isJpeg = src.startsWith('/9j/');
    return `data:image/${isJpeg ? 'jpeg' : 'png'};base64,${src}`;
  }
  return src;
};

// Check if image source is base64 or data URI (needs <img> tag, not Next.js Image)
const isBase64Image = (src: string | null | undefined): boolean => {
  if (!src) return false;
  return src.startsWith('data:') || src.startsWith('/9j/') || src.startsWith('iVBOR');
};

// Helper function to extract dimensions from product attributes
const extractDimensions = (attrs?: Array<{ attribute_name: string; attribute_value: string }>) => {
  if (!attrs) return undefined;
  const dimensions: { width?: string; height?: string; depth?: string } = {};
  for (const attr of attrs) {
    if (attr.attribute_name === 'width') dimensions.width = attr.attribute_value;
    else if (attr.attribute_name === 'height') dimensions.height = attr.attribute_value;
    else if (attr.attribute_name === 'depth') dimensions.depth = attr.attribute_value;
  }
  // Only return if at least one dimension exists
  return (dimensions.width || dimensions.height || dimensions.depth) ? dimensions : undefined;
};

interface ProductAttribute {
  attribute_name: string;
  attribute_value: string;
}

interface Product {
  id: string;
  name: string;
  price: number;
  image_url?: string;
  images?: Array<{
    original_url?: string;
    medium_url?: string;
    large_url?: string;
    is_primary?: boolean;
  }>;
  productType?: string;
  source?: string;
  description?: string;
  quantity?: number;  // Quantity for multiple of same product (default: 1)
  attributes?: ProductAttribute[];  // Product attributes including dimensions (width, height, depth)
}

// NOTE: VisualizationHistoryEntry is now imported from @/types/visualization
// and includes visualizedQuantities for proper quantity tracking

interface CanvasPanelProps {
  products: Product[];
  roomImage: string | null;
  cleanRoomImage?: string | null;  // Clean room without products - used for reset visualization
  onRemoveProduct: (productId: string, removeAll?: boolean) => void;
  onIncrementQuantity: (productId: string) => void;  // Increment quantity for +/- controls
  onClearCanvas: () => void;
  onRoomImageUpload: (imageData: string) => void;
  onSetProducts: (products: Product[]) => void;
  onViewProductDetails?: (product: Product) => void;  // Callback to view product details
  initialVisualizationImage?: string | null;  // Pre-loaded visualization from curated looks
  initialVisualizationHistory?: any[];  // Pre-loaded history from saved project
  onVisualizationHistoryChange?: (history: any[]) => void;  // Callback when history changes
  onVisualizationImageChange?: (image: string | null) => void;  // Callback when visualization image changes
  isProcessingFurniture?: boolean;  // Show furniture removal overlay on room image
  curatedLookId?: number;  // Curated look ID for precomputation cache
  projectId?: string | null;  // Project ID for design page room analysis cache
}

/**
 * Panel 3: Canvas & Visualization
 * Features: Collapsible UI, change tracking, smart visualization states
 */
export default function CanvasPanel({
  products,
  roomImage,
  cleanRoomImage,
  onRemoveProduct,
  onIncrementQuantity,
  onClearCanvas,
  onRoomImageUpload,
  onSetProducts,
  onViewProductDetails,
  initialVisualizationImage,
  initialVisualizationHistory,
  onVisualizationHistoryChange,
  onVisualizationImageChange,
  isProcessingFurniture = false,
  curatedLookId,
  projectId,
}: CanvasPanelProps) {
  // ============================================================================
  // Use shared visualization hook - replaces most local state and handlers
  // ============================================================================
  const visualization = useVisualization({
    products: products as VisualizationProduct[],
    roomImage,
    cleanRoomImage: cleanRoomImage || roomImage,
    onSetProducts: onSetProducts as (products: VisualizationProduct[]) => void,
    config: {
      enableTextBasedEdits: false,  // CanvasPanel uses DraggableFurnitureCanvas instead
      enablePositionEditing: true,
      enableMultiAngle: true,
      enableImproveQuality: true,
      curatedLookId,
      projectId,
    },
    onVisualizationHistoryChange,
    onVisualizationImageChange,
    initialVisualizationImage,
    initialVisualizationHistory,
  });

  // Destructure hook values
  const {
    visualizationImage,
    isVisualizing,
    visualizationProgress,
    visualizedProductIds,
    visualizedProducts,
    visualizedQuantities,
    needsRevisualization,
    canUndo,
    canRedo,
    isEditingPositions,
    currentAngle,
    angleImages,
    loadingAngle,
    isImprovingQuality,
    handleVisualize,
    handleUndo,
    handleRedo,
    handleImproveQuality,
    handleAngleSelect,
    enterEditMode,
    exitEditMode,
    resetVisualization,
    initializeFromExisting,
    _internal,
  } = visualization;

  // Alias for backward compatibility with existing code
  const visualizationResult = visualizationImage;

  // Internal setters for legacy handlers (DraggableFurnitureCanvas callbacks)
  const {
    setVisualizationImage: setVisualizationResult,
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
  } = _internal;

  // History hook access for legacy patterns (DraggableFurnitureCanvas callbacks)
  const {
    pushState: pushHistoryState,
  } = historyHook;

  // ============================================================================
  // Local UI state (not part of visualization logic)
  // ============================================================================
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [visualizationStartTime, setVisualizationStartTime] = useState<number | null>(null);
  // Start expanded if user needs to upload their room image (no roomImage but has curated visualization)
  const [isRoomImageCollapsed, setIsRoomImageCollapsed] = useState(false);

  // Furniture position editing state (DraggableFurnitureCanvas-specific)
  const [furniturePositions, setFurniturePositions] = useState<FurniturePosition[]>([]);
  const [hasUnsavedPositions, setHasUnsavedPositions] = useState(false);

  // Layer extraction state for drag-and-drop editing
  const [baseRoomLayer, setBaseRoomLayer] = useState<string | null>(null);
  const [furnitureLayers, setFurnitureLayers] = useState<any[]>([]);
  const [isExtractingLayers, setIsExtractingLayers] = useState(false);

  // Magic Grab state (new SAM-based editing)
  const [magicGrabBackground, setMagicGrabBackground] = useState<string | null>(null);
  const [magicGrabLayers, setMagicGrabLayers] = useState<MagicGrabLayer[]>([]);
  const [useMagicGrab, setUseMagicGrab] = useState(true);  // Use SAM by default
  const [isCompositingLayers, setIsCompositingLayers] = useState(false);

  // Click-to-select edit mode state
  const [pendingMoveData, setPendingMoveData] = useState<any>(null);  // Pending move for Re-visualize
  const [preEditVisualization, setPreEditVisualization] = useState<string | null>(null);  // For Exit button

  // NOTE: Multi-angle viewing state (currentAngle, angleImages, loadingAngle)
  // is now provided by useVisualization hook

  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasProductsRef = useRef<HTMLDivElement>(null);
  const visualizationRef = useRef<HTMLDivElement>(null);

  // Calculate total price (accounting for quantity)
  const totalPrice = products.reduce((sum, product) => {
    const qty = product.quantity || 1;
    return sum + (product.price || 0) * qty;
  }, 0);

  // Calculate total items (accounting for quantity)
  const totalItems = products.reduce((sum, product) => sum + (product.quantity || 1), 0);

  // Update visualization progress with elapsed time
  useEffect(() => {
    if (!isVisualizing || !visualizationStartTime) return;

    const updateProgress = () => {
      const elapsed = Math.floor((Date.now() - visualizationStartTime) / 1000);
      if (elapsed < 10) {
        setVisualizationProgress('Preparing visualization...');
      } else if (elapsed < 30) {
        setVisualizationProgress(`Generating visualization (${elapsed}s)...`);
      } else if (elapsed < 60) {
        setVisualizationProgress(`Placing furniture in your space (${elapsed}s)...`);
      } else if (elapsed < 90) {
        setVisualizationProgress(`Still working - this is taking longer than usual (${elapsed}s)...`);
      } else {
        setVisualizationProgress(`Almost there - finalizing details (${elapsed}s)...`);
      }
    };

    updateProgress(); // Initial update
    const interval = setInterval(updateProgress, 1000);
    return () => clearInterval(interval);
  }, [isVisualizing, visualizationStartTime]);

  // NOTE: Change detection is now handled by useVisualization hook internally

  // Auto-scroll to canvas products when a product is added
  useEffect(() => {
    if (products.length > 0 && canvasProductsRef.current) {
      // Scroll to canvas products section
      canvasProductsRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    }
  }, [products.length]); // Trigger when product count changes

  // Auto-scroll to visualization result when first visualization completes
  useEffect(() => {
    if (visualizationResult && visualizationRef.current) {
      // Small delay to ensure render is complete
      setTimeout(() => {
        visualizationRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }, 100);
    }
  }, [visualizationResult]); // Trigger when visualization result changes

  // NOTE: The following are now handled by useVisualization hook:
  // - History initialization from props
  // - Parent notifications for history and image changes
  // - Curated look initialization
  // - Product ID and quantity sync

  // Handle file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    // Read file as base64
    const reader = new FileReader();
    reader.onload = (event) => {
      const imageData = event.target?.result as string;
      onRoomImageUpload(imageData);
      // Clear visualization and reset state when new room image is uploaded
      resetVisualization();
    };
    reader.readAsDataURL(file);

    // Reset the input value so selecting the same file triggers onChange again
    e.target.value = '';
  };

  // NOTE: detectChangeType, fetchWithRetry, handleVisualize, handleUndo, handleRedo,
  // handleImproveQuality, and handleAngleSelect are now provided by useVisualization hook
  // Reset angle state when visualization changes (sync front angle with main visualization)
  useEffect(() => {
    if (visualizationResult) {
      // When visualization changes, reset to front view and clear cached angles
      setCurrentAngle('front');
      setAngleImages({ front: visualizationResult, left: null, right: null, back: null });
    }
  }, [visualizationResult]);

  // Position editing handlers
  const handleEnterEditMode = async () => {
    console.log('=== EDIT POSITION CLICKED (Click-to-Select) ===');

    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId || !visualizationResult) {
      console.error('[CanvasPanel] No session ID or visualization found');
      alert('Error: Please create a visualization first.');
      return;
    }

    if (useMagicGrab) {
      // NEW: Click-to-Select mode - user clicks on objects to select them
      // No pre-extraction needed - SAM is called only when user clicks "Drag"
      console.log('[CanvasPanel] Entering Click-to-Select edit mode with', products.length, 'products');
      // Store pre-edit visualization for Exit button
      setPreEditVisualization(visualizationResult);
      setPendingMoveData(null);
      setIsEditingPositions(true);
      setHasUnsavedPositions(false);
      return;
    }

    // LEGACY: Marker-based edit mode
    console.log('[CanvasPanel] Using legacy marker-based edit mode...');
    setBaseRoomLayer(visualizationResult);
    setFurniturePositions([]);
    setFurnitureLayers([]);
    setIsEditingPositions(true);
    setHasUnsavedPositions(false);
    console.log('[CanvasPanel] Legacy edit mode ready - click to place markers');
  };

  // Handle final image from click-to-select mode
  const handleClickToSelectFinalImage = useCallback((newImage: string) => {
    console.log('[CanvasPanel] Click-to-Select final image received');
    setVisualizationResult(newImage);

    // Add to visualization history for undo/redo using hook's pushState
    // This properly tracks visualizedQuantities for change detection
    pushHistoryState({
      image: newImage,
      products: products as VisualizationProduct[],
    });

    // Clear pending move
    setPendingMoveData(null);
    setHasUnsavedPositions(false);

    console.log('[CanvasPanel] Edit position added to history for undo');
    // Stay in edit mode so user can move more objects
  }, [products, pushHistoryState]);

  // Handle pending move changes from DraggableFurnitureCanvas
  const handlePendingMoveChange = useCallback((hasPending: boolean, moveData?: any) => {
    if (hasPending && moveData) {
      setPendingMoveData(moveData);
      setHasUnsavedPositions(true);
    } else {
      setPendingMoveData(null);
      setHasUnsavedPositions(false);
    }
  }, []);

  // Handle Re-visualize for edit mode (finalize the move)
  const handleEditModeRevisualize = useCallback(async () => {
    if (!pendingMoveData) {
      console.error('[CanvasPanel] No pending move data');
      return;
    }

    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId) {
      console.error('[CanvasPanel] No session ID');
      return;
    }

    setIsVisualizing(true);
    setVisualizationStartTime(Date.now());
    setVisualizationProgress('Moving product to new position...');

    try {
      const result = await furniturePositionAPI.finalizeMove(
        sessionId,
        pendingMoveData.originalImage,
        pendingMoveData.mask,
        pendingMoveData.cutout,
        pendingMoveData.originalPosition,
        pendingMoveData.newPosition,
        pendingMoveData.scale,
        pendingMoveData.inpaintedBackground,
        pendingMoveData.matchedProductId
      );

      // Update with the new image
      handleClickToSelectFinalImage(result.image);
      console.log('[CanvasPanel] Edit mode re-visualization complete');

    } catch (error: any) {
      console.error('[CanvasPanel] Edit mode re-visualization failed:', error);
      alert(error?.response?.data?.detail || error?.message || 'Failed to move product');
    } finally {
      setIsVisualizing(false);
      setVisualizationStartTime(null);
      setVisualizationProgress('');
    }
  }, [pendingMoveData, handleClickToSelectFinalImage]);


  // Handle Magic Grab layers change (real-time drag updates)
  const handleMagicGrabLayersChange = (updatedLayers: MagicGrabLayer[]) => {
    setMagicGrabLayers(updatedLayers);
    setHasUnsavedPositions(true);
  };

  // Handle Magic Grab finalization (composite layers and save)
  const handleFinishMagicGrab = async () => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId || !magicGrabBackground || magicGrabLayers.length === 0) {
      console.error('[CanvasPanel] Cannot finish: missing data');
      return;
    }

    setIsCompositingLayers(true);

    try {
      console.log('[CanvasPanel] Compositing layers...', { layersCount: magicGrabLayers.length });

      // Call composite-layers API
      const result = await furniturePositionAPI.compositeLayers(
        sessionId,
        magicGrabBackground,
        magicGrabLayers.map(layer => ({
          id: layer.id,
          cutout: layer.cutout,
          x: layer.x,
          y: layer.y,
          scale: layer.scale || 1.0,
          rotation: layer.rotation || 0,
          opacity: 1.0,
          z_index: layer.zIndex || 0,
        })),
        false  // harmonize = false for faster results (can enable if needed)
      );

      console.log('[CanvasPanel] Compositing complete:', {
        hasImage: !!result.image,
        time: result.processing_time,
      });

      if (result.image) {
        // Update visualization with composited result
        setVisualizationResult(result.image);

        // Add to history for undo using hook's pushState
        // This properly tracks visualizedQuantities for change detection
        pushHistoryState({
          image: result.image,
          products: products as VisualizationProduct[],
        });

        // Exit edit mode
        setIsEditingPositions(false);
        setMagicGrabBackground(null);
        setMagicGrabLayers([]);
        setHasUnsavedPositions(false);

        console.log('[CanvasPanel] Magic Grab edit complete!');
      }
    } catch (error: any) {
      console.error('[CanvasPanel] Error compositing layers:', error);
      alert(`Error applying changes: ${error.message || 'Please try again.'}`);
    } finally {
      setIsCompositingLayers(false);
    }
  };

  // Exit without saving - revert to pre-edit visualization
  const handleExitEditMode = () => {
    if (hasUnsavedPositions) {
      const confirmExit = window.confirm('You have unsaved changes. Exit without saving?');
      if (!confirmExit) return;
    }

    // Revert to pre-edit visualization
    if (preEditVisualization) {
      setVisualizationResult(preEditVisualization);
    }

    setIsEditingPositions(false);
    setHasUnsavedPositions(false);
    setPendingMoveData(null);
    setPreEditVisualization(null);
    // Clean up Magic Grab state
    setMagicGrabBackground(null);
    setMagicGrabLayers([]);
  };

  // Save and exit - keep current visualization
  const handleSaveAndExitEditMode = () => {
    console.log('[CanvasPanel] Save & Exit edit mode');
    setIsEditingPositions(false);
    setHasUnsavedPositions(false);
    setPendingMoveData(null);
    setPreEditVisualization(null);
    // Clean up Magic Grab state
    setMagicGrabBackground(null);
    setMagicGrabLayers([]);
  };

  const handlePositionsChange = (newPositions: FurniturePosition[]) => {
    setFurniturePositions(newPositions);
    setHasUnsavedPositions(true);
  };

  const handleSavePositions = async () => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId) {
      console.error('[CanvasPanel] No session ID found');
      alert('Error: No session found. Please create a visualization first.');
      return;
    }

    try {
      console.log('[CanvasPanel] Saving positions:', furniturePositions);
      const result = await furniturePositionAPI.savePositions(sessionId, furniturePositions);
      console.log('[CanvasPanel] Positions saved successfully:', result);
      setHasUnsavedPositions(false);
      // Position saved silently - button will be disabled until next change
    } catch (error) {
      console.error('[CanvasPanel] Error saving positions:', error);
      alert('Error saving positions. Please try again.');
    }
  };

  const handleRevisualizeWithPositions = async () => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId || !roomImage) {
      console.error('[CanvasPanel] No session ID or room image found');
      alert('Error: No session or room image found. Please start over.');
      return;
    }

    setIsVisualizing(true);

    try {
      console.log('[CanvasPanel] Re-visualizing with new positions:', furniturePositions);

      // Step 1: Save positions to backend
      console.log('[CanvasPanel] Saving positions before re-visualization...');
      await furniturePositionAPI.savePositions(sessionId, furniturePositions);
      console.log('[CanvasPanel] Positions saved successfully');

      // Step 2: Call visualization API with custom positions
      console.log('[CanvasPanel] Calling visualization API with custom positions...');

      // Prepare products for API
      const productDetails = products.map(p => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        style: 0.8,
        category: 'furniture'
      }));

      // Call API with custom_positions using retry logic
      const response = await fetchWithRetry(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: roomImage,
            products: productDetails,
            analysis: {
              design_style: 'modern',
              color_palette: [],
              room_type: 'living_room',
            },
            custom_positions: furniturePositions,  // Pass custom positions
            is_incremental: false,
            force_reset: false,
            curated_look_id: curatedLookId,  // Pass curated look ID for precomputation cache
          }),
        },
        {
          maxRetries: 2,
          timeoutMs: 180000,  // 3 minutes
          retryDelayMs: 3000  // 3 seconds
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Visualization failed');
      }

      const data = await response.json();
      console.log('[CanvasPanel] Visualization response received, image length:', data.visualization?.rendered_image?.length || 0);

      if (!data.visualization?.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      // Update visualization result
      setVisualizationResult(data.visualization.rendered_image);
      setVisualizedProductIds(new Set(products.map(p => String(p.id))));
      setNeedsRevisualization(false);

      // Step 3: Exit edit mode and reset state
      setIsEditingPositions(false);
      setHasUnsavedPositions(false);
      console.log('[CanvasPanel] Re-visualization complete, exited edit mode');
    } catch (error: any) {
      console.error('[CanvasPanel] Error re-visualizing with positions:', error);

      let errorMessage = 'Failed to re-visualize with new positions. Please try again.';
      if (error.name === 'AbortError') {
        errorMessage = 'Request timed out after multiple attempts. Please try again.';
      } else if (error.message?.includes('after all retries')) {
        errorMessage = 'Server is temporarily unavailable. Please try again in a few moments.';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      }

      alert(errorMessage);
    } finally {
      setIsVisualizing(false);
    }
  };

  // Get image URL from product (handles both old and new format)
  const getProductImageUrl = (product: Product): string => {
    // Try images array first (transformed format)
    if (product.images && product.images.length > 0) {
      const primaryImage = product.images.find(img => img.is_primary) || product.images[0];
      return primaryImage.large_url || primaryImage.medium_url || primaryImage.original_url || '/placeholder-product.jpg';
    }
    // Fall back to image_url
    return product.image_url || '/placeholder-product.jpg';
  };

  // Determine button state
  // Can visualize if we have any base image (prefer cleanRoomImage) and products
  const canVisualize = (roomImage !== null || cleanRoomImage !== null) && products.length > 0;
  const isUpToDate = canVisualize && !needsRevisualization && visualizationResult !== null;
  const isReady = canVisualize && (needsRevisualization || visualizationResult === null);

  // Check if user came from curated looks with products but no room image
  // Don't show full-screen overlay if we have a visualization already (from curated looks)
  const needsRoomImageUpload = products.length > 0 && !roomImage && !visualizationResult && !initialVisualizationImage;

  return (
    <div className="flex flex-col h-full overflow-hidden relative">
      {/* Prominent Upload Prompt - shown when products loaded but no room image */}
      {needsRoomImageUpload && (
        <div className="absolute inset-0 z-20 bg-gradient-to-br from-primary-50 to-secondary-50 dark:from-neutral-800 dark:to-neutral-900 flex flex-col items-center justify-center p-6">
          <div className="max-w-sm text-center">
            {/* Icon */}
            <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-primary-500 to-secondary-500 rounded-2xl flex items-center justify-center shadow-lg">
              <svg
                className="w-10 h-10 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </div>

            {/* Title */}
            <h2 className="text-2xl font-bold text-neutral-900 dark:text-white mb-3">
              Upload Your Room
            </h2>

            {/* Description */}
            <p className="text-neutral-600 dark:text-neutral-400 mb-2">
              You have <span className="font-semibold text-primary-600 dark:text-primary-400">{products.length} curated products</span> ready to visualize!
            </p>
            <p className="text-sm text-neutral-500 dark:text-neutral-500 mb-6">
              Upload a photo of your room to see how these products will look in your space.
            </p>

            {/* Upload Button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-4 px-6 bg-gradient-to-r from-primary-600 to-secondary-600 hover:from-primary-700 hover:to-secondary-700 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Upload Room Photo
            </button>

            {/* File format info */}
            <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-3">
              JPG, PNG, WEBP • Max 10MB
            </p>

            {/* Products preview */}
            <div className="mt-6 pt-6 border-t border-neutral-200 dark:border-neutral-700">
              <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">Products ready to visualize:</p>
              <div className="flex justify-center gap-2 flex-wrap">
                {products.slice(0, 4).map((product) => (
                  <div key={product.id} className="w-12 h-12 bg-white dark:bg-neutral-700 rounded-lg shadow overflow-hidden">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-neutral-400">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                        </svg>
                      </div>
                    )}
                  </div>
                ))}
                {products.length > 4 && (
                  <div className="w-12 h-12 bg-neutral-100 dark:bg-neutral-700 rounded-lg flex items-center justify-center text-xs font-semibold text-neutral-600 dark:text-neutral-300">
                    +{products.length - 4}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="p-4 border-b border-neutral-200 dark:border-neutral-700 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold text-neutral-900 dark:text-white">
            Your Canvas
          </h2>
          {products.length > 0 && (
            <button
              onClick={onClearCanvas}
              className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium"
            >
              Clear All
            </button>
          )}
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-neutral-600 dark:text-neutral-400">
            {totalItems} {totalItems === 1 ? 'item' : 'items'}
            {products.length !== totalItems && (
              <span className="text-neutral-400 dark:text-neutral-500"> ({products.length} unique)</span>
            )}
          </span>
          {products.length > 0 && (
            <span className="font-semibold text-neutral-900 dark:text-white">
              ₹{totalPrice.toLocaleString()}
            </span>
          )}
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto">
        {/* Collapsible Room Image Section */}
        <div className="border-b border-neutral-200 dark:border-neutral-700">
          <button
            onClick={() => setIsRoomImageCollapsed(!isRoomImageCollapsed)}
            className="w-full p-4 flex items-center justify-between hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
          >
            <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
              Room Image
            </h3>
            <svg
              className={`w-5 h-5 text-neutral-600 dark:text-neutral-400 transition-transform ${isRoomImageCollapsed ? '' : 'rotate-180'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {!isRoomImageCollapsed && (
            <div className="p-4 pt-0">
              {roomImage ? (
                <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden">
                  {isBase64Image(roomImage) ? (
                    <img
                      src={formatImageSrc(roomImage)}
                      alt="Room"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <Image
                      src={roomImage}
                      alt="Room"
                      fill
                      className="object-cover"
                    />
                  )}
                  {/* Image Processing Loading Overlay */}
                  {isProcessingFurniture && (
                    <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-10">
                      <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-500 mb-2"></div>
                      <span className="text-white font-medium text-sm">Processing Image...</span>
                    </div>
                  )}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="absolute bottom-2 right-2 px-3 py-1.5 bg-gradient-to-r from-primary-600 to-secondary-600 hover:from-primary-700 hover:to-secondary-700 backdrop-blur text-xs font-medium text-white rounded-lg transition-all shadow-md hover:shadow-lg flex items-center gap-1.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    Upload Your Room
                  </button>
                </div>
              ) : (
                <div className="aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg flex flex-col items-center justify-center p-4 border-2 border-dashed border-neutral-300 dark:border-neutral-600">
                  <svg
                    className="w-12 h-12 text-neutral-400 mb-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Upload Your Room Image
                  </button>
                  <p className="text-xs text-neutral-600 dark:text-neutral-300 mt-2 text-center">
                    Add your room image to style with these products
                  </p>
                  <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
                    JPG, PNG, WEBP • Max 10MB
                  </p>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>
          )}
        </div>

        {/* Products in Canvas */}
        <div ref={canvasProductsRef} className="p-4 border-b border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
              Products in Canvas
            </h3>
            {products.length > 0 && (
              <div className="flex gap-1 bg-neutral-100 dark:bg-neutral-700 rounded-lg p-1">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-1.5 rounded ${
                    viewMode === 'grid'
                      ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white'
                      : 'text-neutral-600 dark:text-neutral-400'
                  }`}
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-1.5 rounded ${
                    viewMode === 'list'
                      ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white'
                      : 'text-neutral-600 dark:text-neutral-400'
                  }`}
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              </div>
            )}
          </div>

          {products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-16 h-16 bg-neutral-100 dark:bg-neutral-700 rounded-full flex items-center justify-center mb-3">
                <svg
                  className="w-8 h-8 text-neutral-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                  />
                </svg>
              </div>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                No products added yet
              </p>
              <p className="text-xs text-neutral-500 dark:text-neutral-500 mt-1">
                Select products from the discovery panel
              </p>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-3 gap-2">
              {products.map((product) => {
                const imageUrl = getProductImageUrl(product);
                const qty = product.quantity || 1;
                return (
                  <div
                    key={product.id}
                    className="relative bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden group"
                  >
                    <div className="aspect-square bg-neutral-100 dark:bg-neutral-700 relative">
                      {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
                        <Image
                          src={imageUrl}
                          alt={product.name}
                          fill
                          className="object-cover"
                          unoptimized
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                      {/* Quantity badge */}
                      <div className="absolute top-0.5 left-0.5 bg-primary-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {qty}x
                      </div>
                      {/* Hover overlay with actions */}
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1.5">
                        {/* Quantity controls */}
                        <div className="flex items-center gap-1 bg-white rounded-lg px-1.5 py-0.5">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onRemoveProduct(product.id);
                            }}
                            className="w-5 h-5 bg-neutral-200 hover:bg-neutral-300 rounded text-xs font-bold flex items-center justify-center"
                            title={qty > 1 ? "Decrease quantity" : "Remove"}
                          >
                            -
                          </button>
                          <span className="w-4 text-center font-semibold text-xs">{qty}</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onIncrementQuantity(product.id);
                            }}
                            className="w-5 h-5 bg-primary-600 hover:bg-primary-700 text-white rounded text-xs font-bold flex items-center justify-center"
                            title="Increase quantity"
                          >
                            +
                          </button>
                        </div>
                        {/* Remove button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onRemoveProduct(product.id, true);
                          }}
                          className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] font-medium rounded-lg flex items-center gap-1"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                          Remove
                        </button>
                        {/* View Details button */}
                        {onViewProductDetails && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onViewProductDetails(product);
                            }}
                            className="px-2 py-1 bg-white/90 hover:bg-white text-neutral-800 text-[10px] font-medium rounded-lg flex items-center gap-1"
                          >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            View Details
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="p-1">
                      <p className="text-[10px] font-medium text-neutral-900 dark:text-white line-clamp-1">
                        {product.name}
                      </p>
                      {product.price && (
                        <p className="text-[10px] text-primary-600 dark:text-primary-400 font-semibold">
                          ₹{(product.price * qty).toLocaleString()}
                          {qty > 1 && <span className="text-neutral-400 font-normal"> (₹{product.price.toLocaleString()} x {qty})</span>}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="space-y-1.5">
              {products.map((product) => {
                const imageUrl = getProductImageUrl(product);
                const qty = product.quantity || 1;
                return (
                  <div
                    key={product.id}
                    className="flex items-center gap-2 p-2 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg"
                  >
                    <div className="w-12 h-12 bg-neutral-100 dark:bg-neutral-700 rounded relative flex-shrink-0">
                      {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
                        <Image
                          src={imageUrl}
                          alt={product.name}
                          fill
                          className="object-cover rounded"
                          unoptimized
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <svg className="w-6 h-6 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                      {/* Quantity badge */}
                      {qty > 1 && (
                        <div className="absolute -top-1 -right-1 w-4 h-4 bg-primary-600 text-white rounded-full flex items-center justify-center text-[9px] font-bold">
                          {qty}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-medium text-neutral-900 dark:text-white truncate">
                        {product.name}
                      </p>
                      <p className="text-[10px] text-neutral-600 dark:text-neutral-400">
                        {product.source}
                      </p>
                      {product.price && (
                        <p className="text-xs font-semibold text-primary-600 dark:text-primary-400">
                          ₹{(product.price * qty).toLocaleString()}
                          {qty > 1 && <span className="text-neutral-400 font-normal text-[10px]"> (x{qty})</span>}
                        </p>
                      )}
                    </div>
                    {/* Quantity controls */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => onRemoveProduct(product.id)}
                        className="w-6 h-6 bg-neutral-200 dark:bg-neutral-700 hover:bg-neutral-300 dark:hover:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded flex items-center justify-center text-sm font-bold"
                        title={qty > 1 ? "Decrease quantity" : "Remove"}
                      >
                        −
                      </button>
                      <span className="w-5 text-center text-xs font-semibold text-neutral-900 dark:text-white">
                        {qty}
                      </span>
                      <button
                        onClick={() => onIncrementQuantity(product.id)}
                        className="w-6 h-6 bg-primary-100 dark:bg-primary-900/30 hover:bg-primary-200 dark:hover:bg-primary-900/50 text-primary-700 dark:text-primary-300 rounded flex items-center justify-center text-sm font-bold"
                        title="Increase quantity"
                      >
                        +
                      </button>
                    </div>
                    {/* Remove all button */}
                    <button
                      onClick={() => onRemoveProduct(product.id, true)}
                      className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 p-0.5"
                      title="Remove all"
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Visualization In Progress - Shimmer Preview */}
        {isVisualizing && !visualizationResult && roomImage && (
          <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
                Generating Visualization...
              </h3>
            </div>
            <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden">
              {/* Room image as preview background */}
              {isBase64Image(roomImage) ? (
                <img
                  src={formatImageSrc(roomImage)}
                  alt="Room preview"
                  className="w-full h-full object-cover opacity-60"
                />
              ) : (
                <Image
                  src={roomImage}
                  alt="Room preview"
                  fill
                  className="object-cover opacity-60"
                />
              )}
              {/* Shimmer overlay animation */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
                   style={{ backgroundSize: '200% 100%' }} />
              {/* Progress indicator */}
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20">
                <div className="bg-black/60 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center">
                  <svg className="animate-spin h-8 w-8 text-white mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="text-white font-medium text-sm">{visualizationProgress || 'Placing furniture...'}</span>
                  <span className="text-white/70 text-xs mt-1">Omni is styling your space</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Visualization Result with Outdated Warning */}
        {visualizationResult && (
          <div ref={visualizationRef} className="p-4 border-b border-neutral-200 dark:border-neutral-700">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
                Visualization Result
              </h3>
              <div className="flex items-center gap-2">
                {/* Edit Positions button */}
                {!isEditingPositions && (
                  <button
                    onClick={handleEnterEditMode}
                    disabled={isExtractingLayers}
                    className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white text-xs font-medium transition-colors flex items-center gap-1.5 disabled:cursor-not-allowed"
                    title="Edit furniture positions"
                  >
                    {isExtractingLayers ? (
                      <>
                        <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Extracting Layers...
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Edit Positions
                      </>
                    )}
                  </button>
                )}

                {/* Undo/Redo buttons */}
                <button
                  onClick={handleUndo}
                  disabled={!canUndo || isEditingPositions}
                  className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Undo (Remove last added product)"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                  </svg>
                </button>
                <button
                  onClick={handleRedo}
                  disabled={!canRedo || isEditingPositions}
                  className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Redo (Add back removed product)"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6" />
                  </svg>
                </button>
                <button
                  onClick={() => {
                    setVisualizationResult(null);
                    setVisualizedProductIds(new Set()); // Clear tracking so next visualization is treated as fresh
                    setNeedsRevisualization(false);
                  }}
                  disabled={isEditingPositions}
                  className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Multi-Angle Viewer */}
            {!isEditingPositions && (
              <div className="mb-3">
                <AngleSelector
                  currentAngle={currentAngle}
                  loadingAngle={loadingAngle}
                  availableAngles={Object.entries(angleImages)
                    .filter(([_, img]) => img !== null)
                    .map(([angle]) => angle as ViewingAngle)}
                  onAngleSelect={handleAngleSelect}
                  disabled={isVisualizing || needsRevisualization}
                />
              </div>
            )}

            {/* Outdated Warning Banner */}
            {needsRevisualization && (
              <div className="mb-2 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg flex items-center gap-2">
                <svg className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <p className="text-xs text-amber-800 dark:text-amber-200 font-medium">
                  Canvas changed - Re-visualize to update
                </p>
              </div>
            )}

            {/* Image/Canvas Container - aspect-video only when NOT editing positions */}
            <div className={`relative ${isEditingPositions ? '' : 'aspect-video'} bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden ${needsRevisualization ? 'ring-2 ring-amber-400 dark:ring-amber-600' : ''} ${isEditingPositions ? 'ring-2 ring-purple-400 dark:ring-purple-600' : ''}`}>
              {isEditingPositions ? (
                useMagicGrab ? (
                  // Click-to-Select mode - click on objects, then drag
                  <DraggableFurnitureCanvas
                    mode="click-to-select"
                    visualizationImage={visualizationResult!}
                    sessionId={sessionStorage.getItem('design_session_id') || ''}
                    onFinalImage={handleClickToSelectFinalImage}
                    onPendingMoveChange={handlePendingMoveChange}
                    containerWidth={800}
                    containerHeight={450}
                    curatedProducts={(visualizedProducts.length > 0 ? visualizedProducts : products).map(p => {
                      // Use visualizedProducts (products IN the visualization) for matching
                      // Fall back to current products if visualizedProducts is empty
                      const primaryImage = p.images?.find(img => img.is_primary) || p.images?.[0];
                      const imageUrl = primaryImage?.medium_url || primaryImage?.original_url || p.image_url;
                      return {
                        id: typeof p.id === 'number' ? p.id : parseInt(String(p.id)) || 0,
                        name: p.name,
                        image_url: imageUrl
                      };
                    })}
                  />
                ) : (
                  // Legacy marker mode
                  <DraggableFurnitureCanvas
                    mode="legacy"
                    visualizationImage={visualizationResult!}
                    baseRoomLayer={baseRoomLayer}
                    furnitureLayers={furnitureLayers}
                    furniturePositions={furniturePositions}
                    onPositionsChange={handlePositionsChange}
                    products={products}
                    containerWidth={800}
                    containerHeight={450}
                  />
                )
              ) : (
                <>
                  {/* Display current angle image (front = main visualization, others = generated on-demand) */}
                  {(() => {
                    const displayImage = currentAngle === 'front'
                      ? visualizationResult
                      : (angleImages[currentAngle] || visualizationResult);
                    return isBase64Image(displayImage) ? (
                      <img
                        src={formatImageSrc(displayImage)}
                        alt={`Visualization result - ${currentAngle} view`}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Image
                        src={displayImage!}
                        alt={`Visualization result - ${currentAngle} view`}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    );
                  })()}
                  {/* Angle indicator badge */}
                  {currentAngle !== 'front' && (
                    <div className="absolute top-2 left-2 px-2 py-1 bg-black/60 text-white text-xs font-medium rounded-md">
                      {currentAngle.charAt(0).toUpperCase() + currentAngle.slice(1)} View
                    </div>
                  )}
                  {/* Re-visualization / Improve Quality / Edit shimmer overlay */}
                  {(isVisualizing || isImprovingQuality || isCompositingLayers) && (
                    <>
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
                           style={{ backgroundSize: '200% 100%' }} />
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20">
                        <div className="bg-black/60 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center">
                          <svg className="animate-spin h-8 w-8 text-white mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span className="text-white font-medium text-sm">
                            {isImprovingQuality ? 'Improving quality...' :
                             isCompositingLayers ? 'Applying position changes...' :
                             'Updating visualization...'}
                          </span>
                          <span className="text-white/70 text-xs mt-1">
                            {isImprovingQuality ? 'Re-rendering from original room' :
                             isCompositingLayers ? 'Finalizing edits' :
                             'Omni is updating your space'}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {/* Edit Mode Actions - Only show for legacy mode since click-to-select has its own buttons */}
            {isEditingPositions && !useMagicGrab && (
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={handleExitEditMode}
                  className="px-4 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Save & Exit / Exit buttons for click-to-select mode */}
            {isEditingPositions && useMagicGrab && (
              <div className="mt-3 flex items-center justify-center gap-2">
                <button
                  onClick={handleSaveAndExitEditMode}
                  className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition-colors"
                >
                  Save & Exit
                </button>
                <button
                  onClick={handleExitEditMode}
                  className="px-4 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 text-sm font-medium transition-colors"
                >
                  Exit
                </button>
              </div>
            )}

            {/* Unsaved Changes Warning */}
            {hasUnsavedPositions && isEditingPositions && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-2 text-center flex items-center justify-center gap-1">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                You have unsaved position changes
              </p>
            )}

            {!needsRevisualization && !isEditingPositions && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-2 text-center">
                ✓ Visualization up to date
              </p>
            )}
          </div>
        )}
      </div>

      {/* Visualize Button with Smart States - Fixed at bottom */}
      <div className="p-4 border-t border-neutral-200 dark:border-neutral-700 flex-shrink-0">
        {isEditingPositions && hasUnsavedPositions && useMagicGrab ? (
          // State: Click-to-Select Edit Mode with Pending Move (Purple, Enabled)
          <button
            onClick={handleEditModeRevisualize}
            disabled={isVisualizing || !pendingMoveData}
            className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-neutral-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
          >
            {isVisualizing ? (
              <>
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                <span className="text-sm">Moving product...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Re-visualize
              </>
            )}
          </button>
        ) : isEditingPositions && hasUnsavedPositions ? (
          // State: Legacy Edit Mode with Unsaved Positions (Purple, Enabled)
          <button
            onClick={handleRevisualizeWithPositions}
            disabled={isVisualizing}
            className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-neutral-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
          >
            {isVisualizing ? (
              <>
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                <span className="text-sm">Re-visualizing...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Re-visualize with New Positions
              </>
            )}
          </button>
        ) : isUpToDate ? (
          // State 2: Up to Date (Green, Disabled)
          <button
            disabled
            className="w-full py-3 px-4 bg-green-500 dark:bg-green-600 text-white font-semibold rounded-lg flex items-center justify-center gap-2 cursor-not-allowed opacity-90"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Up to date
          </button>
        ) : isReady ? (
          // State 1: Ready to Visualize (Primary gradient, Enabled)
          <button
            onClick={handleVisualize}
            disabled={isVisualizing}
            className="w-full py-3 px-4 bg-gradient-to-r from-primary-600 to-secondary-600 hover:from-primary-700 hover:to-secondary-700 disabled:from-neutral-400 disabled:to-neutral-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
          >
            {isVisualizing ? (
              <>
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                <span className="text-sm">Visualizing...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                  <path
                    fillRule="evenodd"
                    d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Visualize Room
              </>
            )}
          </button>
        ) : (
          // State 3: Not Ready (Gray, Disabled)
          <button
            disabled
            className="w-full py-3 px-4 bg-neutral-300 dark:bg-neutral-700 text-neutral-500 dark:text-neutral-400 font-semibold rounded-lg cursor-not-allowed flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
              <path
                fillRule="evenodd"
                d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"
                clipRule="evenodd"
              />
            </svg>
            Visualize Room
          </button>
        )}

        {/* Helper Messages */}
        {!roomImage && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-2 text-center">
            Upload a room image to visualize
          </p>
        )}
        {roomImage && products.length === 0 && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-2 text-center">
            Add products to canvas to visualize
          </p>
        )}
        {isUpToDate && (
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2 text-center">
            Visualization matches current canvas
          </p>
        )}

        {/* Improve Quality - Advanced action at bottom */}
        {visualizationResult && products.length > 0 && (
          <div className="mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700">
            <button
              onClick={handleImproveQuality}
              disabled={isImprovingQuality || isVisualizing}
              className="w-full py-2 px-3 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 disabled:bg-neutral-50 dark:disabled:bg-neutral-900 disabled:cursor-not-allowed text-neutral-600 dark:text-neutral-300 disabled:text-neutral-400 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
              title="Re-visualize all products on the original room image to improve quality. Resets undo/redo history."
            >
              {isImprovingQuality ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Improving Quality...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Improve Quality
                </>
              )}
            </button>
            <p className="text-xs text-neutral-400 dark:text-neutral-500 text-center mt-1">Re-renders from original room image. Resets undo/redo.</p>
          </div>
        )}
      </div>
    </div>
  );
}
