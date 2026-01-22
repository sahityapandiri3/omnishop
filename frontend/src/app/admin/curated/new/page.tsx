'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { Panel, Group, GroupImperativeHandle } from 'react-resizable-panels';
import { PanelResizeHandle } from '@/components/ui/PanelResizeHandle';
import { adminCuratedAPI, getCategorizedStores, visualizeRoom, startChatSession, startFurnitureRemoval, checkFurnitureRemovalStatus, furniturePositionAPI, generateAngleView, StoreCategory, getRecoveredCurationState, clearRecoveredCurationState, imageAPI } from '@/utils/api';
import { FurniturePosition, MagicGrabLayer, PendingMoveData } from '@/components/DraggableFurnitureCanvas';
import { AngleSelector, ViewingAngle } from '@/components/AngleSelector';

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

// Product style options (matches Product.primary_style values)
const PRODUCT_STYLES = [
  { value: 'modern', label: 'Modern' },
  { value: 'modern_luxury', label: 'Modern Luxury' },
  { value: 'indian_contemporary', label: 'Indian Contemporary' },
  { value: 'minimalist', label: 'Minimalist' },
  { value: 'japandi', label: 'Japandi' },
  { value: 'scandinavian', label: 'Scandinavian' },
  { value: 'mid_century_modern', label: 'Mid-Century Modern' },
  { value: 'boho', label: 'Boho' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'contemporary', label: 'Contemporary' },
  { value: 'eclectic', label: 'Eclectic' },
];

