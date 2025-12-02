'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { adminCuratedAPI, getAvailableStores, visualizeRoom, startChatSession, startFurnitureRemoval, checkFurnitureRemovalStatus, furniturePositionAPI } from '@/utils/api';
import { FurniturePosition } from '@/components/DraggableFurnitureCanvas';

const DraggableFurnitureCanvas = dynamic(
  () => import('@/components/DraggableFurnitureCanvas').then(mod => ({ default: mod.DraggableFurnitureCanvas })),
  { ssr: false }
);

// Common furniture colors for filtering
const FURNITURE_COLORS = [
  { name: 'White', value: 'white', color: '#FFFFFF', border: true },
  { name: 'Black', value: 'black', color: '#000000' },
  { name: 'Brown', value: 'brown', color: '#8B4513' },
  { name: 'Beige', value: 'beige', color: '#F5F5DC' },
  { name: 'Gray', value: 'gray', color: '#808080' },
  { name: 'Blue', value: 'blue', color: '#4169E1' },
  { name: 'Green', value: 'green', color: '#228B22' },
  { name: 'Red', value: 'red', color: '#DC143C' },
  { name: 'Yellow', value: 'yellow', color: '#FFD700' },
  { name: 'Orange', value: 'orange', color: '#FF8C00' },
  { name: 'Pink', value: 'pink', color: '#FFB6C1' },
  { name: 'Purple', value: 'purple', color: '#9370DB' },
];

interface Category {
  id: number;
  name: string;
  slug: string;
}

// Visualization history entry for local undo/redo tracking
interface VisualizationHistoryEntry {
  image: string;
  products: any[];
  productIds: Set<string>;
}

