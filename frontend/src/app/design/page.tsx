'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import ChatPanel from '@/components/panels/ChatPanel';
import ProductDiscoveryPanel from '@/components/panels/ProductDiscoveryPanel';
import CanvasPanel from '@/components/panels/CanvasPanel';
import { checkFurnitureRemovalStatus, startFurnitureRemoval, getAvailableStores, projectsAPI, restoreDesignStateFromRecovery } from '@/utils/api';
import { useAuth } from '@/contexts/AuthContext';
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

  // Furniture removal state
  const [isProcessingFurniture, setIsProcessingFurniture] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');

  // Store selection state
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [showStoreModal, setShowStoreModal] = useState(false);
  const [availableStores, setAvailableStores] = useState<string[]>([]);

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
  const [projectLoaded, setProjectLoaded] = useState(false); // Track when project data is loaded

  // Visualization history state (for undo/redo persistence)
  const [visualizationHistory, setVisualizationHistory] = useState<any[]>([]);

  // Chat session state (for restoring conversation history)
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);

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
      // Don't load any stored images - let the user start fresh
      return;
    }

    // Try to restore state from 401 recovery (session expiry during work)
    // This restores data that was saved to localStorage before redirect to login
    const wasRecovered = restoreDesignStateFromRecovery();
    if (wasRecovered) {
      console.log('[DesignPage] Restored design state from session recovery');
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

      // If not authenticated, mark as loaded immediately (guest mode)
      if (!isAuthenticated) {
        console.log('[DesignPage] No project to load (guest mode)');
        setProjectLoaded(true);
        return;
      }

      // If authenticated but no project ID, auto-create a new project
      if (!urlProjectId) {
        console.log('[DesignPage] Authenticated user without projectId - auto-creating new project');

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

        try {
          const newProject = await projectsAPI.create({
            name: `New Design ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`,
          });
          console.log('[DesignPage] Auto-created new project:', newProject.id, newProject.name);

          // Redirect to the same page with the new projectId and fresh param
          // Use fresh=1 to signal this is a brand new project
          router.replace(`/design?projectId=${newProject.id}&fresh=1`);
          return;
        } catch (error) {
          console.error('[DesignPage] Failed to auto-create project:', error);
          // Fall back to guest mode on error
          setProjectLoaded(true);
          return;
        }
      }

      try {
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

        // Check if this is a new project (no saved data yet)
        const isNewProject = !project.room_image && !project.visualization_image && !project.canvas_products;

        if (isNewProject) {
          // For new projects, use sessionStorage data (from curated looks or user upload)
          // The first useEffect already loaded curated look data
          // For user-uploaded room images, sessionStorage.roomImage should be set
          console.log('[DesignPage] New project detected, preserving sessionStorage data');

          // Set initial state for change detection (starts as "unsaved" so first save works)
          lastSaveDataRef.current = JSON.stringify({
            room_image: null,
            clean_room_image: null,
            visualization_image: null,
            canvas_products: null,
            visualization_history: null,
            chat_session_id: null,
          });
        } else {
          // Load existing project data
          // BUT FIRST: Check if there's recovered session data (from 401 redirect during save)
          // If recovery data exists, use it instead of backend data since it's more recent
          const recoveredRoomImage = sessionStorage.getItem('roomImage');
          const recoveredCleanRoomImage = sessionStorage.getItem('cleanRoomImage');
          const recoveredCanvasProducts = sessionStorage.getItem('persistedCanvasProducts');
          const hasRecoveredData = recoveredRoomImage || recoveredCanvasProducts;

          if (hasRecoveredData) {
            console.log('[DesignPage] Found recovered session data - using it instead of backend data');
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
          } else {
            // No recovered data - clear sessionStorage and load from backend as usual
            try {
              sessionStorage.removeItem('roomImage');
              sessionStorage.removeItem('cleanRoomImage');
              sessionStorage.removeItem('curatedRoomImage');
              sessionStorage.removeItem('curatedVisualizationImage');
            } catch (e) {
              // Ignore errors when clearing
            }

            if (project.room_image) {
              setRoomImage(project.room_image);
              // Try to cache in sessionStorage but don't fail if quota exceeded
              try {
                sessionStorage.setItem('roomImage', project.room_image);
              } catch (storageError) {
                console.warn('[DesignPage] Could not cache room image in sessionStorage (quota exceeded)');
              }
            }
            if (project.clean_room_image) {
              setCleanRoomImage(project.clean_room_image);
            }
            if (project.visualization_image) {
              setInitialVisualizationImage(project.visualization_image);
            }
            if (project.canvas_products) {
              try {
                const products = JSON.parse(project.canvas_products);
                setCanvasProducts(products);
                console.log('[DesignPage] Loaded', products.length, 'products from project');
              } catch (e) {
                console.error('[DesignPage] Failed to parse project canvas_products:', e);
              }
            }
            // Load visualization history for undo/redo
            if (project.visualization_history) {
              try {
                const history = JSON.parse(project.visualization_history);
                setVisualizationHistory(history);
                console.log('[DesignPage] Loaded', history.length, 'visualization history entries');
              } catch (e) {
                console.error('[DesignPage] Failed to parse visualization history:', e);
              }
            }
            // Load chat session ID for restoring conversation
            if (project.chat_session_id) {
              setChatSessionId(project.chat_session_id);
              console.log('[DesignPage] Loaded chat session ID:', project.chat_session_id);
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

    console.log('[DesignPage] Saving project with data:', {
      room_image: currentData.room_image ? `${currentData.room_image.length} chars` : null,
      visualization_image: currentData.visualization_image ? `${currentData.visualization_image.length} chars` : null,
      canvas_products: currentData.canvas_products ? `${currentData.canvas_products.length} chars` : null,
      chat_session_id: currentData.chat_session_id,
    });

    setSaveStatus('saving');
    const saveStartTime = Date.now();
    const MIN_SAVE_DISPLAY_MS = 400; // Minimum time to show "Saving..." for better UX

    try {
      await projectsAPI.update(projectId, {
        name: projectName || undefined,
        room_image: currentData.room_image || undefined,
        clean_room_image: currentData.clean_room_image || undefined,
        visualization_image: currentData.visualization_image || undefined,
        canvas_products: currentData.canvas_products || undefined,
        visualization_history: currentData.visualization_history || undefined,
        chat_session_id: currentData.chat_session_id || undefined,
      });

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

  // Track unsaved changes - SIMPLE APPROACH
  // Use a ref to track when the project was last saved, and compare against current state
  const isInitialLoadRef = useRef<boolean>(true);
  const lastSavedCanvasRef = useRef<string>('[]');
  const lastSavedRoomImageRef = useRef<string | null>(null);
  const lastSavedVizImageRef = useRef<string | null>(null);
  const lastSavedChatSessionRef = useRef<string | null>(null);

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
        sessionStorage.clear();
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

      // Set the uploaded image immediately so user sees it while furniture removal processes
      setRoomImage(imageData);
      setCleanRoomImage(imageData); // Use uploaded image as clean room initially

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
          <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-secondary-500 rounded-lg"></div>
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
                  className="text-xl font-bold text-neutral-900 dark:text-white bg-transparent border-b-2 border-primary-500 outline-none px-1"
                />
              ) : (
                <h1
                  onClick={() => setIsEditingName(true)}
                  className="text-xl font-bold text-neutral-900 dark:text-white cursor-pointer hover:text-primary-600 dark:hover:text-primary-400 flex items-center gap-2"
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
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-green-600 dark:text-green-400">
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
                  ? 'bg-primary-600 hover:bg-primary-700 text-white shadow-md'
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
            {projectLoaded ? (
              <ChatPanel
                onProductRecommendations={handleProductRecommendations}
                roomImage={roomImage}
                selectedStores={selectedStores}
                initialSessionId={chatSessionId}
                onSessionIdChange={setChatSessionId}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              </div>
            )}
          </div>

          {/* Panel 2: Products (35%) */}
          <div className="w-[35%] border-r border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 overflow-hidden">
            <ProductDiscoveryPanel
              products={productRecommendations}
              onAddToCanvas={handleAddToCanvas}
              canvasProducts={canvasProducts}
              selectedCategories={selectedCategories}
              productsByCategory={productsByCategory}
              totalBudget={totalBudget}
            />
          </div>

          {/* Panel 3: Canvas (40%) */}
          <div className="w-[40%] bg-white dark:bg-neutral-800 overflow-hidden">
            <CanvasPanel
              products={canvasProducts}
              roomImage={roomImage}
              cleanRoomImage={cleanRoomImage}
              onRemoveProduct={handleRemoveFromCanvas}
              onIncrementQuantity={handleIncrementQuantity}
              onClearCanvas={handleClearCanvas}
              onRoomImageUpload={handleRoomImageUpload}
              onSetProducts={setCanvasProducts}
              initialVisualizationImage={initialVisualizationImage}
              initialVisualizationHistory={visualizationHistory}
              onVisualizationHistoryChange={setVisualizationHistory}
              onVisualizationImageChange={setInitialVisualizationImage}
              isProcessingFurniture={isProcessingFurniture}
            />
          </div>
        </div>

        {/* Mobile & Tablet: Single panel with tabs */}
        <div className="lg:hidden h-full">
          <div className={`h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
            {projectLoaded ? (
              <ChatPanel
                onProductRecommendations={handleProductRecommendations}
                roomImage={roomImage}
                selectedStores={selectedStores}
                initialSessionId={chatSessionId}
                onSessionIdChange={setChatSessionId}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              </div>
            )}
          </div>
          <div className={`h-full ${activeTab === 'products' ? 'block' : 'hidden'}`}>
            <ProductDiscoveryPanel
              products={productRecommendations}
              onAddToCanvas={handleAddToCanvas}
              canvasProducts={canvasProducts}
              selectedCategories={selectedCategories}
              productsByCategory={productsByCategory}
              totalBudget={totalBudget}
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
              initialVisualizationImage={initialVisualizationImage}
              initialVisualizationHistory={visualizationHistory}
              onVisualizationHistoryChange={setVisualizationHistory}
              onVisualizationImageChange={setInitialVisualizationImage}
              isProcessingFurniture={isProcessingFurniture}
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

export default function DesignPage() {
  return (
    <ProtectedRoute>
      <DesignPageContent />
    </ProtectedRoute>
  );
}