// Common material options for filtering
const PRODUCT_MATERIALS = [
  { value: 'wood', label: 'Wood' },
  { value: 'metal', label: 'Metal' },
  { value: 'glass', label: 'Glass' },
  { value: 'fabric', label: 'Fabric' },
  { value: 'leather', label: 'Leather' },
  { value: 'ceramic', label: 'Ceramic' },
  { value: 'marble', label: 'Marble' },
  { value: 'brass', label: 'Brass' },
  { value: 'iron', label: 'Iron' },
  { value: 'concrete', label: 'Concrete' },
  { value: 'linen', label: 'Linen' },
  { value: 'velvet', label: 'Velvet' },
  { value: 'cotton', label: 'Cotton' },
  { value: 'stone', label: 'Stone' },
  { value: 'bamboo', label: 'Bamboo' },
  { value: 'rattan', label: 'Rattan' },
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
  const searchParams = useSearchParams();
  const styleFromId = searchParams?.get('style_from');
  const editId = searchParams?.get('edit');
  // Use either style_from or edit parameter for loading existing look
  const initialLookId = styleFromId || editId || null;

  // Track existing look ID as state so we can update it after creating a new draft
  const [existingLookId, setExistingLookId] = useState<string | null>(initialLookId);

  // Loading state for style_from
  const [loadingStyleFrom, setLoadingStyleFrom] = useState(false);

  // Session for visualization
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Filter state
  const [categories, setCategories] = useState<Category[]>([]);
  const [stores, setStores] = useState<string[]>([]);
  const [storeCategories, setStoreCategories] = useState<StoreCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [selectedColors, setSelectedColors] = useState<string[]>([]);
  const [selectedProductStyles, setSelectedProductStyles] = useState<string[]>([]);
  const [selectedMaterials, setSelectedMaterials] = useState<string[]>([]);

  // Product discovery state
  const [discoveredProducts, setDiscoveredProducts] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  // Pagination state for infinite scroll
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [totalProducts, setTotalProducts] = useState(0);
  const [totalPrimary, setTotalPrimary] = useState(0);
  const [totalRelated, setTotalRelated] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const productsContainerRef = useRef<HTMLDivElement>(null);
  const panelGroupRef = useRef<GroupImperativeHandle>(null);

  // Canvas state
  const [selectedProducts, setSelectedProducts] = useState<any[]>([]);
  const [roomImage, setRoomImage] = useState<string | null>(null);
  const [visualizationImage, setVisualizationImage] = useState<string | null>(null);
  const [isVisualizing, setIsVisualizing] = useState(false);

  // Multi-angle viewing state
  const [currentAngle, setCurrentAngle] = useState<ViewingAngle>('front');
  const [angleImages, setAngleImages] = useState<Record<ViewingAngle, string | null>>({
    front: null, left: null, right: null, back: null
  });
  const [loadingAngle, setLoadingAngle] = useState<ViewingAngle | null>(null);

  // Furniture removal state
  const [isRemovingFurniture, setIsRemovingFurniture] = useState(false);
  const [furnitureRemovalJobId, setFurnitureRemovalJobId] = useState<string | null>(null);
  const [preparedRoomImage, setPreparedRoomImage] = useState<string | null>(null);

  // Publish state
  const [title, setTitle] = useState('');
  const [styleTheme, setStyleTheme] = useState('');
  const [styleDescription, setStyleDescription] = useState('');
  const [styleLabels, setStyleLabels] = useState<string[]>([]);
  const [roomType, setRoomType] = useState<'living_room' | 'bedroom'>('living_room');
  // Budget tier options (auto-calculated based on total price)
  // Must match backend BudgetTier enum in database/models.py
  const BUDGET_TIER_OPTIONS = [
    { value: 'pocket_friendly', label: 'Pocket-friendly', range: '< ₹2L' },
    { value: 'mid_tier', label: 'Mid-tier', range: '₹2L – ₹8L' },
    { value: 'premium', label: 'Premium', range: '₹8L – ₹15L' },
    { value: 'luxury', label: 'Luxury', range: '₹15L+' },
  ];

  // Auto-calculate budget tier based on total price
  const calculateBudgetTier = (price: number): { value: string; label: string; range: string } => {
    if (price < 200000) return BUDGET_TIER_OPTIONS[0]; // Pocket-friendly
    if (price < 800000) return BUDGET_TIER_OPTIONS[1]; // Mid-tier
    if (price < 1500000) return BUDGET_TIER_OPTIONS[2]; // Premium
    return BUDGET_TIER_OPTIONS[3]; // Luxury
  };

  // Available style labels for multi-select
  const STYLE_LABEL_OPTIONS = [
    { value: 'modern', label: 'Modern' },
    { value: 'modern_luxury', label: 'Modern Luxury' },
    { value: 'indian_contemporary', label: 'Indian Contemporary' },
    { value: 'minimalist', label: 'Minimalist' },
    { value: 'japandi', label: 'Japandi' },
    { value: 'scandinavian', label: 'Scandinavian' },
    { value: 'mid_century_modern', label: 'Mid-Century Modern' },
    { value: 'bohemian', label: 'Bohemian' },
    { value: 'industrial', label: 'Industrial' },
    { value: 'contemporary', label: 'Contemporary' },
    { value: 'eclectic', label: 'Eclectic' },
  ];
  const [saving, setSaving] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ref-based guards to prevent double submissions (more reliable than state alone)
  const isSavingRef = useRef(false);
  const isSavingDraftRef = useRef(false);

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

  // Magic Grab state (for draggable layers mode)
  const [magicGrabBackground, setMagicGrabBackground] = useState<string | null>(null);
  const [magicGrabLayers, setMagicGrabLayers] = useState<MagicGrabLayer[]>([]);
  const [useMagicGrabMode, setUseMagicGrabMode] = useState(false);

  // Click-to-Select edit mode state
  const [pendingMoveData, setPendingMoveData] = useState<PendingMoveData | null>(null);
  const [preEditVisualization, setPreEditVisualization] = useState<string | null>(null);

  // Special instructions for edit mode (text-based repositioning)
  const [editSpecialInstructions, setEditSpecialInstructions] = useState('');

  // Track if positions have been manually edited (to inform subsequent visualizations)
  const [positionsWereEdited, setPositionsWereEdited] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasProductsRef = useRef<HTMLDivElement>(null);
  const visualizationRef = useRef<HTMLDivElement>(null);
  const furnitureRemovalIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Memoize curatedProducts to prevent infinite re-renders in DraggableFurnitureCanvas
  const curatedProductsForCanvas = useMemo(() =>
    selectedProducts.map(p => ({
      id: p.id,
      name: p.name,
      image_url: p.images?.[0]?.medium_url || p.images?.[0]?.original_url
    })),
    [selectedProducts]
  );

  // Memoize curatedLookId to prevent re-renders
  const curatedLookIdForCanvas = useMemo(() =>
    existingLookId ? parseInt(existingLookId) : undefined,
    [existingLookId]
  );

  // Initialize on mount and restore state if recovered from session expiry
  useEffect(() => {
    // Check for recovered state first (from 401 redirect)
    const recoveredState = getRecoveredCurationState();
    if (recoveredState) {
      console.log('[Curation] Restoring state from session recovery');

      // Restore all state
      if (recoveredState.selectedProducts) setSelectedProducts(recoveredState.selectedProducts);
      if (recoveredState.roomImage) setRoomImage(recoveredState.roomImage);
      if (recoveredState.visualizationImage) setVisualizationImage(recoveredState.visualizationImage);
      if (recoveredState.title) setTitle(recoveredState.title);
      if (recoveredState.styleTheme) setStyleTheme(recoveredState.styleTheme);
      if (recoveredState.styleDescription) setStyleDescription(recoveredState.styleDescription);
      if (recoveredState.styleLabels) setStyleLabels(recoveredState.styleLabels);
      if (recoveredState.roomType) setRoomType(recoveredState.roomType);
      if (recoveredState.preparedRoomImage) setPreparedRoomImage(recoveredState.preparedRoomImage);
      if (recoveredState.furniturePositions) setFurniturePositions(recoveredState.furniturePositions);

      // Clear recovery data after restoring
      clearRecoveredCurationState();
      console.log('[Curation] State restored successfully');
    }

    initSession();
    loadCategories();
    loadStores();
  }, []);

  // Continuously save curation state to sessionStorage for recovery after 401
  useEffect(() => {
    // Don't save empty state or during initial load
    if (!roomImage && selectedProducts.length === 0 && !title) {
      return;
    }

    const state = {
      selectedProducts,
      roomImage,
      visualizationImage,
      title,
      styleTheme,
      styleDescription,
      styleLabels,
      roomType,
      preparedRoomImage,
      furniturePositions,
    };

    try {
      sessionStorage.setItem('curation_page_state', JSON.stringify(state));
    } catch (e) {
      console.warn('[Curation] Failed to save state to sessionStorage:', e);
    }
  }, [selectedProducts, roomImage, visualizationImage, title, styleTheme, styleDescription, styleLabels, roomType, preparedRoomImage, furniturePositions]);

  // Load existing curated look if style_from or edit parameter is present
  useEffect(() => {
    if (existingLookId && sessionId) {
      loadExistingLook(parseInt(existingLookId));
    }
  }, [existingLookId, sessionId]);

  const loadExistingLook = async (lookId: number) => {
    try {
      setLoadingStyleFrom(true);
      console.log('[StyleFrom] Loading existing look:', lookId);

      const look = await adminCuratedAPI.get(lookId);
      console.log('[StyleFrom] Loaded look:', look.title, 'with', look.products.length, 'products');

      // Pre-populate metadata (including title for editing the same item)
      setTitle(look.title || '');
      setStyleTheme(look.style_theme || '');
      setStyleDescription(look.style_description || '');
      setStyleLabels(look.style_labels || []);
      setRoomType(look.room_type as 'living_room' | 'bedroom');
      // budget_tier is auto-calculated based on total price, no need to load it

      // Pre-populate room image
      if (look.room_image) {
        const roomImg = look.room_image.startsWith('data:')
          ? look.room_image
          : `data:image/png;base64,${look.room_image}`;
        setRoomImage(roomImg);
      }

      // Pre-populate visualization image
      if (look.visualization_image) {
        const vizImg = look.visualization_image.startsWith('data:')
          ? look.visualization_image
          : `data:image/png;base64,${look.visualization_image}`;
        setVisualizationImage(vizImg);
      }

      // Pre-populate products with quantities from the API
      const productsWithQuantity = look.products.map(p => ({
        ...p,
        quantity: p.quantity || 1, // Use actual quantity from API
        product_type: p.product_type || ''
      }));
      setSelectedProducts(productsWithQuantity);

      // Set visualized state - assume the saved visualization matches database quantities
      // This prevents false "quantity changed" detection on initial load
      // Only when user ACTUALLY changes quantities should it trigger re-visualization
      const productIds = new Set(look.products.map(p => String(p.id)));
      setVisualizedProductIds(productIds);

      // Set visualized products with ACTUAL quantities from database
      // This assumes the saved visualization was created with these quantities
      setVisualizedProducts(productsWithQuantity);

      // IMPORTANT: Explicitly set needsRevisualization to false AFTER all state updates
      // This prevents the change detection useEffect from incorrectly flagging changes
      // due to timing issues between state updates
      setNeedsRevisualization(false);

      // CRITICAL: Save the initial state to visualization history
      // This allows undo to go back to the loaded state instead of null
      if (look.visualization_image) {
        const vizImg = look.visualization_image.startsWith('data:')
          ? look.visualization_image
          : `data:image/png;base64,${look.visualization_image}`;
        const initialHistoryEntry = {
          image: vizImg,
          products: productsWithQuantity,
          productIds: productIds
        };
        setVisualizationHistory([initialHistoryEntry]);
        setCanUndo(false); // Can't undo past the initial loaded state
        setRedoStack([]); // Clear any redo stack
        console.log('[StyleFrom] Added initial state to visualization history');
      }

      console.log('[StyleFrom] Pre-populated canvas with', productsWithQuantity.length, 'products');
      console.log('[StyleFrom] Product IDs (string):', Array.from(productIds));
      console.log('[StyleFrom] Selected products (actual qty):', productsWithQuantity.map(p => ({ id: p.id, name: p.name, qty: p.quantity })));
      console.log('[StyleFrom] Visualized products set to match selected (no false quantity changes)');
      console.log('[StyleFrom] needsRevisualization explicitly set to FALSE');
    } catch (err) {
      console.error('[StyleFrom] Error loading look:', err);
      setError('Failed to load existing look');
    } finally {
      setLoadingStyleFrom(false);
    }
  };

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
      // Force refresh to always get latest stores from server (categorized)
      const response = await getCategorizedStores(true);
      setStoreCategories(response.categories);
      // Also maintain flat list for backwards compatibility
      setStores(response.all_stores.map(s => s.name));
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

  // Build search params helper
  const buildSearchParams = (page: number = 1) => ({
    query: searchQuery || undefined,
    categoryId: selectedCategory || undefined,
    sourceWebsite: selectedStores.length > 0 ? selectedStores.join(',') : undefined,
    minPrice: minPrice ? parseFloat(minPrice) : undefined,
    maxPrice: maxPrice ? parseFloat(maxPrice) : undefined,
    colors: selectedColors.length > 0 ? selectedColors.join(',') : undefined,
    styles: selectedProductStyles.length > 0 ? selectedProductStyles.join(',') : undefined,
    materials: selectedMaterials.length > 0 ? selectedMaterials.join(',') : undefined,
    page,
    pageSize: 50,
  });

  // Search products with filters (first page)
  const handleSearch = async () => {
    try {
      setSearching(true);
      setCurrentPage(1);
      setDiscoveredProducts([]);

      const response = await adminCuratedAPI.searchProducts(buildSearchParams(1));

      // Backend now handles multi-store filtering
      setDiscoveredProducts(response.products);
      setHasMore(response.has_more);
      setTotalProducts(response.total);
      setTotalPrimary(response.total_primary || 0);
      setTotalRelated(response.total_related || 0);
    } catch (err) {
      console.error('Error searching products:', err);
    } finally {
      setSearching(false);
    }
  };

  // Load more products for infinite scroll
  const loadMoreProducts = async () => {
    if (loadingMore || !hasMore) return;

    try {
      setLoadingMore(true);
      const nextPage = currentPage + 1;
      const response = await adminCuratedAPI.searchProducts(buildSearchParams(nextPage));

      // Backend now handles multi-store filtering
      setDiscoveredProducts(prev => [...prev, ...response.products]);
      setCurrentPage(nextPage);
      setHasMore(response.has_more);
    } catch (err) {
      console.error('Error loading more products:', err);
    } finally {
      setLoadingMore(false);
    }
  };

  // Scroll handler for infinite scroll
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    // Load more when user scrolls to bottom (with 200px threshold)
    if (scrollHeight - scrollTop - clientHeight < 200 && !loadingMore && hasMore) {
      loadMoreProducts();
    }
  };

  // Toggle product style selection
  const toggleProductStyle = (styleValue: string) => {
    if (selectedProductStyles.includes(styleValue)) {
      setSelectedProductStyles(selectedProductStyles.filter(s => s !== styleValue));
    } else {
      setSelectedProductStyles([...selectedProductStyles, styleValue]);
    }
  };

  // Toggle material selection
  const toggleMaterial = (materialValue: string) => {
    if (selectedMaterials.includes(materialValue)) {
      setSelectedMaterials(selectedMaterials.filter(m => m !== materialValue));
    } else {
      setSelectedMaterials([...selectedMaterials, materialValue]);
    }
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedCategory(null);
    setSelectedStores([]);
    setMinPrice('');
    setMaxPrice('');
    setSelectedColors([]);
    setSelectedProductStyles([]);
    setSelectedMaterials([]);
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

      // OPTIMIZATION: Upload image and perform room analysis FIRST (if existing look)
      // This caches room analysis (camera view, dimensions, furniture detection) in the CuratedLook table
      // Saves 4-13 seconds per subsequent visualization by avoiding redundant Gemini calls
      if (existingLookId) {
        try {
          console.log('[CuratedNew] Uploading room image for analysis with curated_look_id:', existingLookId);
          const uploadResponse = await imageAPI.uploadRoomImageFromBase64(
            base64Image,
            null,  // project_id
            parseInt(existingLookId)  // curated_look_id
          );
          console.log('[CuratedNew] Room analysis complete:', uploadResponse.room_analysis?.room_type);
        } catch (uploadError) {
          // Log but don't fail - room analysis caching is an optimization, not critical
          console.warn('[CuratedNew] Room analysis upload failed (non-critical):', uploadError);
        }
      }

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
        } catch (err: any) {
          console.error('Error polling furniture removal status:', err);

          // Check if it's a 404 error (job not found - server may have restarted)
          const is404 = err?.response?.status === 404 ||
                        err?.status === 404 ||
                        err?.message?.includes('404') ||
                        err?.message?.includes('not found') ||
                        err?.response?.data?.detail?.includes('not found');

          if (is404) {
            console.log('Furniture removal job not found (404) - server may have restarted, stopping polling');
            isCompleted = true;
            if (furnitureRemovalIntervalRef.current) {
              clearInterval(furnitureRemovalIntervalRef.current);
              furnitureRemovalIntervalRef.current = null;
            }
            setIsRemovingFurniture(false);
            setFurnitureRemovalJobId(null);
            // Don't show error - just silently stop polling since the job is gone
          }
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

  // Add product to canvas - curator mode uses quantity tracking
  const addProduct = (product: any) => {
    // Extract and set product type if not already set
    const productType = product.product_type || extractProductType(product.name || '');

    // Check if product already exists in canvas
    const existingIndex = selectedProducts.findIndex(p => p.id === product.id);

    if (existingIndex !== -1) {
      // Increment quantity if product exists
      const updatedProducts = [...selectedProducts];
      updatedProducts[existingIndex] = {
        ...updatedProducts[existingIndex],
        quantity: (updatedProducts[existingIndex].quantity || 1) + 1
      };
      setSelectedProducts(updatedProducts);
      console.log('[AdminCurated] Incrementing quantity for:', product.name, 'New quantity:', updatedProducts[existingIndex].quantity);
    } else {
      // Add new product with quantity 1
      const productWithType = {
        ...product,
        product_type: productType,
        quantity: 1
      };
      setSelectedProducts([...selectedProducts, productWithType]);
      console.log('[AdminCurated] Adding product to canvas:', product.name);
    }
  };

  // Update product quantity
  const updateProductQuantity = (productId: number, newQuantity: number) => {
    if (newQuantity <= 0) {
      // Remove product if quantity is 0 or negative
      setSelectedProducts(selectedProducts.filter(p => p.id !== productId));
    } else {
      const updatedProducts = selectedProducts.map(p =>
        p.id === productId ? { ...p, quantity: newQuantity } : p
      );
      setSelectedProducts(updatedProducts);
    }
  };

  // Increment product quantity
  const incrementQuantity = (productId: number) => {
    const product = selectedProducts.find(p => p.id === productId);
    if (product) {
      updateProductQuantity(productId, (product.quantity || 1) + 1);
    }
  };

  // Decrement product quantity
  const decrementQuantity = (productId: number) => {
    const product = selectedProducts.find(p => p.id === productId);
    if (product) {
      updateProductQuantity(productId, (product.quantity || 1) - 1);
    }
  };

  // Remove product from canvas
  const removeProduct = (productId: number) => {
    setSelectedProducts(selectedProducts.filter(p => p.id !== productId));
    // DO NOT update visualizedProducts here - it should only change after successful visualization
    // The visualizedProducts represents what's actually in the visualization image
    // Keeping them different allows detectChangeType to detect the removal
  };

  // Get quantity for a product (for display in discovery panel)
  const getProductQuantity = (productId: number): number => {
    const product = selectedProducts.find(p => p.id === productId);
    return product?.quantity || 0;
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
        quantity: p.quantity || 1,
      }));

      const result = await visualizeRoom(sessionId, {
        image: imageData,
        products: productsForViz,
        user_action: 'admin_curated_visualization',
        curated_look_id: existingLookId ? parseInt(existingLookId) : undefined,
      });

      if (result.visualization) {
        const vizImage = result.visualization.startsWith('data:')
          ? result.visualization
          : `data:image/png;base64,${result.visualization}`;
        setVisualizationImage(vizImage);
        // Reset angle cache - new visualization starts from front view
        setAngleImages({ front: vizImage, left: null, right: null, back: null });
        setCurrentAngle('front');
      }
    } catch (err) {
      console.error('Error visualizing:', err);
      setError('Failed to generate visualization. Please try again.');
    } finally {
      setIsVisualizing(false);
    }
  };

  // Handle angle selection for multi-angle viewing
  const handleAngleSelect = async (angle: ViewingAngle) => {
    // Front view is always the original visualization
    if (angle === 'front') {
      setCurrentAngle('front');
      return;
    }

    // If angle is already cached, just switch to it
    if (angleImages[angle]) {
      setCurrentAngle(angle);
      return;
    }

    // Generate the angle on-demand
    if (!sessionId || !visualizationImage) return;

    setLoadingAngle(angle);
    try {
      const result = await generateAngleView(sessionId, {
        visualization_image: visualizationImage,
        target_angle: angle,
        products_description: selectedProducts.map(p => p.name).join(', ')
      });

      // Cache the generated image
      const angleImage = result.image.startsWith('data:')
        ? result.image
        : `data:image/png;base64,${result.image}`;
      setAngleImages(prev => ({ ...prev, [angle]: angleImage }));
      setCurrentAngle(angle);
    } catch (err) {
      console.error(`Error generating ${angle} view:`, err);
      setError(`Failed to generate ${angle} view. Please try again.`);
    } finally {
      setLoadingAngle(null);
    }
  };

  // Publish
  const handlePublish = async () => {
    // Prevent double-submission using both ref (immediate) and state (for UI)
    if (isSavingRef.current || saving) {
      console.log('[Publish] Already saving, ignoring duplicate request');
      return;
    }

    // Immediately set ref to prevent any race conditions
    isSavingRef.current = true;

    if (!title.trim()) {
      isSavingRef.current = false;
      setError('Please enter a title');
      return;
    }
    if (!visualizationImage) {
      isSavingRef.current = false;
      setError('Please generate a visualization first');
      return;
    }
    if (selectedProducts.length === 0) {
      isSavingRef.current = false;
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
        isSavingRef.current = false;
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

      // Derive style_theme from first selected style label, or fall back to title
      const derivedStyleTheme = styleLabels.length > 0
        ? STYLE_LABEL_OPTIONS.find(o => o.value === styleLabels[0])?.label || styleLabels[0]
        : title;

      const lookData = {
        title,
        style_theme: derivedStyleTheme,  // Always use freshly derived value
        style_description: styleDescription,
        style_labels: styleLabels,
        room_type: roomType,
        // budget_tier is auto-calculated on the backend based on total price
        room_image: roomImageData || undefined,
        visualization_image: vizImageData,
        is_published: true,
        product_ids: selectedProducts.map(p => p.id),
        product_types: selectedProducts.map(p => p.product_type || ''),
        product_quantities: selectedProducts.map(p => p.quantity || 1),
      };

      // Update existing look if editing, otherwise create new
      const result = existingLookId
        ? await adminCuratedAPI.update(parseInt(existingLookId), lookData)
        : await adminCuratedAPI.create(lookData);

      console.log('[Publish] Success:', result, existingLookId ? '(updated existing)' : '(created new)');

      // If we created a new look, update existingLookId so any subsequent action uses update instead of create
      if (!existingLookId && result?.id) {
        setExistingLookId(String(result.id));
        console.log('[Publish] Updated existingLookId to:', result.id);
      }

      // Clear saved state on successful publish
      sessionStorage.removeItem('curation_page_state');
      router.push('/admin/curated');
    } catch (err: any) {
      console.error('Error saving look:', err);
      console.error('Error details:', err.response?.data || err.message);
      setError(`Failed to publish: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setSaving(false);
      isSavingRef.current = false;
    }
  };

  // Save as Draft - saves without publishing
  const handleSaveAsDraft = async () => {
    // Prevent double-submission using both ref (immediate) and state (for UI)
    if (isSavingDraftRef.current || savingDraft) {
      console.log('[SaveDraft] Already saving, ignoring duplicate request');
      return;
    }

    // Immediately set ref to prevent any race conditions
    isSavingDraftRef.current = true;

    if (!title.trim()) {
      isSavingDraftRef.current = false;
      setError('Please enter a title for the curated look');
      return;
    }

    // Allow saving draft even without visualization (curators can save work-in-progress)
    try {
      setSavingDraft(true);
      setError(null);

      const vizImageData = visualizationImage?.includes('base64,')
        ? visualizationImage.split('base64,')[1]
        : visualizationImage;

      const roomImageData = roomImage?.includes('base64,')
        ? roomImage.split('base64,')[1]
        : roomImage;

      console.log(`[SaveDraft] Saving curated look as draft - products: ${selectedProducts.length}, existingLookId: ${existingLookId || 'none'}`);
      console.log('[SaveDraft] Product quantities:', selectedProducts.map(p => ({ name: p.name, qty: p.quantity || 1 })));

      // Derive style_theme from first selected style label, or fall back to title
      const derivedStyleTheme = styleLabels.length > 0
        ? STYLE_LABEL_OPTIONS.find(o => o.value === styleLabels[0])?.label || styleLabels[0]
        : title;

      const lookData = {
        title,
        style_theme: derivedStyleTheme,  // Always use freshly derived value
        style_description: styleDescription,
        style_labels: styleLabels,
        room_type: roomType,
        // budget_tier is auto-calculated on the backend based on total price
        room_image: roomImageData || undefined,
        visualization_image: vizImageData || undefined,
        is_published: false,  // Key difference: saved as draft
        product_ids: selectedProducts.map(p => p.id),
        product_types: selectedProducts.map(p => p.product_type || ''),
        product_quantities: selectedProducts.map(p => p.quantity || 1),
      };

      // Update existing look if editing, otherwise create new
      const result = existingLookId
        ? await adminCuratedAPI.update(parseInt(existingLookId), lookData)
        : await adminCuratedAPI.create(lookData);

      console.log('[SaveDraft] Success:', result, existingLookId ? '(updated existing)' : '(created new)');

      // If we created a new look, update existingLookId so subsequent saves update instead of create
      if (!existingLookId && result?.id) {
        setExistingLookId(String(result.id));
        console.log('[SaveDraft] Updated existingLookId to:', result.id);
      }

      // Clear saved state on successful save
      sessionStorage.removeItem('curation_page_state');
      router.push('/admin/curated');
    } catch (err: any) {
      console.error('Error saving draft:', err);
      console.error('Error details:', err.response?.data || err.message);
      setError(`Failed to save draft: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setSavingDraft(false);
      isSavingDraftRef.current = false;
    }
  };

  // ============================================
  // CANVAS PANEL HANDLERS (Lifted from CanvasPanel.tsx)
  // ============================================

  // Check if canvas has changed since last visualization (including quantity changes)
  useEffect(() => {
    console.log('[ChangeDetect] Running change detection...');
    console.log('[ChangeDetect] visualizedProductIds.size:', visualizedProductIds.size);
    console.log('[ChangeDetect] visualizationImage exists:', !!visualizationImage);
    console.log('[ChangeDetect] selectedProducts.length:', selectedProducts.length);

    if (visualizedProductIds.size === 0 && !visualizationImage) {
      console.log('[ChangeDetect] Early return - no visualized products and no image');
      return;
    }
    const currentIds = new Set(selectedProducts.map(p => String(p.id)));

    // Check if product IDs changed
    const idsChanged =
      selectedProducts.length !== visualizedProductIds.size ||
      selectedProducts.some(p => !visualizedProductIds.has(String(p.id)));

    // Check if quantities changed (even if product IDs are the same)
    const quantitiesChanged = selectedProducts.some(currentProduct => {
      const visualizedProduct = visualizedProducts.find(vp => vp.id === currentProduct.id);
      if (!visualizedProduct) return false; // Product wasn't visualized, will be caught by idsChanged
      return (currentProduct.quantity || 1) !== (visualizedProduct.quantity || 1);
    });

    console.log('[ChangeDetect] idsChanged:', idsChanged, 'quantitiesChanged:', quantitiesChanged);
    console.log('[ChangeDetect] visualizedProductIds:', Array.from(visualizedProductIds));
    console.log('[ChangeDetect] selectedProducts ids:', selectedProducts.map(p => p.id));

    if (idsChanged || quantitiesChanged) {
      console.log('[ChangeDetect] Setting needsRevisualization to TRUE');
      setNeedsRevisualization(true);
    } else {
      console.log('[ChangeDetect] No changes detected, setting needsRevisualization to FALSE');
      setNeedsRevisualization(false);
    }
  }, [selectedProducts, visualizedProductIds, visualizedProducts, visualizationImage]);

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
    console.log('[DetectChangeType] ========== STARTING DETECTION ==========');
    console.log('[DetectChangeType] selectedProducts:', selectedProducts.map(p => ({ id: p.id, name: p.name, qty: p.quantity })));
    console.log('[DetectChangeType] visualizedProducts:', visualizedProducts.map(p => ({ id: p.id, name: p.name, qty: p.quantity })));
    console.log('[DetectChangeType] visualizedProductIds:', Array.from(visualizedProductIds));

    const currentIds = new Set(selectedProducts.map(p => String(p.id)));
    const removedProductIds = Array.from(visualizedProductIds).filter(id => !currentIds.has(id));
    console.log('[DetectChangeType] removedProductIds:', removedProductIds);

    // Check for new products BEFORE deciding on removal vs reset
    // We need to know this because removal + addition requires reset, not just removal
    const newProducts = selectedProducts.filter(p => !visualizedProductIds.has(String(p.id)));
    console.log('[DetectChangeType] newProducts (early check):', newProducts.map(p => ({ id: p.id, name: p.name })));

    if (removedProductIds.length > 0) {
      // Get full product info for removed products, including their quantities as removeCount
      // When a product is completely removed, we need to remove ALL instances (quantity)
      const removedProductsInfo = visualizedProducts
        .filter(p => removedProductIds.includes(String(p.id)))
        .map(p => ({
          ...p,
          removeCount: p.quantity || 1  // Remove ALL instances of this product
        }));

      // OPTIMIZATION: If products are BOTH removed AND added, use remove_and_add workflow
      // This avoids full reset and instead: (1) removes products (2) adds new ones incrementally
      if (newProducts.length > 0 && visualizationImage) {
        console.log('[DetectChangeType] => REMOVE_AND_ADD: Removed:', removedProductsInfo.map(p => `${p.name} (qty=${p.removeCount})`), 'Added:', newProducts.map(p => p.name));
        return {
          type: 'remove_and_add',
          reason: 'products_removed_and_added',
          removedProducts: removedProductsInfo,
          newProducts: newProducts
        };
      }

      // Only removals, no additions - use removal mode
      console.log('[DetectChangeType] => REMOVAL: Products removed:', removedProductsInfo.map(p => `${p.name} (qty=${p.removeCount})`));
      return {
        type: 'removal',
        reason: 'products_removed',
        removedProducts: removedProductsInfo,
        remainingProducts: selectedProducts
      };
    }

    // Check for quantity changes
    // - Quantity INCREASE: additive (just add more instances to existing visualization)
    // - Quantity DECREASE: reset (need to re-render without the removed instances)
    let hasQuantityIncrease = false;
    let hasQuantityDecrease = false;
    const additionalInstances: any[] = [];

    const decreasedProducts: any[] = [];

    selectedProducts.forEach(currentProduct => {
      const visualizedProduct = visualizedProducts.find(vp => vp.id === currentProduct.id);
      if (!visualizedProduct) {
        console.log(`[DetectChangeType] Product ${currentProduct.name} (${currentProduct.id}) not in visualizedProducts - will be caught as new product`);
        return;
      }

      const currentQty = currentProduct.quantity || 1;
      const visualizedQty = visualizedProduct.quantity || 1;
      console.log(`[DetectChangeType] Comparing ${currentProduct.name}: current=${currentQty}, visualized=${visualizedQty}`);

      if (currentQty > visualizedQty) {
        // Quantity increased - we need to add (currentQty - visualizedQty) more copies
        const additionalCount = currentQty - visualizedQty;
        console.log(`[DetectChangeType] => QUANTITY INCREASE for ${currentProduct.name}: ${visualizedQty} -> ${currentQty} (add ${additionalCount} more)`);
        hasQuantityIncrease = true;
        // Instead of creating individual instances, create ONE entry with the count to add
        additionalInstances.push({
          ...currentProduct,
          quantity: additionalCount, // How many MORE to add
          _isQuantityIncrease: true // Flag to indicate this is additional copies
        });
      } else if (currentQty < visualizedQty) {
        // Quantity decreased - track how many to remove
        const removeCount = visualizedQty - currentQty;
        console.log(`[DetectChangeType] => QUANTITY DECREASE for ${currentProduct.name}: ${visualizedQty} -> ${currentQty} (remove ${removeCount})`);
        hasQuantityDecrease = true;
        decreasedProducts.push({
          ...currentProduct,
          removeCount: removeCount, // How many to remove
          originalQty: visualizedQty,
          newQty: currentQty
        });
      }
    });

    // Quantity decrease - use removal mode instead of full reset
    if (hasQuantityDecrease) {
      console.log('[DetectChangeType] => FINAL RESULT: REMOVAL (quantities decreased)', decreasedProducts.map(p => `${p.name}: remove ${p.removeCount}`));
      return {
        type: 'removal',
        reason: 'quantities_decreased',
        removedProducts: decreasedProducts,
        remainingProducts: selectedProducts
      };
    }

    // newProducts was already calculated at the top of this function
    // (used for checking removal+addition scenario)
    // Now combine quantity increases AND new products into one additive operation
    const allNewItems = [...additionalInstances, ...newProducts];

    if (allNewItems.length > 0 && visualizedProductIds.size > 0) {
      const reasons = [];
      if (additionalInstances.length > 0) reasons.push(`${additionalInstances.length} quantity increases`);
      if (newProducts.length > 0) reasons.push(`${newProducts.length} new products`);
      console.log('[DetectChangeType] => FINAL RESULT: ADDITIVE - adding', allNewItems.length, 'items:', reasons.join(' + '));
      return { type: 'additive', newProducts: allNewItems, reason: reasons.join('_and_') };
    }
    if (visualizedProductIds.size === 0) {
      console.log('[DetectChangeType] => FINAL RESULT: INITIAL (no products visualized yet)');
      return { type: 'initial' };
    }
    console.log('[DetectChangeType] => FINAL RESULT: NO_CHANGE');
    return { type: 'no_change' };
  };

  // Smart Visualization with incremental support (from CanvasPanel)
  const handleSmartVisualize = async () => {
    console.log('[Visualize] handleSmartVisualize called');
    console.log('[Visualize] roomImage exists:', !!roomImage);
    console.log('[Visualize] selectedProducts.length:', selectedProducts.length);
    console.log('[Visualize] sessionId:', sessionId);

    if (!roomImage || selectedProducts.length === 0) {
      console.log('[Visualize] Early return - no room image or products');
      return;
    }
    if (!sessionId) {
      setError('Session not initialized. Please refresh the page.');
      return;
    }

    setIsVisualizing(true);
    setError(null);

    try {
      const changeInfo = detectChangeType();
      console.log('[Visualize] Change detection result:', changeInfo);
      console.log('[Visualize] Selected products quantities:', selectedProducts.map(p => ({ name: p.name, qty: p.quantity || 1 })));
      console.log('[Visualize] Visualized products quantities:', visualizedProducts.map(p => ({ name: p.name, qty: p.quantity || 1 })));

      if (changeInfo.type === 'no_change') {
        setIsVisualizing(false);
        return;
      }

      let baseImage: string;
      let productsToVisualize: any[];
      let isIncremental = false;
      let forceReset = false;
      let removalMode = false;
      let productsToRemove: any[] = [];
      let productsToAdd: any[] = [];

      if (changeInfo.type === 'additive' && visualizationImage) {
        baseImage = visualizationImage;
        productsToVisualize = changeInfo.newProducts!;
        isIncremental = true;
      } else if (changeInfo.type === 'remove_and_add' && visualizationImage) {
        // OPTIMIZATION: Two-step workflow - remove then add incrementally
        // This avoids full reset when products are both removed and added
        baseImage = visualizationImage;
        productsToVisualize = selectedProducts; // All remaining products (for reference)
        productsToRemove = changeInfo.removedProducts || [];
        productsToAdd = changeInfo.newProducts || [];
        removalMode = true;
        console.log('[Visualize] REMOVE_AND_ADD MODE: Removing', productsToRemove.map((p: any) => p.name), 'Adding', productsToAdd.map((p: any) => p.name));
        console.log('[Visualize] productsToAdd full data:', JSON.stringify(productsToAdd.map((p: any) => ({ id: p.id, name: p.name, image_url: p.image_url?.substring(0, 50) }))));
      } else if (changeInfo.type === 'removal' && visualizationImage) {
        // Product removal: use current visualization and remove specific products
        baseImage = visualizationImage;
        productsToVisualize = selectedProducts; // Remaining products (for reference)
        productsToRemove = changeInfo.removedProducts || [];
        removalMode = true;
        console.log('[Visualize] REMOVAL MODE: Removing products:', productsToRemove.map((p: any) => p.name));
      } else if (changeInfo.type === 'reset') {
        baseImage = roomImage;
        productsToVisualize = selectedProducts;
        forceReset = true;
      } else {
        baseImage = roomImage;
        productsToVisualize = selectedProducts;
      }

      const productDetails = productsToVisualize.map(p => {
        // If this is an additional instance from quantity increase, append the instance label
        const instanceLabel = p._instanceLabel || '';
        const displayName = instanceLabel ? `${p.name} ${instanceLabel}` : p.name;

        return {
          id: p.id,
          name: displayName,
          full_name: displayName,
          style: 0.8,
          category: 'furniture',
          quantity: p.quantity || 1,  // Pass quantity for multiple instances
          image_url: p.image_url || p.imageUrl || p.image,  // Product image for accurate rendering
          furniture_type: p.furniture_type || p.furnitureType || p.type,  // Furniture category
        };
      });

      console.log('[Visualize] Sending products:', productDetails.map(p => ({ name: p.name, qty: p.quantity })));
      console.log('[Visualize] forceReset:', forceReset, 'isIncremental:', isIncremental, 'removalMode:', removalMode, 'reason:', changeInfo.reason || 'none');
      if (removalMode) {
        console.log('[Visualize] Products to remove with counts:', productsToRemove.map((p: any) => ({ name: p.name, removeCount: p.removeCount })));
        if (productsToAdd.length > 0) {
          console.log('[Visualize] Products to add:', productsToAdd.map((p: any) => p.name));
        }
      }

      // Prepare removal products info for backend - include image_url so Gemini can visually identify what to remove
      const removalProductDetails = productsToRemove.map((p: any) => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        remove_count: p.removeCount || 1, // For quantity decreases, how many to remove
        image_url: p.image_url || p.imageUrl || p.image,  // Product image for visual identification
        furniture_type: p.furniture_type || p.furnitureType || p.type,  // Furniture category
      }));

      // Prepare products to add info for backend (for remove_and_add workflow)
      // Include image_url and furniture_type for proper visualization
      console.log('[Visualize] Creating addProductDetails from productsToAdd:', productsToAdd.length, 'items');
      const addProductDetails = productsToAdd.map((p: any) => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        quantity: p.quantity || 1,
        image_url: p.image_url || p.imageUrl || p.image,
        furniture_type: p.furniture_type || p.furnitureType || p.type,
      }));
      console.log('[Visualize] addProductDetails created:', addProductDetails.length, 'items', addProductDetails.map(p => p.name));

      // For incremental visualization, send products already in the base image
      // This allows the AI to know exactly what furniture to preserve
      const visualizedProductDetails = visualizedProducts.map((p: any) => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        quantity: p.quantity || 1,
      }));

      if (isIncremental) {
        console.log('[Visualize] Existing products in base image:', visualizedProductDetails.map(p => ({ name: p.name, qty: p.quantity })));
      }

      // Debug: Log what we're actually sending
      console.log('[Visualize] Request body:', {
        removalMode,
        productsToRemoveCount: removalProductDetails.length,
        productsToAddCount: addProductDetails.length,
        addProductDetails: addProductDetails.map(p => ({ id: p.id, name: p.name })),
      });

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: baseImage,
          products: productDetails,
          analysis: { design_style: 'modern', color_palette: [], room_type: 'living_room' },
          is_incremental: isIncremental,
          force_reset: forceReset,
          removal_mode: removalMode,
          products_to_remove: removalMode ? removalProductDetails : undefined,
          products_to_add: removalMode ? addProductDetails : [],  // Always send array for remove_and_add workflow
          visualized_products: isIncremental ? visualizedProductDetails : [],  // Products already in base image (for incremental)
          user_uploaded_new_image: changeInfo.type === 'initial',
          action: 'add',  // Always add products in curated looks editor (skip furniture replacement clarification)
          curated_look_id: existingLookId ? parseInt(existingLookId) : undefined,  // For precomputation cache
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Visualization failed');
      }

      const data = await response.json();
      console.log('[Visualize] Response data:', {
        hasVisualization: !!data.visualization,
        hasRenderedImage: !!data.visualization?.rendered_image,
        imageLength: data.visualization?.rendered_image?.length,
        mode: data.mode,
        removedProducts: data.removed_products,
      });

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
            existing_furniture: data.existing_furniture,
            curated_look_id: existingLookId ? parseInt(existingLookId) : undefined,  // For precomputation cache
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
        // Deep copy selected products with their quantities to track what was visualized
        setVisualizedProducts(selectedProducts.map(p => ({ ...p, quantity: p.quantity || 1 })));
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

      console.log('[Visualize] Setting new image, length:', newImage?.length);
      setVisualizationImage(newImage);
      setVisualizedProductIds(newProductIds);
      // Deep copy selected products with their quantities to track what was visualized
      setVisualizedProducts(selectedProducts.map(p => ({ ...p, quantity: p.quantity || 1 })));
      setNeedsRevisualization(false);
      // Reset position edit flag since AI placed products fresh in this visualization
      setPositionsWereEdited(false);
      // Use local history length to determine undo/redo state (more reliable than backend)
      setCanUndo(true); // Can always undo after a visualization
      setCanRedo(false); // Clear redo after new visualization
      console.log('[Visualize] State update complete, selectedProducts:', selectedProducts.map(p => p.name));
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
    // Use > 1 because we want to preserve the initial loaded state (entry 0)
    // and not allow undoing past it on "Style this further" pages
    setCanUndo(newHistory.length > 1);
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

  // Enter edit mode for positions - now uses click-to-select
  const handleEnterEditMode = async () => {
    if (!sessionId || !visualizationImage) {
      setError('Please create a visualization first.');
      return;
    }

    // Text-based edit mode - user types instructions, no dragging needed
    console.log('[AdminCurated] Entering text-based edit mode...');

    // Store the current visualization for potential revert
    setPreEditVisualization(visualizationImage);

    setIsEditingPositions(true);
    setEditSpecialInstructions(''); // Clear any previous instructions
    console.log('[AdminCurated] Edit mode ready - type instructions to reposition items');
  };

  // Handle final image from click-to-select mode
  const handleClickToSelectFinalImage = (newImage: string) => {
    console.log('[AdminCurated] Click-to-Select final image received');
    setVisualizationImage(newImage);
    // Stay in edit mode so user can move more objects
  };

  // Handle pending move changes from DraggableFurnitureCanvas
  const handlePendingMoveChange = (hasPending: boolean, moveData?: PendingMoveData) => {
    console.log('[AdminCurated] Pending move change:', { hasPending, hasData: !!moveData });
    if (hasPending && moveData) {
      setPendingMoveData(moveData);
      setHasUnsavedPositions(true);
    } else {
      setPendingMoveData(null);
      setHasUnsavedPositions(false);
    }
  };

  // Handle Re-visualize for edit mode (finalize the move via API)
  const handleEditModeRevisualize = async () => {
    if (!pendingMoveData || !sessionId) {
      console.log('[AdminCurated] No pending move data or session');
      return;
    }

    console.log('[AdminCurated] Finalizing move via API...');
    setIsVisualizing(true);

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

      if (result.image) {
        console.log('[AdminCurated] Move finalized successfully');

        // Add to history for undo/redo
        const newHistoryEntry: VisualizationHistoryEntry = {
          image: result.image,
          products: [...visualizedProducts],
          productIds: new Set(visualizedProducts.map((p: any) => String(p.id))),
        };
        setVisualizationHistory(prev => [...prev, newHistoryEntry]);
        setRedoStack([]);
        setCanUndo(true);
        setCanRedo(false);

        // Update visualization with final image
        handleClickToSelectFinalImage(result.image);

        // Clear pending move data
        setPendingMoveData(null);
        setHasUnsavedPositions(false);
      }
    } catch (error: any) {
      console.error('[AdminCurated] Error finalizing move:', error);
      setError('Failed to finalize move: ' + (error.message || 'Unknown error'));
    } finally {
      setIsVisualizing(false);
    }
  };

  // Legacy enter edit mode (kept for reference but not used)
  const handleEnterEditModeLegacy = async () => {
    if (!sessionId || !visualizationImage) {
      setError('Please create a visualization first.');
      return;
    }

    setIsExtractingLayers(true);
    try {
      console.log('[AdminCurated] Entering edit mode with layer extraction...');

      // Get products to edit
      const productsToEdit = visualizedProducts.length > 0 ? visualizedProducts : selectedProducts;

      // Prepare products for API (expand by quantity)
      const expandedProductsForApi: Array<{ id: string; name: string }> = [];
      productsToEdit.forEach(product => {
        const qty = product.quantity || 1;
        for (let i = 1; i <= qty; i++) {
          const instanceId = qty > 1 ? `${product.id}-${i}` : String(product.id);
          const label = qty > 1 ? `${product.name} (${i} of ${qty})` : product.name;
          expandedProductsForApi.push({ id: instanceId, name: label });
        }
      });

      // Call the layer extraction API (Magic Grab) to get actual positions and cropped layers
      console.log('[AdminCurated] Extracting furniture layers via Magic Grab... curatedLookId:', existingLookId);
      const result = await furniturePositionAPI.extractLayers(
        sessionId,
        visualizationImage,
        expandedProductsForApi,
        true,  // useSam = true for Magic Grab (falls back to Gemini if SAM unavailable)
        existingLookId ? parseInt(existingLookId) : undefined  // curated_look_id for cache lookup
      );

      console.log('[AdminCurated] Layer extraction result:', {
        hasBackground: !!result.background,
        layersCount: result.layers?.length || 0,
        method: result.extraction_method,
      });

      // Get clean background and layers
      const cleanBackground = result.background || result.clean_background || visualizationImage;
      const layers = result.layers || [];

      // Check if layers have cutout images (Magic Grab mode)
      const hasCutouts = layers.length > 0 && layers.some((l: any) => l.cutout || l.layer_image);

      if (hasCutouts && cleanBackground !== visualizationImage) {
        // === MAGIC GRAB MODE ===
        console.log(`[AdminCurated] Enabling Magic Grab mode with ${layers.length} draggable layers`);

        // Convert to MagicGrabLayer format
        const magicLayers: MagicGrabLayer[] = layers.map((layer: any, index: number) => ({
          id: String(layer.id || layer.product_id || `layer_${index}`),
          productId: layer.product_id || layer.id,
          productName: layer.product_name || 'Product',
          cutout: layer.cutout || layer.layer_image || '',
          x: layer.x ?? layer.center?.x ?? 0.5,
          y: layer.y ?? layer.center?.y ?? 0.5,
          width: layer.width ?? layer.bounding_box?.width ?? 0.15,
          height: layer.height ?? layer.bounding_box?.height ?? 0.15,
          scale: layer.scale || 1.0,
          rotation: 0,
          zIndex: index,
        }));

        // Set Magic Grab state
        setMagicGrabBackground(cleanBackground);
        setMagicGrabLayers(magicLayers);
        setUseMagicGrabMode(true);
        setIsEditingPositions(true);
        setHasUnsavedPositions(false);

        console.log('[AdminCurated] Magic Grab mode ready - drag furniture to reposition');
      } else {
        // === LEGACY MODE (fallback) ===
        console.log('[AdminCurated] Using legacy edit mode');
        setBaseRoomLayer(cleanBackground);
        setUseMagicGrabMode(false);

        let initialPositions: FurniturePosition[];

        if (layers.length > 0) {
          initialPositions = layers.map((layer: any) => ({
            productId: String(layer.product_id || layer.id),
            x: layer.x ?? layer.center?.x ?? 0.5,
            y: layer.y ?? layer.center?.y ?? 0.5,
            width: layer.width ?? layer.bounding_box?.width ?? 0.15,
            height: layer.height ?? layer.bounding_box?.height ?? 0.15,
            label: layer.product_name || 'Product',
            layerImage: layer.cutout || layer.layer_image || undefined,
          }));
          console.log(`[AdminCurated] Using ${initialPositions.length} detected positions`);
        } else {
          console.log('[AdminCurated] No layers detected, using default grid layout');
          const numProducts = expandedProductsForApi.length;
          const cols = Math.ceil(Math.sqrt(numProducts));

          initialPositions = expandedProductsForApi.map((item, index) => {
            const row = Math.floor(index / cols);
            const col = index % cols;
            const spacingX = 0.6 / (cols + 1);
            const spacingY = 0.6 / (Math.ceil(numProducts / cols) + 1);

            return {
              productId: item.id,
              x: 0.2 + (col + 1) * spacingX,
              y: 0.2 + (row + 1) * spacingY,
              label: item.name,
              width: 0.15,
              height: 0.15,
            };
          });
        }

        setFurniturePositions(initialPositions);
        setFurnitureLayers([]);
        setIsEditingPositions(true);
        setHasUnsavedPositions(false);
      }
    } catch (error: any) {
      console.error('[AdminCurated] Error entering edit mode:', error);

      // Fall back to simple furniture removal approach
      console.log('[AdminCurated] Falling back to simple edit mode...');
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/remove-furniture`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: visualizationImage }),
          }
        );

        if (response.ok) {
          const data = await response.json();
          setBaseRoomLayer(data.clean_image || visualizationImage);
        }

        // Use default grid positions
        const productsToEdit = visualizedProducts.length > 0 ? visualizedProducts : selectedProducts;
        const expandedProducts: Array<{product: any, instanceIndex: number, totalInstances: number}> = [];
        productsToEdit.forEach(product => {
          const qty = product.quantity || 1;
          for (let i = 1; i <= qty; i++) {
            expandedProducts.push({ product, instanceIndex: i, totalInstances: qty });
          }
        });

        const numProducts = expandedProducts.length;
        const cols = Math.ceil(Math.sqrt(numProducts));

        const fallbackPositions: FurniturePosition[] = expandedProducts.map((item, index) => {
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

        setFurniturePositions(fallbackPositions);
        setFurnitureLayers([]);
        setIsEditingPositions(true);
        setHasUnsavedPositions(false);
      } catch (fallbackError) {
        console.error('[AdminCurated] Fallback also failed:', fallbackError);
        setError('Error entering edit mode. Please try again.');
      }
    } finally {
      setIsExtractingLayers(false);
    }
  };

  // Exit edit mode - keep current visualization (changes are applied via Apply button)
  const handleExitEditMode = () => {
    console.log('[AdminCurated] Exiting edit mode');

    // Clean up edit mode state
    setIsEditingPositions(false);
    setEditSpecialInstructions('');
    setPreEditVisualization(null);
  };

  // Save and exit edit mode - keep current visualization
  const handleSaveAndExitEditMode = () => {
    console.log('[AdminCurated] Saving and exiting edit mode');

    // Add current visualization to history if we have changes
    if (visualizationImage && preEditVisualization && visualizationImage !== preEditVisualization) {
      const newHistoryEntry: VisualizationHistoryEntry = {
        image: visualizationImage,
        products: [...visualizedProducts],
        productIds: new Set(visualizedProducts.map((p: any) => String(p.id))),
      };
      setVisualizationHistory(prev => [...prev, newHistoryEntry]);
      setRedoStack([]);
      setCanUndo(true);
      setCanRedo(false);
    }

    // Clean up edit mode state (keep current visualization)
    setIsEditingPositions(false);
    setHasUnsavedPositions(false);
    setPendingMoveData(null);
    setPreEditVisualization(null);
    setUseMagicGrabMode(false);
    setMagicGrabBackground(null);
    setMagicGrabLayers([]);
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

      // Expand products by quantity to match the positions
      // Each instance ID in furniturePositions (e.g., "123-1", "123-2") needs a matching product entry
      const productDetails: Array<{id: string, name: string, full_name: string, style: number, category: string, image_url?: string}> = [];
      selectedProducts.forEach(p => {
        const qty = p.quantity || 1;
        for (let i = 1; i <= qty; i++) {
          const instanceId = qty > 1 ? `${p.id}-${i}` : String(p.id);
          const instanceName = qty > 1 ? `${p.name} (${i} of ${qty})` : p.name;
          productDetails.push({
            id: instanceId,
            name: instanceName,
            full_name: instanceName,
            style: 0.8,
            category: 'furniture',
            image_url: p.image_url || p.images?.[0]?.original_url
          });
        }
      });

      // Use force_reset: true to regenerate from clean room image with all products
      // This gives better results than trying to modify an existing visualization
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
            force_reset: true,  // IMPORTANT: Start fresh from clean room to properly place products
            curated_look_id: existingLookId ? parseInt(existingLookId) : undefined,  // For precomputation cache
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

  // Re-visualize using text-based instructions (Gemini edits existing visualization)
  const handleRevisualizeWithInstructions = async () => {
    if (!sessionId || !visualizationImage) {
      setError('No session or visualization image found.');
      return;
    }

    if (!editSpecialInstructions.trim()) {
      setError('Please enter special instructions for how to reposition items.');
      return;
    }

    setIsVisualizing(true);
    try {
      // Build product list with names and image URLs for Gemini reference
      const products = selectedProducts.map(p => ({
        id: p.id,
        name: p.name,
        quantity: p.quantity || 1,
        image_url: p.images?.[0]?.large_url || p.images?.[0]?.medium_url || p.images?.[0]?.original_url || p.image_url,
      }));

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/visualization/sessions/${sessionId}/edit-with-instructions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image: visualizationImage,
            instructions: editSpecialInstructions.trim(),
            products: products,  // Include product info so Gemini knows what products should look like
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to apply edit instructions');
      }

      const data = await response.json();

      if (!data.image) throw new Error('No edited image was generated');

      setVisualizationImage(data.image);

      // Add to history for undo/redo support
      const newHistoryEntry: VisualizationHistoryEntry = {
        image: data.image,
        products: [...visualizedProducts],
        productIds: new Set(visualizedProducts.map((p: any) => String(p.id))),
      };
      setVisualizationHistory(prev => [...prev, newHistoryEntry]);
      setRedoStack([]); // Clear redo stack on new edit
      setCanUndo(true);
      setCanRedo(false);

      setNeedsRevisualization(false);
      setIsEditingPositions(false);
      setHasUnsavedPositions(false);
      setEditSpecialInstructions(''); // Clear instructions after successful edit
      setPositionsWereEdited(true); // Mark that positions were manually edited - affects next visualization
    } catch (error: any) {
      setError(error.message || 'Failed to apply edit instructions.');
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

  // Debug: Log button state
  useEffect(() => {
    console.log('[ButtonState] canVisualize:', canVisualize);
    console.log('[ButtonState] needsRevisualization:', needsRevisualization);
    console.log('[ButtonState] visualizationImage exists:', !!visualizationImage);
    console.log('[ButtonState] isUpToDate:', isUpToDate);
    console.log('[ButtonState] isReady:', isReady);
  }, [canVisualize, needsRevisualization, visualizationImage, isUpToDate, isReady]);

  // ============================================
  // END CANVAS PANEL HANDLERS
  // ============================================

  // Improve Quality - Re-visualize all products on clean base image
  const [isImprovingQuality, setIsImprovingQuality] = useState(false);

  const handleImproveQuality = async () => {
    if (!roomImage || selectedProducts.length === 0 || !sessionId) {
      console.log('[ImproveQuality] Missing requirements');
      return;
    }

    // Confirm with warning about undo/redo reset
    const confirmed = window.confirm(
      'Improve Quality will re-visualize all products on the original room image.\n\n' +
      'WARNING: This will reset your undo/redo history.\n\n' +
      'Continue?'
    );
    if (!confirmed) return;

    setIsImprovingQuality(true);
    console.log('[ImproveQuality] Starting quality improvement with', selectedProducts.length, 'products');

    try {
      const productDetails = selectedProducts.map(p => ({
        id: p.id,
        name: p.name,
        full_name: p.name,
        style: 0.8,
        category: 'furniture',
        quantity: p.quantity || 1,
        image_url: p.image_url || p.imageUrl || p.image,
        furniture_type: p.furniture_type || p.furnitureType || p.type,
      }));

      console.log('[ImproveQuality] Sending products:', productDetails.map(p => ({ name: p.name, qty: p.quantity })));

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/sessions/${sessionId}/visualize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: roomImage,  // Use original room image, not current visualization
          products: productDetails,
          analysis: { design_style: 'modern', color_palette: [], room_type: 'living_room' },
          is_incremental: false,
          force_reset: true,  // Force fresh visualization
          user_uploaded_new_image: false,
          action: 'add',
          curated_look_id: existingLookId ? parseInt(existingLookId) : undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Quality improvement failed');
      }

      const data = await response.json();

      if (!data.visualization?.rendered_image) {
        throw new Error('No visualization image was generated');
      }

      const newImage = data.visualization.rendered_image;
      console.log('[ImproveQuality] Success! New image length:', newImage?.length);

      // Update visualization image
      setVisualizationImage(newImage);

      // Reset undo/redo stack
      setVisualizationHistory([{
        image: newImage,
        products: selectedProducts.map(p => ({ ...p, quantity: p.quantity || 1 })),
        productIds: new Set(selectedProducts.map(p => String(p.id))),
      }]);
      setRedoStack([]);
      setCanUndo(false);
      setCanRedo(false);

      // Update visualized state
      const newProductIds = new Set(selectedProducts.map(p => String(p.id)));
      setVisualizedProductIds(newProductIds);
      setVisualizedProducts(selectedProducts.map(p => ({ ...p, quantity: p.quantity || 1 })));
      setNeedsRevisualization(false);

    } catch (error) {
      console.error('[ImproveQuality] Error:', error);
      alert(`Failed to improve quality: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsImprovingQuality(false);
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const totalPrice = selectedProducts.reduce((sum, p) => sum + (p.price || 0) * (p.quantity || 1), 0);

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
          <h1 className="text-lg font-bold text-gray-900">
            {existingLookId ? 'Edit Curated Look' : 'Create Curated Look'}
          </h1>
          {existingLookId && !loadingStyleFrom && (
            <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
              Editing #{existingLookId}
            </span>
          )}
          {loadingStyleFrom && (
            <span className="text-sm text-purple-600 flex items-center gap-1">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Loading existing look...
            </span>
          )}
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

      {/* Three Panel Layout - Resizable */}
      <div className="flex-1 overflow-hidden h-full">
        <Group
          groupRef={panelGroupRef}
          orientation="horizontal"
          id="omnishop-curated-panels"
          className="h-full"
        >
          {/* Panel 1: Filters */}
          <Panel
            id="filters-panel"
            defaultSize={15}
            minSize={10}
            className="bg-white overflow-hidden border-r border-gray-200"
          >
            <div className="h-full flex flex-col">
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
                      // Toggle: if already selected, clear the filter
                      if (minPrice === range.min && maxPrice === range.max) {
                        setMinPrice('');
                        setMaxPrice('');
                      } else {
                        setMinPrice(range.min);
                        setMaxPrice(range.max);
                      }
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

            {/* Store Filter - Categorized by Budget Tier */}
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
              <div className="space-y-3 max-h-60 overflow-y-auto">
                {storeCategories.map((category) => (
                  <div key={category.tier}>
                    {/* Category Header */}
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                        {category.label}
                      </span>
                      <span className="text-xs text-gray-400">({category.stores.length})</span>
                    </div>
                    {/* Stores in this category */}
                    <div className="space-y-1 pl-2 border-l-2 border-gray-200">
                      {category.stores.map((store) => (
                        <label
                          key={store.name}
                          className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1.5 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedStores.includes(store.name)}
                            onChange={() => toggleStore(store.name)}
                            className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                          />
                          <span className="text-sm text-gray-700">{store.display_name}</span>
                        </label>
                      ))}
                    </div>
                  </div>
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

            {/* Style Filter */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">Style</label>
                {selectedProductStyles.length > 0 && (
                  <button
                    onClick={() => setSelectedProductStyles([])}
                    className="text-xs text-purple-600 hover:text-purple-700"
                  >
                    Clear ({selectedProductStyles.length})
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {PRODUCT_STYLES.map((style) => (
                  <button
                    key={style.value}
                    onClick={() => toggleProductStyle(style.value)}
                    className={`px-2 py-1 text-xs rounded-full transition-all ${
                      selectedProductStyles.includes(style.value)
                        ? 'bg-purple-100 text-purple-700 border border-purple-300'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-transparent'
                    }`}
                  >
                    {selectedProductStyles.includes(style.value) && (
                      <svg className="w-3 h-3 inline mr-0.5 -ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                    {style.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Material Filter */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">Material</label>
                {selectedMaterials.length > 0 && (
                  <button
                    onClick={() => setSelectedMaterials([])}
                    className="text-xs text-purple-600 hover:text-purple-700"
                  >
                    Clear ({selectedMaterials.length})
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                {PRODUCT_MATERIALS.map((material) => (
                  <button
                    key={material.value}
                    onClick={() => toggleMaterial(material.value)}
                    className={`px-2 py-1 text-xs rounded-full transition-all ${
                      selectedMaterials.includes(material.value)
                        ? 'bg-blue-100 text-blue-700 border border-blue-300'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-transparent'
                    }`}
                  >
                    {selectedMaterials.includes(material.value) && (
                      <svg className="w-3 h-3 inline mr-0.5 -ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                    {material.label}
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
          </Panel>

          <PanelResizeHandle id="filters-products-handle" />

          {/* Panel 2: Product Discovery */}
          <Panel
            id="products-panel"
            defaultSize={40}
            minSize={25}
            className="bg-white overflow-hidden border-r border-gray-200"
          >
            <div className="h-full flex flex-col">
              <div className="p-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-purple-50">
                <div className="flex justify-between items-center">
                  <h2 className="font-semibold text-gray-900 text-sm">Products</h2>
                  {totalProducts > 0 && (
                    <span className="text-xs text-purple-600 font-medium">
                      {discoveredProducts.length} of {totalProducts} found
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">Click to add to canvas</p>
              </div>

              {/* Product Grid */}
              <div
                ref={productsContainerRef}
                className="flex-1 overflow-y-auto p-3"
                onScroll={handleScroll}
              >
                {searching ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
              </div>
            ) : discoveredProducts.length > 0 ? (
              <>
              {/* Separate products into primary matches and related */}
              {(() => {
                const primaryProducts = discoveredProducts.filter((p: any) => p.is_primary_match);
                const relatedProducts = discoveredProducts.filter((p: any) => !p.is_primary_match);

                // Debug logging
                console.log(`[Products] Total: ${discoveredProducts.length}, Primary: ${primaryProducts.length}, Related: ${relatedProducts.length}, totalPrimary: ${totalPrimary}, totalRelated: ${totalRelated}`);

                const renderProductGrid = (products: any[], keyPrefix: string) => (
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    {products.map((product: any, index: number) => {
                  const quantity = getProductQuantity(product.id);
                  const isInCanvas = quantity > 0;
                  const imageUrl = getProductImage(product);
                  return (
                    <div
                      key={`${product.id}-${index}`}
                      className={`group rounded-lg border-2 overflow-hidden transition-all ${
                        isInCanvas
                          ? 'border-green-500 bg-green-50'
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
                        {/* Quantity badge when in canvas */}
                        {isInCanvas && (
                          <div className="absolute top-1 left-1 bg-purple-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                            {quantity}x
                          </div>
                        )}
                        {/* Hover Action Buttons - Show for all products */}
                        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                          {isInCanvas ? (
                            <>
                              {/* Quantity controls for products in canvas */}
                              <div className="flex items-center gap-1.5 bg-white rounded-lg px-2 py-1">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    decrementQuantity(product.id);
                                  }}
                                  className="w-6 h-6 bg-gray-200 hover:bg-gray-300 rounded text-sm font-bold flex items-center justify-center"
                                >
                                  -
                                </button>
                                <span className="w-5 text-center font-semibold text-sm">{quantity}</span>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    incrementQuantity(product.id);
                                  }}
                                  className="w-6 h-6 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-bold flex items-center justify-center"
                                >
                                  +
                                </button>
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  removeProduct(product.id);
                                }}
                                className="px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs font-medium rounded-lg flex items-center gap-1"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                                Remove
                              </button>
                            </>
                          ) : (
                            <>
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
                            </>
                          )}
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
                );

                return (
                  <>
                    {/* Primary Matches Section */}
                    {primaryProducts.length > 0 && (
                      <>
                        <div className="mb-2">
                          <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-1 rounded">
                            Best Matches ({totalPrimary > 0 ? totalPrimary : primaryProducts.length})
                          </span>
                        </div>
                        {renderProductGrid(primaryProducts, 'primary')}
                      </>
                    )}

                    {/* More Products Section */}
                    {relatedProducts.length > 0 && (
                      <>
                        <div className={`mb-2 ${primaryProducts.length > 0 ? 'mt-4 pt-3 border-t border-gray-200' : ''}`}>
                          <span className="text-xs font-semibold text-gray-600 bg-gray-100 px-2 py-1 rounded">
                            {primaryProducts.length > 0 ? 'More Products' : 'Products'} ({totalRelated > 0 ? totalRelated : relatedProducts.length})
                          </span>
                        </div>
                        {renderProductGrid(relatedProducts, 'related')}
                      </>
                    )}

                    {/* Show More Products header even if none loaded yet (but we know they exist) */}
                    {relatedProducts.length === 0 && totalRelated > 0 && primaryProducts.length > 0 && (
                      <div className="mb-2 mt-4 pt-3 border-t border-gray-200">
                        <span className="text-xs font-semibold text-gray-600 bg-gray-100 px-2 py-1 rounded">
                          More Products ({totalRelated})
                        </span>
                        <p className="text-xs text-gray-400 mt-1">Scroll down to load more...</p>
                      </div>
                    )}

                    {/* Fallback if no is_primary_match flag (backwards compatibility) */}
                    {primaryProducts.length === 0 && relatedProducts.length === 0 && discoveredProducts.length > 0 && (
                      renderProductGrid(discoveredProducts, 'all')
                    )}
                  </>
                );
              })()}
              {/* Infinite scroll loading indicator */}
              {loadingMore && (
                <div className="flex items-center justify-center py-4">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
                  <span className="ml-2 text-sm text-gray-500">Loading more...</span>
                </div>
              )}
              {hasMore && !loadingMore && (
                <div className="text-center py-3">
                  <span className="text-xs text-gray-400">Scroll for more</span>
                </div>
              )}
              </>
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
          </Panel>

          <PanelResizeHandle id="products-canvas-handle" />

          {/* Panel 3: Canvas & Visualization */}
          <Panel
            id="canvas-panel"
            defaultSize={45}
            minSize={30}
            className="bg-white overflow-hidden"
          >
            <div className="h-full flex flex-col overflow-hidden">
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
                        src={roomImage.startsWith('data:') ? roomImage : `data:image/jpeg;base64,${roomImage}`}
                        alt="Room"
                        className="w-full h-full object-cover"
                        onLoad={() => console.log('Room image loaded successfully')}
                      />
                      {/* Image Processing Loading Overlay */}
                      {isRemovingFurniture && (
                        <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-10">
                          <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-500 mb-2"></div>
                          <span className="text-white font-medium text-sm">Processing Image...</span>
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
                        {/* Quantity badge */}
                        {(product.quantity || 1) > 1 && (
                          <div className="absolute top-1 left-1 px-1.5 py-0.5 bg-purple-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center z-10">
                            {product.quantity}x
                          </div>
                        )}
                        {/* Hover overlay with controls - same as product panel */}
                        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                          {/* Quantity controls */}
                          <div className="flex items-center gap-1.5 bg-white rounded-lg px-2 py-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                decrementQuantity(product.id);
                              }}
                              className="w-6 h-6 bg-gray-200 hover:bg-gray-300 rounded text-sm font-bold flex items-center justify-center"
                            >
                              -
                            </button>
                            <span className="w-5 text-center font-semibold text-sm">{product.quantity || 1}</span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                incrementQuantity(product.id);
                              }}
                              className="w-6 h-6 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-bold flex items-center justify-center"
                            >
                              +
                            </button>
                          </div>
                          {/* Remove button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              removeProduct(product.id);
                            }}
                            className="px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs font-medium rounded-lg flex items-center gap-1"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Remove
                          </button>
                          {/* View Details button */}
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
                      </div>
                      <div className="p-1">
                        <p className="text-[10px] font-medium text-gray-900 line-clamp-1 cursor-pointer hover:text-purple-600" onClick={() => setDetailProduct(product)}>{product.name}</p>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-gray-500 capitalize">{product.source_website || product.source}</span>
                          <p className="text-[10px] text-purple-600 font-semibold">{formatPrice((product.price || 0) * (product.quantity || 1))}</p>
                        </div>
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
                        {/* Quantity badge */}
                        {(product.quantity || 1) > 1 && (
                          <div className="absolute -top-1 -right-1 w-5 h-5 bg-purple-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                            {product.quantity}
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-gray-900 truncate cursor-pointer hover:text-purple-600" onClick={() => setDetailProduct(product)}>{product.name}</p>
                        <p className="text-[10px] text-gray-500 capitalize">{product.source_website || product.source}</p>
                        <p className="text-xs font-semibold text-purple-600">{formatPrice((product.price || 0) * (product.quantity || 1))}</p>
                      </div>
                      {/* Quantity controls */}
                      <div className="flex items-center gap-1 mr-2">
                        <button
                          onClick={() => decrementQuantity(product.id)}
                          className="w-6 h-6 bg-gray-200 hover:bg-gray-300 rounded text-sm font-bold flex items-center justify-center"
                        >
                          -
                        </button>
                        <span className="w-6 text-sm text-center font-medium">{product.quantity || 1}</span>
                        <button
                          onClick={() => incrementQuantity(product.id)}
                          className="w-6 h-6 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded text-sm font-bold flex items-center justify-center"
                        >
                          +
                        </button>
                      </div>
                      <button
                        onClick={() => setDetailProduct(product)}
                        className="text-blue-600 hover:text-blue-700 p-0.5 mr-1"
                        title="View Details"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => removeProduct(product.id)}
                        className="text-red-600 hover:text-red-700 p-0.5"
                        title="Remove"
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

            {/* Visualization In Progress - Shimmer Preview (first-time visualization) */}
            {isVisualizing && !visualizationImage && roomImage && (
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-900">Generating Visualization...</h3>
                </div>
                <div className="relative aspect-video bg-gray-100 rounded-lg overflow-hidden ring-2 ring-blue-400">
                  {/* Room image as preview background */}
                  <img
                    src={roomImage?.startsWith('data:') ? roomImage : `data:image/jpeg;base64,${roomImage}`}
                    alt="Room preview"
                    className="w-full h-full object-cover opacity-50"
                  />
                  {/* Shimmer overlay animation */}
                  <div
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer z-10"
                    style={{ backgroundSize: '200% 100%' }}
                  />
                  {/* Progress indicator */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/30 z-20">
                    <div className="bg-black/70 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center shadow-2xl">
                      <svg className="animate-spin h-10 w-10 text-white mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className="text-white font-semibold text-base">Placing furniture in your room...</span>
                      <span className="text-white/80 text-sm mt-1">Omni is styling your space</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

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
                        // Reset angle state
                        setCurrentAngle('front');
                        setAngleImages({ front: null, left: null, right: null, back: null });
                      }}
                      disabled={isEditingPositions}
                      className="text-xs text-red-600 hover:text-red-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                {/* Angle Selector - Multi-angle viewing */}
                {!isEditingPositions && (
                  <div className="mt-2 mb-2">
                    <AngleSelector
                      currentAngle={currentAngle}
                      loadingAngle={loadingAngle}
                      availableAngles={Object.entries(angleImages)
                        .filter(([_, img]) => img !== null)
                        .map(([angle]) => angle as ViewingAngle)}
                      onAngleSelect={handleAngleSelect}
                      disabled={isVisualizing || isExtractingLayers}
                    />
                  </div>
                )}

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
                  <img
                    src={isEditingPositions ? visualizationImage : (angleImages[currentAngle] || visualizationImage)}
                    alt={`Visualization result${isEditingPositions ? ' - Edit Mode' : ` - ${currentAngle} view`}`}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute bottom-2 left-2 flex items-center gap-2">
                    {isEditingPositions ? (
                      <span className="bg-purple-500 text-white px-2 py-0.5 rounded-full text-xs font-medium">
                        Edit Mode
                      </span>
                    ) : (
                      <>
                        <span className="bg-green-500 text-white px-2 py-0.5 rounded-full text-xs font-medium">
                          AI Visualization
                        </span>
                        {currentAngle !== 'front' && (
                          <span className="bg-purple-500 text-white px-2 py-0.5 rounded-full text-xs font-medium capitalize">
                            {currentAngle} View
                          </span>
                        )}
                      </>
                    )}
                  </div>
                  {loadingAngle && !isEditingPositions && (
                    <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
                      <div className="bg-white rounded-lg px-4 py-3 flex items-center gap-3 shadow-lg">
                        <svg className="animate-spin h-5 w-5 text-purple-600" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span className="text-sm font-medium text-gray-700">Generating {loadingAngle} view...</span>
                      </div>
                    </div>
                  )}
                  {/* Re-visualization / Improve Quality shimmer overlay */}
                  {(isVisualizing || isImprovingQuality) && !isEditingPositions && (
                    <div className="absolute inset-0 z-20">
                      <div
                        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer"
                        style={{ backgroundSize: '200% 100%' }}
                      />
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/30">
                        <div className="bg-black/70 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center shadow-2xl">
                          <svg className="animate-spin h-10 w-10 text-white mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span className="text-white font-semibold text-base">
                            {isImprovingQuality ? 'Improving quality...' : 'Updating visualization...'}
                          </span>
                          <span className="text-white/80 text-sm mt-1">
                            {isImprovingQuality ? 'Re-rendering from original room' : 'Omni is updating your space'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Edit Mode Actions - Special Instructions + Exit button */}
                {isEditingPositions && (
                  <div className="mt-3 space-y-3">
                    {/* Special Instructions Input */}
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Special Instructions
                      </label>
                      <textarea
                        value={editSpecialInstructions}
                        onChange={(e) => setEditSpecialInstructions(e.target.value)}
                        placeholder="e.g., 'Place the flower vase on the bench' or 'Move the lamp to the left corner'"
                        rows={2}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Describe how you want to reposition items
                      </p>
                    </div>

                    {/* Exit button */}
                    <div className="flex items-center justify-center">
                      <button
                        onClick={handleExitEditMode}
                        className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 text-sm font-medium transition-colors"
                      >
                        Exit Edit Mode
                      </button>
                    </div>
                  </div>
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
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Budget Tier (auto-calculated)</label>
                  <div className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50">
                    {(() => {
                      const tier = calculateBudgetTier(totalPrice);
                      return (
                        <span className="flex items-center justify-between">
                          <span className="font-medium text-gray-800">{tier.label}</span>
                          <span className="text-xs text-gray-500">{tier.range}</span>
                        </span>
                      );
                    })()}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Style Labels (for filtering)</label>
                  <div className="flex flex-wrap gap-2 p-2 border border-gray-300 rounded-lg bg-gray-50 min-h-[80px]">
                    {STYLE_LABEL_OPTIONS.map((option) => {
                      const isSelected = styleLabels.includes(option.value);
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => {
                            if (isSelected) {
                              setStyleLabels(styleLabels.filter(l => l !== option.value));
                            } else {
                              setStyleLabels([...styleLabels, option.value]);
                            }
                          }}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                            isSelected
                              ? 'bg-purple-600 text-white'
                              : 'bg-white text-gray-700 border border-gray-300 hover:border-purple-400'
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                  {styleLabels.length > 0 && (
                    <p className="text-xs text-gray-500 mt-1">
                      Selected: {styleLabels.map(l => STYLE_LABEL_OPTIONS.find(o => o.value === l)?.label).join(', ')}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Visualize & Publish Buttons - Fixed at bottom (Smart states from CanvasPanel) */}
          <div className="p-4 border-t border-gray-200 flex-shrink-0 space-y-2">
            {/* Visualize Button with Smart States */}
            {isEditingPositions ? (
              /* Edit Mode: Show Apply button if instructions exist, otherwise show prompt */
              editSpecialInstructions.trim() ? (
                /* State: Edit Mode with Special Instructions (Purple, Enabled) */
                <button
                  onClick={handleRevisualizeWithInstructions}
                  disabled={isVisualizing}
                  className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
                >
                  {isVisualizing ? (
                    <>
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Applying Instructions...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Apply Edit Instructions
                    </>
                  )}
                </button>
              ) : (
                /* State: Edit Mode without instructions - prompt user */
                <button
                  disabled
                  className="w-full py-3 px-4 bg-purple-200 text-purple-600 font-semibold rounded-lg cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Enter instructions above or exit edit mode
                </button>
              )
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

            {/* Save & Publish Buttons */}
            <div className="flex gap-2">
              {/* Save as Draft Button */}
              <button
                onClick={handleSaveAsDraft}
                disabled={savingDraft || saving || !title.trim()}
                className="flex-1 py-3 px-4 bg-gray-100 hover:bg-gray-200 disabled:bg-gray-50 disabled:cursor-not-allowed text-gray-700 disabled:text-gray-400 font-semibold rounded-lg transition-colors flex items-center justify-center gap-2 border border-gray-300"
              >
                {savingDraft ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Saving...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                    </svg>
                    Save Draft
                  </>
                )}
              </button>

              {/* Publish Button */}
              <button
                onClick={handlePublish}
                disabled={saving || savingDraft || !visualizationImage || selectedProducts.length === 0 || !title.trim()}
                className="flex-1 py-3 px-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
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
                    Publish
                  </>
                )}
              </button>
            </div>

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

            {/* Improve Quality - Advanced action at bottom */}
            {visualizationImage && selectedProducts.length > 0 && (
              <div className="mt-4 pt-3 border-t border-gray-200">
                <button
                  onClick={handleImproveQuality}
                  disabled={isImprovingQuality || isVisualizing}
                  className="w-full py-2 px-3 bg-gray-100 hover:bg-gray-200 disabled:bg-gray-50 disabled:cursor-not-allowed text-gray-600 disabled:text-gray-400 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
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
                <p className="text-xs text-gray-400 text-center mt-1">Re-renders from original room image. Resets undo/redo.</p>
              </div>
            )}
          </div>
            </div>
          </Panel>
        </Group>
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