export default function CreateCuratedLookPage() {
  const router = useRouter();

  // Session for visualization
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Filter state
  const [categories, setCategories] = useState<Category[]>([]);
  const [stores, setStores] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [selectedColors, setSelectedColors] = useState<string[]>([]);

  // Product discovery state
  const [discoveredProducts, setDiscoveredProducts] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);

  // Canvas state
  const [selectedProducts, setSelectedProducts] = useState<any[]>([]);
  const [roomImage, setRoomImage] = useState<string | null>(null);
  const [visualizationImage, setVisualizationImage] = useState<string | null>(null);
  const [isVisualizing, setIsVisualizing] = useState(false);

  // Furniture removal state
  const [isRemovingFurniture, setIsRemovingFurniture] = useState(false);
  const [furnitureRemovalJobId, setFurnitureRemovalJobId] = useState<string | null>(null);
  const [preparedRoomImage, setPreparedRoomImage] = useState<string | null>(null);

  // Publish state
  const [title, setTitle] = useState('');
  const [styleTheme, setStyleTheme] = useState('');
  const [styleDescription, setStyleDescription] = useState('');
  const [roomType, setRoomType] = useState<'living_room' | 'bedroom'>('living_room');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Furniture quantity rules - same as user experience
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
    if (name.includes('lamp') || name.includes('light')) return 'lamp';
    if (name.includes('bed')) return 'bed';
    if (name.includes('dresser')) return 'dresser';
    if (name.includes('mirror')) return 'mirror';
    if (name.includes('rug') || name.includes('carpet')) {
      if (name.includes('wall') || name.includes('hanging') || name.includes('tapestry')) {
        return 'wall_rug';
      }
      return 'floor_rug';
    }
    if (name.includes('planter') || name.includes('plant') || name.includes('vase')) return 'planter';
    if (name.includes('ottoman') || name.includes('pouf')) return 'ottoman';
    if (name.includes('bench')) return 'bench';
    if (name.includes('table')) return 'table';
    if (name.includes('chair')) return 'chair';
    return 'other';
  };

  // Product detail modal state
  const [detailProduct, setDetailProduct] = useState<any | null>(null);

  // Canvas panel UI state (matching user panel exactly)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isRoomImageCollapsed, setIsRoomImageCollapsed] = useState(false);

  // Smart re-visualization tracking (from CanvasPanel)
  const [visualizedProductIds, setVisualizedProductIds] = useState<Set<string>>(new Set());
  const [visualizedProducts, setVisualizedProducts] = useState<any[]>([]);
  const [needsRevisualization, setNeedsRevisualization] = useState(false);

  // Undo/Redo state (from CanvasPanel)
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Local visualization history for reliable undo/redo (not dependent on backend in-memory state)
  const [visualizationHistory, setVisualizationHistory] = useState<VisualizationHistoryEntry[]>([]);
  const [redoStack, setRedoStack] = useState<VisualizationHistoryEntry[]>([]);

  // Furniture position editing state (from CanvasPanel)
  const [isEditingPositions, setIsEditingPositions] = useState(false);
  const [furniturePositions, setFurniturePositions] = useState<FurniturePosition[]>([]);
  const [hasUnsavedPositions, setHasUnsavedPositions] = useState(false);

  // Layer extraction state for drag-and-drop editing (from CanvasPanel)
  const [baseRoomLayer, setBaseRoomLayer] = useState<string | null>(null);
  const [furnitureLayers, setFurnitureLayers] = useState<any[]>([]);
  const [isExtractingLayers, setIsExtractingLayers] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasProductsRef = useRef<HTMLDivElement>(null);
  const visualizationRef = useRef<HTMLDivElement>(null);
  const furnitureRemovalIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize on mount
  useEffect(() => {
    initSession();
    loadCategories();
    loadStores();
  }, []);

  const initSession = async () => {
    try {
      const session = await startChatSession();
      setSessionId(session.session_id);
    } catch (err) {
      console.error('Error creating session:', err);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await adminCuratedAPI.getCategories();
      setCategories(response.categories);
    } catch (err) {
      console.error('Error loading categories:', err);
    }
  };

  const loadStores = async () => {
    try {
      const response = await getAvailableStores();
      setStores(response.stores);
    } catch (err) {
      console.error('Error loading stores:', err);
    }
  };

  // Toggle store selection
  const toggleStore = (store: string) => {
    if (selectedStores.includes(store)) {
      setSelectedStores(selectedStores.filter(s => s !== store));
    } else {
      setSelectedStores([...selectedStores, store]);
    }
  };

  // Select/Deselect all stores
  const toggleAllStores = () => {
    if (selectedStores.length === stores.length) {
      setSelectedStores([]);
    } else {
      setSelectedStores([...stores]);
    }
  };

  // Toggle color selection
  const toggleColor = (colorValue: string) => {
    if (selectedColors.includes(colorValue)) {
      setSelectedColors(selectedColors.filter(c => c !== colorValue));
    } else {
      setSelectedColors([...selectedColors, colorValue]);
    }
  };

  // Search products with filters
  const handleSearch = async () => {
    try {
      setSearching(true);

      // Build search params - server now handles price and color filtering
      const searchParams: any = {
        query: searchQuery || undefined,
        categoryId: selectedCategory || undefined,
        sourceWebsite: selectedStores.length === 1 ? selectedStores[0] : undefined,
        minPrice: minPrice ? parseFloat(minPrice) : undefined,
        maxPrice: maxPrice ? parseFloat(maxPrice) : undefined,
        colors: selectedColors.length > 0 ? selectedColors.join(',') : undefined,
        limit: 500  // High limit to show all matching products
      };

      const response = await adminCuratedAPI.searchProducts(searchParams);

      // Apply client-side filtering for multiple stores (if needed)
      let products = response.products;

      // Filter by selected stores if multiple
      if (selectedStores.length > 1) {
        products = products.filter((p: any) =>
          selectedStores.includes(p.source_website) || selectedStores.includes(p.source)
        );
      }

      setDiscoveredProducts(products);
    } catch (err) {
      console.error('Error searching products:', err);
    } finally {
      setSearching(false);
    }
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedCategory(null);
    setSelectedStores([]);
    setMinPrice('');
    setMaxPrice('');
    setSelectedColors([]);
  };

  // Handle room image upload and trigger furniture removal
  const handleRoomImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      console.log('No file selected');
      return;
    }

    console.log('File selected:', file.name, 'Size:', file.size, 'Type:', file.type);

    // Clear any existing polling interval
    if (furnitureRemovalIntervalRef.current) {
      clearInterval(furnitureRemovalIntervalRef.current);
      furnitureRemovalIntervalRef.current = null;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      console.log('FileReader completed. Base64 length:', base64.length);
      console.log('Base64 prefix:', base64.substring(0, 50));

      // Set the original image first so it displays
      setRoomImage(base64);
      setVisualizationImage(null);
      setPreparedRoomImage(null);
      setError(null);

      console.log('State updated - roomImage set');

      // Start furniture removal
      startFurnitureRemovalProcess(base64);
    };
    reader.onerror = () => {
      console.error('FileReader error:', reader.error);
      setError('Failed to read image file');
    };
    reader.readAsDataURL(file);
  };

  // Separate async function for furniture removal to avoid closure issues
  const startFurnitureRemovalProcess = async (base64Image: string) => {
    try {
      setIsRemovingFurniture(true);

      // Extract just the base64 data (without the data:image/... prefix)
      const imageData = base64Image.includes('base64,')
        ? base64Image.split('base64,')[1]
        : base64Image;

      // Start the furniture removal job
      const response = await startFurnitureRemoval(imageData);
      const jobId = response.job_id;
      setFurnitureRemovalJobId(jobId);

      // Track if we've completed
      let isCompleted = false;

      // Poll for completion
      furnitureRemovalIntervalRef.current = setInterval(async () => {
        if (isCompleted) return;

        try {
          const status = await checkFurnitureRemovalStatus(jobId);
          console.log('Furniture removal status:', status.status);

          if (status.status === 'completed' && status.image) {
            isCompleted = true;
            if (furnitureRemovalIntervalRef.current) {
              clearInterval(furnitureRemovalIntervalRef.current);
              furnitureRemovalIntervalRef.current = null;
            }

            // Set the prepared room image (furniture removed)
            const preparedImage = status.image.startsWith('data:')
              ? status.image
              : `data:image/png;base64,${status.image}`;

            setPreparedRoomImage(preparedImage);
            setRoomImage(preparedImage);
            setIsRemovingFurniture(false);
          } else if (status.status === 'failed') {
            isCompleted = true;
            if (furnitureRemovalIntervalRef.current) {
              clearInterval(furnitureRemovalIntervalRef.current);
              furnitureRemovalIntervalRef.current = null;
            }
            setIsRemovingFurniture(false);
            setError('Failed to remove furniture from image. Using original image.');
          }
        } catch (err) {
          console.error('Error polling furniture removal status:', err);
        }
      }, 2000);

      // Timeout after 2 minutes
      setTimeout(() => {
        if (!isCompleted && furnitureRemovalIntervalRef.current) {
          clearInterval(furnitureRemovalIntervalRef.current);
          furnitureRemovalIntervalRef.current = null;
          setIsRemovingFurniture(false);
          setError('Furniture removal timed out. Using original image.');
        }
      }, 120000);

    } catch (err) {
      console.error('Error starting furniture removal:', err);
      setIsRemovingFurniture(false);
      setError('Failed to start furniture removal. Using original image.');
    }
  };

  // Add product to canvas with smart replacement logic
  const addProduct = (product: any) => {
    // Skip if exact same product is already in canvas
    if (selectedProducts.find(p => p.id === product.id)) return;

    // Extract and set product type if not already set
    const productType = product.product_type || extractProductType(product.name || '');
    const productWithType = { ...product, product_type: productType };

    console.log('[AdminCurated] Adding product to canvas:', product.name);
    console.log('[AdminCurated] Product type:', productType);

    // Check if this product type has quantity restrictions
    const isSingleInstance = FURNITURE_QUANTITY_RULES.SINGLE_INSTANCE.includes(productType);
    const isUnlimited = FURNITURE_QUANTITY_RULES.UNLIMITED.includes(productType);

    if (isSingleInstance) {
      // SINGLE INSTANCE: Replace existing product of same type
      const existingIndex = selectedProducts.findIndex((p) =>
        (p.product_type || extractProductType(p.name || '')) === productType
      );

      if (existingIndex >= 0) {
        console.log('[AdminCurated] Replacing existing single-instance product at index', existingIndex);
        const updated = [...selectedProducts];
        updated[existingIndex] = productWithType;
        setSelectedProducts(updated);
      } else {
        console.log('[AdminCurated] Adding new single-instance product');
        setSelectedProducts([...selectedProducts, productWithType]);
      }
    } else if (isUnlimited) {
      // UNLIMITED: Always add (no replacement)
      console.log('[AdminCurated] Adding unlimited product (no replacement)');
      setSelectedProducts([...selectedProducts, productWithType]);
    } else {
      // DEFAULT: For unclassified items, use the old replacement behavior
      const existingIndex = selectedProducts.findIndex((p) =>
        (p.product_type || extractProductType(p.name || '')) === productType
      );

      if (existingIndex >= 0) {
        console.log('[AdminCurated] Replacing existing product at index', existingIndex);
        const updated = [...selectedProducts];
        updated[existingIndex] = productWithType;
        setSelectedProducts(updated);
      } else {
        console.log('[AdminCurated] Adding new product');
        setSelectedProducts([...selectedProducts, productWithType]);
      }
    }
  };

  // Remove product from canvas
  const removeProduct = (productId: number) => {
    setSelectedProducts(selectedProducts.filter(p => p.id !== productId));
  };

  // Visualize
  const handleVisualize = async () => {
    if (!roomImage || selectedProducts.length === 0) {
      setError('Please upload a room image and add at least one product');
      return;
    }

    if (!sessionId) {
      setError('Session not initialized. Please refresh the page.');
      return;
    }

    try {
      setIsVisualizing(true);
      setError(null);

      const imageData = roomImage.includes('base64,')
        ? roomImage.split('base64,')[1]
        : roomImage;

      const productsForViz = selectedProducts.map(p => ({
        id: p.id,
        name: p.name,
        price: p.price,
        category: 'furniture',
        brand: p.brand || p.source_website,
        image_url: p.image_url || p.primary_image?.url,
        description: p.description || '',
      }));

      const result = await visualizeRoom(sessionId, {
        image: imageData,
        products: productsForViz,
        user_action: 'admin_curated_visualization',
      });

      if (result.visualization) {
        const vizImage = result.visualization.startsWith('data:')
          ? result.visualization
          : `data:image/png;base64,${result.visualization}`;
        setVisualizationImage(vizImage);
      }
    } catch (err) {
      console.error('Error visualizing:', err);
      setError('Failed to generate visualization. Please try again.');
    } finally {
      setIsVisualizing(false);
    }
  };

  // Publish
  const handlePublish = async () => {
    if (!title.trim()) {
      setError('Please enter a title');
      return;
    }
    if (!visualizationImage) {
      setError('Please generate a visualization first');
      return;
    }
    if (selectedProducts.length === 0) {
      setError('Please add at least one product');
      return;
    }

    // Check for product mismatch between selected products and visualized products
    const selectedIds = new Set(selectedProducts.map(p => String(p.id)));
    const visualizedIds = visualizedProductIds;

    // Find products that were visualized but are not in the selected list
    const missingFromSelected: string[] = [];
    visualizedIds.forEach(id => {
      if (!selectedIds.has(id)) {
        const product = visualizedProducts.find(p => String(p.id) === id);
        if (product) {
          missingFromSelected.push(product.name);
        }
      }
    });

    // Find products that are selected but weren't visualized
    const notVisualized: string[] = [];
    selectedProducts.forEach(p => {
      if (!visualizedIds.has(String(p.id))) {
        notVisualized.push(p.name);
      }
    });

    // Warn if there's a mismatch
    if (missingFromSelected.length > 0 || notVisualized.length > 0) {
      let warningMessage = 'Warning: Product mismatch detected!\n\n';

      if (missingFromSelected.length > 0) {
        warningMessage += `Products shown in visualization but NOT in product list:\n- ${missingFromSelected.join('\n- ')}\n\n`;
      }

      if (notVisualized.length > 0) {
        warningMessage += `Products in list but NOT shown in visualization:\n- ${notVisualized.join('\n- ')}\n\n`;
      }

      warningMessage += 'The saved curated look will only include products from the product list. Continue anyway?';

      if (!confirm(warningMessage)) {
        return;
      }
    }

    try {
      setSaving(true);
      setError(null);

      const vizImageData = visualizationImage.includes('base64,')
        ? visualizationImage.split('base64,')[1]
        : visualizationImage;

      const roomImageData = roomImage?.includes('base64,')
        ? roomImage.split('base64,')[1]
        : roomImage;

      // Debug: log the size of the data being sent
      const vizSizeMB = vizImageData ? (vizImageData.length * 0.75 / 1024 / 1024).toFixed(2) : '0';
      const roomSizeMB = roomImageData ? (roomImageData.length * 0.75 / 1024 / 1024).toFixed(2) : '0';
      console.log(`[Publish] Sending curated look - viz: ${vizSizeMB}MB, room: ${roomSizeMB}MB, products: ${selectedProducts.length}`);

      const result = await adminCuratedAPI.create({
        title,
        style_theme: styleTheme || title,
        style_description: styleDescription,
        room_type: roomType,
        room_image: roomImageData || undefined,
        visualization_image: vizImageData,
        is_published: true,
        product_ids: selectedProducts.map(p => p.id),
        product_types: selectedProducts.map(p => p.product_type || ''),
      });

      console.log('[Publish] Success:', result);
      router.push('/admin/curated');
    } catch (err: any) {
      console.error('Error saving look:', err);
      console.error('Error details:', err.response?.data || err.message);
      setError(`Failed to publish: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setSaving(false);
    }
  };

  // ============================================
  // CANVAS PANEL HANDLERS (Lifted from CanvasPanel.tsx)
  // ============================================

  // Check if canvas has changed since last visualization
  useEffect(() => {
    if (visualizedProductIds.size === 0 && !visualizationImage) {
      return;
    }
    const currentIds = new Set(selectedProducts.map(p => String(p.id)));
    const productsChanged =
      selectedProducts.length !== visualizedProductIds.size ||
      selectedProducts.some(p => !visualizedProductIds.has(String(p.id)));
    if (productsChanged) {
      setNeedsRevisualization(true);
    }
  }, [selectedProducts, visualizedProductIds, visualizationImage]);

  // Auto-scroll to canvas products when a product is added
  useEffect(() => {
    if (selectedProducts.length > 0 && canvasProductsRef.current) {
      canvasProductsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [selectedProducts.length]);

  // Auto-scroll to visualization result when first visualization completes
  useEffect(() => {
    if (visualizationImage && visualizationRef.current) {
      setTimeout(() => {
        visualizationRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [visualizationImage]);

  // Detect visualization change type
  const detectChangeType = () => {
    const currentIds = new Set(selectedProducts.map(p => String(p.id)));
    const removedProducts = Array.from(visualizedProductIds).filter(id => !currentIds.has(id));
    if (removedProducts.length > 0) {
      return { type: 'reset', reason: 'products_removed' };
    }
    const newProducts = selectedProducts.filter(p => !visualizedProductIds.has(String(p.id)));
    if (newProducts.length > 0 && visualizedProductIds.size > 0) {
      return { type: 'additive', newProducts };
    }
    if (visualizedProductIds.size === 0) {
      return { type: 'initial' };
    }
    return { type: 'no_change' };
  };

  // Smart Visualization with incremental support (from CanvasPanel)
  const handleSmartVisualize = async () => {
    if (!roomImage || selectedProducts.length === 0) return;
    if (!sessionId) {
      setError('Session not initialized. Please refresh the page.');
      return;
    }

    setIsVisualizing(true);
    setError(null);

    try {
      const changeInfo = detectChangeType();
      if (changeInfo.type === 'no_change') {
        setIsVisualizing(false);
        return;
      }

      let baseImage: string;
      let productsToVisualize: any[];
      let isIncremental = false;
      let forceReset = false;

      if (changeInfo.type === 'additive' && visualizationImage) {
        baseImage = visualizationImage;
        productsToVisualize = changeInfo.newProducts!;
        isIncremental = true;
      } else if (changeInfo.type === 'reset') {
        baseImage = roomImage;
        productsToVisualize = selectedProducts;
        forceReset = true;
      } else {
        baseImage = roomImage;
        productsToVisualize = selectedProducts;
      }

      const productDetails = productsToVisualize.map(p => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        style: 0.8,
        category: 'furniture'
      }));

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: baseImage,
          products: productDetails,
          analysis: { design_style: 'modern', color_palette: [], room_type: 'living_room' },
          is_incremental: isIncremental,
          force_reset: forceReset,
          user_uploaded_new_image: changeInfo.type === 'initial',
          action: 'add'  // Always add products in curated looks editor (skip furniture replacement clarification)
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Visualization failed');
      }

      const data = await response.json();

      // Handle needs_clarification response (shouldn't happen with action: 'add', but handle just in case)
      if (data.needs_clarification) {
        console.log('Clarification needed:', data.message);
        // Retry with explicit 'add' action
        const retryResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: baseImage,
            products: productDetails,
            analysis: { design_style: 'modern', color_palette: [], room_type: 'living_room' },
            is_incremental: isIncremental,
            force_reset: forceReset,
            user_uploaded_new_image: changeInfo.type === 'initial',
            action: 'add',
            existing_furniture: data.existing_furniture
          }),
        });
        if (!retryResponse.ok) {
          throw new Error('Visualization failed after clarification');
        }
        const retryData = await retryResponse.json();
        if (!retryData.visualization?.rendered_image) {
          throw new Error('No visualization image was generated');
        }
        const retryImage = retryData.visualization.rendered_image;
        const retryProductIds = new Set(selectedProducts.map(p => String(p.id)));

        // Push to local visualization history for reliable undo
        setVisualizationHistory(prev => [...prev, {
          image: retryImage,
          products: [...selectedProducts],
          productIds: retryProductIds
        }]);
        setRedoStack([]);

        setVisualizationImage(retryImage);
        setVisualizedProductIds(retryProductIds);
        setVisualizedProducts(selectedProducts);
        setNeedsRevisualization(false);
        setCanUndo(true);
        setCanRedo(false);
        return;
      }

      if (!data.visualization?.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      const newImage = data.visualization.rendered_image;
      const newProductIds = new Set(selectedProducts.map(p => String(p.id)));

      // Push to local visualization history for reliable undo
      setVisualizationHistory(prev => [...prev, {
        image: newImage,
        products: [...selectedProducts],
        productIds: newProductIds
      }]);
      // Clear redo stack when new visualization is added
      setRedoStack([]);

      setVisualizationImage(newImage);
      setVisualizedProductIds(newProductIds);
      setVisualizedProducts(selectedProducts);
      setNeedsRevisualization(false);
      // Use local history length to determine undo/redo state (more reliable than backend)
      setCanUndo(true); // Can always undo after a visualization
      setCanRedo(false); // Clear redo after new visualization
    } catch (error: any) {
      console.error('Visualization error:', error);
      setError(error.message || 'Failed to generate visualization. Please try again.');
    } finally {
      setIsVisualizing(false);
    }
  };

  // Handle undo visualization - uses local history for reliability
  const handleUndo = () => {
    // Check if we have local history to undo
    if (visualizationHistory.length === 0) {
      console.log('Cannot undo: no visualization history');
      return;
    }

    // Pop current state from history and push to redo stack
    const newHistory = [...visualizationHistory];
    const currentState = newHistory.pop();

    if (currentState) {
      setRedoStack(prev => [...prev, currentState]);
    }

    // If there's a previous state, restore it
    if (newHistory.length > 0) {
      const previousState = newHistory[newHistory.length - 1];
      setVisualizationImage(previousState.image);
      setVisualizedProductIds(previousState.productIds);
      setVisualizedProducts(previousState.products);
      setSelectedProducts(previousState.products);
    } else {
      // No previous state, go back to original room image
      setVisualizationImage(null);
      setVisualizedProductIds(new Set());
      setVisualizedProducts([]);
      setSelectedProducts([]);
    }

    setVisualizationHistory(newHistory);
    setCanUndo(newHistory.length > 0);
    setCanRedo(true);
    console.log(`Undo: history now has ${newHistory.length} items, redo stack has ${redoStack.length + 1} items`);
  };

  // Handle redo visualization - uses local history for reliability
  const handleRedo = () => {
    // Check if we have redo stack items
    if (redoStack.length === 0) {
      console.log('Cannot redo: no redo history');
      return;
    }

    // Pop from redo stack and push back to history
    const newRedoStack = [...redoStack];
    const stateToRestore = newRedoStack.pop();

    if (stateToRestore) {
      setVisualizationHistory(prev => [...prev, stateToRestore]);
      setVisualizationImage(stateToRestore.image);
      setVisualizedProductIds(stateToRestore.productIds);
      setVisualizedProducts(stateToRestore.products);
      setSelectedProducts(stateToRestore.products);
    }

    setRedoStack(newRedoStack);
    setCanUndo(true);
    setCanRedo(newRedoStack.length > 0);
    console.log(`Redo: history now has ${visualizationHistory.length + 1} items, redo stack has ${newRedoStack.length} items`);
  };

  // Enter edit mode for positions
  const handleEnterEditMode = async () => {
    if (!sessionId || !visualizationImage) {
      setError('Please create a visualization first.');
      return;
    }

    setIsExtractingLayers(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/remove-furniture`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: visualizationImage }),
        }
      );
      if (!response.ok) throw new Error('Failed to get clean room background');

      const data = await response.json();
      const cleanRoom = data.clean_image || visualizationImage;
      setBaseRoomLayer(cleanRoom);

      const productsToEdit = visualizedProducts.length > 0 ? visualizedProducts : selectedProducts;
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

      setFurniturePositions(initialPositions);
      setFurnitureLayers([]);
      setIsEditingPositions(true);
      setHasUnsavedPositions(false);
    } catch (error: any) {
      setError('Error entering edit mode. Please try again.');
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

  const handleRevisualizeWithPositions = async () => {
    if (!sessionId || !roomImage) {
      setError('No session or room image found.');
      return;
    }

    setIsVisualizing(true);
    try {
      await furniturePositionAPI.savePositions(sessionId, furniturePositions);

      const productDetails = selectedProducts.map(p => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        style: 0.8,
        category: 'furniture'
      }));

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: roomImage,
            products: productDetails,
            analysis: { design_style: 'modern', color_palette: [], room_type: 'living_room' },
            custom_positions: furniturePositions,
            is_incremental: false,
            force_reset: false,
          }),
        }
      );

      if (!response.ok) throw new Error('Visualization failed');
      const data = await response.json();

      if (!data.visualization?.rendered_image) throw new Error('No visualization image was generated');

      setVisualizationImage(data.visualization.rendered_image);
      setVisualizedProductIds(new Set(selectedProducts.map(p => String(p.id))));
      setNeedsRevisualization(false);
      setIsEditingPositions(false);
      setHasUnsavedPositions(false);
    } catch (error: any) {
      setError(error.message || 'Failed to re-visualize with new positions.');
    } finally {
      setIsVisualizing(false);
    }
  };

  // Get image URL from product
  const getProductImageUrl = (product: any): string => {
    if (product.images && product.images.length > 0) {
      const primaryImage = product.images.find((img: any) => img.is_primary) || product.images[0];
      return primaryImage.large_url || primaryImage.medium_url || primaryImage.original_url || '/placeholder-product.jpg';
    }
    return product.image_url || product.primary_image?.url || '/placeholder-product.jpg';
  };

  // Determine button state
  const canVisualize = roomImage !== null && selectedProducts.length > 0;
  const isUpToDate = canVisualize && !needsRevisualization && visualizationImage !== null;
  const isReady = canVisualize && (needsRevisualization || visualizationImage === null);

  // ============================================
  // END CANVAS PANEL HANDLERS
  // ============================================

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const totalPrice = selectedProducts.reduce((sum, p) => sum + (p.price || 0), 0);

  const getProductImage = (product: any) => {
    return product.image_url || product.primary_image?.url || null;
  };

  const activeFiltersCount = (selectedStores.length > 0 ? 1 : 0) +
    (minPrice || maxPrice ? 1 : 0) +
    (selectedColors.length > 0 ? 1 : 0);

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <Link href="/admin/curated" className="text-gray-500 hover:text-gray-700">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-lg font-bold text-gray-900">Create Curated Look</h1>
        </div>

        {/* Status indicators */}
        <div className="flex items-center gap-3 text-sm">
          {selectedProducts.length > 0 && (
            <span className="text-gray-600">
              {selectedProducts.length} product{selectedProducts.length !== 1 ? 's' : ''} selected
            </span>
          )}
          {visualizationImage && (
            <span className="flex items-center gap-1 text-green-600">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Visualization ready
            </span>
          )}
        </div>
      </header>

      {error && (
        <div className="mx-4 mt-2 p-2 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 font-bold">&times;</button>
        </div>
      )}

      {/* Three Panel Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Panel 1: Filters (15%) */}
        <div className="w-[15%] border-r border-gray-200 bg-white flex flex-col">
          <div className="p-3 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-pink-50 flex justify-between items-center">
            <div>
              <h2 className="font-semibold text-gray-900 text-sm">Filters</h2>
              {activeFiltersCount > 0 && (
                <p className="text-xs text-purple-600">{activeFiltersCount} filter(s) active</p>
              )}
            </div>
            {activeFiltersCount > 0 && (
              <button
                onClick={clearFilters}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Clear all
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-4">
            {/* Search Bar */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search products..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>

            {/* Price Range Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Price Range</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={minPrice}
                  onChange={(e) => setMinPrice(e.target.value)}
                  placeholder="Min"
                  className="w-1/2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500"
                />
                <input
                  type="number"
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  placeholder="Max"
                  className="w-1/2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div className="flex gap-1 mt-2 flex-wrap">
                {[
                  { label: '<10K', min: '', max: '10000' },
                  { label: '10-25K', min: '10000', max: '25000' },
                  { label: '25-50K', min: '25000', max: '50000' },
                  { label: '50K+', min: '50000', max: '' },
                ].map((range) => (
                  <button
                    key={range.label}
                    onClick={() => {
                      setMinPrice(range.min);
                      setMaxPrice(range.max);
                    }}
                    className={`px-2 py-1 text-xs rounded-full transition-colors ${
                      minPrice === range.min && maxPrice === range.max
                        ? 'bg-purple-100 text-purple-700 border border-purple-300'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Store Filter */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">Stores</label>
                <button
                  onClick={toggleAllStores}
                  className="text-xs text-purple-600 hover:text-purple-700"
                >
                  {selectedStores.length === stores.length ? 'Deselect all' : 'Select all'}
                </button>
              </div>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {stores.map((store) => (
                  <label
                    key={store}
                    className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1.5 rounded"
                  >
                    <input
                      type="checkbox"
                      checked={selectedStores.includes(store)}
                      onChange={() => toggleStore(store)}
                      className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm text-gray-700 capitalize">{store}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Color Filter */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">Colors</label>
                {selectedColors.length > 0 && (
                  <button
                    onClick={() => setSelectedColors([])}
                    className="text-xs text-purple-600 hover:text-purple-700"
                  >
                    Clear ({selectedColors.length})
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {FURNITURE_COLORS.map((color) => (
                  <button
                    key={color.value}
                    onClick={() => toggleColor(color.value)}
                    className={`w-7 h-7 rounded-full transition-all flex items-center justify-center ${
                      selectedColors.includes(color.value)
                        ? 'ring-2 ring-purple-500 ring-offset-1'
                        : 'hover:scale-110'
                    } ${color.border ? 'border border-gray-300' : ''}`}
                    style={{ backgroundColor: color.color }}
                    title={color.name}
                  >
                    {selectedColors.includes(color.value) && (
                      <svg
                        className={`w-4 h-4 ${
                          ['white', 'beige', 'yellow'].includes(color.value)
                            ? 'text-gray-800'
                            : 'text-white'
                        }`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={3}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Apply Filters Button */}
          <div className="p-3 border-t border-gray-200">
            <button
              onClick={handleSearch}
              disabled={searching}
              className="w-full py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {searching ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Searching...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  Apply Filters
                </>
              )}
            </button>
          </div>
        </div>

        {/* Panel 2: Product Discovery (40%) */}
        <div className="w-[40%] border-r border-gray-200 bg-white flex flex-col">
          <div className="p-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-purple-50">
            <div className="flex justify-between items-center">
              <h2 className="font-semibold text-gray-900 text-sm">Products</h2>
              {discoveredProducts.length > 0 && (
                <span className="text-xs text-purple-600 font-medium">
                  {discoveredProducts.length} found
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1">Click to add to canvas</p>
          </div>

          {/* Product Grid */}
          <div className="flex-1 overflow-y-auto p-3">
            {searching ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
              </div>
            ) : discoveredProducts.length > 0 ? (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                {discoveredProducts.map((product) => {
                  const isSelected = selectedProducts.find(p => p.id === product.id);
                  const imageUrl = getProductImage(product);
                  return (
                    <div
                      key={product.id}
                      className={`group rounded-lg border-2 overflow-hidden transition-all ${
                        isSelected
                          ? 'border-green-500 bg-green-50 opacity-60'
                          : 'border-gray-200 hover:border-purple-400 hover:shadow-md'
                      }`}
                    >
                      <div className="aspect-square relative bg-gray-100">
                        {imageUrl ? (
                          <Image
                            src={imageUrl}
                            alt={product.name}
                            fill
                            className="object-cover"
                            sizes="150px"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                        )}
                        {isSelected && (
                          <div className="absolute inset-0 bg-green-500/30 flex items-center justify-center">
                            <div className="bg-green-500 text-white rounded-full p-1.5">
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          </div>
                        )}
                        {/* Hover Action Buttons */}
                        {!isSelected && (
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                addProduct(product);
                              }}
                              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium rounded-lg flex items-center gap-1"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                              </svg>
                              Add to Canvas
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDetailProduct(product);
                              }}
                              className="px-3 py-1.5 bg-white/90 hover:bg-white text-gray-800 text-xs font-medium rounded-lg flex items-center gap-1"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              View Details
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="p-2">
                        <p className="font-medium text-gray-900 text-xs line-clamp-2">{product.name}</p>
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-[10px] text-gray-500 capitalize">{product.source_website || product.source}</span>
                          <span className="text-xs font-semibold text-purple-600">{formatPrice(product.price || 0)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-center text-gray-400">
                <div>
                  <svg className="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  <p className="text-sm">Apply filters or search to find products</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Panel 3: Canvas & Visualization (45%) - Matching User Panel Design */}
        <div className="w-[45%] bg-white flex flex-col overflow-hidden">
          {/* Hidden file input - always in DOM */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleRoomImageUpload}
            className="hidden"
          />

          {/* Header */}
          <div className="p-4 border-b border-gray-200 flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-gray-900">Your Canvas</h2>
              {selectedProducts.length > 0 && (
                <button
                  onClick={() => setSelectedProducts([])}
                  className="text-sm text-red-600 hover:text-red-700 font-medium"
                >
                  Clear All
                </button>
              )}
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">
                {selectedProducts.length} {selectedProducts.length === 1 ? 'item' : 'items'}
              </span>
              {selectedProducts.length > 0 && (
                <span className="font-semibold text-gray-900">{formatPrice(totalPrice)}</span>
              )}
            </div>
          </div>

          {/* Scrollable Content Area */}
          <div className="flex-1 overflow-y-auto">
            {/* Collapsible Room Image Section */}
            <div className="border-b border-gray-200">
              <button
                onClick={() => setIsRoomImageCollapsed(!isRoomImageCollapsed)}
                className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <h3 className="text-sm font-medium text-gray-900">Room Image</h3>
                <svg
                  className={`w-5 h-5 text-gray-600 transition-transform ${isRoomImageCollapsed ? '' : 'rotate-180'}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {!isRoomImageCollapsed && (
                <div className="px-4 pb-4">
                  {roomImage ? (
                    <div className="relative aspect-video bg-gray-100 rounded-lg overflow-hidden">
                      <img
                        src={roomImage}
                        alt="Room"
                        className="w-full h-full object-cover"
                        onLoad={() => console.log('Room image loaded successfully')}
                      />
                      {/* Furniture Removal Loading Overlay */}
                      {isRemovingFurniture && (
                        <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-10">
                          <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-500 mb-2"></div>
                          <span className="text-white font-medium text-sm">Removing Furniture...</span>
                        </div>
                      )}
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="absolute bottom-2 right-2 px-3 py-1.5 bg-white/90 backdrop-blur text-xs font-medium text-gray-900 rounded-lg hover:bg-white transition-colors"
                      >
                        Change
                      </button>
                      {preparedRoomImage && !isRemovingFurniture && (
                        <div className="absolute top-2 left-2 bg-green-500 text-white px-2 py-0.5 rounded-full text-xs font-medium">
                          Room Ready
                        </div>
                      )}
                    </div>
                  ) : (
                    <div
                      className="aspect-video bg-gray-100 rounded-lg flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 cursor-pointer hover:border-purple-400 transition-colors"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <svg className="w-12 h-12 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <button className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors">
                        Upload Room Image
                      </button>
                      <p className="text-xs text-gray-500 mt-2">Furniture will be auto-removed</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Products in Canvas */}
            <div ref={canvasProductsRef} className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-900">Products in Canvas</h3>
                {selectedProducts.length > 0 && (
                  <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                    <button
                      onClick={() => setViewMode('grid')}
                      className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600'}`}
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setViewMode('list')}
                      className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600'}`}
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>
                )}
              </div>

              {selectedProducts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                    <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                    </svg>
                  </div>
                  <p className="text-sm text-gray-600">No products added yet</p>
                  <p className="text-xs text-gray-500 mt-1">Select products from the discovery panel</p>
                </div>
              ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-3 gap-2">
                  {selectedProducts.map((product) => (
                    <div key={product.id} className="relative bg-white border border-gray-200 rounded-lg overflow-hidden group">
                      <div className="aspect-square bg-gray-100 relative">
                        {getProductImage(product) ? (
                          <Image src={getProductImage(product)} alt={product.name} fill className="object-cover" sizes="100px" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                        )}
                        <button
                          onClick={() => removeProduct(product.id)}
                          className="absolute top-0.5 right-0.5 w-5 h-5 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        </button>
                      </div>
                      <div className="p-1">
                        <p className="text-[10px] font-medium text-gray-900 line-clamp-1">{product.name}</p>
                        <p className="text-[10px] text-purple-600 font-semibold">{formatPrice(product.price || 0)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-1.5">
                  {selectedProducts.map((product) => (
                    <div key={product.id} className="flex items-center gap-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                      <div className="w-12 h-12 bg-gray-100 rounded relative flex-shrink-0">
                        {getProductImage(product) ? (
                          <Image src={getProductImage(product)} alt={product.name} fill className="object-cover rounded" sizes="48px" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-gray-900 truncate">{product.name}</p>
                        <p className="text-[10px] text-gray-500 capitalize">{product.source_website || product.source}</p>
                        <p className="text-xs font-semibold text-purple-600">{formatPrice(product.price || 0)}</p>
                      </div>
                      <button
                        onClick={() => removeProduct(product.id)}
                        className="text-red-600 hover:text-red-700 p-0.5"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Visualization Result with Edit Positions, Undo/Redo (Exact copy from CanvasPanel) */}
            {visualizationImage && (
              <div ref={visualizationRef} className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-900">Visualization Result</h3>
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
                            Extracting...
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
                      className="p-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      title="Undo"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                      </svg>
                    </button>
                    <button
                      onClick={handleRedo}
                      disabled={!canRedo || isEditingPositions}
                      className="p-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      title="Redo"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6" />
                      </svg>
                    </button>
                    <button
                      onClick={() => {
                        setVisualizationImage(null);
                        setVisualizedProductIds(new Set());
                        setNeedsRevisualization(false);
                      }}
                      disabled={isEditingPositions}
                      className="text-xs text-red-600 hover:text-red-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                {/* Outdated Warning Banner */}
                {needsRevisualization && (
                  <div className="mb-2 p-2 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
                    <svg className="w-5 h-5 text-amber-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <p className="text-xs text-amber-800 font-medium">Canvas changed - Re-visualize to update</p>
                  </div>
                )}

                {/* Image/Canvas Container */}
                <div className={`relative aspect-video bg-gray-100 rounded-lg overflow-hidden ${needsRevisualization ? 'ring-2 ring-amber-400' : ''} ${isEditingPositions ? 'ring-2 ring-purple-400' : ''}`}>
                  {isEditingPositions ? (
                    <DraggableFurnitureCanvas
                      visualizationImage={visualizationImage}
                      baseRoomLayer={baseRoomLayer}
                      furnitureLayers={furnitureLayers}
                      furniturePositions={furniturePositions}
                      onPositionsChange={handlePositionsChange}
                      products={selectedProducts}
                      containerWidth={800}
                      containerHeight={450}
                    />
                  ) : (
                    <>
                      <img
                        src={visualizationImage}
                        alt="Visualization result"
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute bottom-2 left-2 bg-green-500 text-white px-2 py-0.5 rounded-full text-xs font-medium">
                        AI Visualization
                      </div>
                    </>
                  )}
                </div>

                {/* Edit Mode Actions */}
                {isEditingPositions && (
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      onClick={handleExitEditMode}
                      className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 text-sm font-medium transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                )}

                {/* Unsaved Changes Warning */}
                {hasUnsavedPositions && isEditingPositions && (
                  <p className="text-xs text-amber-600 mt-2 text-center flex items-center justify-center gap-1">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    You have unsaved position changes
                  </p>
                )}

                {!needsRevisualization && !isEditingPositions && (
                  <p className="text-xs text-green-600 mt-2 text-center">Visualization up to date</p>
                )}
              </div>
            )}

            {/* Look Details */}
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-sm font-medium text-gray-900 mb-3">Look Details</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Title *</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Give your look a name..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={styleDescription}
                    onChange={(e) => setStyleDescription(e.target.value)}
                    placeholder="Describe this curated look..."
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Room Type</label>
                  <select
                    value={roomType}
                    onChange={(e) => setRoomType(e.target.value as 'living_room' | 'bedroom')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    <option value="living_room">Living Room</option>
                    <option value="bedroom">Bedroom</option>
                    <option value="dining_room">Dining Room</option>
                    <option value="office">Office</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Visualize & Publish Buttons - Fixed at bottom (Smart states from CanvasPanel) */}
          <div className="p-4 border-t border-gray-200 flex-shrink-0 space-y-2">
            {/* Visualize Button with Smart States */}
            {isEditingPositions && hasUnsavedPositions ? (
              /* State: Edit Mode with Unsaved Positions (Purple, Enabled) */
              <button
                onClick={handleRevisualizeWithPositions}
                disabled={isVisualizing}
                className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
              >
                {isVisualizing ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
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
              /* State 2: Up to Date (Green, Disabled) */
              <button
                disabled
                className="w-full py-3 px-4 bg-green-500 text-white font-semibold rounded-lg flex items-center justify-center gap-2 cursor-not-allowed opacity-90"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Up to date
              </button>
            ) : isReady ? (
              /* State 1: Ready to Visualize (Primary gradient, Enabled) */
              <button
                onClick={handleSmartVisualize}
                disabled={isVisualizing || isRemovingFurniture}
                className="w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
              >
                {isVisualizing ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Visualizing...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                      <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                    </svg>
                    Visualize Room
                  </>
                )}
              </button>
            ) : (
              /* State 3: Not Ready (Gray, Disabled) */
              <button
                disabled
                className="w-full py-3 px-4 bg-gray-300 text-gray-500 font-semibold rounded-lg cursor-not-allowed flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                  <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                </svg>
                Visualize Room
              </button>
            )}

            {/* Publish Button */}
            <button
              onClick={handlePublish}
              disabled={saving || !visualizationImage || selectedProducts.length === 0 || !title.trim()}
              className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Publishing...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Publish Curated Look
                </>
              )}
            </button>

            {/* Helper Messages */}
            {!roomImage && (
              <p className="text-xs text-amber-600 text-center">Upload a room image to visualize</p>
            )}
            {roomImage && selectedProducts.length === 0 && (
              <p className="text-xs text-amber-600 text-center">Add products to canvas to visualize</p>
            )}
            {visualizationImage && !title.trim() && (
              <p className="text-xs text-amber-600 text-center">Enter a title to publish</p>
            )}
          </div>
        </div>
      </div>

      {/* Product Detail Modal */}
      {detailProduct && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex justify-between items-center p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Product Details</h3>
              <button
                onClick={() => setDetailProduct(null)}
                className="p-1 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-4 overflow-y-auto max-h-[calc(90vh-140px)]">
              <div className="flex gap-4">
                {/* Product Image */}
                <div className="w-1/3 flex-shrink-0">
                  <div className="aspect-square relative bg-gray-100 rounded-lg overflow-hidden">
                    {getProductImage(detailProduct) ? (
                      <Image
                        src={getProductImage(detailProduct)}
                        alt={detailProduct.name}
                        fill
                        className="object-cover"
                        sizes="300px"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <svg className="w-12 h-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                    )}
                  </div>
                </div>

                {/* Product Info */}
                <div className="flex-1">
                  <h4 className="text-xl font-bold text-gray-900 mb-2">{detailProduct.name}</h4>

                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-2xl font-bold text-purple-600">
                      {formatPrice(detailProduct.price || 0)}
                    </span>
                    <span className="text-sm text-gray-500 capitalize px-2 py-0.5 bg-gray-100 rounded">
                      {detailProduct.source_website || detailProduct.source}
                    </span>
                  </div>

                  {detailProduct.brand && (
                    <p className="text-sm text-gray-600 mb-2">
                      <span className="font-medium">Brand:</span> {detailProduct.brand}
                    </p>
                  )}

                  {detailProduct.description && (
                    <div className="mt-4">
                      <h5 className="text-sm font-medium text-gray-700 mb-1">Description</h5>
                      <p className="text-sm text-gray-600 leading-relaxed">
                        {detailProduct.description}
                      </p>
                    </div>
                  )}

                  {detailProduct.source_url && (
                    <a
                      href={detailProduct.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 mt-4"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      View on {detailProduct.source_website || 'store'}
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setDetailProduct(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => {
                  addProduct(detailProduct);
                  setDetailProduct(null);
                }}
                disabled={selectedProducts.find(p => p.id === detailProduct.id)}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                {selectedProducts.find(p => p.id === detailProduct.id) ? 'Already Added' : 'Add to Canvas'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
