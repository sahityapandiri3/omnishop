'use client';

import { useState, useEffect } from 'react';
import ChatPanel from '@/components/panels/ChatPanel';
import ProductDiscoveryPanel from '@/components/panels/ProductDiscoveryPanel';
import CanvasPanel from '@/components/panels/CanvasPanel';
import { checkFurnitureRemovalStatus, startFurnitureRemoval, getAvailableStores } from '@/utils/api';

/**
 * New UI V2: Three-Panel Design Interface
 *
 * Layout:
 * - Left Panel (25%): Chat Interface
 * - Center Panel (50%): Product Discovery & Selection
 * - Right Panel (25%): Canvas & Visualization
 */
export default function DesignPage() {
  // Mobile tab state
  const [activeTab, setActiveTab] = useState<'chat' | 'products' | 'canvas'>('chat');

  // Shared state for cross-panel communication
  const [roomImage, setRoomImage] = useState<string | null>(null);
  const [canvasProducts, setCanvasProducts] = useState<any[]>([]);
  const [productRecommendations, setProductRecommendations] = useState<any[]>([]);
  const [initialVisualizationImage, setInitialVisualizationImage] = useState<string | null>(null);

  // Furniture removal state
  const [isProcessingFurniture, setIsProcessingFurniture] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');

  // Store selection state
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [showStoreModal, setShowStoreModal] = useState(false);
  const [availableStores, setAvailableStores] = useState<string[]>([]);

  // Load room image, products, and stores from sessionStorage on mount
  useEffect(() => {
    // Check if user has uploaded their own room image
    const userUploadedImage = sessionStorage.getItem('roomImage');

    // Check for curated look data
    const curatedRoomImage = sessionStorage.getItem('curatedRoomImage');
    const curatedVisualizationImage = sessionStorage.getItem('curatedVisualizationImage');
    const preselectedProducts = sessionStorage.getItem('preselectedProducts');

    console.log('[DesignPage] Session storage check:', {
      hasUserUploadedImage: !!userUploadedImage,
      hasCuratedVisualization: !!curatedVisualizationImage,
      curatedVizLength: curatedVisualizationImage?.length || 0,
      hasPreselectedProducts: !!preselectedProducts,
    });

    // Room image logic:
    // - If user uploaded image exists, use it and clear curated data
    // - Otherwise, load curated visualization if it exists
    if (userUploadedImage) {
      setRoomImage(userUploadedImage);
      console.log('[DesignPage] Using user-uploaded room image');
      // Clear curated data since we're using user's room
      sessionStorage.removeItem('curatedVisualizationImage');
      sessionStorage.removeItem('curatedRoomImage');
    } else if (curatedVisualizationImage) {
      // Load curated visualization image (shows in visualization result section at bottom)
      // Don't load curatedRoomImage into roomImage - user should upload their own room
      // Ensure proper data URI prefix
      const formattedVizImage = curatedVisualizationImage.startsWith('data:')
        ? curatedVisualizationImage
        : `data:image/png;base64,${curatedVisualizationImage}`;
      setInitialVisualizationImage(formattedVizImage);
      console.log('[DesignPage] Loaded curated visualization image:', {
        originalLength: curatedVisualizationImage.length,
        formattedLength: formattedVizImage.length,
        startsWithData: formattedVizImage.startsWith('data:'),
      });
      sessionStorage.removeItem('curatedVisualizationImage');
    }

    // Load preselected products from curated look
    if (preselectedProducts) {
      try {
        const products = JSON.parse(preselectedProducts);
        // Transform products to match design page format - preserve ALL context for visualization
        const formattedProducts = products.map((p: any) => ({
          id: String(p.id),
          name: p.name,
          price: p.price || 0,
          image_url: p.image_url,
          productType: p.product_type || 'other',
          source: p.source_website,
          source_url: p.source_url,  // Preserve source URL
          description: p.description,  // Preserve description for AI context
        }));
        setCanvasProducts(formattedProducts);
        console.log('[DesignPage] Loaded', formattedProducts.length, 'preselected products from curated look with full context');
        // Clear after loading
        sessionStorage.removeItem('preselectedProducts');
        sessionStorage.removeItem('preselectedLookTheme');
      } catch (e) {
        console.error('[DesignPage] Failed to parse preselected products:', e);
      }
    }

    // Clean up curated room image after loading
    sessionStorage.removeItem('curatedRoomImage');

    // Load primary store selection from sessionStorage
    const storedStores = sessionStorage.getItem('primaryStores');
    if (storedStores) {
      try {
        const parsed = JSON.parse(storedStores);
        setSelectedStores(parsed);
        console.log('[DesignPage] Loaded stores from sessionStorage:', parsed);
      } catch (e) {
        console.error('[DesignPage] Failed to parse stored stores:', e);
      }
    }

    // Fetch available stores for the modal
    const fetchStores = async () => {
      try {
        const response = await getAvailableStores();
        setAvailableStores(response.stores);
      } catch (error) {
        console.error('[DesignPage] Failed to fetch available stores:', error);
      }
    };
    fetchStores();

    // Clear session ID on page load to start fresh
    // This prevents old visualization history from bleeding into new sessions
    sessionStorage.removeItem('design_session_id');
    console.log('[DesignPage] Cleared session ID on page load - starting fresh session');
  }, []);

  // Poll for furniture removal job completion
  useEffect(() => {
    const jobId = sessionStorage.getItem('furnitureRemovalJobId');
    if (!jobId) return;

    console.log('[DesignPage] Found furniture removal job:', jobId);
    setIsProcessingFurniture(true);
    setProcessingStatus('Removing existing furniture from your room...');

    let pollAttempts = 0;
    const MAX_POLL_ATTEMPTS = 30; // 30 attempts * 2 seconds = 60 seconds max

    const pollInterval = setInterval(async () => {
      pollAttempts++;

      // Timeout after max attempts
      if (pollAttempts > MAX_POLL_ATTEMPTS) {
        console.error('[DesignPage] Furniture removal timed out after 60 seconds');
        sessionStorage.removeItem('furnitureRemovalJobId');
        setIsProcessingFurniture(false);
        setProcessingStatus('');
        clearInterval(pollInterval);
        alert('Furniture removal took too long. Using original image.');
        return;
      }

      try {
        const status = await checkFurnitureRemovalStatus(jobId);
        console.log('[DesignPage] Furniture removal status:', status);

        if (status.status === 'completed') {
          console.log('[DesignPage] Furniture removal completed successfully');
          if (status.image) {
            setRoomImage(status.image);
            sessionStorage.setItem('roomImage', status.image);
          }
          sessionStorage.removeItem('furnitureRemovalJobId');
          setIsProcessingFurniture(false);
          setProcessingStatus('');
          clearInterval(pollInterval);
        } else if (status.status === 'failed') {
          console.log('[DesignPage] Furniture removal failed, using original image');
          sessionStorage.removeItem('furnitureRemovalJobId');
          setIsProcessingFurniture(false);
          setProcessingStatus('');
          clearInterval(pollInterval);
        } else if (status.status === 'processing') {
          setProcessingStatus('Processing your room image (this may take a moment)...');
        }
      } catch (error) {
        console.error('[DesignPage] Error checking furniture removal status:', error);
        // Stop polling after 3 consecutive errors
        if (pollAttempts > 3) {
          console.error('[DesignPage] Too many errors, stopping furniture removal polling');
          sessionStorage.removeItem('furnitureRemovalJobId');
          setIsProcessingFurniture(false);
          setProcessingStatus('');
          clearInterval(pollInterval);
        }
      }
    }, 2000); // Poll every 2 seconds

    // Cleanup on unmount
    return () => clearInterval(pollInterval);
  }, []);

  // Handle product recommendation from chat
  const handleProductRecommendations = (products: any[]) => {
    console.log('[DesignPage] handleProductRecommendations called with', products.length, 'products');
    console.log('[DesignPage] First product:', products[0]);
    setProductRecommendations(products);
    console.log('[DesignPage] productRecommendations state updated to:', products);
    // Auto-switch to products tab on mobile
    if (window.innerWidth < 768) {
      setActiveTab('products');
    }
  };

  // Furniture quantity restriction rules
  // SINGLE_INSTANCE: Only one of this type allowed in the canvas (replaces existing)
  // UNLIMITED: Multiple instances allowed (always adds new)
  const FURNITURE_QUANTITY_RULES = {
    SINGLE_INSTANCE: ['sofa', 'bed', 'coffee_table', 'floor_rug', 'ceiling_lamp'],
    UNLIMITED: ['planter', 'floor_lamp', 'standing_lamp', 'side_table', 'ottoman', 'table_lamp'],
  };

  // Extract product type from product name
  const extractProductType = (productName: string): string => {
    const name = productName.toLowerCase();

    // Check for specific product types (order matters - check specific types first)
    if (name.includes('sofa') || name.includes('couch') || name.includes('sectional')) return 'sofa';
    if (name.includes('coffee table') || name.includes('center table') || name.includes('centre table')) return 'coffee_table';
    if (name.includes('side table') || name.includes('end table') || name.includes('nightstand')) return 'side_table';
    if (name.includes('dining table')) return 'dining_table';
    if (name.includes('console table')) return 'console_table';
    if (name.includes('accent chair') || name.includes('armchair')) return 'accent_chair';
    if (name.includes('dining chair')) return 'dining_chair';
    if (name.includes('office chair')) return 'office_chair';
    if (name.includes('table lamp') || name.includes('desk lamp')) return 'table_lamp';
    if (name.includes('floor lamp') || name.includes('standing lamp')) return 'floor_lamp';
    if (name.includes('ceiling lamp') || name.includes('pendant') || name.includes('chandelier')) return 'ceiling_lamp';
    if (name.includes('planter') || name.includes('plant pot') || name.includes('flower pot')) return 'planter';
    if (name.includes('table')) return 'table';
    if (name.includes('chair')) return 'chair';
    if (name.includes('lamp')) return 'lamp';
    if (name.includes('bed')) return 'bed';
    if (name.includes('dresser')) return 'dresser';
    if (name.includes('mirror')) return 'mirror';
    if (name.includes('rug') || name.includes('carpet')) {
      // Distinguish between wall rugs and floor rugs
      if (name.includes('wall') || name.includes('hanging') || name.includes('tapestry')) {
        return 'wall_rug';
      }
      return 'floor_rug';
    }
    if (name.includes('ottoman')) return 'ottoman';
    if (name.includes('bench')) return 'bench';

    // Default to 'other' for unrecognized types
    return 'other';
  };

  // Handle add to canvas from product panel
  const handleAddToCanvas = (product: any) => {
    // Extract and set product type if not already set
    const productType = product.productType || extractProductType(product.name || '');
    const productWithType = { ...product, productType };

    console.log('[DesignPage] Adding product to canvas:', product.name);
    console.log('[DesignPage] Product type:', productType);
    console.log('[DesignPage] Current canvas products:', canvasProducts.map(p => ({ name: p.name, type: p.productType })));

    // Check if this product type has quantity restrictions
    const isSingleInstance = FURNITURE_QUANTITY_RULES.SINGLE_INSTANCE.includes(productType);
    const isUnlimited = FURNITURE_QUANTITY_RULES.UNLIMITED.includes(productType);

    if (isSingleInstance) {
      // SINGLE INSTANCE: Replace existing product of same type
      const existingIndex = canvasProducts.findIndex((p) => p.productType === productType);

      if (existingIndex >= 0) {
        console.log('[DesignPage] Replacing existing single-instance product at index', existingIndex);
        const updated = [...canvasProducts];
        updated[existingIndex] = productWithType;
        setCanvasProducts(updated);
      } else {
        console.log('[DesignPage] Adding new single-instance product');
        setCanvasProducts([...canvasProducts, productWithType]);
      }
    } else if (isUnlimited) {
      // UNLIMITED: Always add new instance (allow multiples)
      console.log('[DesignPage] Adding new unlimited-instance product (multiples allowed)');
      setCanvasProducts([...canvasProducts, productWithType]);
    } else {
      // DEFAULT: For unclassified items, use the old replacement behavior
      const existingIndex = canvasProducts.findIndex((p) => p.productType === productType);

      if (existingIndex >= 0) {
        console.log('[DesignPage] Replacing existing product at index', existingIndex);
        const updated = [...canvasProducts];
        updated[existingIndex] = productWithType;
        setCanvasProducts(updated);
      } else {
        console.log('[DesignPage] Adding new product');
        setCanvasProducts([...canvasProducts, productWithType]);
      }
    }

    // Auto-switch to canvas tab on mobile
    if (window.innerWidth < 768) {
      setActiveTab('canvas');
    }
  };

  // Handle remove from canvas
  const handleRemoveFromCanvas = (productId: string) => {
    setCanvasProducts(canvasProducts.filter((p) => p.id !== productId));
  };

  // Handle clear canvas
  const handleClearCanvas = () => {
    setCanvasProducts([]);
  };

  // Handle room image upload with furniture removal
  const handleRoomImageUpload = async (imageData: string) => {
    try {
      console.log('[DesignPage] Starting furniture removal for uploaded image...');

      // IMPORTANT: Clear any existing furniture removal job to prevent infinite loop
      const existingJobId = sessionStorage.getItem('furnitureRemovalJobId');
      if (existingJobId) {
        console.log('[DesignPage] Clearing existing furniture removal job:', existingJobId);
        sessionStorage.removeItem('furnitureRemovalJobId');
      }

      setIsProcessingFurniture(true);
      setProcessingStatus('Removing existing furniture from your room...');

      // Start async furniture removal
      const response = await startFurnitureRemoval(imageData);
      sessionStorage.setItem('furnitureRemovalJobId', response.job_id);
      sessionStorage.setItem('roomImage', imageData);

      console.log('[DesignPage] Furniture removal started:', response);
      // Trigger page reload to restart the polling useEffect with new job ID
      window.location.reload();
    } catch (error) {
      console.error('[DesignPage] Error starting furniture removal:', error);
      // On error, use original image
      setRoomImage(imageData);
      sessionStorage.setItem('roomImage', imageData);
      setIsProcessingFurniture(false);
      setProcessingStatus('');
    }
  };

  // Handle store selection change
  const handleStoreSelectionChange = (stores: string[]) => {
    setSelectedStores(stores);
    sessionStorage.setItem('primaryStores', JSON.stringify(stores));
    console.log('[DesignPage] Updated store selection:', stores);
    // Note: User will need to re-fetch products by sending a new chat message
  };

  return (
    <div className="h-screen flex flex-col bg-neutral-50 dark:bg-neutral-900">
      {/* Header */}
      <header className="bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-secondary-500 rounded-lg"></div>
          <h1 className="text-xl font-bold text-neutral-900 dark:text-white">
            Omnishop Design Studio
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {/* Store Selection Button */}
          <button
            onClick={() => setShowStoreModal(true)}
            className="hidden sm:flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 px-3 py-1.5 bg-neutral-100 dark:bg-neutral-700 rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-600 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            {selectedStores.length === 0 ? 'All Stores' : `${selectedStores.length} Store${selectedStores.length > 1 ? 's' : ''}`}
          </button>
          <button className="p-2 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded-lg transition-colors">
            <svg
              className="w-5 h-5 text-neutral-600 dark:text-neutral-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* Processing Overlay */}
      {isProcessingFurniture && (
        <div className="absolute inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white dark:bg-neutral-800 rounded-2xl shadow-2xl p-8 max-w-md mx-4">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4">
                <svg className="animate-spin h-16 w-16 text-primary-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-neutral-900 dark:text-white mb-2">
                Processing Your Room
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400">
                {processingStatus}
              </p>
              <p className="text-sm text-neutral-500 dark:text-neutral-500 mt-4">
                This may take up to 30 seconds. Please wait...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Mobile Tab Navigation */}
      <div className="lg:hidden bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 px-4">
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'chat'
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
            }`}
          >
            Chat
            {activeTab === 'chat' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600 dark:bg-primary-400"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab('products')}
            className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'products'
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
            }`}
          >
            Products
            {productRecommendations.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-primary-600 rounded-full">
                {productRecommendations.length}
              </span>
            )}
            {activeTab === 'products' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600 dark:bg-primary-400"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab('canvas')}
            className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'canvas'
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
            }`}
          >
            Canvas
            {canvasProducts.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-primary-600 rounded-full">
                {canvasProducts.length}
              </span>
            )}
            {activeTab === 'canvas' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600 dark:bg-primary-400"></div>
            )}
          </button>
        </div>
      </div>

      {/* Three-Panel Layout */}
      <div className="flex-1 overflow-hidden">
        {/* Desktop: Three columns - 25%, 35%, 40% */}
        <div className="hidden lg:flex h-full gap-0">
          {/* Panel 1: Chat (25%) */}
          <div className="w-[25%] border-r border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 overflow-hidden">
            <ChatPanel
              onProductRecommendations={handleProductRecommendations}
              roomImage={roomImage}
              selectedStores={selectedStores}
            />
          </div>

          {/* Panel 2: Products (35%) */}
          <div className="w-[35%] border-r border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 overflow-hidden">
            <ProductDiscoveryPanel
              products={productRecommendations}
              onAddToCanvas={handleAddToCanvas}
              canvasProducts={canvasProducts}
            />
          </div>

          {/* Panel 3: Canvas (40%) */}
          <div className="w-[40%] bg-white dark:bg-neutral-800 overflow-hidden">
            <CanvasPanel
              products={canvasProducts}
              roomImage={roomImage}
              onRemoveProduct={handleRemoveFromCanvas}
              onClearCanvas={handleClearCanvas}
              onRoomImageUpload={handleRoomImageUpload}
              onSetProducts={setCanvasProducts}
              initialVisualizationImage={initialVisualizationImage}
            />
          </div>
        </div>

        {/* Mobile & Tablet: Single panel with tabs */}
        <div className="lg:hidden h-full">
          <div className={`h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
            <ChatPanel
              onProductRecommendations={handleProductRecommendations}
              roomImage={roomImage}
              selectedStores={selectedStores}
            />
          </div>
          <div className={`h-full ${activeTab === 'products' ? 'block' : 'hidden'}`}>
            <ProductDiscoveryPanel
              products={productRecommendations}
              onAddToCanvas={handleAddToCanvas}
              canvasProducts={canvasProducts}
            />
          </div>
          <div className={`h-full ${activeTab === 'canvas' ? 'block' : 'hidden'}`}>
            <CanvasPanel
              products={canvasProducts}
              roomImage={roomImage}
              onRemoveProduct={handleRemoveFromCanvas}
              onClearCanvas={handleClearCanvas}
              onRoomImageUpload={handleRoomImageUpload}
              onSetProducts={setCanvasProducts}
              initialVisualizationImage={initialVisualizationImage}
            />
          </div>
        </div>
      </div>

      {/* Store Selection Modal */}
      {showStoreModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-neutral-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-700 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">
                Select Stores
              </h2>
              <button
                onClick={() => setShowStoreModal(false)}
                className="p-2 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto max-h-[calc(80vh-140px)]">
              {/* Action Buttons */}
              <div className="flex gap-3 mb-6">
                <button
                  onClick={() => handleStoreSelectionChange([...availableStores])}
                  className="flex-1 bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 py-2 px-4 rounded-lg hover:bg-primary-200 dark:hover:bg-primary-800 transition font-medium"
                >
                  Select All
                </button>
                <button
                  onClick={() => handleStoreSelectionChange([])}
                  className="flex-1 bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 py-2 px-4 rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-600 transition font-medium"
                >
                  Clear All
                </button>
              </div>

              {/* Selection Info */}
              <div className="mb-6 text-center">
                <p className="text-sm text-neutral-600 dark:text-neutral-400">
                  {selectedStores.length === 0 ? (
                    <span className="text-primary-600 dark:text-primary-400 font-semibold">
                      No stores selected - will search all {availableStores.length} stores
                    </span>
                  ) : (
                    <span>
                      Selected <span className="font-semibold text-primary-600 dark:text-primary-400">{selectedStores.length}</span> of {availableStores.length} stores
                    </span>
                  )}
                </p>
              </div>

              {/* Store Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {availableStores.map((store) => {
                  const isSelected = selectedStores.includes(store);
                  return (
                    <button
                      key={store}
                      onClick={() => {
                        const updated = isSelected
                          ? selectedStores.filter((s) => s !== store)
                          : [...selectedStores, store];
                        handleStoreSelectionChange(updated);
                      }}
                      className={`
                        p-4 rounded-lg border-2 transition-all duration-200
                        ${
                          isSelected
                            ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 shadow-md'
                            : 'border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 hover:border-primary-300 dark:hover:border-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/10'
                        }
                      `}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium capitalize text-left">
                          {store.replace(/([A-Z])/g, ' $1').trim()}
                        </span>
                        {isSelected && (
                          <svg
                            className="w-5 h-5 text-primary-600 dark:text-primary-400 flex-shrink-0"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                              clipRule="evenodd"
                            />
                          </svg>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900">
              <div className="flex gap-3">
                <button
                  onClick={() => setShowStoreModal(false)}
                  className="flex-1 bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 py-2.5 px-4 rounded-lg hover:bg-neutral-300 dark:hover:bg-neutral-600 transition font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={() => setShowStoreModal(false)}
                  className="flex-1 bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-2.5 px-4 rounded-lg hover:from-primary-700 hover:to-secondary-700 transition font-medium shadow-lg"
                >
                  Apply Selection
                </button>
              </div>
              <p className="text-xs text-neutral-500 dark:text-neutral-500 mt-3 text-center">
                Changes will apply to new product searches. Send a new message to the AI to see updated results.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
