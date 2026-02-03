'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import ChatPanel from '@/components/panels/ChatPanel';
import ProductDiscoveryPanel from '@/components/panels/ProductDiscoveryPanel';
import CanvasPanel from '@/components/panels/CanvasPanel';
import { ProductDetailModal } from '@/components/ProductDetailModal';
import { ResizablePanelLayout } from '@/components/panels/ResizablePanelLayout';
import { KeywordSearchPanel, SearchFilters, KeywordSearchPanelRef } from '@/components/products';
import { WallFilterPanel } from '@/components/walls';
import { useWallColor } from '@/hooks/useWallColor';
import { useWallFilters } from '@/hooks/useWallFilters';
import { useWallTextures } from '@/hooks/useWallTextures';
import {
  useCanvas,
  CanvasItem,
  extractProducts as extractCanvasProducts,
  extractWallColor as extractCanvasWallColor,
  extractTextureVariant as extractCanvasTextureVariant,
  extractTexture as extractCanvasTexture,
} from '@/hooks/useCanvas';
import { WallColor, WallColorFamily } from '@/types/wall-colors';
import { WallType, TextureType } from '@/types/wall-textures';
import { SubModeToggle, SearchSubMode } from '@/components/search';

type SearchMode = 'ai' | 'search';

/**
 * Top ModeToggle Component - Search vs AI Stylist
 */
