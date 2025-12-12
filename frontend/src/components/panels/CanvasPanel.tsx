'use client';

import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { FurniturePosition } from '../DraggableFurnitureCanvas';
import { furniturePositionAPI } from '@/utils/api';

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
}

// Visualization history entry for local undo/redo tracking
// This fixes the issue where backend in-memory state is lost on server restart
interface VisualizationHistoryEntry {
  image: string;
  products: Product[];
  productIds: Set<string>;
}

interface CanvasPanelProps {
  products: Product[];
  roomImage: string | null;
  cleanRoomImage?: string | null;  // Clean room without products - used for reset visualization
  onRemoveProduct: (productId: string) => void;
  onClearCanvas: () => void;
  onRoomImageUpload: (imageData: string) => void;
  onSetProducts: (products: Product[]) => void;
  initialVisualizationImage?: string | null;  // Pre-loaded visualization from curated looks
  initialVisualizationHistory?: any[];  // Pre-loaded history from saved project
  onVisualizationHistoryChange?: (history: any[]) => void;  // Callback when history changes
  onVisualizationImageChange?: (image: string | null) => void;  // Callback when visualization image changes
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
  onClearCanvas,
  onRoomImageUpload,
  onSetProducts,
  initialVisualizationImage,
  initialVisualizationHistory,
  onVisualizationHistoryChange,
  onVisualizationImageChange,
}: CanvasPanelProps) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isVisualizing, setIsVisualizing] = useState(false);
  const [visualizationResult, setVisualizationResult] = useState<string | null>(null);
  // Start expanded if user needs to upload their room image (no roomImage but has curated visualization)
  const [isRoomImageCollapsed, setIsRoomImageCollapsed] = useState(false);

  // Smart re-visualization tracking
  const [visualizedProductIds, setVisualizedProductIds] = useState<Set<string>>(new Set());
  const [visualizedProducts, setVisualizedProducts] = useState<Product[]>([]); // Track all visualized products
  const [needsRevisualization, setNeedsRevisualization] = useState(false);

  // Undo/Redo state
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Local visualization history for reliable undo/redo (fixes server restart issue)
  const [visualizationHistory, setVisualizationHistory] = useState<VisualizationHistoryEntry[]>(
    initialVisualizationHistory || []
  );
  const [redoStack, setRedoStack] = useState<VisualizationHistoryEntry[]>([]);
  const [historyInitialized, setHistoryInitialized] = useState(false);

  // Furniture position editing state
  const [isEditingPositions, setIsEditingPositions] = useState(false);
  const [furniturePositions, setFurniturePositions] = useState<FurniturePosition[]>([]);
  const [hasUnsavedPositions, setHasUnsavedPositions] = useState(false);

  // Layer extraction state for drag-and-drop editing
  const [baseRoomLayer, setBaseRoomLayer] = useState<string | null>(null);
  const [furnitureLayers, setFurnitureLayers] = useState<any[]>([]);
  const [isExtractingLayers, setIsExtractingLayers] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasProductsRef = useRef<HTMLDivElement>(null);
  const visualizationRef = useRef<HTMLDivElement>(null);

  // Calculate total price
  const totalPrice = products.reduce((sum, product) => sum + (product.price || 0), 0);

  // Check if canvas has changed since last visualization
  useEffect(() => {
    // Don't trigger on initial load or if never visualized
    if (visualizedProductIds.size === 0 && !visualizationResult) {
      return;
    }

    // Compare current products with last visualized products
    // Ensure IDs are strings for consistent comparison
    const currentIds = new Set(products.map(p => String(p.id)));
    const productsChanged =
      products.length !== visualizedProductIds.size ||
      products.some(p => !visualizedProductIds.has(String(p.id)));

    if (productsChanged) {
      setNeedsRevisualization(true);
    }
  }, [products, visualizedProductIds, visualizationResult]);

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

  // Debug logging for curated visualization
  useEffect(() => {
    console.log('[CanvasPanel] Props received:', {
      hasInitialVisualizationImage: !!initialVisualizationImage,
      initialVisualizationImageLength: initialVisualizationImage?.length || 0,
      hasRoomImage: !!roomImage,
      productsCount: products.length,
      currentVisualizationResult: !!visualizationResult,
    });
  }, [initialVisualizationImage, roomImage, products.length, visualizationResult]);

  // Initialize history from props (only once when loaded from saved project)
  useEffect(() => {
    if (initialVisualizationHistory && initialVisualizationHistory.length > 0 && !historyInitialized) {
      console.log('[CanvasPanel] Initializing history from saved project:', initialVisualizationHistory.length, 'entries');
      setVisualizationHistory(initialVisualizationHistory);
      setCanUndo(initialVisualizationHistory.length > 1);
      setHistoryInitialized(true);

      // Also set the visualization result from the last history entry
      const lastEntry = initialVisualizationHistory[initialVisualizationHistory.length - 1];
      if (lastEntry?.image) {
        setVisualizationResult(lastEntry.image);
        setVisualizedProductIds(lastEntry.productIds || new Set());
        setVisualizedProducts(lastEntry.products || []);
      }
    }
  }, [initialVisualizationHistory, historyInitialized]);

  // Notify parent when visualization history changes
  useEffect(() => {
    if (onVisualizationHistoryChange && historyInitialized) {
      onVisualizationHistoryChange(visualizationHistory);
    }
  }, [visualizationHistory, onVisualizationHistoryChange, historyInitialized]);

  // Notify parent when visualization image changes
  useEffect(() => {
    if (onVisualizationImageChange) {
      onVisualizationImageChange(visualizationResult);
    }
  }, [visualizationResult, onVisualizationImageChange]);

  // Initialize visualization from curated look (pre-loaded image)
  // This runs when initialVisualizationImage is provided (e.g., from curated looks)
  useEffect(() => {
    console.log('[CanvasPanel] Init effect running:', {
      hasInitialViz: !!initialVisualizationImage,
      hasCurrentViz: !!visualizationResult,
    });

    if (initialVisualizationImage && !visualizationResult) {
      console.log('[CanvasPanel] Initializing visualization from curated look image, length:', initialVisualizationImage.length);
      // Format the image properly (ensure data URI format)
      const formattedImage = formatImageSrc(initialVisualizationImage);

      console.log('[CanvasPanel] Setting visualizationResult with formatted image, starts with data:', formattedImage.startsWith('data:'));
      setVisualizationResult(formattedImage);

      // Also track the initial products as visualized
      const productIds = new Set(products.map(p => String(p.id)));
      setVisualizedProductIds(productIds);
      setVisualizedProducts([...products]);

      // Add to history for undo support
      setVisualizationHistory([{
        image: formattedImage,
        products: [...products],
        productIds: productIds
      }]);
      setCanUndo(false); // No previous state to undo to initially

      console.log('[CanvasPanel] Curated visualization initialized successfully');
    }
  }, [initialVisualizationImage, visualizationResult, products]); // Include visualizationResult to prevent re-running after set

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
      setVisualizationResult(null);
      setVisualizedProductIds(new Set());
      setVisualizedProducts([]);
      setNeedsRevisualization(false);
      // Clear visualization history when uploading new room
      setVisualizationHistory([]);
      setRedoStack([]);
      setCanUndo(false);
      setCanRedo(false);
    };
    reader.readAsDataURL(file);

    // Reset the input value so selecting the same file triggers onChange again
    e.target.value = '';
  };

  // Detect visualization change type
  const detectChangeType = () => {
    // Ensure IDs are strings for consistent comparison
    const currentIds = new Set(products.map(p => String(p.id)));

    // Check for removals (products that were visualized but no longer in canvas)
    const removedProducts = Array.from(visualizedProductIds).filter(id => !currentIds.has(id));
    if (removedProducts.length > 0) {
      console.log('[CanvasPanel] Detected removal, will reset visualization');
      return { type: 'reset', reason: 'products_removed' };
    }

    // Check for additions (products in canvas but not yet visualized)
    const newProducts = products.filter(p => !visualizedProductIds.has(String(p.id)));
    if (newProducts.length > 0 && visualizedProductIds.size > 0) {
      console.log('[CanvasPanel] Detected additions, will use incremental visualization');
      return { type: 'additive', newProducts };
    }

    // Initial visualization (nothing visualized yet)
    if (visualizedProductIds.size === 0) {
      console.log('[CanvasPanel] Initial visualization');
      return { type: 'initial' };
    }

    return { type: 'no_change' };
  };

  // Helper function to make fetch request with timeout and retry
  const fetchWithRetry = async (
    url: string,
    options: RequestInit,
    maxRetries: number = 2,
    timeoutMs: number = 180000,  // 3 minutes default
    retryDelayMs: number = 2000  // 2 seconds initial delay
  ): Promise<Response> => {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.error(`[CanvasPanel] Request timeout after ${timeoutMs / 1000}s (attempt ${attempt + 1}/${maxRetries + 1})`);
        controller.abort();
      }, timeoutMs);

      try {
        if (attempt > 0) {
          const delay = retryDelayMs * Math.pow(2, attempt - 1);  // Exponential backoff
          console.log(`[CanvasPanel] Retry attempt ${attempt}/${maxRetries} after ${delay}ms delay...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }

        console.log(`[CanvasPanel] Starting request (attempt ${attempt + 1}/${maxRetries + 1})...`);
        const requestStartTime = Date.now();

        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        const fetchTime = Date.now() - requestStartTime;
        console.log(`[CanvasPanel] HTTP response received in ${fetchTime}ms, status: ${response.status}`);

        // Don't retry on client errors (4xx), only on server errors (5xx) or network issues
        if (response.ok || (response.status >= 400 && response.status < 500)) {
          return response;
        }

        // Server error - will retry
        const errorText = await response.text().catch(() => 'Unknown server error');
        lastError = new Error(`Server error ${response.status}: ${errorText}`);
        console.error(`[CanvasPanel] Server error on attempt ${attempt + 1}:`, lastError.message);

      } catch (error: any) {
        clearTimeout(timeoutId);
        lastError = error;

        if (error.name === 'AbortError') {
          console.error(`[CanvasPanel] Request timed out on attempt ${attempt + 1}`);
          // Continue to retry on timeout
        } else if (error.message?.includes('fetch') || error.message?.includes('network')) {
          console.error(`[CanvasPanel] Network error on attempt ${attempt + 1}:`, error.message);
          // Continue to retry on network errors
        } else {
          // Unknown error - don't retry
          throw error;
        }
      }
    }

    // All retries exhausted
    throw lastError || new Error('Request failed after all retries');
  };

  // V1 Visualization: Smart re-visualization with incremental support
  const handleVisualize = async () => {
    // Need at least one base image (prefer cleanRoomImage) and products
    if ((!roomImage && !cleanRoomImage) || products.length === 0) return;

    setIsVisualizing(true);

    try {
      // Detect change type
      const changeInfo = detectChangeType();

      if (changeInfo.type === 'no_change') {
        console.log('[CanvasPanel] No changes detected, skipping visualization');
        setIsVisualizing(false);
        return;
      }

      // Get or create session ID
      let sessionId = sessionStorage.getItem('design_session_id');
      if (!sessionId) {
        // Create new session
        const sessionResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });

        if (!sessionResponse.ok) {
          throw new Error('Failed to create session');
        }

        const sessionData = await sessionResponse.json();
        sessionId = sessionData.session_id;
        if (sessionId) {
          sessionStorage.setItem('design_session_id', sessionId);
        }
      }

      // Prepare API request based on change type
      let baseImage: string;
      let productsToVisualize: Product[];
      let isIncremental = false;
      let forceReset = false;

      if (changeInfo.type === 'additive') {
        // Use previous visualization as base, only add new products
        baseImage = visualizationResult!;
        productsToVisualize = changeInfo.newProducts!;
        isIncremental = true;
        console.log(`[CanvasPanel] Incremental visualization: adding ${productsToVisualize.length} new products`);
      } else if (changeInfo.type === 'reset') {
        // Reset: use CLEAN room image to ensure removed products don't appear
        // This is critical when using curated looks where roomImage might have products baked in
        if (cleanRoomImage) {
          baseImage = cleanRoomImage;
          console.log('[CanvasPanel] Reset visualization: using clean room image (no products baked in)');
        } else if (roomImage) {
          // No clean room available - this may happen with curated looks that don't have room_image
          // The backend will need to handle this with furniture removal or exclusive_products mode
          baseImage = roomImage;
          console.log('[CanvasPanel] Reset visualization: WARNING - no clean room available, using roomImage (may have baked-in products)');
        } else {
          // No image available at all - cannot proceed
          console.error('[CanvasPanel] Reset visualization: No room image available');
          return;
        }
        productsToVisualize = products;
        forceReset = true;
        console.log('[CanvasPanel] Reset visualization: re-visualizing all products from scratch');
      } else {
        // Initial: prefer clean room image if available, otherwise use room image
        const imageToUse = cleanRoomImage || roomImage;
        if (!imageToUse) {
          console.error('[CanvasPanel] Initial visualization: No room image available');
          return;
        }
        baseImage = imageToUse;
        productsToVisualize = products;
        console.log(`[CanvasPanel] Initial visualization: visualizing all products (using ${cleanRoomImage ? 'clean room' : 'room image'})`);
      }

      // Helper function to format product for API
      const formatProductForApi = (p: Product) => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        image_url: p.image_url || getProductImageUrl(p),  // Include product image for AI reference
        description: p.description || '',  // Include description for AI context (materials, colors, style)
        product_type: p.productType || 'furniture',
        style: 0.8,
        category: p.productType || 'furniture'
      });

      // Prepare products for V1 API with complete context
      // Including image_url and description is crucial for AI to render exact product appearance
      const productDetails = productsToVisualize.map(formatProductForApi);

      // Also send ALL products currently in the scene (for backend history accuracy)
      // This is important because the frontend manages undo/redo locally and the backend
      // needs to know the complete state of all products in the scene.
      const allProductDetails = products.map(formatProductForApi);

      // V1 Visualization API call with timeout and retry
      const requestStartTime = Date.now();
      const response = await fetchWithRetry(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: baseImage,
            products: productDetails,  // Products to visualize in this request (may be subset for incremental)
            all_products: allProductDetails,  // All products currently in the scene (for backend history)
            analysis: {
              design_style: 'modern',
              color_palette: [],
              room_type: 'living_room',
            },
            is_incremental: isIncremental,
            force_reset: forceReset,
            user_uploaded_new_image: changeInfo.type === 'initial'
          }),
        },
        2,  // maxRetries: 2 retries (3 total attempts)
        180000,  // timeout: 3 minutes per attempt
        3000  // retryDelay: 3 seconds initial delay
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Visualization failed');
      }

      // Parse JSON response - this can take time for large images
      console.log('[CanvasPanel] Parsing JSON response...');
      const parseStartTime = Date.now();
      const data = await response.json();
      const parseTime = Date.now() - parseStartTime;
      console.log(`[CanvasPanel] JSON parsed in ${parseTime}ms, total time: ${Date.now() - requestStartTime}ms`);
      console.log('[CanvasPanel] Visualization response received, image length:', data.visualization?.rendered_image?.length || 0);

      if (!data.visualization?.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      // Set visualization result and update tracking
      const newImage = data.visualization.rendered_image;
      const newProductIds = new Set(products.map(p => String(p.id)));

      setVisualizationResult(newImage);
      // Ensure IDs are strings for consistency with undo/redo
      setVisualizedProductIds(newProductIds); // Track all current products as visualized
      setVisualizedProducts([...products]); // Store actual product objects for edit mode
      setNeedsRevisualization(false); // Reset change flag

      // Push to local visualization history for reliable undo (fixes server restart issue)
      setVisualizationHistory(prev => [...prev, {
        image: newImage,
        products: [...products],
        productIds: newProductIds
      }]);
      // Clear redo stack when new visualization is added
      setRedoStack([]);
      setCanUndo(true);
      setCanRedo(false);

      console.log(`[CanvasPanel] Visualization successful. Tracked ${products.length} products as visualized. History size: ${visualizationHistory.length + 1}`);
    } catch (error: any) {
      console.error('[CanvasPanel] Visualization error:', error);

      // Provide more specific error messages
      let errorMessage = 'Failed to generate visualization. Please try again.';

      if (error.name === 'AbortError') {
        errorMessage = 'Visualization request timed out after multiple attempts. Please try with fewer products or a simpler image.';
      } else if (error.message?.includes('fetch') || error.message?.includes('network')) {
        errorMessage = 'Network error: Unable to reach the server. Please check your connection and try again.';
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

  // Update undo/redo state from backend
  const updateUndoRedoState = async (sessionId: string) => {
    try {
      // We can check undo/redo availability by calling a lightweight endpoint
      // For now, we'll just check after each visualization response
      // The backend returns can_undo and can_redo in undo/redo responses
      // After visualization, we assume undo is available
      setCanUndo(true);
      setCanRedo(false); // Redo is cleared after new visualization
    } catch (error) {
      console.error('[CanvasPanel] Error updating undo/redo state:', error);
    }
  };

  // Handle undo visualization - uses local history instead of backend API
  // This fixes the issue where backend in-memory state is lost on server restart
  const handleUndo = () => {
    if (visualizationHistory.length === 0) {
      console.log('[CanvasPanel] Cannot undo: no visualization history');
      return;
    }

    console.log('[CanvasPanel] Undoing visualization using local history...');
    console.log('[CanvasPanel] Current history size:', visualizationHistory.length);

    // Pop the current state from history
    const newHistory = [...visualizationHistory];
    const currentState = newHistory.pop();

    // Push current state to redo stack
    if (currentState) {
      setRedoStack(prev => [...prev, currentState]);
    }

    // Restore previous state
    if (newHistory.length > 0) {
      const previousState = newHistory[newHistory.length - 1];
      console.log('[CanvasPanel] Restoring previous state with', previousState.products.length, 'products');

      setVisualizationResult(previousState.image);
      setVisualizedProductIds(previousState.productIds);
      setVisualizedProducts(previousState.products);
      onSetProducts(previousState.products);
    } else {
      // No previous state - clear visualization (back to base room image)
      console.log('[CanvasPanel] No previous state - clearing visualization');
      setVisualizationResult(null);
      setVisualizedProductIds(new Set());
      setVisualizedProducts([]);
      onSetProducts([]);
    }

    // Update history and undo/redo availability
    setVisualizationHistory(newHistory);
    setCanUndo(newHistory.length > 0);
    setCanRedo(true);

    console.log('[CanvasPanel] Undo successful. New history size:', newHistory.length);
  };

  // Handle redo visualization - uses local redo stack instead of backend API
  // This fixes the issue where backend in-memory state is lost on server restart
  const handleRedo = () => {
    if (redoStack.length === 0) {
      console.log('[CanvasPanel] Cannot redo: no redo history');
      return;
    }

    console.log('[CanvasPanel] Redoing visualization using local redo stack...');
    console.log('[CanvasPanel] Current redo stack size:', redoStack.length);

    // Pop state from redo stack
    const newRedoStack = [...redoStack];
    const stateToRestore = newRedoStack.pop();

    if (stateToRestore) {
      // Push to history and restore state
      setVisualizationHistory(prev => [...prev, stateToRestore]);
      setVisualizationResult(stateToRestore.image);
      setVisualizedProductIds(stateToRestore.productIds);
      setVisualizedProducts(stateToRestore.products);
      onSetProducts(stateToRestore.products);

      console.log('[CanvasPanel] Restored state with', stateToRestore.products.length, 'products');
    }

    // Update redo stack and undo/redo availability
    setRedoStack(newRedoStack);
    setCanUndo(true);
    setCanRedo(newRedoStack.length > 0);

    console.log('[CanvasPanel] Redo successful. Remaining redo stack size:', newRedoStack.length);
  };

  // Position editing handlers
  const handleEnterEditMode = async () => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId || !visualizationResult) {
      console.error('[CanvasPanel] No session ID or visualization found');
      alert('Error: Please create a visualization first.');
      return;
    }

    setIsExtractingLayers(true);

    try {
      console.log('[CanvasPanel] Entering edit mode (simplified - no layer extraction)');

      // Get clean room background by calling furniture removal
      console.log('[CanvasPanel] Removing furniture to get clean room background...');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/remove-furniture`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: visualizationResult
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to get clean room background');
      }

      const data = await response.json();
      const cleanRoom = data.clean_image || visualizationResult;
      console.log('[CanvasPanel] Got clean room background');
      setBaseRoomLayer(cleanRoom);

      // Initialize default positions for ALL visualized products (not just newly added ones)
      // ISSUE #2 FIX: Use visualizedProducts instead of products to include all visualized items
      const productsToEdit = visualizedProducts.length > 0 ? visualizedProducts : products;
      const numProducts = productsToEdit.length;
      const cols = Math.ceil(Math.sqrt(numProducts));

      const initialPositions: FurniturePosition[] = productsToEdit.map((product, index) => {
        const row = Math.floor(index / cols);
        const col = index % cols;
        const spacingX = 0.6 / (cols + 1);
        const spacingY = 0.6 / (Math.ceil(numProducts / cols) + 1);

        return {
          productId: String(product.id),
          x: 0.2 + (col + 1) * spacingX,
          y: 0.2 + (row + 1) * spacingY,
          label: product.name,
          width: 0.15,
          height: 0.15,
        };
      });

      console.log(`[CanvasPanel] Initialized default positions for ${numProducts} visualized products:`, initialPositions);
      setFurniturePositions(initialPositions);
      setFurnitureLayers([]); // No layers needed with simplified approach
      setIsEditingPositions(true);
      setHasUnsavedPositions(false);
    } catch (error: any) {
      console.error('[CanvasPanel] Error entering edit mode:', error);
      alert('Error entering edit mode. Please try again.');
    } finally {
      setIsExtractingLayers(false);
    }
  };

  const handleExitEditMode = () => {
    if (hasUnsavedPositions) {
      const confirmExit = window.confirm('You have unsaved position changes. Exit anyway?');
      if (!confirmExit) return;
    }
    setIsEditingPositions(false);
    setHasUnsavedPositions(false);
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
          }),
        },
        2,  // maxRetries
        180000,  // timeout: 3 minutes
        3000  // retryDelay: 3 seconds
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
            {products.length} {products.length === 1 ? 'item' : 'items'}
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
                      <button
                        onClick={() => onRemoveProduct(product.id)}
                        className="absolute top-0.5 right-0.5 w-5 h-5 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                    </div>
                    <div className="p-1">
                      <p className="text-[10px] font-medium text-neutral-900 dark:text-white line-clamp-1">
                        {product.name}
                      </p>
                      {product.price && (
                        <p className="text-[10px] text-primary-600 dark:text-primary-400 font-semibold">
                          ₹{product.price.toLocaleString()}
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
                          ₹{product.price.toLocaleString()}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => onRemoveProduct(product.id)}
                      className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 p-0.5"
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

            {/* Image/Canvas Container */}
            <div className={`relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden ${needsRevisualization ? 'ring-2 ring-amber-400 dark:ring-amber-600' : ''} ${isEditingPositions ? 'ring-2 ring-purple-400 dark:ring-purple-600' : ''}`}>
              {isEditingPositions ? (
                <DraggableFurnitureCanvas
                  visualizationImage={visualizationResult}
                  baseRoomLayer={baseRoomLayer}
                  furnitureLayers={furnitureLayers}
                  furniturePositions={furniturePositions}
                  onPositionsChange={handlePositionsChange}
                  products={products}
                  containerWidth={800}
                  containerHeight={450}
                />
              ) : (
                <>
                  {isBase64Image(visualizationResult) ? (
                    <img
                      src={formatImageSrc(visualizationResult)}
                      alt="Visualization result"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <Image
                      src={visualizationResult}
                      alt="Visualization result"
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  )}
                </>
              )}
            </div>

            {/* Edit Mode Actions */}
            {isEditingPositions && (
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={handleExitEditMode}
                  className="px-4 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 text-sm font-medium transition-colors"
                >
                  Cancel
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
        {isEditingPositions && hasUnsavedPositions ? (
          // State: Edit Mode with Unsaved Positions (Purple, Enabled)
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
                Re-visualizing...
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
                Visualizing...
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
      </div>
    </div>
  );
}
