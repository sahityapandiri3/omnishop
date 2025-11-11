'use client';

import { useState, useEffect } from 'react';
import ChatPanel from '@/components/panels/ChatPanel';
import ProductDiscoveryPanel from '@/components/panels/ProductDiscoveryPanel';
import CanvasPanel from '@/components/panels/CanvasPanel';

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

  // Load room image from sessionStorage on mount
  useEffect(() => {
    const storedImage = sessionStorage.getItem('roomImage');
    if (storedImage) {
      setRoomImage(storedImage);
      // Don't clear sessionStorage immediately - keep it for refresh
    }
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
    if (name.includes('floor lamp')) return 'floor_lamp';
    if (name.includes('ceiling lamp') || name.includes('pendant') || name.includes('chandelier')) return 'ceiling_lamp';
    if (name.includes('table')) return 'table';
    if (name.includes('chair')) return 'chair';
    if (name.includes('lamp')) return 'lamp';
    if (name.includes('bed')) return 'bed';
    if (name.includes('dresser')) return 'dresser';
    if (name.includes('mirror')) return 'mirror';
    if (name.includes('rug') || name.includes('carpet')) return 'rug';
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

    // Check if product type already exists (for replaceable items like sofas, tables)
    const existingIndex = canvasProducts.findIndex(
      (p) => p.productType === productType
    );

    if (existingIndex >= 0) {
      // Replace existing product of same type
      const updated = [...canvasProducts];
      updated[existingIndex] = productWithType;
      setCanvasProducts(updated);
    } else {
      // Add new product
      setCanvasProducts([...canvasProducts, productWithType]);
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

  // Handle room image upload
  const handleRoomImageUpload = (imageData: string) => {
    setRoomImage(imageData);
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
          <span className="hidden sm:inline-block text-sm text-neutral-600 dark:text-neutral-400 px-3 py-1 bg-neutral-100 dark:bg-neutral-700 rounded-full">
            New UI V2
          </span>
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
            />
          </div>
        </div>

        {/* Mobile & Tablet: Single panel with tabs */}
        <div className="lg:hidden h-full">
          <div className={`h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
            <ChatPanel
              onProductRecommendations={handleProductRecommendations}
              roomImage={roomImage}
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
            />
          </div>
        </div>
      </div>
    </div>
  );
}