function ModeToggle({
  mode,
  onModeChange,
}: {
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
}) {
  return (
    <div className="inline-flex items-center p-0.5 bg-neutral-100 dark:bg-neutral-800 rounded-lg">
      <button
        onClick={() => onModeChange('search')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center ${
          mode === 'search'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        Search
      </button>
      <button
        disabled
        className="px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center text-neutral-400 dark:text-neutral-500 cursor-not-allowed opacity-50"
        title="Coming soon"
      >
        AI Stylist
      </button>
    </div>
  );
}

// Default filter values
const DEFAULT_FILTERS: SearchFilters = {
  selectedStores: [],
  selectedStyles: [],
  selectedColors: [],
  selectedMaterials: [],
  priceMin: 0,
  priceMax: Infinity,
};
import { checkFurnitureRemovalStatus, startFurnitureRemoval, getCategorizedStores, projectsAPI, restoreDesignStateFromRecovery, CategorizedStoresResponse, StoreCategory, imageAPI, adminCuratedAPI } from '@/utils/api';
import { STYLE_LABEL_OPTIONS, BUDGET_TIER_OPTIONS } from '@/constants/products';
import { calculateBudgetTier } from '@/utils/product-transforms';
import { useAuth, canPublishLooks } from '@/contexts/AuthContext';
import { useNavigationGuard } from '@/hooks/useNavigationGuard';
import { ProtectedRoute } from '@/components/ProtectedRoute';

/**
 * New UI V2: Three-Panel Design Interface
 *
 * Layout:
 * - Left Panel (25%): Chat Interface
 * - Center Panel (50%): Product Discovery & Selection
 * - Right Panel (25%): Canvas & Visualization
 */
function DesignPageContent() {
  // Mobile tab state
  const [activeTab, setActiveTab] = useState<'chat' | 'products' | 'canvas'>('chat');

  // Search mode state - AI Stylist (chat) or Search
  const [searchMode, setSearchMode] = useState<SearchMode>('search');
  // Sub-mode for Search - Furniture & Decor or Walls (only shown when searchMode is 'search')
  const [searchSubMode, setSearchSubMode] = useState<SearchSubMode>('furniture');

  // Shared state for cross-panel communication
  const [roomImage, setRoomImage] = useState<string | null>(null);
  // Clean room image without any products - used for reset visualization
  // This is critical when using curated looks where roomImage might have products baked in
  const [cleanRoomImage, setCleanRoomImage] = useState<string | null>(null);
  const [canvasProducts, setCanvasProducts] = useState<any[]>([]);
  const [productRecommendations, setProductRecommendations] = useState<any[]>([]);
  const [initialVisualizationImage, setInitialVisualizationImage] = useState<string | null>(null);

  // Category-based product discovery state
  const [selectedCategories, setSelectedCategories] = useState<any[] | null>(null);
  const [productsByCategory, setProductsByCategory] = useState<Record<string, any[]> | null>(null);
  const [totalBudget, setTotalBudget] = useState<number | null>(null);

  // Keyword search results state (when in keyword mode, results display in Panel 2)
  const [keywordSearchResults, setKeywordSearchResults] = useState<{
    products: any[];
    totalProducts: number;
    totalPrimary: number;
    totalRelated: number;
    hasMore: boolean;
    isSearching: boolean;
    isLoadingMore: boolean;
  } | null>(null);

  // Global filter state (persists across mode switches)
  const [searchFilters, setSearchFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [showSearchFilters, setShowSearchFilters] = useState(false);

  // Furniture removal state
  const [isProcessingFurniture, setIsProcessingFurniture] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');

  // Store selection state
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [showStoreModal, setShowStoreModal] = useState(false);
  const [availableStores, setAvailableStores] = useState<string[]>([]);
  const [storeCategories, setStoreCategories] = useState<StoreCategory[]>([]);

  // Product detail modal state
  const [selectedProduct, setSelectedProduct] = useState<any | null>(null);

  // Publish modal state (for Curator tier users)
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishTitle, setPublishTitle] = useState('');
  const [publishDescription, setPublishDescription] = useState('');
  const [publishTags, setPublishTags] = useState('');
  const [publishRoomType, setPublishRoomType] = useState<'living_room' | 'bedroom'>('living_room');
  const [publishStyleLabels, setPublishStyleLabels] = useState<string[]>([]);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishSuccess, setPublishSuccess] = useState(false);

  // Project state (for logged-in users)
  const searchParams = useSearchParams();
  const router = useRouter();
  const { isAuthenticated, user, sessionInvalidatedExternally, clearExternalInvalidation } = useAuth();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string>('');
  const [isEditingName, setIsEditingName] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const lastSaveDataRef = useRef<string>('');
  // Refs for tracking what was last saved (used for optimized saves that only send changed fields)
  const lastSavedCanvasRef = useRef<string>('[]');
  const lastSavedRoomImageRef = useRef<string | null>(null);
  const lastSavedVizImageRef = useRef<string | null>(null);
  const lastSavedChatSessionRef = useRef<string | null>(null);
  const [projectLoaded, setProjectLoaded] = useState(false); // Track when project data is loaded

  // Visualization history state (for undo/redo persistence)
  const [visualizationHistory, setVisualizationHistory] = useState<any[]>([]);

  // Chat session state (for restoring conversation history)
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);

  // Track if we recovered from a 401 session expiry (used to determine if sessionStorage data should be used)
  const wasRecoveredFromSessionExpiryRef = useRef<boolean>(false);

  // Track if we're currently creating a project (to prevent duplicate creation from React re-renders)
  const isCreatingProjectRef = useRef<boolean>(false);

  // Ref for KeywordSearchPanel to call loadMore from ProductDiscoveryPanel
  const keywordSearchRef = useRef<KeywordSearchPanelRef>(null);

  // Track if we're on mobile (for conditional rendering of KeywordSearchPanel)
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Wall color state - color is added to canvas, then applied during visualization
  const {
    canvasWallColor,
    selectedColor: selectedWallColor,
    handleSelectColor: handleSelectWallColor,
    handleAddToCanvas: handleAddWallColorToCanvas,
    removeFromCanvas: removeWallColorFromCanvas,
    setCanvasWallColor,  // For undo/redo
  } = useWallColor();

  // Wall filters state - manages Color/Textured toggle and filter selections
  const {
    wallType,
    selectedFamilies,
    selectedBrands,
    setWallType,
    toggleFamily,
    toggleBrand,
    clearAllFilters,
    hasActiveFilters,
  } = useWallFilters();

  // Wall textures state - fetches textures lazily when textured tab is selected
  const {
    textures,
    brands: availableTextureBrands,
    isLoading: isLoadingTextures,
    fetchTextures,
    selectedVariant: selectedTextureVariant,
    selectedTexture,
    canvasTextureVariant,
    canvasTexture,
    setSelectedVariant: handleSelectTextureVariant,
    addToCanvas: handleAddTextureToCanvas,
    removeFromCanvas: removeTextureFromCanvas,
    setCanvasTextureVariant,  // For undo/redo
  } = useWallTextures();

  // Lazy-load textures only when user switches to textured wall tab
  useEffect(() => {
    if (searchSubMode === 'walls' && wallType === 'textured') {
      fetchTextures();
    }
  }, [searchSubMode, wallType, fetchTextures]);

  // Unified canvas state management
  const canvas = useCanvas();

  // Wrap wall color/texture add-to-canvas to sync with unified canvas
  const handleAddWallColorToCanvasUnified = useCallback((color: WallColor) => {
    handleAddWallColorToCanvas(color);
    canvas.addWallColor(color);
  }, [handleAddWallColorToCanvas, canvas.addWallColor]);

  const handleAddTextureToCanvasUnified = useCallback((variant: any, texture: any) => {
    handleAddTextureToCanvas(variant, texture);
    canvas.addTexture(variant, texture);
  }, [handleAddTextureToCanvas, canvas.addTexture]);

  const removeWallColorFromCanvasUnified = useCallback(() => {
    removeWallColorFromCanvas();
    canvas.setWallColor(null);
  }, [removeWallColorFromCanvas, canvas.setWallColor]);

  const removeTextureFromCanvasUnified = useCallback(() => {
    removeTextureFromCanvas();
    canvas.setTextureVariant(null);
  }, [removeTextureFromCanvas, canvas.setTextureVariant]);

  // Handle canvas items restore from undo/redo
  const handleSetCanvasItems = useCallback((items: CanvasItem[]) => {
    canvas.setItems(items);
    // Also sync legacy state from the canvas items
    const restoredProducts = extractCanvasProducts(items);
    const restoredWallColor = extractCanvasWallColor(items);
    const restoredTextureVariant = extractCanvasTextureVariant(items);
    const restoredTexture = extractCanvasTexture(items);
    setCanvasProducts(restoredProducts);
    setCanvasWallColor(restoredWallColor);
    setCanvasTextureVariant(restoredTextureVariant, restoredTexture);
  }, [canvas.setItems, setCanvasWallColor, setCanvasTextureVariant]);

  // Track if we have unsaved changes
  const hasUnsavedChanges = saveStatus === 'unsaved' || saveStatus === 'saving';

  // Enable navigation guard when there are unsaved changes
  // BUT disable it if session was invalidated by another tab (allow user to navigate to login)
  useNavigationGuard({
    enabled: hasUnsavedChanges && !sessionInvalidatedExternally,
    message: 'You have unsaved changes. Are you sure you want to leave?',
    onNavigationAttempt: () => {
      console.log('[DesignPage] Navigation blocked due to unsaved changes');
    },
  });

  // Load room image, products, and stores from sessionStorage on mount
  useEffect(() => {
    // Check for "fresh" param indicating a brand new project - clear all stale data
    const isFreshProject = searchParams?.get('fresh') === '1';
    if (isFreshProject) {
      console.log('[DesignPage] Fresh project detected - clearing sessionStorage');
      sessionStorage.removeItem('roomImage');
      sessionStorage.removeItem('cleanRoomImage');
      sessionStorage.removeItem('curatedRoomImage');
      sessionStorage.removeItem('curatedVisualizationImage');
      sessionStorage.removeItem('preselectedProducts');
      sessionStorage.removeItem('persistedCanvasProducts');
      sessionStorage.removeItem('design_session_id');
      sessionStorage.removeItem('furnitureRemovalJobId');
      sessionStorage.removeItem('designAccessGranted'); // Clear tier bypass for fresh project
      // Don't load any stored images - let the user start fresh
      return;
    }

    // IMPORTANT: If loading an existing project (projectId in URL), skip this useEffect
    // The project loading useEffect will handle deciding whether to use sessionStorage or backend data
    // based on whether the project already has saved data
    // NOTE: Do NOT clear sessionStorage here - curated looks need it for new projects!
    const urlProjectId = searchParams?.get('projectId');
    if (urlProjectId) {
      console.log('[DesignPage] Loading existing project - deferring to project loading logic');
      return;
    }

    // IMPORTANT: If authenticated but no projectId, a new project will be created by the second useEffect
    // Don't process sessionStorage here - it will be cleared after reading, then the project creation
    // redirect will lose the data. Let the second useEffect handle sessionStorage after project creation.
    if (isAuthenticated && !urlProjectId) {
      console.log('[DesignPage] Authenticated without projectId - deferring to project creation logic');
      return;
    }

    // Try to restore state from 401 recovery (session expiry during work)
    // This restores data that was saved to localStorage before redirect to login
    const wasRecovered = restoreDesignStateFromRecovery();
    if (wasRecovered) {
      console.log('[DesignPage] Restored design state from session recovery');
      wasRecoveredFromSessionExpiryRef.current = true;
    }

    // Check if user has uploaded their own room image
    const userUploadedImage = sessionStorage.getItem('roomImage');
    // Check for persisted clean room image (from furniture removal)
    const persistedCleanRoomImage = sessionStorage.getItem('cleanRoomImage');

    // Check for curated look data
    const curatedRoomImage = sessionStorage.getItem('curatedRoomImage');
    const curatedVisualizationImage = sessionStorage.getItem('curatedVisualizationImage');
    const preselectedProducts = sessionStorage.getItem('preselectedProducts');

    console.log('[DesignPage] Session storage check:', {
      hasUserUploadedImage: !!userUploadedImage,
      hasCleanRoomImage: !!persistedCleanRoomImage,
      hasCuratedVisualization: !!curatedVisualizationImage,
      curatedVizLength: curatedVisualizationImage?.length || 0,
      hasPreselectedProducts: !!preselectedProducts,
    });

    // Check if we need to auto-trigger furniture removal (from onboarding)
    const pendingFurnitureRemoval = sessionStorage.getItem('pendingFurnitureRemoval');

    // Room image logic:
    // - If user uploaded image exists, use it and clear curated data
    // - Otherwise, use curated room image as the base room for visualization
    if (userUploadedImage) {
      setRoomImage(userUploadedImage);
      // If furniture removal already completed, use the clean room image; otherwise, uploaded image is clean
      if (persistedCleanRoomImage) {
        setCleanRoomImage(persistedCleanRoomImage);
        console.log('[DesignPage] Using user-uploaded room image with furniture-removed clean room');
      } else {
        setCleanRoomImage(userUploadedImage); // User-uploaded image is clean (before furniture removal)
        console.log('[DesignPage] Using user-uploaded room image (furniture removal pending or not needed)');
      }
      // Clear curated data since we're using user's room
      sessionStorage.removeItem('curatedVisualizationImage');
      sessionStorage.removeItem('curatedRoomImage');

      // Auto-trigger furniture removal if flagged from onboarding
      if (pendingFurnitureRemoval === 'true' && !persistedCleanRoomImage) {
        console.log('[DesignPage] Auto-triggering furniture removal for onboarding image');
        sessionStorage.removeItem('pendingFurnitureRemoval');
        // Delay slightly to ensure state is set, then trigger furniture removal
        setTimeout(async () => {
          try {
            setIsProcessingFurniture(true);
            setProcessingStatus('Preparing your room for design...');
            const { startFurnitureRemoval: triggerRemoval, checkFurnitureRemovalStatus: checkStatus } = await import('@/utils/api');
            const response = await triggerRemoval(userUploadedImage);
            console.log('[DesignPage] Furniture removal started:', response.job_id);
            sessionStorage.setItem('furnitureRemovalJobId', response.job_id);

            // Start inline polling since the mount-time useEffect already ran
            let pollAttempts = 0;
            const MAX_POLL_ATTEMPTS = 150;
            const poll = async () => {
              pollAttempts++;
              if (pollAttempts > MAX_POLL_ATTEMPTS) {
                setIsProcessingFurniture(false);
                setProcessingStatus('');
                sessionStorage.removeItem('furnitureRemovalJobId');
                return;
              }
              try {
                const status = await checkStatus(response.job_id);
                if (status.status === 'completed' && status.image) {
                  const imageToSet = status.image.startsWith('data:') ? status.image : `data:image/png;base64,${status.image}`;
                  setRoomImage(imageToSet);
                  setCleanRoomImage(imageToSet);
                  try {
                    sessionStorage.setItem('cleanRoomImage', imageToSet);
                    sessionStorage.setItem('roomImage', imageToSet);
                  } catch (e) { /* quota exceeded */ }
                  setIsProcessingFurniture(false);
                  setProcessingStatus('');
                  sessionStorage.removeItem('furnitureRemovalJobId');
                } else if (status.status === 'failed') {
                  setIsProcessingFurniture(false);
                  setProcessingStatus('');
                  sessionStorage.removeItem('furnitureRemovalJobId');
                } else {
                  setProcessingStatus('Processing your room image...');
                  setTimeout(poll, 2000);
                }
              } catch (error) {
                setIsProcessingFurniture(false);
                setProcessingStatus('');
                sessionStorage.removeItem('furnitureRemovalJobId');
              }
            };
            poll();
          } catch (error) {
            console.error('[DesignPage] Auto furniture removal failed:', error);
            setIsProcessingFurniture(false);
            setProcessingStatus('');
          }
        }, 100);
      }
    } else if (curatedRoomImage || curatedVisualizationImage) {
      // No user room image - use curated look's room image as the base
      // This allows visualization to happen on the curated room
      if (curatedRoomImage) {
        const formattedRoomImage = curatedRoomImage.startsWith('data:')
          ? curatedRoomImage
          : `data:image/png;base64,${curatedRoomImage}`;
        setRoomImage(formattedRoomImage);
        setCleanRoomImage(formattedRoomImage); // Clean room image available from curated look
        console.log('[DesignPage] Using curated room image as base for visualization');
      } else if (curatedVisualizationImage) {
        // FALLBACK: If no clean room image, use visualization as base for display
        // NOTE: cleanRoomImage remains null - backend will need to extract clean room when force_reset is needed
        const formattedVizAsRoom = curatedVisualizationImage.startsWith('data:')
          ? curatedVisualizationImage
          : `data:image/png;base64,${curatedVisualizationImage}`;
        setRoomImage(formattedVizAsRoom);
        // DO NOT set cleanRoomImage here - it has products baked in!
        // When force_reset is needed, we'll need to extract clean room from visualization
        console.log('[DesignPage] Using curated visualization as base (no clean room available - will extract on reset)');
      }

      // Also load the curated visualization image if it exists (shows pre-rendered result)
      if (curatedVisualizationImage) {
        const formattedVizImage = curatedVisualizationImage.startsWith('data:')
          ? curatedVisualizationImage
          : `data:image/png;base64,${curatedVisualizationImage}`;
        setInitialVisualizationImage(formattedVizImage);
        console.log('[DesignPage] Loaded curated visualization image:', {
          originalLength: curatedVisualizationImage.length,
          formattedLength: formattedVizImage.length,
          startsWithData: formattedVizImage.startsWith('data:'),
        });
      }
      sessionStorage.removeItem('curatedVisualizationImage');
    }

    // Load preselected products from curated look OR persisted canvas products (after page reload)
    const persistedCanvasProducts = sessionStorage.getItem('persistedCanvasProducts');
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
          attributes: p.attributes,  // Preserve attributes for dimensions (width, height, depth)
        }));
        setCanvasProducts(formattedProducts);
        canvas.setProducts(formattedProducts);
        console.log('[DesignPage] Loaded', formattedProducts.length, 'preselected products from curated look with full context');
        // Clear after loading
        sessionStorage.removeItem('preselectedProducts');
        sessionStorage.removeItem('preselectedLookTheme');
      } catch (e) {
        console.error('[DesignPage] Failed to parse preselected products:', e);
      }
    } else if (persistedCanvasProducts) {
      // Restore canvas products after page reload (e.g., after uploading a new room image)
      try {
        const products = JSON.parse(persistedCanvasProducts);
        setCanvasProducts(products);
        canvas.setProducts(products);
        console.log('[DesignPage] Restored', products.length, 'canvas products after page reload');
        // Clear after loading
        sessionStorage.removeItem('persistedCanvasProducts');
      } catch (e) {
        console.error('[DesignPage] Failed to parse persisted canvas products:', e);
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

    // Fetch available stores for the modal (categorized by budget tier)
    const fetchStores = async () => {
      try {
        const response = await getCategorizedStores();
        setStoreCategories(response.categories);
        // Also maintain flat list for backwards compatibility
        setAvailableStores(response.all_stores.map(s => s.name));
      } catch (error) {
        console.error('[DesignPage] Failed to fetch available stores:', error);
      }
    };
    fetchStores();

    // Clear session ID on page load to start fresh visualization session
    // This prevents old visualization history from bleeding into new sessions
    // NOTE: Do NOT clear furnitureRemovalJobId here - the polling useEffect needs it!
    sessionStorage.removeItem('design_session_id');
    console.log('[DesignPage] Cleared session ID on page load - starting fresh session');
  }, []);

  // Keep design state synced to sessionStorage for 401 recovery
  // This ensures we can restore the user's work if their session expires
  useEffect(() => {
    try {
      // Persist canvas products
      if (canvasProducts.length > 0) {
        sessionStorage.setItem('persistedCanvasProducts', JSON.stringify(canvasProducts));
      }
      // Persist chat session ID
      if (chatSessionId) {
        sessionStorage.setItem('design_session_id', chatSessionId);
      }
    } catch (e) {
      // Silently fail if storage quota exceeded
    }
  }, [canvasProducts, chatSessionId]);

  // Load project data if projectId is in URL params, or auto-create if authenticated without projectId
  useEffect(() => {
    const loadProject = async () => {
      const urlProjectId = searchParams?.get('projectId');

      // CRITICAL: Reset projectLoaded when starting to load a new project
      // This forces ChatPanel to unmount, which resets its refs (sessionInitializedRef, onboardingProcessedRef)
      // Without this, switching between projects wouldn't properly reset the chat session
      setProjectLoaded(false);

      // If not authenticated, mark as loaded immediately (guest mode)
      if (!isAuthenticated) {
        console.log('[DesignPage] No project to load (guest mode)');
        setProjectLoaded(true);
        return;
      }

      // If authenticated but no project ID, auto-create a new project
      if (!urlProjectId) {
        // CRITICAL: Prevent duplicate project creation from React re-renders (Strict Mode, etc.)
        if (isCreatingProjectRef.current) {
          console.log('[DesignPage] Project creation already in progress - skipping duplicate');
          return;
        }
        isCreatingProjectRef.current = true;
        console.log('[DesignPage] Authenticated user without projectId - auto-creating new project');

        // Check if there's curated data that needs to be preserved
        const hasCuratedData = sessionStorage.getItem('curatedRoomImage') ||
                               sessionStorage.getItem('curatedVisualizationImage') ||
                               sessionStorage.getItem('preselectedProducts');

        if (hasCuratedData) {
          console.log('[DesignPage] Curated data detected - preserving sessionStorage for new project');
        } else {
          // Clear any stale sessionStorage data from previous projects
          // This ensures the new project starts fresh, not with old images/products
          sessionStorage.removeItem('roomImage');
          sessionStorage.removeItem('cleanRoomImage');
          sessionStorage.removeItem('curatedRoomImage');
          sessionStorage.removeItem('curatedVisualizationImage');
          sessionStorage.removeItem('preselectedProducts');
          sessionStorage.removeItem('persistedCanvasProducts');
          sessionStorage.removeItem('design_session_id');
          sessionStorage.removeItem('furnitureRemovalJobId');
          console.log('[DesignPage] Cleared sessionStorage for fresh project creation');

          // Also clear React state to ensure fresh start when component doesn't re-mount
          setRoomImage(null);
          setCleanRoomImage(null);
          setCanvasProducts([]);
          setProductRecommendations([]);
          setInitialVisualizationImage(null);
          setSelectedCategories(null);
          setProductsByCategory(null);
          setTotalBudget(null);
          setVisualizationHistory([]);
          setChatSessionId(null);
          setProjectId(null);
          setProjectName('');
        }

        try {
          const newProject = await projectsAPI.create({
            name: `New Design ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`,
          });
          console.log('[DesignPage] Auto-created new project:', newProject.id, newProject.name);

          // Mark this project ID as newly created so we know to use sessionStorage data for it
          sessionStorage.setItem('newlyCreatedProjectId', newProject.id);

          // Redirect to the same page with the new projectId
          // Use fresh=1 ONLY if no curated data - otherwise let project loading read from sessionStorage
          const freshParam = hasCuratedData ? '' : '&fresh=1';
          router.replace(`/design?projectId=${newProject.id}${freshParam}`);
          return;
        } catch (error) {
          console.error('[DesignPage] Failed to auto-create project:', error);
          // Reset the creation ref so user can retry
          isCreatingProjectRef.current = false;
          // Fall back to guest mode on error
          setProjectLoaded(true);
          return;
        }
      }

      try {
        // Reset the creation ref now that we have a projectId (redirect completed)
        isCreatingProjectRef.current = false;
        console.log('[DesignPage] Loading project:', urlProjectId);
        const project = await projectsAPI.get(urlProjectId);
        console.log('[DesignPage] Project API response:', {
          id: project.id,
          name: project.name,
          hasRoomImage: !!project.room_image,
          roomImageLength: project.room_image?.length || 0,
          hasVisualizationImage: !!project.visualization_image,
          vizImageLength: project.visualization_image?.length || 0,
          hasCanvasProducts: !!project.canvas_products,
          canvasProductsLength: project.canvas_products?.length || 0,
          chatSessionId: project.chat_session_id,
        });
        setProjectId(project.id);
        setProjectName(project.name);

        // Check if this is a newly created project that should use sessionStorage data
        // IMPORTANT: Only use sessionStorage if this is the project we JUST created in this session
        // This prevents old sessionStorage data from bleeding into existing empty projects
        const newlyCreatedProjectId = sessionStorage.getItem('newlyCreatedProjectId');
        const isNewlyCreatedProject = newlyCreatedProjectId === project.id;
        const hasNoSavedData = !project.room_image && !project.visualization_image && !project.canvas_products;

        // NOTE: Don't clear newlyCreatedProjectId here — if the useEffect re-runs
        // (React Strict Mode, searchParams change), the second run would miss the
        // marker and fall into the "existing empty project" branch, clearing all
        // sessionStorage data. Clear it only after data is fully consumed (line below).

        if (isNewlyCreatedProject && hasNoSavedData) {
          // For newly created projects, load sessionStorage data (from curated looks or user upload)
          console.log('[DesignPage] Newly created project detected, loading sessionStorage data');

          // Check for curated look data
          const curatedRoomImage = sessionStorage.getItem('curatedRoomImage');
          const curatedVisualizationImage = sessionStorage.getItem('curatedVisualizationImage');
          const preselectedProducts = sessionStorage.getItem('preselectedProducts');
          const userUploadedImage = sessionStorage.getItem('roomImage');
          const cleanRoomImage = sessionStorage.getItem('cleanRoomImage');

          // Check if we need to auto-trigger furniture removal (from onboarding)
          const pendingFurnitureRemoval = sessionStorage.getItem('pendingFurnitureRemoval');

          console.log('[DesignPage] SessionStorage for new project:', {
            hasCuratedRoom: !!curatedRoomImage,
            hasCuratedViz: !!curatedVisualizationImage,
            hasPreselectedProducts: !!preselectedProducts,
            hasUserUploadedImage: !!userUploadedImage,
            pendingFurnitureRemoval: pendingFurnitureRemoval === 'true',
          });

          // Load room image (prefer user-uploaded, then curated)
          // IMPORTANT: Must explicitly clear state if no data, since component doesn't remount on navigation
          if (userUploadedImage) {
            setRoomImage(userUploadedImage);
            setCleanRoomImage(cleanRoomImage || userUploadedImage);

            // Auto-trigger furniture removal if flagged from onboarding
            if (pendingFurnitureRemoval === 'true' && !cleanRoomImage) {
              console.log('[DesignPage] Auto-triggering furniture removal for onboarding image (authenticated)');
              sessionStorage.removeItem('pendingFurnitureRemoval');
              // Trigger after a short delay to let state settle
              setTimeout(async () => {
                try {
                  setIsProcessingFurniture(true);
                  setProcessingStatus('Preparing your room for design...');
                  const response = await startFurnitureRemoval(userUploadedImage);
                  console.log('[DesignPage] Furniture removal started:', response.job_id);
                  sessionStorage.setItem('furnitureRemovalJobId', response.job_id);

                  // Start inline polling since mount-time useEffect already ran
                  let pollAttempts = 0;
                  const MAX_POLL_ATTEMPTS = 150;
                  const poll = async () => {
                    pollAttempts++;
                    if (pollAttempts > MAX_POLL_ATTEMPTS) {
                      setIsProcessingFurniture(false);
                      setProcessingStatus('');
                      sessionStorage.removeItem('furnitureRemovalJobId');
                      return;
                    }
                    try {
                      const status = await checkFurnitureRemovalStatus(response.job_id);
                      if (status.status === 'completed' && status.image) {
                        const imageToSet = status.image.startsWith('data:') ? status.image : `data:image/png;base64,${status.image}`;
                        setRoomImage(imageToSet);
                        setCleanRoomImage(imageToSet);
                        try {
                          sessionStorage.setItem('cleanRoomImage', imageToSet);
                          sessionStorage.setItem('roomImage', imageToSet);
                        } catch (e) { /* quota exceeded */ }
                        setIsProcessingFurniture(false);
                        setProcessingStatus('');
                        sessionStorage.removeItem('furnitureRemovalJobId');
                      } else if (status.status === 'failed') {
                        setIsProcessingFurniture(false);
                        setProcessingStatus('');
                        sessionStorage.removeItem('furnitureRemovalJobId');
                      } else {
                        setProcessingStatus('Processing your room image...');
                        setTimeout(poll, 2000);
                      }
                    } catch (error) {
                      setIsProcessingFurniture(false);
                      setProcessingStatus('');
                      sessionStorage.removeItem('furnitureRemovalJobId');
                    }
                  };
                  poll();
                } catch (error) {
                  console.error('[DesignPage] Auto furniture removal failed:', error);
                  setIsProcessingFurniture(false);
                  setProcessingStatus('');
                }
              }, 100);
            }
          } else if (curatedRoomImage) {
            const formattedRoomImage = curatedRoomImage.startsWith('data:')
              ? curatedRoomImage
              : `data:image/png;base64,${curatedRoomImage}`;
            setRoomImage(formattedRoomImage);
            setCleanRoomImage(formattedRoomImage);
          } else if (curatedVisualizationImage) {
            // Use visualization as room image if no clean room available
            const formattedViz = curatedVisualizationImage.startsWith('data:')
              ? curatedVisualizationImage
              : `data:image/png;base64,${curatedVisualizationImage}`;
            setRoomImage(formattedViz);
            setCleanRoomImage(null); // No clean room available
          } else {
            // No room image data - explicitly clear state (prevents stale data from previous project)
            setRoomImage(null);
            setCleanRoomImage(null);
          }

          // Load curated visualization image (or clear if none)
          if (curatedVisualizationImage) {
            const formattedVizImage = curatedVisualizationImage.startsWith('data:')
              ? curatedVisualizationImage
              : `data:image/png;base64,${curatedVisualizationImage}`;
            setInitialVisualizationImage(formattedVizImage);
          } else {
            setInitialVisualizationImage(null);
          }

          // Load preselected products from curated look (or clear if none)
          if (preselectedProducts) {
            try {
              const products = JSON.parse(preselectedProducts);
              const formattedProducts = products.map((p: any) => ({
                id: String(p.id),
                name: p.name,
                price: p.price || 0,
                image_url: p.image_url,
                productType: p.product_type || 'other',
                source: p.source_website,
                source_url: p.source_url,
                description: p.description,
                attributes: p.attributes,
              }));
              setCanvasProducts(formattedProducts);
              canvas.setProducts(formattedProducts);
              console.log('[DesignPage] Loaded', formattedProducts.length, 'preselected products from curated look');
            } catch (e) {
              console.error('[DesignPage] Failed to parse preselected products:', e);
              setCanvasProducts([]);
              canvas.setProducts([]);
            }
          } else {
            setCanvasProducts([]);
            canvas.setProducts([]);
          }

          // Clear other state that might persist from previous project
          setVisualizationHistory([]);
          setChatSessionId(null);
          setProductRecommendations([]);
          setSelectedCategories(null);
          setProductsByCategory(null);
          setTotalBudget(null);

          // Clear curated data from sessionStorage after loading
          sessionStorage.removeItem('curatedVisualizationImage');
          sessionStorage.removeItem('curatedRoomImage');
          sessionStorage.removeItem('preselectedProducts');
          sessionStorage.removeItem('preselectedLookTheme');
          // Now safe to clear the marker — data has been fully consumed
          sessionStorage.removeItem('newlyCreatedProjectId');

          // Set initial state for change detection (starts as "unsaved" so first save works)
          lastSaveDataRef.current = JSON.stringify({
            room_image: null,
            clean_room_image: null,
            visualization_image: null,
            canvas_products: null,
            visualization_history: null,
            chat_session_id: null,
          });
        } else if (hasNoSavedData) {
          // Existing empty project (not newly created) - show empty state
          // IMPORTANT: Clear stale sessionStorage to prevent old data from bleeding in
          console.log('[DesignPage] Existing empty project - clearing sessionStorage and showing empty state');
          try {
            sessionStorage.removeItem('roomImage');
            sessionStorage.removeItem('cleanRoomImage');
            sessionStorage.removeItem('curatedRoomImage');
            sessionStorage.removeItem('curatedVisualizationImage');
            sessionStorage.removeItem('preselectedProducts');
            sessionStorage.removeItem('persistedCanvasProducts');
          } catch (e) {
            // Ignore errors when clearing
          }
          setRoomImage(null);
          setCleanRoomImage(null);
          setInitialVisualizationImage(null);
          setCanvasProducts([]);
          canvas.setProducts([]);
          setVisualizationHistory([]);
          setChatSessionId(null);
          setProjectLoaded(true);
        } else {
          // Load existing project data (project has saved data)
          // ONLY use sessionStorage data if we ACTUALLY recovered from a 401 session expiry
          // This prevents stale sessionStorage data from overriding the saved project
          const wasActuallyRecovered = wasRecoveredFromSessionExpiryRef.current;

          if (wasActuallyRecovered) {
            // We recovered from 401 - check for recovered data
            const recoveredRoomImage = sessionStorage.getItem('roomImage');
            const recoveredCleanRoomImage = sessionStorage.getItem('cleanRoomImage');
            const recoveredCanvasProducts = sessionStorage.getItem('persistedCanvasProducts');
            const hasRecoveredData = recoveredRoomImage || recoveredCanvasProducts;

            if (hasRecoveredData) {
              console.log('[DesignPage] Found recovered session data from 401 recovery - using it instead of backend data');
              // Use recovered data (already in sessionStorage from restoreDesignStateFromRecovery)
              if (recoveredRoomImage) {
                setRoomImage(recoveredRoomImage);
              }
              if (recoveredCleanRoomImage) {
                setCleanRoomImage(recoveredCleanRoomImage);
              }
              if (recoveredCanvasProducts) {
                try {
                  const products = JSON.parse(recoveredCanvasProducts);
                  setCanvasProducts(products);
                  canvas.setProducts(products);
                  console.log('[DesignPage] Restored', products.length, 'products from session recovery');
                } catch (e) {
                  console.error('[DesignPage] Failed to parse recovered canvas products:', e);
                }
              }
              // For visualization, chat session - use backend data if available
              if (project.visualization_image) {
                setInitialVisualizationImage(project.visualization_image);
              }
              if (project.chat_session_id) {
                setChatSessionId(project.chat_session_id);
              }
              // Mark as having unsaved changes since recovery data wasn't saved
              lastSaveDataRef.current = JSON.stringify({
                room_image: null,
                clean_room_image: null,
                visualization_image: null,
                canvas_products: null,
                visualization_history: null,
                chat_session_id: null,
              });
              // Clear the recovery flag after using the data
              wasRecoveredFromSessionExpiryRef.current = false;
            }
          }

          // If no recovery happened OR recovery had no relevant data, load from backend
          // Check if we need to load from backend: either no recovery, or recovery didn't have the data we need
          const recoveredRoomImageCheck = wasActuallyRecovered ? sessionStorage.getItem('roomImage') : null;
          const recoveredProductsCheck = wasActuallyRecovered ? sessionStorage.getItem('persistedCanvasProducts') : null;
          const skipBackendLoad = wasActuallyRecovered && (recoveredRoomImageCheck || recoveredProductsCheck);

          if (!skipBackendLoad) {
            // No recovered data - clear sessionStorage and load from backend as usual
            try {
              sessionStorage.removeItem('roomImage');
              sessionStorage.removeItem('cleanRoomImage');
              sessionStorage.removeItem('curatedRoomImage');
              sessionStorage.removeItem('curatedVisualizationImage');
            } catch (e) {
              // Ignore errors when clearing
            }

            // IMPORTANT: Explicitly set state from project data (including null values)
            // This ensures any stale React state is cleared
            setRoomImage(project.room_image || null);
            setCleanRoomImage(project.clean_room_image || null);
            setInitialVisualizationImage(project.visualization_image || null);

            // Try to cache room image in sessionStorage (but don't fail if quota exceeded)
            if (project.room_image) {
              try {
                sessionStorage.setItem('roomImage', project.room_image);
              } catch (storageError) {
                console.warn('[DesignPage] Could not cache room image in sessionStorage (quota exceeded)');
              }
            }

            // Load canvas products (or clear if none)
            if (project.canvas_products) {
              try {
                const products = JSON.parse(project.canvas_products);
                setCanvasProducts(products);
                canvas.setProducts(products);
                console.log('[DesignPage] Loaded', products.length, 'products from project');
              } catch (e) {
                console.error('[DesignPage] Failed to parse project canvas_products:', e);
                setCanvasProducts([]);
                canvas.setProducts([]);
              }
            } else {
              setCanvasProducts([]);
              canvas.setProducts([]);
            }
            // Load visualization history for undo/redo (or clear if none)
            if (project.visualization_history) {
              try {
                const history = JSON.parse(project.visualization_history);
                setVisualizationHistory(history);
                console.log('[DesignPage] Loaded', history.length, 'visualization history entries');
              } catch (e) {
                console.error('[DesignPage] Failed to parse visualization history:', e);
                setVisualizationHistory([]);
              }
            } else {
              setVisualizationHistory([]);
            }
            // Load chat session ID for restoring conversation (or clear if none)
            if (project.chat_session_id) {
              setChatSessionId(project.chat_session_id);
              console.log('[DesignPage] Loaded chat session ID:', project.chat_session_id);
            } else {
              setChatSessionId(null);
            }

            // Store the initial state for change detection
            // IMPORTANT: Re-stringify canvas_products and visualization_history to ensure consistent format
            // This is needed because JSON from database might have different formatting than JSON.stringify produces
            const savedState = {
              room_image: project.room_image,
              clean_room_image: project.clean_room_image,
              visualization_image: project.visualization_image,
              canvas_products: project.canvas_products ? JSON.stringify(JSON.parse(project.canvas_products)) : null,
              visualization_history: project.visualization_history ? JSON.stringify(JSON.parse(project.visualization_history)) : null,
              chat_session_id: project.chat_session_id,
            };
            lastSaveDataRef.current = JSON.stringify(savedState);
            console.log('[DesignPage] Set lastSaveDataRef for existing project:', {
              roomImageLength: savedState.room_image?.length || 0,
              vizImageLength: savedState.visualization_image?.length || 0,
              canvasProductsLength: savedState.canvas_products?.length || 0,
              chatSessionId: savedState.chat_session_id,
            });
          }
        }

        console.log('[DesignPage] Project loaded successfully:', project.name);
      } catch (error) {
        console.error('[DesignPage] Failed to load project:', error);
      } finally {
        // Mark project as loaded regardless of success/failure
        setProjectLoaded(true);
      }
    };

    loadProject();
  }, [searchParams, isAuthenticated, router]);

  // Manual save function
  const saveProject = useCallback(async () => {
    console.log('[DesignPage] Save button clicked', { isAuthenticated, projectId, saveStatus });

    if (!isAuthenticated) {
      console.warn('[DesignPage] Cannot save: Not authenticated');
      return;
    }
    if (!projectId) {
      console.warn('[DesignPage] Cannot save: No projectId');
      return;
    }

    // Get current state
    const currentData = {
      room_image: roomImage,
      clean_room_image: cleanRoomImage,
      visualization_image: initialVisualizationImage,
      canvas_products: canvasProducts.length > 0 ? JSON.stringify(canvasProducts) : null,
      visualization_history: visualizationHistory.length > 0 ? JSON.stringify(visualizationHistory) : null,
      chat_session_id: chatSessionId,
    };

    // OPTIMIZATION: Only send fields that have changed to reduce payload size
    // Large base64 images can be 1-5 MB each, so sending unchanged images is wasteful
    const updatePayload: Record<string, any> = {};

    if (projectName) {
      updatePayload.name = projectName;
    }
    if (roomImage !== lastSavedRoomImageRef.current) {
      updatePayload.room_image = currentData.room_image || undefined;
      updatePayload.clean_room_image = currentData.clean_room_image || undefined;
    }
    if (initialVisualizationImage !== lastSavedVizImageRef.current) {
      updatePayload.visualization_image = currentData.visualization_image || undefined;
    }
    if (JSON.stringify(canvasProducts) !== lastSavedCanvasRef.current) {
      updatePayload.canvas_products = currentData.canvas_products || undefined;
    }
    if (visualizationHistory.length > 0) {
      updatePayload.visualization_history = currentData.visualization_history || undefined;
    }
    if (chatSessionId !== lastSavedChatSessionRef.current) {
      updatePayload.chat_session_id = currentData.chat_session_id || undefined;
    }

    // Calculate payload size for logging
    const payloadSize = JSON.stringify(updatePayload).length;
    const payloadSizeKB = (payloadSize / 1024).toFixed(1);

    console.log('[DesignPage] Saving project with OPTIMIZED payload:', {
      fields: Object.keys(updatePayload),
      payloadSize: `${payloadSizeKB} KB`,
      room_image_changed: roomImage !== lastSavedRoomImageRef.current,
      viz_image_changed: initialVisualizationImage !== lastSavedVizImageRef.current,
      canvas_changed: JSON.stringify(canvasProducts) !== lastSavedCanvasRef.current,
    });

    setSaveStatus('saving');
    const saveStartTime = Date.now();
    const MIN_SAVE_DISPLAY_MS = 400; // Minimum time to show "Saving..." for better UX

    try {
      await projectsAPI.update(projectId, updatePayload);

      lastSaveDataRef.current = JSON.stringify(currentData);

      // CRITICAL: Update "last saved" refs SYNCHRONOUSLY before setting status to 'saved'
      // This prevents the change tracking effect from immediately re-detecting changes
      // Note: Use JSON.stringify(canvasProducts) to match the format used in change detection
      lastSavedCanvasRef.current = JSON.stringify(canvasProducts);
      lastSavedRoomImageRef.current = roomImage;
      lastSavedVizImageRef.current = initialVisualizationImage;
      lastSavedChatSessionRef.current = chatSessionId;
      console.log('[DesignPage] Updated saved refs synchronously in saveProject');

      // Ensure minimum display time for "Saving..." spinner
      const elapsed = Date.now() - saveStartTime;
      if (elapsed < MIN_SAVE_DISPLAY_MS) {
        await new Promise(resolve => setTimeout(resolve, MIN_SAVE_DISPLAY_MS - elapsed));
      }

      setSaveStatus('saved');
      setLastSavedAt(new Date());
      console.log('[DesignPage] Project saved');
    } catch (error: any) {
      console.error('[DesignPage] Save failed:', error);
      console.error('[DesignPage] Error details:', {
        message: error?.message,
        status: error?.response?.status,
        data: error?.response?.data,
      });
      setSaveStatus('unsaved');
    }
  }, [isAuthenticated, projectId, projectName, roomImage, cleanRoomImage, initialVisualizationImage, canvasProducts, visualizationHistory, chatSessionId, saveStatus]);

  // Publish look function (for Curator tier users)
  const handlePublishLook = useCallback(async () => {
    if (!canPublishLooks(user)) {
      console.warn('[DesignPage] User does not have publish permission');
      return;
    }

    if (!publishTitle.trim()) {
      alert('Please enter a title for your look');
      return;
    }

    if (!initialVisualizationImage) {
      alert('Please create a visualization before publishing');
      return;
    }

    setIsPublishing(true);

    try {
      // Calculate budget tier based on total product prices
      const totalPrice = canvasProducts.reduce((sum, p) => sum + (p.price || 0), 0);
      const budgetTier = calculateBudgetTier(totalPrice);

      // Derive style theme from style labels
      const styleTheme = publishStyleLabels.length > 0
        ? publishStyleLabels[0].replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
        : 'Modern';

      // Prepare the look data for API
      const lookData = {
        title: publishTitle,
        style_theme: styleTheme,
        style_description: publishDescription || undefined,
        style_labels: publishStyleLabels,
        room_type: publishRoomType,
        visualization_image: initialVisualizationImage.startsWith('data:')
          ? initialVisualizationImage.split(',')[1]
          : initialVisualizationImage,
        room_image: (cleanRoomImage || roomImage)?.startsWith('data:')
          ? (cleanRoomImage || roomImage)?.split(',')[1]
          : (cleanRoomImage || roomImage) || undefined,
        is_published: true, // Curators can publish directly
        product_ids: canvasProducts.map(p => parseInt(p.id)).filter(id => !isNaN(id)),
        product_types: canvasProducts.map(p => p.productType || 'other'),
        product_quantities: canvasProducts.map(() => 1),
        budget_tier: budgetTier,
      };

      console.log('[DesignPage] Publishing look with data:', {
        title: lookData.title,
        styleTheme: lookData.style_theme,
        roomType: lookData.room_type,
        styleLabels: lookData.style_labels,
        productCount: lookData.product_ids.length,
        budgetTier: lookData.budget_tier,
      });

      // Call the real API
      const result = await adminCuratedAPI.create(lookData);
      console.log('[DesignPage] Look published successfully:', result);

      setPublishSuccess(true);

      // Reset form after success
      setTimeout(() => {
        setShowPublishModal(false);
        setPublishSuccess(false);
        setPublishTitle('');
        setPublishDescription('');
        setPublishTags('');
        setPublishRoomType('living_room');
        setPublishStyleLabels([]);
      }, 2000);

    } catch (error: any) {
      console.error('[DesignPage] Publish failed:', error);
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to publish look. Please try again.';
      alert(errorMessage);
    } finally {
      setIsPublishing(false);
    }
  }, [user, publishTitle, publishDescription, publishTags, publishRoomType, publishStyleLabels, initialVisualizationImage, roomImage, cleanRoomImage, canvasProducts]);

  // Track unsaved changes - SIMPLE APPROACH
  // Use a ref to track when the project was last saved, and compare against current state
  const isInitialLoadRef = useRef<boolean>(true);
  // Note: lastSavedCanvasRef, lastSavedRoomImageRef, lastSavedVizImageRef, lastSavedChatSessionRef
  // are declared at the top of the component (near other refs) to ensure they're available for useCallback

  // This effect tracks changes and marks as unsaved
  useEffect(() => {
    // Skip if not authenticated or no project
    if (!isAuthenticated || !projectId) {
      return;
    }

    // Skip during initial load
    if (isInitialLoadRef.current) {
      return;
    }

    // Compare current state against last saved state
    const currentCanvasJSON = JSON.stringify(canvasProducts);
    const canvasChanged = currentCanvasJSON !== lastSavedCanvasRef.current;
    const roomImageChanged = roomImage !== lastSavedRoomImageRef.current;
    const vizImageChanged = initialVisualizationImage !== lastSavedVizImageRef.current;
    const chatSessionChanged = chatSessionId !== lastSavedChatSessionRef.current;

    const hasChanges = canvasChanged || roomImageChanged || vizImageChanged || chatSessionChanged;

    console.log('[DesignPage] Change tracking:', {
      canvasChanged,
      roomImageChanged: roomImageChanged ? 'YES' : 'no',
      vizImageChanged: vizImageChanged ? 'YES' : 'no',
      chatSessionChanged,
      hasChanges,
      canvasProductsCount: canvasProducts.length,
    });

    if (hasChanges && saveStatus !== 'unsaved') {
      console.log('[DesignPage] >>> CHANGES DETECTED - Setting status to UNSAVED <<<');
      setSaveStatus('unsaved');
    }
  }, [isAuthenticated, projectId, roomImage, initialVisualizationImage, canvasProducts, chatSessionId, saveStatus]);

  // Update "last saved" refs when project loads or saves successfully
  useEffect(() => {
    if (projectLoaded && isInitialLoadRef.current) {
      // Project just loaded - set the "last saved" state to current state
      console.log('[DesignPage] Setting initial saved state refs');
      lastSavedCanvasRef.current = JSON.stringify(canvasProducts);
      lastSavedRoomImageRef.current = roomImage;
      lastSavedVizImageRef.current = initialVisualizationImage;
      lastSavedChatSessionRef.current = chatSessionId;

      // Enable change tracking after a short delay to let React settle
      const timer = setTimeout(() => {
        console.log('[DesignPage] Initial load complete - enabling change tracking');
        isInitialLoadRef.current = false;
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [projectLoaded, canvasProducts, roomImage, initialVisualizationImage, chatSessionId]);

  // NOTE: "last saved" refs are now updated SYNCHRONOUSLY in saveProject() to prevent race conditions
  // The old effect-based approach caused a bug where the first save wouldn't work because the
  // change tracking effect could run before the "update refs" effect

  // Save on page unload/navigation
  useEffect(() => {
    if (!isAuthenticated || !projectId) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (saveStatus === 'unsaved') {
        // Attempt to save before leaving
        saveProject();
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isAuthenticated, projectId, saveStatus, saveProject]);

  // Poll for furniture removal job completion
  useEffect(() => {
    const jobId = sessionStorage.getItem('furnitureRemovalJobId');
    if (!jobId) return;

    console.log('[DesignPage] Found furniture removal job:', jobId);
    setIsProcessingFurniture(true);
    setProcessingStatus('Removing existing furniture from your room...');

    let pollAttempts = 0;
    const MAX_POLL_ATTEMPTS = 150; // 150 attempts * 2 seconds = 5 minutes max (room analysis + perspective transform + furniture removal)

    const pollInterval = setInterval(async () => {
      pollAttempts++;

      // Timeout after max attempts
      if (pollAttempts > MAX_POLL_ATTEMPTS) {
        console.error('[DesignPage] Furniture removal timed out after 5 minutes');
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
            // Show the furniture-removed image to the user
            // This lets users see the empty room that will be used for visualization
            setRoomImage(status.image); // Show cleaned room image
            setCleanRoomImage(status.image); // Also use for visualization base
            console.log('[DesignPage] Set cleaned room image (furniture removed) as display and base');
            // Save to sessionStorage for persistence (with quota handling)
            try {
              // Clear old images first to free up space
              sessionStorage.removeItem('cleanRoomImage');
              sessionStorage.removeItem('curatedRoomImage');
              sessionStorage.removeItem('curatedVisualizationImage');
              sessionStorage.setItem('cleanRoomImage', status.image);
              sessionStorage.setItem('roomImage', status.image);
            } catch (storageError) {
              console.warn('[DesignPage] SessionStorage quota exceeded, image stored in memory only:', storageError);
              // Image is still in React state, just won't persist across reloads
            }
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
      } catch (error: any) {
        console.error('[DesignPage] Error checking furniture removal status:', error);
        // Check if it's a 404 error (job not found - server may have restarted)
        // Also check for axios error structure
        const is404 = error?.response?.status === 404 ||
                      error?.status === 404 ||
                      error?.message?.includes('404') ||
                      error?.message?.includes('not found') ||
                      error?.response?.data?.detail?.includes('not found');
        if (is404) {
          console.log('[DesignPage] Job not found (404) - server may have restarted, clearing stale job ID');
          sessionStorage.removeItem('furnitureRemovalJobId');
          setIsProcessingFurniture(false);
          setProcessingStatus('');
          clearInterval(pollInterval);
          return;
        }
        // Stop polling after 3 consecutive errors for other errors
        // This includes network errors or any other failures
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

  // Handle product recommendation from chat (supports both legacy and category-based formats)
  const handleProductRecommendations = (response: {
    products?: any[];
    recommended_products?: any[];
    selected_categories?: any[];
    products_by_category?: Record<string, any[]>;
    total_budget?: number | null;
    conversation_state?: string;
    follow_up_question?: string | null;
  }) => {
    console.log('[DesignPage] handleProductRecommendations called with response:', response);

    // Check if we have category-based data (new format)
    if (response.selected_categories && response.products_by_category) {
      console.log('[DesignPage] Using category-based format');
      console.log('[DesignPage] Categories:', response.selected_categories);
      console.log('[DesignPage] Products by category:', Object.keys(response.products_by_category));

      setSelectedCategories(response.selected_categories);
      setProductsByCategory(response.products_by_category);
      setTotalBudget(response.total_budget || null);

      // Also set legacy productRecommendations for backward compatibility (flatten all products)
      const allProducts = Object.values(response.products_by_category).flat();
      setProductRecommendations(allProducts);
      console.log('[DesignPage] Total products across all categories:', allProducts.length);
    } else if (response.products && response.products.length > 0) {
      // Legacy format - flat list of products
      console.log('[DesignPage] Using legacy format with', response.products.length, 'products');
      setProductRecommendations(response.products);
      // Clear category-based state
      setSelectedCategories(null);
      setProductsByCategory(null);
      setTotalBudget(null);
    }

    // Auto-switch to products tab on mobile
    if (window.innerWidth < 768) {
      setActiveTab('products');
    }
  };

  // Extract product type from product name (used for categorization/display)
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
    if (name.includes('planter') || name.includes('plant pot') || name.includes('flower pot') || name.includes(' pot')) return 'planter';
    // Wall art - paintings, canvas, wall hangings (goes ON walls)
    if (name.includes('wall art') || name.includes('wall decor') || name.includes('painting') ||
        name.includes('canvas art') || name.includes('wall hanging') || name.includes('wall panel') ||
        name.includes('artwork') || name.includes('print') || name.includes('poster') ||
        name.includes('wall plate') || name.includes('wall clock')) return 'wall_art';
    // Decor items - these go ON tables/surfaces (UNLIMITED - multiple allowed)
    if (name.includes('vase') || name.includes('flower bunch') || name.includes('flower arrangement') || name.includes('artificial flower')) return 'vase';
    // Sculptures - 3D decorative items that sit on surfaces (NOT wall art)
    if (name.includes('sculpture') || name.includes('statue') || name.includes('figurine') || name.includes('bust')) return 'sculpture';
    if (name.includes('candle') || name.includes('candle holder') || name.includes('candlestick')) return 'candle';
    if (name.includes('picture frame') || name.includes('photo frame')) return 'picture_frame';
    if (name.includes('decor') || name.includes('decorative') || name.includes('ornament') || name.includes('accent piece')) return 'decor';
    if (name.includes('cushion') || name.includes('pillow') || name.includes('throw pillow')) return 'cushion';
    if (name.includes('throw') || name.includes('blanket')) return 'throw';
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

    // Check if product already exists in canvas (by ID)
    const existingIndex = canvasProducts.findIndex(
      (p) => p.id.toString() === product.id.toString()
    );

    if (existingIndex >= 0) {
      // Product exists - increment quantity
      const updatedProducts = [...canvasProducts];
      const currentQuantity = updatedProducts[existingIndex].quantity || 1;
      updatedProducts[existingIndex] = {
        ...updatedProducts[existingIndex],
        quantity: currentQuantity + 1,
      };
      setCanvasProducts(updatedProducts);
      console.log('[DesignPage] Incremented quantity for:', product.name, 'to', currentQuantity + 1);
    } else {
      // New product - add with quantity: 1
      setCanvasProducts([...canvasProducts, { ...productWithType, quantity: 1 }]);
      console.log('[DesignPage] Added new product to canvas with quantity 1');
    }

    // Sync with unified canvas
    canvas.addProduct(productWithType);

    // Auto-switch to canvas tab on mobile
    if (window.innerWidth < 768) {
      setActiveTab('canvas');
    }
  };

  // Handle remove from canvas (decrements quantity, removes when qty = 0)
  const handleRemoveFromCanvas = (productId: string, removeAll: boolean = false) => {
    const existingIndex = canvasProducts.findIndex(
      (p) => p.id.toString() === productId.toString()
    );

    if (existingIndex < 0) return;

    const product = canvasProducts[existingIndex];
    const currentQuantity = product.quantity || 1;

    if (removeAll || currentQuantity <= 1) {
      // Remove completely
      setCanvasProducts(canvasProducts.filter((p) => p.id.toString() !== productId.toString()));
      console.log('[DesignPage] Removed product from canvas:', product.name);
    } else {
      // Decrement quantity
      const updatedProducts = [...canvasProducts];
      updatedProducts[existingIndex] = {
        ...updatedProducts[existingIndex],
        quantity: currentQuantity - 1,
      };
      setCanvasProducts(updatedProducts);
      console.log('[DesignPage] Decremented quantity for:', product.name, 'to', currentQuantity - 1);
    }

    // Sync with unified canvas
    canvas.removeProduct(productId, removeAll);
  };

  // Handle increment quantity (used by CanvasPanel +/- controls)
  const handleIncrementQuantity = (productId: string) => {
    const existingIndex = canvasProducts.findIndex(
      (p) => p.id.toString() === productId.toString()
    );

    if (existingIndex < 0) return;

    const updatedProducts = [...canvasProducts];
    const currentQuantity = updatedProducts[existingIndex].quantity || 1;
    updatedProducts[existingIndex] = {
      ...updatedProducts[existingIndex],
      quantity: currentQuantity + 1,
    };
    setCanvasProducts(updatedProducts);

    // Sync with unified canvas
    canvas.updateQuantity(`product-${productId}`, 1);
  };

  // Handle clear canvas
  const handleClearCanvas = () => {
    setCanvasProducts([]);
    canvas.clearAll();
  };

  // Handle room image upload with furniture removal
  // If isAlreadyProcessed is true, skip furniture removal (used for previously uploaded rooms)
  const handleRoomImageUpload = async (imageData: string, isAlreadyProcessed: boolean = false) => {
    try {
      console.log('[DesignPage] Starting room image upload...', { isAlreadyProcessed });

      // If the room is already processed (from previous rooms), skip furniture removal
      if (isAlreadyProcessed) {
        console.log('[DesignPage] Room already processed, skipping furniture removal');
        setRoomImage(imageData);
        setCleanRoomImage(imageData);
        // Store in session storage for persistence
        try {
          sessionStorage.setItem('roomImage', imageData);
          sessionStorage.setItem('cleanRoomImage', imageData);
        } catch (e) {
          console.warn('[DesignPage] Could not store room image in sessionStorage');
        }
        return;
      }

      // IMPORTANT: Clear any existing furniture removal job to prevent infinite loop
      const existingJobId = sessionStorage.getItem('furnitureRemovalJobId');
      if (existingJobId) {
        console.log('[DesignPage] Clearing existing furniture removal job:', existingJobId);
        sessionStorage.removeItem('furnitureRemovalJobId');
      }

      // CRITICAL: Set room image IMMEDIATELY so the processing overlay shows right away
      // Previously this was set after API calls, causing the "Upload Your Room" screen to linger for 10+ seconds
      setRoomImage(imageData);
      setCleanRoomImage(imageData);
      setIsProcessingFurniture(true);
      setProcessingStatus('Analyzing room...');

      // OPTIMIZATION: Upload image and perform room analysis FIRST
      // This caches room analysis (camera view, dimensions, furniture detection) in the Project table
      // Saves 4-13 seconds per subsequent visualization by avoiding redundant Gemini calls
      if (projectId) {
        try {
          console.log('[DesignPage] Uploading room image for analysis with project_id:', projectId);
          const uploadResponse = await imageAPI.uploadRoomImageFromBase64(imageData, projectId);
          console.log('[DesignPage] Room analysis complete:', uploadResponse.room_analysis?.room_type);
        } catch (uploadError) {
          // Log but don't fail - room analysis caching is an optimization, not critical
          console.warn('[DesignPage] Room analysis upload failed (non-critical):', uploadError);
        }
      }

      setProcessingStatus('Removing existing furniture from your room...');

      // Start async furniture removal
      const response = await startFurnitureRemoval(imageData);

      // Store job ID and image in sessionStorage with quota handling
      try {
        // Clear old images first to free up space
        sessionStorage.removeItem('cleanRoomImage');
        sessionStorage.removeItem('curatedRoomImage');
        sessionStorage.removeItem('curatedVisualizationImage');

        sessionStorage.setItem('furnitureRemovalJobId', response.job_id);
        // Store uploaded image for display during furniture removal process
        sessionStorage.setItem('roomImage', imageData);
      } catch (storageError) {
        // If quota exceeded, clear everything and try again
        console.warn('[DesignPage] SessionStorage quota exceeded, clearing and retrying...');
        // Preserve the design access bypass key before clearing
        const hadDesignAccess = sessionStorage.getItem('designAccessGranted');
        sessionStorage.clear();
        if (hadDesignAccess) {
          sessionStorage.setItem('designAccessGranted', hadDesignAccess);
        }
        sessionStorage.setItem('furnitureRemovalJobId', response.job_id);
        // Don't store the image if it's too large - the API already has it
        console.log('[DesignPage] Image too large for sessionStorage, will fetch from API after reload');
      }

      // Persist canvas products before page reload so they survive the reload
      try {
        if (canvasProducts.length > 0) {
          sessionStorage.setItem('persistedCanvasProducts', JSON.stringify(canvasProducts));
          console.log('[DesignPage] Persisted', canvasProducts.length, 'canvas products before reload');
        }
      } catch (e) {
        console.warn('[DesignPage] Could not persist canvas products due to storage quota');
      }

      console.log('[DesignPage] Furniture removal started:', response);

      // Room image already set at the start of this function for immediate UI feedback

      // Start polling for furniture removal completion without page reload
      const pollForCompletion = async () => {
        let pollAttempts = 0;
        const MAX_POLL_ATTEMPTS = 150; // 150 attempts * 2 seconds = 5 minutes max (room analysis + perspective transform + furniture removal)

        const poll = async () => {
          pollAttempts++;

          if (pollAttempts > MAX_POLL_ATTEMPTS) {
            console.error('[DesignPage] Furniture removal timed out after 5 minutes');
            setIsProcessingFurniture(false);
            setProcessingStatus('');
            sessionStorage.removeItem('furnitureRemovalJobId');
            return;
          }

          try {
            const status = await checkFurnitureRemovalStatus(response.job_id);
            console.log('[DesignPage] Furniture removal status:', status);

            if (status.status === 'completed' && status.image) {
              console.log('[DesignPage] Furniture removal completed, image length:', status.image.length);
              console.log('[DesignPage] Image starts with data:', status.image.startsWith('data:'));
              console.log('[DesignPage] Image preview:', status.image.substring(0, 50));

              // Ensure image has proper data URL format
              let imageToSet = status.image;
              if (!status.image.startsWith('data:')) {
                console.log('[DesignPage] Adding data URL prefix to image');
                imageToSet = `data:image/png;base64,${status.image}`;
              }

              setRoomImage(imageToSet);
              setCleanRoomImage(imageToSet);
              // Save to sessionStorage with quota handling
              try {
                // Clear old images first to free up space
                sessionStorage.removeItem('cleanRoomImage');
                sessionStorage.removeItem('curatedRoomImage');
                sessionStorage.removeItem('curatedVisualizationImage');
                sessionStorage.setItem('cleanRoomImage', imageToSet);
                sessionStorage.setItem('roomImage', imageToSet);
                console.log('[DesignPage] Image saved to sessionStorage, length:', imageToSet.length);
              } catch (storageError) {
                console.warn('[DesignPage] SessionStorage quota exceeded, image stored in memory only:', storageError);
              }
              setIsProcessingFurniture(false);
              setProcessingStatus('');
              sessionStorage.removeItem('furnitureRemovalJobId');
            } else if (status.status === 'failed') {
              console.log('[DesignPage] Furniture removal failed, using original image');
              setIsProcessingFurniture(false);
              setProcessingStatus('');
              sessionStorage.removeItem('furnitureRemovalJobId');
            } else {
              // Still processing, poll again
              setProcessingStatus('Processing your room image...');
              setTimeout(poll, 2000);
            }
          } catch (error) {
            console.error('[DesignPage] Error checking status:', error);
            setIsProcessingFurniture(false);
            setProcessingStatus('');
            sessionStorage.removeItem('furnitureRemovalJobId');
          }
        };

        poll();
      };

      pollForCompletion();
    } catch (error) {
      console.error('[DesignPage] Error starting furniture removal:', error);
      // On error, use original image
      setRoomImage(imageData);
      setCleanRoomImage(imageData);
      try {
        sessionStorage.setItem('roomImage', imageData);
      } catch (storageError) {
        console.warn('[DesignPage] Could not store image in sessionStorage:', storageError);
      }
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
      {/* Session Invalidated Banner - shows when logged out from another tab */}
      {sessionInvalidatedExternally && (
        <div className="bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-700 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                Your session changed in another tab
              </p>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                You were logged out or logged in as a different user. Please save your work locally if needed.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push('/login')}
              className="px-3 py-1.5 text-xs font-medium text-amber-800 dark:text-amber-200 bg-amber-100 dark:bg-amber-800/50 hover:bg-amber-200 dark:hover:bg-amber-800 rounded-md transition-colors"
            >
              Go to Login
            </button>
            <button
              onClick={clearExternalInvalidation}
              className="p-1.5 text-amber-600 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-200 transition-colors"
              title="Dismiss"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-neutral-600 to-neutral-700 rounded-lg"></div>
          <div>
            {/* Editable Project Name */}
            {isAuthenticated && projectId ? (
              isEditingName ? (
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => {
                    setProjectName(e.target.value);
                    setSaveStatus('unsaved'); // Mark as unsaved when name changes
                  }}
                  onBlur={() => setIsEditingName(false)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') setIsEditingName(false);
                    if (e.key === 'Escape') setIsEditingName(false);
                  }}
                  autoFocus
                  className="text-xl font-bold text-neutral-900 dark:text-white bg-transparent border-b-2 border-neutral-500 outline-none px-1"
                />
              ) : (
                <h1
                  onClick={() => setIsEditingName(true)}
                  className="text-xl font-bold text-neutral-900 dark:text-white cursor-pointer hover:text-neutral-700 dark:hover:text-neutral-300 flex items-center gap-2"
                  title="Click to edit project name"
                >
                  {projectName || 'Untitled Project'}
                  <svg className="w-4 h-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </h1>
              )
            ) : (
              <h1 className="text-xl font-bold text-neutral-900 dark:text-white">
                Omnishop Design Studio
              </h1>
            )}
            {/* Save Status Indicator */}
            {isAuthenticated && projectId && (
              <div className="flex items-center gap-1.5 text-xs">
                {saveStatus === 'saved' && (
                  <>
                    <div className="w-2 h-2 rounded-full bg-neutral-600" />
                    <span className="text-neutral-600 dark:text-neutral-400">
                      Saved {lastSavedAt && `at ${lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
                    </span>
                  </>
                )}
                {saveStatus === 'saving' && (
                  <>
                    <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                    <span className="text-yellow-600 dark:text-yellow-400">Saving...</span>
                  </>
                )}
                {saveStatus === 'unsaved' && (
                  <>
                    <div className="w-2 h-2 rounded-full bg-orange-500" />
                    <span className="text-orange-600 dark:text-orange-400">Unsaved changes</span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Save Button */}
          {isAuthenticated && projectId && (
            <button
              onClick={saveProject}
              disabled={saveStatus === 'saving' || saveStatus === 'saved'}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                saveStatus === 'unsaved'
                  ? 'bg-neutral-800 hover:bg-neutral-900 text-white shadow-md'
                  : saveStatus === 'saving'
                  ? 'bg-neutral-200 dark:bg-neutral-700 text-neutral-500 dark:text-neutral-400 cursor-not-allowed'
                  : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-500 dark:text-neutral-400'
              }`}
            >
              {saveStatus === 'saving' ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Saving...
                </>
              ) : saveStatus === 'saved' ? (
                <>
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  Saved
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                  Save
                </>
              )}
            </button>
          )}
          {/* Publish Button (Curator tier only) */}
          {isAuthenticated && canPublishLooks(user) && initialVisualizationImage && (
            <button
              onClick={() => setShowPublishModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all bg-green-600 hover:bg-green-700 text-white shadow-md"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              Publish Look
            </button>
          )}
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

      {/* Furniture removal overlay is now shown on the room image in CanvasPanel */}

      {/* Mobile Tab Navigation */}
      <div className="md:hidden bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 px-4">
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'chat'
                ? 'text-neutral-800 dark:text-neutral-200'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
            }`}
          >
            Chat
            {activeTab === 'chat' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-800 dark:bg-neutral-600"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab('products')}
            className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'products'
                ? 'text-neutral-800 dark:text-neutral-200'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
            }`}
          >
            Products
            {productRecommendations.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-neutral-800 rounded-full">
                {productRecommendations.length}
              </span>
            )}
            {activeTab === 'products' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-800 dark:bg-neutral-600"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab('canvas')}
            className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'canvas'
                ? 'text-neutral-800 dark:text-neutral-200'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
            }`}
          >
            Canvas
            {canvasProducts.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-neutral-800 rounded-full">
                {canvasProducts.length}
              </span>
            )}
            {activeTab === 'canvas' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-800 dark:bg-neutral-600"></div>
            )}
          </button>
        </div>
      </div>

      {/* Three-Panel Layout */}
      <div className="flex-1 overflow-hidden">
        {/* Desktop: Resizable three-panel layout */}
        <div className="hidden md:block h-full">
          <ResizablePanelLayout
            chatPanel={
              <div className="flex flex-col h-full">
                {/* Top Mode Toggle: Search vs AI Stylist */}
                <div className="px-4 py-2 border-b border-neutral-200 dark:border-neutral-700 flex-shrink-0 flex justify-center">
                  <ModeToggle mode={searchMode} onModeChange={setSearchMode} />
                </div>

                {/* Sub Mode Toggle: Furniture & Decor vs Walls - only when Search is selected */}
                {searchMode === 'search' && (
                  <div className="px-4 py-2 border-b border-neutral-200 dark:border-neutral-700 flex-shrink-0 flex justify-center">
                    <SubModeToggle subMode={searchSubMode} onSubModeChange={setSearchSubMode} />
                  </div>
                )}

                {/* Furniture & Decor Search Panel - visible when Search + Furniture sub-mode */}
                {!isMobile && searchMode === 'search' && searchSubMode === 'furniture' && (
                  <div className="flex-1 min-h-0">
                    <KeywordSearchPanel
                      ref={keywordSearchRef}
                      onAddProduct={handleAddToCanvas}
                      canvasProducts={canvasProducts.map(p => ({ id: p.id, quantity: p.quantity }))}
                      showSearchInput={true}
                      compact={false}
                      showResultsInline={false}
                      onSearchResults={setKeywordSearchResults}
                      filters={searchFilters}
                      onFiltersChange={setSearchFilters}
                      showFilters={showSearchFilters}
                      onShowFiltersChange={setShowSearchFilters}
                    />
                  </div>
                )}

                {/* Wall Filter Panel - visible when Search + Walls sub-mode */}
                {searchMode === 'search' && searchSubMode === 'walls' && (
                  <div className="flex-1 min-h-0 overflow-hidden">
                    <WallFilterPanel
                      wallType={wallType}
                      onWallTypeChange={setWallType}
                      selectedFamilies={selectedFamilies}
                      onToggleFamily={toggleFamily}
                      selectedBrands={selectedBrands}
                      availableBrands={availableTextureBrands}
                      onToggleBrand={toggleBrand}
                      onClearFilters={clearAllFilters}
                      hasActiveFilters={hasActiveFilters}
                    />
                  </div>
                )}

                {/* AI Chat Panel - Only visible in AI mode */}
                {searchMode === 'ai' && (
                  <div className="relative flex-1 overflow-hidden border-t border-neutral-200 dark:border-neutral-700">
                    <ChatPanel
                      key={projectId || 'new-project'}
                      onProductRecommendations={handleProductRecommendations}
                      roomImage={roomImage}
                      selectedStores={selectedStores}
                      initialSessionId={chatSessionId}
                      onSessionIdChange={setChatSessionId}
                    />
                    {/* Loading overlay - shows on top while project is loading */}
                    {!projectLoaded && (
                      <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-neutral-800"></div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            }
            productsPanel={
              <ProductDiscoveryPanel
                products={productRecommendations}
                onAddToCanvas={handleAddToCanvas}
                canvasProducts={canvasProducts}
                selectedCategories={selectedCategories}
                productsByCategory={productsByCategory}
                enableModeToggle={false}
                totalBudget={totalBudget}
                sessionId={chatSessionId}
                isKeywordSearchMode={searchMode === 'search' && searchSubMode === 'furniture'}
                keywordSearchResults={keywordSearchResults}
                onLoadMoreKeywordResults={() => keywordSearchRef.current?.loadMore()}
                // Wall mode props
                searchSubMode={searchSubMode}
                wallType={wallType}
                colorFamilyFilter={selectedFamilies}
                textureBrandFilter={selectedBrands}
                textures={textures}
                texturesLoading={isLoadingTextures}
                texturesError={null}
                selectedWallColor={selectedWallColor}
                canvasWallColor={canvasWallColor}
                onSelectWallColor={handleSelectWallColor}
                onAddWallColorToCanvas={handleAddWallColorToCanvasUnified}
                selectedTextureVariant={selectedTextureVariant}
                selectedTexture={selectedTexture}
                canvasTextureVariant={canvasTextureVariant}
                canvasTexture={canvasTexture}
                onSelectTextureVariant={handleSelectTextureVariant}
                onAddTextureToCanvas={handleAddTextureToCanvasUnified}
                onRemoveWallFromCanvas={wallType === 'color' ? removeWallColorFromCanvasUnified : removeTextureFromCanvasUnified}
              />
            }
            canvasPanel={
              <CanvasPanel
                products={canvasProducts}
                roomImage={roomImage}
                cleanRoomImage={cleanRoomImage}
                onRemoveProduct={handleRemoveFromCanvas}
                onIncrementQuantity={handleIncrementQuantity}
                onClearCanvas={handleClearCanvas}
                onRoomImageUpload={handleRoomImageUpload}
                onSetProducts={setCanvasProducts}
                onViewProductDetails={setSelectedProduct}
                initialVisualizationImage={initialVisualizationImage}
                initialVisualizationHistory={visualizationHistory}
                onVisualizationHistoryChange={setVisualizationHistory}
                onVisualizationImageChange={setInitialVisualizationImage}
                isProcessingFurniture={isProcessingFurniture}
                projectId={projectId}
                canvasWallColor={canvasWallColor}
                onRemoveWallColor={removeWallColorFromCanvasUnified}
                onSetWallColor={setCanvasWallColor}
                canvasTexture={canvasTexture}
                canvasTextureVariant={canvasTextureVariant}
                onRemoveTexture={removeTextureFromCanvasUnified}
                canvasItems={canvas.items}
                onSetCanvasItems={handleSetCanvasItems}
                onRemoveCanvasItem={canvas.removeItem}
                onUpdateCanvasItemQuantity={canvas.updateQuantity}
              />
            }
          />
        </div>

        {/* Mobile & Tablet: Single panel with tabs */}
        <div className="md:hidden h-full">
          <div className={`h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
            <div className="flex flex-col h-full">
              {/* Top Mode Toggle: Search vs AI Stylist */}
              <div className="px-4 py-2 border-b border-neutral-200 dark:border-neutral-700 flex-shrink-0 flex justify-center">
                <ModeToggle mode={searchMode} onModeChange={setSearchMode} />
              </div>

              {/* Sub Mode Toggle: Furniture & Decor vs Walls - only when Search is selected */}
              {searchMode === 'search' && (
                <div className="px-4 py-2 border-b border-neutral-200 dark:border-neutral-700 flex-shrink-0 flex justify-center">
                  <SubModeToggle subMode={searchSubMode} onSubModeChange={setSearchSubMode} />
                </div>
              )}

              {/* Furniture & Decor Search Panel - visible when Search + Furniture sub-mode on mobile */}
              {isMobile && searchMode === 'search' && searchSubMode === 'furniture' && (
                <div className="flex-1 min-h-0">
                  <KeywordSearchPanel
                    ref={keywordSearchRef}
                    onAddProduct={handleAddToCanvas}
                    canvasProducts={canvasProducts.map(p => ({ id: p.id, quantity: p.quantity }))}
                    showSearchInput={true}
                    compact={true}
                    showResultsInline={false}
                    onSearchResults={setKeywordSearchResults}
                    filters={searchFilters}
                    onFiltersChange={setSearchFilters}
                    showFilters={showSearchFilters}
                    onShowFiltersChange={setShowSearchFilters}
                  />
                </div>
              )}

              {/* Wall Filter Panel - visible when Search + Walls sub-mode on mobile */}
              {searchMode === 'search' && searchSubMode === 'walls' && (
                <div className="flex-1 min-h-0 overflow-hidden">
                  <WallFilterPanel
                    wallType={wallType}
                    onWallTypeChange={setWallType}
                    selectedFamilies={selectedFamilies}
                    onToggleFamily={toggleFamily}
                    selectedBrands={selectedBrands}
                    availableBrands={availableTextureBrands}
                    onToggleBrand={toggleBrand}
                    onClearFilters={clearAllFilters}
                    hasActiveFilters={hasActiveFilters}
                    compact={true}
                  />
                </div>
              )}

              {/* AI Chat Panel - Only visible in AI mode */}
              {searchMode === 'ai' && (
                <div className="relative flex-1 overflow-hidden border-t border-neutral-200 dark:border-neutral-700">
                  <ChatPanel
                    key={projectId || 'new-project'}
                    onProductRecommendations={handleProductRecommendations}
                    roomImage={roomImage}
                    selectedStores={selectedStores}
                    initialSessionId={chatSessionId}
                    onSessionIdChange={setChatSessionId}
                  />
                  {/* Loading overlay - shows on top while project is loading */}
                  {!projectLoaded && (
                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-neutral-800"></div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className={`h-full ${activeTab === 'products' ? 'block' : 'hidden'}`}>
            <ProductDiscoveryPanel
              products={productRecommendations}
              onAddToCanvas={handleAddToCanvas}
              canvasProducts={canvasProducts}
              selectedCategories={selectedCategories}
              productsByCategory={productsByCategory}
              totalBudget={totalBudget}
              sessionId={chatSessionId}
              enableModeToggle={false}
              isKeywordSearchMode={searchMode === 'search' && searchSubMode === 'furniture'}
              keywordSearchResults={keywordSearchResults}
              onLoadMoreKeywordResults={() => keywordSearchRef.current?.loadMore()}
              // Wall mode props
              searchSubMode={searchSubMode}
              wallType={wallType}
              colorFamilyFilter={selectedFamilies}
              textureBrandFilter={selectedBrands}
              textures={textures}
              texturesLoading={isLoadingTextures}
              texturesError={null}
              selectedWallColor={selectedWallColor}
              canvasWallColor={canvasWallColor}
              onSelectWallColor={handleSelectWallColor}
              onAddWallColorToCanvas={handleAddWallColorToCanvasUnified}
              selectedTextureVariant={selectedTextureVariant}
              selectedTexture={selectedTexture}
              canvasTextureVariant={canvasTextureVariant}
              canvasTexture={canvasTexture}
              onSelectTextureVariant={handleSelectTextureVariant}
              onAddTextureToCanvas={handleAddTextureToCanvasUnified}
              onRemoveWallFromCanvas={wallType === 'color' ? removeWallColorFromCanvasUnified : removeTextureFromCanvasUnified}
            />
          </div>
          <div className={`h-full ${activeTab === 'canvas' ? 'block' : 'hidden'}`}>
            <CanvasPanel
              products={canvasProducts}
              roomImage={roomImage}
              cleanRoomImage={cleanRoomImage}
              onRemoveProduct={handleRemoveFromCanvas}
              onIncrementQuantity={handleIncrementQuantity}
              onClearCanvas={handleClearCanvas}
              onRoomImageUpload={handleRoomImageUpload}
              onSetProducts={setCanvasProducts}
              onViewProductDetails={setSelectedProduct}
              initialVisualizationImage={initialVisualizationImage}
              initialVisualizationHistory={visualizationHistory}
              onVisualizationHistoryChange={setVisualizationHistory}
              onVisualizationImageChange={setInitialVisualizationImage}
              isProcessingFurniture={isProcessingFurniture}
              projectId={projectId}
              canvasWallColor={canvasWallColor}
              onRemoveWallColor={removeWallColorFromCanvasUnified}
              onSetWallColor={setCanvasWallColor}
              canvasTexture={canvasTexture}
              canvasTextureVariant={canvasTextureVariant}
              onRemoveTexture={removeTextureFromCanvasUnified}
              canvasItems={canvas.items}
              onSetCanvasItems={handleSetCanvasItems}
              onRemoveCanvasItem={canvas.removeItem}
              onUpdateCanvasItemQuantity={canvas.updateQuantity}
            />
          </div>
        </div>
      </div>

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          isOpen={true}
          onClose={() => setSelectedProduct(null)}
          onAddToCanvas={() => {
            handleAddToCanvas(selectedProduct);
            setSelectedProduct(null);
          }}
          inCanvas={canvasProducts.some(p => p.id?.toString() === selectedProduct.id?.toString())}
          canvasQuantity={canvasProducts.find(p => p.id?.toString() === selectedProduct.id?.toString())?.quantity || 0}
        />
      )}

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
                  className="flex-1 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 py-2 px-4 rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-700 transition font-medium"
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
                    <span className="text-neutral-800 dark:text-neutral-200 font-semibold">
                      No stores selected - will search all {availableStores.length} stores
                    </span>
                  ) : (
                    <span>
                      Selected <span className="font-semibold text-neutral-800 dark:text-neutral-200">{selectedStores.length}</span> of {availableStores.length} stores
                    </span>
                  )}
                </p>
              </div>

              {/* Store Categories */}
              <div className="space-y-6">
                {storeCategories.map((category) => (
                  <div key={category.tier}>
                    {/* Category Header */}
                    <div className="flex items-center gap-2 mb-3">
                      <h4 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">
                        {category.label}
                      </h4>
                      <span className="text-xs text-neutral-500 dark:text-neutral-400">
                        ({category.stores.length} stores)
                      </span>
                    </div>
                    {/* Store Grid for this category */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {category.stores.map((store) => {
                        const isSelected = selectedStores.includes(store.name);
                        return (
                          <button
                            key={store.name}
                            onClick={() => {
                              const updated = isSelected
                                ? selectedStores.filter((s) => s !== store.name)
                                : [...selectedStores, store.name];
                              handleStoreSelectionChange(updated);
                            }}
                            className={`
                              p-4 rounded-lg border-2 transition-all duration-200
                              ${
                                isSelected
                                  ? 'border-neutral-800 bg-neutral-100 dark:bg-neutral-800/20 text-neutral-700 dark:text-neutral-300 shadow-md'
                                  : 'border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 hover:border-neutral-400 dark:hover:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-neutral-800/10'
                              }
                            `}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-left">
                                {store.display_name}
                              </span>
                              {isSelected && (
                                <svg
                                  className="w-5 h-5 text-neutral-800 dark:text-neutral-200 flex-shrink-0"
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
                ))}
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
                  className="flex-1 bg-neutral-800 text-white py-2.5 px-4 rounded-lg hover:bg-neutral-900 transition font-medium shadow-lg"
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

      {/* Publish Modal (Curator tier only) */}
      {showPublishModal && canPublishLooks(user) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-neutral-800 rounded-xl max-w-lg w-full shadow-2xl">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-700 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">
                Publish to Curated Gallery
              </h2>
              <button
                onClick={() => {
                  setShowPublishModal(false);
                  setPublishSuccess(false);
                }}
                className="p-1 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6">
              {publishSuccess ? (
                <div className="text-center py-8">
                  <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-medium text-neutral-800 dark:text-neutral-200 mb-2">
                    Look Published Successfully!
                  </h3>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    Your look has been submitted for review and will appear in the curated gallery soon.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Preview */}
                  {initialVisualizationImage && (
                    <div className="aspect-video rounded-lg overflow-hidden bg-neutral-100 dark:bg-neutral-700">
                      <img
                        src={initialVisualizationImage.startsWith('data:') ? initialVisualizationImage : `data:image/png;base64,${initialVisualizationImage}`}
                        alt="Preview"
                        className="w-full h-full object-cover"
                      />
                    </div>
                  )}

                  {/* Title */}
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                      Title *
                    </label>
                    <input
                      type="text"
                      value={publishTitle}
                      onChange={(e) => setPublishTitle(e.target.value)}
                      placeholder="e.g., Modern Minimalist Living Room"
                      className="w-full px-4 py-2.5 border border-neutral-200 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 placeholder-neutral-400 dark:placeholder-neutral-500 focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all"
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                      Description
                    </label>
                    <textarea
                      value={publishDescription}
                      onChange={(e) => setPublishDescription(e.target.value)}
                      placeholder="Describe your design..."
                      rows={2}
                      className="w-full px-4 py-2.5 border border-neutral-200 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 placeholder-neutral-400 dark:placeholder-neutral-500 focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all resize-none"
                    />
                  </div>

                  {/* Room Type */}
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                      Room Type *
                    </label>
                    <select
                      value={publishRoomType}
                      onChange={(e) => setPublishRoomType(e.target.value as 'living_room' | 'bedroom')}
                      className="w-full px-4 py-2.5 border border-neutral-200 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all"
                    >
                      <option value="living_room">Living Room</option>
                      <option value="bedroom">Bedroom</option>
                    </select>
                  </div>

                  {/* Style Labels */}
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                      Style Labels (select multiple)
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {STYLE_LABEL_OPTIONS.map((style) => (
                        <button
                          key={style.value}
                          type="button"
                          onClick={() => {
                            setPublishStyleLabels(prev =>
                              prev.includes(style.value)
                                ? prev.filter(s => s !== style.value)
                                : [...prev, style.value]
                            );
                          }}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                            publishStyleLabels.includes(style.value)
                              ? 'bg-green-600 text-white'
                              : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-600'
                          }`}
                        >
                          {style.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Budget Tier (auto-calculated) */}
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5">
                      Budget Tier (auto-calculated)
                    </label>
                    <div className="px-4 py-2.5 bg-neutral-100 dark:bg-neutral-700 rounded-lg text-neutral-600 dark:text-neutral-300 text-sm">
                      {(() => {
                        const totalPrice = canvasProducts.reduce((sum, p) => sum + (p.price || 0), 0);
                        const tier = calculateBudgetTier(totalPrice);
                        return `${tier.label} (${tier.range})`;
                      })()}
                    </div>
                  </div>

                  {/* Info note */}
                  <div className="flex items-start gap-2 p-3 bg-neutral-50 dark:bg-neutral-700/50 rounded-lg">
                    <svg className="w-5 h-5 text-neutral-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400">
                      Your look will be reviewed before appearing in the public gallery. This includes the visualization, room image, and product selections.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            {!publishSuccess && (
              <div className="px-6 py-4 border-t border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 rounded-b-xl">
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowPublishModal(false)}
                    className="flex-1 bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 py-2.5 px-4 rounded-lg hover:bg-neutral-300 dark:hover:bg-neutral-600 transition font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handlePublishLook}
                    disabled={isPublishing || !publishTitle.trim()}
                    className="flex-1 bg-green-600 text-white py-2.5 px-4 rounded-lg hover:bg-green-700 transition font-medium shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isPublishing ? (
                      <>
                        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Publishing...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Publish Look
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DesignPage() {
  return (
    <ProtectedRoute
      requiredRole="user"
      requiredTiers={['advanced', 'curator']}
      allowAdmin={true}
      bypassTierWithSessionKeys={['curatedRoomImage', 'curatedVisualizationImage', 'preselectedProducts', 'designAccessGranted']}
    >
      <DesignPageContent />
    </ProtectedRoute>
  );
}
