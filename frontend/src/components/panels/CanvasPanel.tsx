'use client';

import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';

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
}

interface CanvasPanelProps {
  products: Product[];
  roomImage: string | null;
  onRemoveProduct: (productId: string) => void;
  onClearCanvas: () => void;
  onRoomImageUpload: (imageData: string) => void;
  onSetProducts: (products: Product[]) => void;
}

/**
 * Panel 3: Canvas & Visualization
 * Features: Collapsible UI, change tracking, smart visualization states
 */
export default function CanvasPanel({
  products,
  roomImage,
  onRemoveProduct,
  onClearCanvas,
  onRoomImageUpload,
  onSetProducts,
}: CanvasPanelProps) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isVisualizing, setIsVisualizing] = useState(false);
  const [visualizationResult, setVisualizationResult] = useState<string | null>(null);
  const [isRoomImageCollapsed, setIsRoomImageCollapsed] = useState(false);

  // Smart re-visualization tracking
  const [visualizedProductIds, setVisualizedProductIds] = useState<Set<string>>(new Set());
  const [needsRevisualization, setNeedsRevisualization] = useState(false);

  // Undo/Redo state
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Calculate total price
  const totalPrice = products.reduce((sum, product) => sum + product.price, 0);

  // Check if canvas has changed since last visualization
  useEffect(() => {
    // Don't trigger on initial load or if never visualized
    if (visualizedProductIds.size === 0 && !visualizationResult) {
      return;
    }

    // Compare current products with last visualized products
    const currentIds = new Set(products.map(p => p.id));
    const productsChanged =
      products.length !== visualizedProductIds.size ||
      products.some(p => !visualizedProductIds.has(p.id));

    if (productsChanged) {
      setNeedsRevisualization(true);
    }
  }, [products, visualizedProductIds, visualizationResult]);

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
      setNeedsRevisualization(false);
    };
    reader.readAsDataURL(file);
  };

  // Detect visualization change type
  const detectChangeType = () => {
    const currentIds = new Set(products.map(p => p.id));

    // Check for removals (products that were visualized but no longer in canvas)
    const removedProducts = Array.from(visualizedProductIds).filter(id => !currentIds.has(id));
    if (removedProducts.length > 0) {
      console.log('[CanvasPanel] Detected removal, will reset visualization');
      return { type: 'reset', reason: 'products_removed' };
    }

    // Check for additions (products in canvas but not yet visualized)
    const newProducts = products.filter(p => !visualizedProductIds.has(p.id));
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

  // V1 Visualization: Smart re-visualization with incremental support
  const handleVisualize = async () => {
    if (!roomImage || products.length === 0) return;

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
        sessionStorage.setItem('design_session_id', sessionId);
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
        // Reset: use room image, visualize all current products
        baseImage = roomImage;
        productsToVisualize = products;
        forceReset = true;
        console.log('[CanvasPanel] Reset visualization: re-visualizing all products from scratch');
      } else {
        // Initial: use room image, visualize all products
        baseImage = roomImage;
        productsToVisualize = products;
        console.log('[CanvasPanel] Initial visualization: visualizing all products');
      }

      // Prepare products for V1 API
      const productDetails = productsToVisualize.map(p => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        style: 0.8,
        category: 'furniture'
      }));

      // V1 Visualization API call
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: baseImage,
          products: productDetails,
          analysis: {
            design_style: 'modern',
            color_palette: [],
            room_type: 'living_room',
          },
          is_incremental: isIncremental,
          force_reset: forceReset,
          user_uploaded_new_image: changeInfo.type === 'initial'
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Visualization failed');
      }

      const data = await response.json();
      console.log('[CanvasPanel] Visualization response:', data);

      if (!data.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      // Set visualization result and update tracking
      setVisualizationResult(data.rendered_image);
      setVisualizedProductIds(new Set(products.map(p => p.id))); // Track all current products as visualized
      setNeedsRevisualization(false); // Reset change flag

      // Update undo/redo availability (need to check backend state)
      // After visualization, undo should be available if there's history
      await updateUndoRedoState(sessionId);

      console.log(`[CanvasPanel] Visualization successful. Tracked ${products.length} products as visualized.`);
    } catch (error: any) {
      console.error('[CanvasPanel] Visualization error:', error);
      alert(
        error.response?.data?.detail ||
        error.message ||
        'Failed to generate visualization. Please try again.'
      );
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

  // Handle undo visualization
  const handleUndo = async () => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId) {
      console.error('[CanvasPanel] No session ID found');
      return;
    }

    try {
      console.log('[CanvasPanel] Undoing visualization...');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualization/undo`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Undo failed' }));
        throw new Error(errorData.detail || 'Undo failed');
      }

      const data = await response.json();
      console.log('[CanvasPanel] Undo response:', data);

      // Update visualization with previous state
      if (data.visualization?.rendered_image) {
        setVisualizationResult(data.visualization.rendered_image);

        // Update canvas products to match the undone state
        const previousProducts = data.visualization.products_in_scene || [];
        onSetProducts(previousProducts);

        // Update visualized product IDs
        setVisualizedProductIds(new Set(previousProducts.map((p: Product) => p.id)));
      }

      // Update undo/redo availability
      setCanUndo(data.can_undo || false);
      setCanRedo(data.can_redo || false);

      console.log('[CanvasPanel] Undo successful');
    } catch (error: any) {
      console.error('[CanvasPanel] Undo error:', error);
      alert(error.message || 'Failed to undo visualization');
    }
  };

  // Handle redo visualization
  const handleRedo = async () => {
    const sessionId = sessionStorage.getItem('design_session_id');
    if (!sessionId) {
      console.error('[CanvasPanel] No session ID found');
      return;
    }

    try {
      console.log('[CanvasPanel] Redoing visualization...');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualization/redo`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Redo failed' }));
        throw new Error(errorData.detail || 'Redo failed');
      }

      const data = await response.json();
      console.log('[CanvasPanel] Redo response:', data);

      // Update visualization with next state
      if (data.visualization?.rendered_image) {
        setVisualizationResult(data.visualization.rendered_image);

        // Update canvas products to match the redone state
        const nextProducts = data.visualization.products_in_scene || [];
        onSetProducts(nextProducts);

        // Update visualized product IDs
        setVisualizedProductIds(new Set(nextProducts.map((p: Product) => p.id)));
      }

      // Update undo/redo availability
      setCanUndo(data.can_undo || false);
      setCanRedo(data.can_redo || false);

      console.log('[CanvasPanel] Redo successful');
    } catch (error: any) {
      console.error('[CanvasPanel] Redo error:', error);
      alert(error.message || 'Failed to redo visualization');
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
  const canVisualize = roomImage !== null && products.length > 0;
  const isUpToDate = canVisualize && !needsRevisualization && visualizationResult !== null;
  const isReady = canVisualize && (needsRevisualization || visualizationResult === null);

  return (
    <div className="flex flex-col h-full overflow-hidden">
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
                  {roomImage.startsWith('data:') ? (
                    <img
                      src={roomImage}
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
                    className="absolute bottom-2 right-2 px-3 py-1.5 bg-white/90 dark:bg-neutral-900/90 backdrop-blur text-xs font-medium text-neutral-900 dark:text-white rounded-lg hover:bg-white dark:hover:bg-neutral-900 transition-colors"
                  >
                    Change
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
                    Upload Room Image
                  </button>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
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
        <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
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
                      <p className="text-[10px] text-primary-600 dark:text-primary-400 font-semibold">
                        ₹{product.price.toLocaleString()}
                      </p>
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
                      <p className="text-xs font-semibold text-primary-600 dark:text-primary-400">
                        ₹{product.price.toLocaleString()}
                      </p>
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
          <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
                Visualization Result
              </h3>
              <div className="flex items-center gap-2">
                {/* Undo/Redo buttons */}
                <button
                  onClick={handleUndo}
                  disabled={!canUndo}
                  className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Undo (Remove last added product)"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                  </svg>
                </button>
                <button
                  onClick={handleRedo}
                  disabled={!canRedo}
                  className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Redo (Add back removed product)"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6" />
                  </svg>
                </button>
                <button
                  onClick={() => setVisualizationResult(null)}
                  className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 font-medium"
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

            <div className={`relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden ${needsRevisualization ? 'ring-2 ring-amber-400 dark:ring-amber-600' : ''}`}>
              {visualizationResult.startsWith('data:') ? (
                <img
                  src={visualizationResult}
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
            </div>

            {!needsRevisualization && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-2 text-center">
                ✓ Visualization up to date
              </p>
            )}
          </div>
        )}
      </div>

      {/* Visualize Button with Smart States - Fixed at bottom */}
      <div className="p-4 border-t border-neutral-200 dark:border-neutral-700 flex-shrink-0">
        {isUpToDate ? (
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
