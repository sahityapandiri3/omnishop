import axios, { AxiosResponse } from 'axios';
import { Product, Category, ChatMessage, DesignAnalysis, ProductFilters } from '@/types';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 200000, // Increased to 200 seconds to accommodate AI image generation
});

// Request interceptor for authentication
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Session recovery storage key
const SESSION_RECOVERY_KEY = 'omnishop_session_recovery';

// Flag to prevent multiple 401 redirect attempts
// This prevents infinite loop when navigation guard blocks the redirect
let isRedirectingToLogin = false;
let redirectResetTimeout: NodeJS.Timeout | null = null;

// Function to reset redirect flag (allows retry after user cancels navigation)
const resetRedirectFlag = () => {
  isRedirectingToLogin = false;
  if (redirectResetTimeout) {
    clearTimeout(redirectResetTimeout);
    redirectResetTimeout = null;
  }
};

// Export for use by auth components after successful login
export const clearRedirectState = () => {
  resetRedirectFlag();
};

// Session storage keys for curation page state
const CURATION_RECOVERY_KEY = 'omnishop_curation_recovery';

// Function to save curation page state before 401 redirect
export const saveCurationStateForRecovery = () => {
  if (typeof window === 'undefined') return;

  try {
    // Get current curation state from sessionStorage
    const curationState = sessionStorage.getItem('curation_page_state');

    if (curationState) {
      const recoveryData = {
        curationState,
        timestamp: Date.now(),
      };

      localStorage.setItem(CURATION_RECOVERY_KEY, JSON.stringify(recoveryData));
      console.log('[API] Saved curation state for recovery');
    }
  } catch (e) {
    console.warn('[API] Failed to save curation state for recovery:', e);
  }
};

// Function to get recovered curation state after login
export const getRecoveredCurationState = () => {
  if (typeof window === 'undefined') return null;

  try {
    const data = localStorage.getItem(CURATION_RECOVERY_KEY);
    if (!data) return null;

    const recoveryData = JSON.parse(data);

    // Check if recovery data is less than 1 hour old
    const ageMs = Date.now() - recoveryData.timestamp;
    if (ageMs > 60 * 60 * 1000) {
      console.log('[API] Curation recovery data expired, discarding');
      localStorage.removeItem(CURATION_RECOVERY_KEY);
      return null;
    }

    return recoveryData.curationState ? JSON.parse(recoveryData.curationState) : null;
  } catch (e) {
    console.warn('[API] Failed to get recovered curation state:', e);
    return null;
  }
};

// Function to clear recovered curation state
export const clearRecoveredCurationState = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(CURATION_RECOVERY_KEY);
  }
};

// Function to save design state before 401 redirect
export const saveDesignStateForRecovery = () => {
  if (typeof window === 'undefined') return;

  try {
    // Get current design state from sessionStorage (using the actual keys the design page uses)
    const roomImage = sessionStorage.getItem('roomImage');
    const cleanRoomImage = sessionStorage.getItem('cleanRoomImage');
    const persistedCanvasProducts = sessionStorage.getItem('persistedCanvasProducts');
    const chatSessionId = sessionStorage.getItem('design_session_id');

    // Also grab curated look data if present
    const curatedRoomImage = sessionStorage.getItem('curatedRoomImage');
    const curatedVisualizationImage = sessionStorage.getItem('curatedVisualizationImage');
    const preselectedProducts = sessionStorage.getItem('preselectedProducts');
    const primaryStores = sessionStorage.getItem('primaryStores');

    // Only save if there's actual data to recover
    if (roomImage || curatedVisualizationImage || persistedCanvasProducts || preselectedProducts) {
      const recoveryData = {
        roomImage,
        cleanRoomImage,
        persistedCanvasProducts,
        chatSessionId,
        curatedRoomImage,
        curatedVisualizationImage,
        preselectedProducts,
        primaryStores,
        timestamp: Date.now(),
      };

      // Use localStorage so it persists across page reloads during login
      localStorage.setItem(SESSION_RECOVERY_KEY, JSON.stringify(recoveryData));
      console.log('[API] Saved design state for recovery:', {
        hasRoomImage: !!roomImage,
        hasCleanRoomImage: !!cleanRoomImage,
        hasCanvasProducts: !!persistedCanvasProducts,
        hasCuratedData: !!(curatedRoomImage || curatedVisualizationImage),
      });
    }
  } catch (e) {
    console.warn('[API] Failed to save design state for recovery:', e);
  }
};

// Function to get recovered design state after login
export const getRecoveredDesignState = () => {
  if (typeof window === 'undefined') return null;

  try {
    const data = localStorage.getItem(SESSION_RECOVERY_KEY);
    if (!data) return null;

    const recoveryData = JSON.parse(data);

    // Check if recovery data is less than 1 hour old
    const ageMs = Date.now() - recoveryData.timestamp;
    if (ageMs > 60 * 60 * 1000) {
      console.log('[API] Recovery data expired, discarding');
      localStorage.removeItem(SESSION_RECOVERY_KEY);
      return null;
    }

    return recoveryData;
  } catch (e) {
    console.warn('[API] Failed to get recovered design state:', e);
    return null;
  }
};

// Function to clear recovered design state (after successful restore)
export const clearRecoveredDesignState = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(SESSION_RECOVERY_KEY);
  }
};

// Function to restore design state to sessionStorage (called after login redirect back to design)
export const restoreDesignStateFromRecovery = (): boolean => {
  if (typeof window === 'undefined') return false;

  try {
    const recoveryData = getRecoveredDesignState();
    if (!recoveryData) return false;

    console.log('[API] Restoring design state from recovery...');

    // Restore each piece of state to sessionStorage
    if (recoveryData.roomImage) {
      sessionStorage.setItem('roomImage', recoveryData.roomImage);
    }
    if (recoveryData.cleanRoomImage) {
      sessionStorage.setItem('cleanRoomImage', recoveryData.cleanRoomImage);
    }
    if (recoveryData.persistedCanvasProducts) {
      sessionStorage.setItem('persistedCanvasProducts', recoveryData.persistedCanvasProducts);
    }
    if (recoveryData.chatSessionId) {
      sessionStorage.setItem('design_session_id', recoveryData.chatSessionId);
    }
    if (recoveryData.curatedRoomImage) {
      sessionStorage.setItem('curatedRoomImage', recoveryData.curatedRoomImage);
    }
    if (recoveryData.curatedVisualizationImage) {
      sessionStorage.setItem('curatedVisualizationImage', recoveryData.curatedVisualizationImage);
    }
    if (recoveryData.preselectedProducts) {
      sessionStorage.setItem('preselectedProducts', recoveryData.preselectedProducts);
    }
    if (recoveryData.primaryStores) {
      sessionStorage.setItem('primaryStores', recoveryData.primaryStores);
    }

    // Clear the recovery data after successful restore
    clearRecoveredDesignState();

    console.log('[API] Design state restored successfully');
    return true;
  } catch (e) {
    console.warn('[API] Failed to restore design state:', e);
    return false;
  }
};

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access - token expired or invalid
      if (typeof window !== 'undefined') {
        const currentPath = window.location.pathname;
        // Only clear token and redirect if not already on auth pages
        // AND if we haven't already started a redirect (prevents infinite loop when navigation guard blocks)
        if (!currentPath.startsWith('/login') && !currentPath.startsWith('/register') && !isRedirectingToLogin) {
          console.warn('[API] 401 Unauthorized - Session expired. Redirecting to login...');

          // Set flag to prevent multiple redirect attempts
          isRedirectingToLogin = true;

          // Reset the flag after 10 seconds in case user cancels navigation
          // This allows a retry if user wants to navigate after dealing with unsaved work
          if (redirectResetTimeout) {
            clearTimeout(redirectResetTimeout);
          }
          redirectResetTimeout = setTimeout(() => {
            console.log('[API] Redirect flag reset after timeout');
            isRedirectingToLogin = false;
            redirectResetTimeout = null;
          }, 10000);

          // Save design state before redirecting (if on design page)
          if (currentPath.startsWith('/design')) {
            saveDesignStateForRecovery();
          }

          // Save curation state before redirecting (if on curation page)
          if (currentPath.startsWith('/admin/curated')) {
            saveCurationStateForRecovery();
          }

          localStorage.removeItem('auth_token');
          // Force page reload to trigger auth check and redirect
          window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
        } else if (isRedirectingToLogin) {
          console.log('[API] 401 received but redirect already in progress, ignoring...');
        }
      }
    }
    return Promise.reject(error);
  }
);

// Simplified API functions that work with our mock backend
export const getProducts = async (params?: {
  page?: number;
  size?: number;
  search?: string;
  category_id?: number;
  min_price?: number;
  max_price?: number;
  brand?: string[];
  source_website?: string[];
  is_available?: boolean;
  is_on_sale?: boolean;
  sort_by?: string;
  sort_direction?: string;
}) => {
  try {
    const response = await api.get('/api/products', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching products:', error);
    // Return mock data as fallback
    return {
      items: [
        {
          id: 1,
          name: "Modern Sofa",
          price: 899.99,
          currency: "USD",
          brand: "West Elm",
          source_website: "westelm.com",
          is_available: true,
          is_on_sale: false,
          description: "A beautiful modern sofa perfect for any living room.",
          images: [
            {
              id: 1,
              original_url: "https://images.westelm.com/is/image/WestElm/sofa-1",
              is_primary: true,
              alt_text: "Modern Sofa"
            }
          ],
          category: { id: 1, name: "Furniture", slug: "furniture" }
        },
        {
          id: 2,
          name: "Coffee Table",
          price: 299.99,
          original_price: 399.99,
          currency: "USD",
          brand: "Orange Tree",
          source_website: "orangetree.com",
          is_available: true,
          is_on_sale: true,
          description: "Elegant coffee table with storage compartments.",
          images: [
            {
              id: 2,
              original_url: "https://orangetree.com/images/coffee-table-1",
              is_primary: true,
              alt_text: "Coffee Table"
            }
          ],
          category: { id: 1, name: "Furniture", slug: "furniture" }
        }
      ],
      total: 2,
      page: params?.page || 1,
      size: params?.size || 20,
      pages: 1,
      has_next: false,
      has_prev: false
    };
  }
};

export const getCategories = async () => {
  try {
    const response = await api.get('/api/categories');
    return response.data;
  } catch (error) {
    console.error('Error fetching categories:', error);
    // Return mock data as fallback
    return [
      { id: 1, name: "Furniture", slug: "furniture", product_count: 150 },
      { id: 2, name: "Lighting", slug: "lighting", product_count: 75 },
      { id: 3, name: "Decor", slug: "decor", product_count: 200 }
    ];
  }
};

export const startChatSession = async (data?: { user_id?: string }) => {
  try {
    const response = await api.post('/api/chat/sessions', data || {});
    return response.data;
  } catch (error) {
    console.error('Error starting chat session:', error);
    throw error; // Don't fall back to mock session, let the frontend handle the error
  }
};

export interface OnboardingPreferences {
  roomType: string | null;
  primaryStyle: string | null;
  secondaryStyle: string | null;
  budget: number | null;
  budgetFlexible: boolean;
  roomImage: string | null;
  processedImage?: string | null;
}

export const sendChatMessage = async (sessionId: string, data: { message: string; image?: string; selected_product_id?: string; selected_stores?: string[]; onboarding_preferences?: OnboardingPreferences }) => {
  try {
    const response = await api.post(`/api/chat/sessions/${sessionId}/messages`, data);
    return response.data;
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw error; // Don't fall back to generic response, let the frontend handle the error
  }
};

export const getChatHistory = async (sessionId: string) => {
  try {
    const response = await api.get(`/api/chat/sessions/${sessionId}/history`);
    return response.data;
  } catch (error) {
    console.error('Error fetching chat history:', error);
    throw error; // Don't fall back to empty messages, let the frontend handle the error
  }
};

export const visualizeRoom = async (sessionId: string, data: {
  image: string;
  products: any[];
  analysis?: any;
  user_action: string;
  detected_furniture?: any[];
  furniture_ids_to_replace?: string[];
  curated_look_id?: number;
}) => {
  try {
    const response = await api.post(`/api/chat/sessions/${sessionId}/visualize`, data);
    return response.data;
  } catch (error) {
    console.error('Error visualizing room:', error);
    throw error;
  }
};

export const generateAngleView = async (
  sessionId: string,
  data: {
    visualization_image: string;
    target_angle: 'left' | 'right' | 'back';
    products_description?: string;
  }
): Promise<{ angle: string; image: string; message: string }> => {
  try {
    const response = await api.post(`/api/chat/sessions/${sessionId}/visualize/angle`, data);
    return response.data;
  } catch (error) {
    console.error('Error generating angle view:', error);
    throw error;
  }
};

export const undoVisualization = async (sessionId: string) => {
  try {
    const response = await api.post(`/api/chat/sessions/${sessionId}/visualization/undo`);
    return response.data;
  } catch (error) {
    console.error('Error undoing visualization:', error);
    throw error;
  }
};

export const redoVisualization = async (sessionId: string) => {
  try {
    const response = await api.post(`/api/chat/sessions/${sessionId}/visualization/redo`);
    return response.data;
  } catch (error) {
    console.error('Error redoing visualization:', error);
    throw error;
  }
};

// Furniture removal API
export const startFurnitureRemoval = async (image: string): Promise<{ job_id: string; status: string }> => {
  try {
    const response = await api.post('/api/furniture/remove', { image });
    return response.data;
  } catch (error) {
    console.error('Error starting furniture removal:', error);
    throw error;
  }
};

export const checkFurnitureRemovalStatus = async (jobId: string): Promise<{ job_id: string; status: string; image?: string; error?: string }> => {
  try {
    const response = await api.get(`/api/furniture/status/${jobId}`);
    return response.data;
  } catch (error) {
    console.error('Error checking furniture removal status:', error);
    throw error;
  }
};

// Stores API with localStorage caching
const STORES_CACHE_KEY = 'omnishop_stores_cache';
const CATEGORIZED_STORES_CACHE_KEY = 'omnishop_categorized_stores_cache';
const STORES_CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

interface StoresCache {
  stores: string[];
  timestamp: number;
}

// Types for categorized stores
export interface StoreInfo {
  name: string;
  display_name: string;
  budget_tier: string | null;
}

export interface StoreCategory {
  tier: string;
  label: string;
  stores: StoreInfo[];
}

export interface CategorizedStoresResponse {
  categories: StoreCategory[];
  all_stores: StoreInfo[];
}

interface CategorizedStoresCache {
  data: CategorizedStoresResponse;
  timestamp: number;
}

export const clearStoresCache = (): void => {
  if (typeof window !== 'undefined' && window.localStorage) {
    localStorage.removeItem(STORES_CACHE_KEY);
    localStorage.removeItem(CATEGORIZED_STORES_CACHE_KEY);
    console.log('[Stores Cache] Cache cleared');
  }
};

export const getAvailableStores = async (forceRefresh = false): Promise<{ stores: string[] }> => {
  try {
    // Check if we're in a browser environment
    if (typeof window !== 'undefined' && window.localStorage) {
      // Force refresh clears the cache
      if (forceRefresh) {
        localStorage.removeItem(STORES_CACHE_KEY);
        console.log('[Stores Cache] Force refresh requested, clearing cache');
      } else {
        // Try to get cached data
        const cached = localStorage.getItem(STORES_CACHE_KEY);

        if (cached) {
          try {
            const cacheData: StoresCache = JSON.parse(cached);
            const age = Date.now() - cacheData.timestamp;

            // If cache is less than 24 hours old, return it
            if (age < STORES_CACHE_TTL) {
              console.log('[Stores Cache] Using cached stores data (age:', Math.round(age / 1000 / 60), 'minutes)');
              return { stores: cacheData.stores };
            } else {
              console.log('[Stores Cache] Cache expired, fetching fresh data');
            }
          } catch (e) {
            console.warn('[Stores Cache] Failed to parse cached data, fetching fresh');
          }
        }
      }
    }

    // Fetch from API
    const response = await api.get('/api/stores');
    const storesData = response.data;

    // Cache the result
    if (typeof window !== 'undefined' && window.localStorage) {
      try {
        const cacheData: StoresCache = {
          stores: storesData.stores,
          timestamp: Date.now(),
        };
        localStorage.setItem(STORES_CACHE_KEY, JSON.stringify(cacheData));
        console.log('[Stores Cache] Cached fresh stores data');
      } catch (e) {
        console.warn('[Stores Cache] Failed to cache data:', e);
      }
    }

    return storesData;
  } catch (error) {
    console.error('Error fetching available stores:', error);
    throw error;
  }
};

export const getCategorizedStores = async (forceRefresh = false): Promise<CategorizedStoresResponse> => {
  try {
    // Check if we're in a browser environment
    if (typeof window !== 'undefined' && window.localStorage) {
      // Force refresh clears the cache
      if (forceRefresh) {
        localStorage.removeItem(CATEGORIZED_STORES_CACHE_KEY);
        console.log('[Categorized Stores Cache] Force refresh requested, clearing cache');
      } else {
        // Try to get cached data
        const cached = localStorage.getItem(CATEGORIZED_STORES_CACHE_KEY);

        if (cached) {
          try {
            const cacheData: CategorizedStoresCache = JSON.parse(cached);
            const age = Date.now() - cacheData.timestamp;

            // If cache is less than 24 hours old, return it
            if (age < STORES_CACHE_TTL) {
              console.log('[Categorized Stores Cache] Using cached data (age:', Math.round(age / 1000 / 60), 'minutes)');
              return cacheData.data;
            } else {
              console.log('[Categorized Stores Cache] Cache expired, fetching fresh data');
            }
          } catch (e) {
            console.warn('[Categorized Stores Cache] Failed to parse cached data, fetching fresh');
          }
        }
      }
    }

    // Fetch from API
    const response = await api.get('/api/stores/categorized');
    const categorizedData: CategorizedStoresResponse = response.data;

    // Cache the result
    if (typeof window !== 'undefined' && window.localStorage) {
      try {
        const cacheData: CategorizedStoresCache = {
          data: categorizedData,
          timestamp: Date.now(),
        };
        localStorage.setItem(CATEGORIZED_STORES_CACHE_KEY, JSON.stringify(cacheData));
        console.log('[Categorized Stores Cache] Cached fresh data');
      } catch (e) {
        console.warn('[Categorized Stores Cache] Failed to cache data:', e);
      }
    }

    return categorizedData;
  } catch (error) {
    console.error('Error fetching categorized stores:', error);
    throw error;
  }
};

// Legacy support - export the old structure for existing components
export { api as default };

// Named export for components using import { api }
export { api };

// Export API groups for backward compatibility
export const productAPI = {
  getProducts: (page = 1, size = 20, filters?: ProductFilters, sort?: any) =>
    getProducts({ page, size, ...filters, sort_by: sort?.field, sort_direction: sort?.direction })
};

export const categoryAPI = {
  getCategories
};

export const chatAPI = {
  startSession: () => startChatSession(),
  sendMessage: (message: string, sessionId?: string, image?: File) => {
    // Convert File to base64 if needed
    return sendChatMessage(sessionId || '', { message });
  },
  getChatHistory
};

export const imageAPI = {
  /**
   * Upload room image and perform combined room analysis.
   * This is called during image upload to cache room analysis for faster visualization.
   *
   * @param file - The image file to upload
   * @param projectId - Optional project ID (design page flow)
   * @param curatedLookId - Optional curated look ID (admin curation flow)
   * @returns Upload response with image data and room analysis
   */
  uploadRoomImage: async (
    file: File,
    projectId?: string | null,
    curatedLookId?: number | null
  ): Promise<{
    image_data: string;
    filename: string;
    size: number;
    content_type: string;
    upload_timestamp: string;
    room_analysis: Record<string, unknown>;
  }> => {
    const formData = new FormData();
    formData.append('file', file);

    // Build URL with query parameters
    const params = new URLSearchParams();
    if (projectId) {
      params.append('project_id', projectId);
    }
    if (curatedLookId) {
      params.append('curated_look_id', curatedLookId.toString());
    }

    const queryString = params.toString();
    const url = `/api/visualization/upload-room-image${queryString ? `?${queryString}` : ''}`;

    const response = await api.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  },

  /**
   * Upload room image from base64 string (for use when image is already loaded).
   * Converts base64 to File and calls uploadRoomImage.
   *
   * @param base64Data - Base64 encoded image data (with or without data URI prefix)
   * @param projectId - Optional project ID (design page flow)
   * @param curatedLookId - Optional curated look ID (admin curation flow)
   * @returns Upload response with image data and room analysis
   */
  uploadRoomImageFromBase64: async (
    base64Data: string,
    projectId?: string | null,
    curatedLookId?: number | null
  ): Promise<{
    image_data: string;
    filename: string;
    size: number;
    content_type: string;
    upload_timestamp: string;
    room_analysis: Record<string, unknown>;
  }> => {
    // Extract base64 content and mime type
    let mimeType = 'image/jpeg';
    let base64Content = base64Data;

    if (base64Data.startsWith('data:')) {
      const matches = base64Data.match(/^data:([^;]+);base64,(.+)$/);
      if (matches) {
        mimeType = matches[1];
        base64Content = matches[2];
      }
    }

    // Convert base64 to Blob then to File
    const byteCharacters = atob(base64Content);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: mimeType });
    const file = new File([blob], 'room-image.jpg', { type: mimeType });

    return imageAPI.uploadRoomImage(file, projectId, curatedLookId);
  },

  getOptimizedImageUrl: (url: string) => url
};

export const analyticsAPI = {
  trackProductView: async (productId: number) => { /* Mock */ },
  trackSearch: async (query: string, results_count: number) => { /* Mock */ },
  trackChatInteraction: async (sessionId: string, messageType: string) => { /* Mock */ }
};

// Curated Styling API
export interface CuratedLook {
  look_id: string;
  title?: string;  // Display title (e.g., "Emerald-Centered Living Room")
  style_theme: string;
  style_description: string;
  room_image: string | null;  // Base room image (furniture removed)
  visualization_image: string | null;
  products: Array<{
    id: number;
    name: string;
    price: number;
    image_url: string | null;
    source_website: string;
    source_url: string | null;
    product_type: string;
    description?: string;
  }>;
  total_price: number;
  generation_status: 'pending' | 'generating' | 'completed' | 'failed';
  error_message?: string | null;
}

export interface CuratedLooksResponse {
  session_id: string;
  room_type: string;
  looks: CuratedLook[];
  generation_complete: boolean;
}

export const generateCuratedLooks = async (data: {
  room_image: string;
  selected_stores: string[];
  num_looks?: number;
}): Promise<CuratedLooksResponse> => {
  // This is a long-running operation that generates AI visualizations
  // Each look takes ~30 seconds for visualization, so 3 looks = ~2 minutes minimum
  // We use a longer timeout and NO retries to avoid duplicate requests
  const CURATED_LOOKS_TIMEOUT = 300000; // 5 minutes for this specific operation

  try {
    console.log('[Curated Looks] Starting generation (timeout: 5 minutes)...');
    const response = await api.post('/api/curated/generate', {
      room_image: data.room_image,
      selected_stores: data.selected_stores,
      num_looks: data.num_looks || 3,
    }, {
      timeout: CURATED_LOOKS_TIMEOUT, // Override default timeout for this long operation
    });
    console.log('[Curated Looks] Success!');
    return response.data;
  } catch (error: any) {
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');
    const isConnectionError = error.code === 'ERR_NETWORK' ||
                              error.message?.includes('Network Error') ||
                              error.code === 'ERR_CONNECTION_REFUSED';

    console.error('[Curated Looks] Failed:', {
      code: error.code,
      message: error.message,
      status: error.response?.status,
      isTimeout,
      isConnectionError
    });

    // Create enhanced error with specific messages
    let errorMessage: string;
    if (isTimeout) {
      errorMessage = 'Generation is taking longer than expected. Please try with fewer looks or try again later.';
    } else if (isConnectionError) {
      errorMessage = 'Could not connect to server. Please check your internet connection and try again.';
    } else {
      errorMessage = error.response?.data?.detail || error.message || 'Failed to generate curated looks';
    }

    const enhancedError = new Error(errorMessage);
    (enhancedError as any).originalError = error;
    (enhancedError as any).isTimeout = isTimeout;
    (enhancedError as any).isConnectionError = isConnectionError;
    throw enhancedError;
  }
};

// Furniture Position Management API
export interface FurniturePositionData {
  productId: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  label?: string;
  isAiPlaced?: boolean;
}

export const furniturePositionAPI = {
  /**
   * Save furniture positions for a visualization session
   */
  savePositions: async (sessionId: string, positions: FurniturePositionData[]) => {
    try {
      const response = await api.post(`/api/visualization/sessions/${sessionId}/furniture-positions`, positions);
      return response.data;
    } catch (error) {
      console.error('Error saving furniture positions:', error);
      throw error;
    }
  },

  /**
   * Get saved furniture positions for a visualization session
   */
  getPositions: async (sessionId: string) => {
    try {
      const response = await api.get(`/api/visualization/sessions/${sessionId}/furniture-positions`);
      return response.data;
    } catch (error) {
      console.error('Error retrieving furniture positions:', error);
      throw error;
    }
  },

  /**
   * Update a specific furniture position
   */
  updatePosition: async (sessionId: string, productId: number, positionUpdate: Partial<FurniturePositionData>) => {
    try {
      const response = await api.put(`/api/visualization/sessions/${sessionId}/furniture-positions/${productId}`, positionUpdate);
      return response.data;
    } catch (error) {
      console.error('Error updating furniture position:', error);
      throw error;
    }
  },

  /**
   * Delete all furniture positions for a session
   */
  deleteAllPositions: async (sessionId: string) => {
    try {
      const response = await api.delete(`/api/visualization/sessions/${sessionId}/furniture-positions`);
      return response.data;
    } catch (error) {
      console.error('Error deleting furniture positions:', error);
      throw error;
    }
  },

  /**
   * Extract furniture layers from a visualization using SAM segmentation (Magic Grab).
   * Returns clean background and individual furniture layers with transparent cutouts.
   *
   * @param sessionId - The session ID
   * @param visualizationImage - Base64 visualization image
   * @param products - List of products (for matching/labeling)
   * @param useSam - Use SAM for precise segmentation (true) or Gemini bounding boxes (false)
   */
  extractLayers: async (
    sessionId: string,
    visualizationImage: string,
    products: any[],
    useSam: boolean = true,
    curatedLookId?: number
  ) => {
    try {
      console.log('[extractLayers] Starting Magic Grab extraction...', {
        sessionId,
        imageLength: visualizationImage?.length || 0,
        productsCount: products?.length || 0,
        useSam,
        curatedLookId,
      });

      const response = await api.post(
        `/api/visualization/sessions/${sessionId}/extract-layers`,
        {
          visualization_image: visualizationImage,
          products: products,
          use_sam: useSam,  // Use SAM for precise segmentation
          curated_look_id: curatedLookId,  // For cache lookup
        },
        {
          timeout: 300000, // 5 minute timeout for SAM (Replicate cold starts can be slow)
        }
      );

      console.log('[extractLayers] Magic Grab extraction complete:', {
        hasBackground: !!response.data?.background,
        layersCount: response.data?.layers?.length || 0,
        method: response.data?.extraction_method,
        time: response.data?.extraction_time,
      });

      return response.data;
    } catch (error: any) {
      console.error('[extractLayers] API error:', {
        message: error?.message,
        status: error?.response?.status,
        statusText: error?.response?.statusText,
        data: error?.response?.data,
      });
      throw error;
    }
  },

  /**
   * Composite layers onto background at new positions (Magic Grab finalization).
   * Called when user clicks "Done" after dragging objects.
   *
   * @param sessionId - The session ID
   * @param background - Base64 clean background image
   * @param layers - Array of layers with new positions {id, cutout, x, y, scale}
   * @param harmonize - Apply AI lighting harmonization (optional, adds ~3-5 sec)
   */
  compositeLayers: async (
    sessionId: string,
    background: string,
    layers: Array<{
      id: string;
      cutout: string;  // Base64 PNG with transparency
      x: number;       // Normalized position (0-1)
      y: number;
      scale?: number;
      rotation?: number;
      opacity?: number;
      z_index?: number;
    }>,
    harmonize: boolean = false
  ) => {
    try {
      console.log('[compositeLayers] Starting layer compositing...', {
        sessionId,
        backgroundLength: background?.length || 0,
        layersCount: layers?.length || 0,
        harmonize,
      });

      const response = await api.post(
        `/api/visualization/sessions/${sessionId}/composite-layers`,
        {
          background,
          layers,
          harmonize
        },
        {
          timeout: harmonize ? 60000 : 30000, // Longer timeout if harmonizing
        }
      );

      console.log('[compositeLayers] Compositing complete:', {
        hasImage: !!response.data?.image,
        layersComposited: response.data?.layers_composited,
        time: response.data?.processing_time,
      });

      return response.data;
    } catch (error: any) {
      console.error('[compositeLayers] API error:', {
        message: error?.message,
        status: error?.response?.status,
        data: error?.response?.data,
      });
      throw error;
    }
  },

  /**
   * Segment object at a clicked point using SAM 2 (click-to-select).
   * Returns a layer with cutout, mask, and position data for dragging.
   *
   * @param sessionId - The session ID
   * @param imageBase64 - The visualization image
   * @param point - Normalized click coordinates {x: 0-1, y: 0-1}
   * @param label - Optional label for the object
   * @param products - Optional list of products for matching
   * @param curatedLookId - Optional curated look ID for cache lookup
   */
  segmentAtPoint: async (
    sessionId: string,
    imageBase64: string,
    point: { x: number; y: number },
    label: string = 'object',
    products?: Array<{ id: number; name: string; image_url?: string }>,
    curatedLookId?: number
  ): Promise<{
    layer: {
      id: string;
      label: string;
      cutout: string;
      mask: string;
      bbox: { x: number; y: number; width: number; height: number };
      x: number;
      y: number;
      width: number;
      height: number;
      scale: number;
      area: number;
      stability_score: number;
      product_id?: number;
    };
    inpainted_background?: string;
    matched_product_id?: number;
    session_id: string;
    status: string;
  }> => {
    try {
      console.log('[segmentAtPoint] Starting SAM 2 segmentation...', {
        sessionId,
        point,
        label,
        imageLength: imageBase64?.length || 0,
        productsCount: products?.length || 0,
      });

      const response = await api.post(
        `/api/visualization/sessions/${sessionId}/segment-at-point`,
        {
          image_base64: imageBase64,
          point,
          label,
          products: products || undefined,
          curated_look_id: curatedLookId || undefined,
        },
        {
          timeout: 300000, // 5 minute timeout for SAM (Replicate cold starts can be slow)
        }
      );

      console.log('[segmentAtPoint] Segmentation complete:', {
        hasLayer: !!response.data?.layer,
        layerId: response.data?.layer?.id,
        area: response.data?.layer?.area,
        matchedProductId: response.data?.matched_product_id,
      });

      return response.data;
    } catch (error: any) {
      console.error('[segmentAtPoint] API error:', {
        message: error?.message,
        status: error?.response?.status,
        data: error?.response?.data,
      });
      throw error;
    }
  },

  /**
   * Segment object using multiple click points (grouped selection).
   * Use for selecting sofa + pillows, or table + objects as one unit.
   *
   * @param sessionId - The session ID
   * @param imageBase64 - The visualization image
   * @param points - Array of normalized click coordinates
   * @param label - Label for the combined object
   */
  segmentAtPoints: async (
    sessionId: string,
    imageBase64: string,
    points: Array<{ x: number; y: number }>,
    label: string = 'object'
  ): Promise<{
    layer: {
      id: string;
      label: string;
      cutout: string;
      mask: string;
      bbox: { x: number; y: number; width: number; height: number };
      x: number;
      y: number;
      width: number;
      height: number;
      scale: number;
      area: number;
      stability_score: number;
    };
    session_id: string;
    status: string;
  }> => {
    try {
      console.log('[segmentAtPoints] Starting multi-point segmentation...', {
        sessionId,
        pointsCount: points.length,
        label,
      });

      const response = await api.post(
        `/api/visualization/sessions/${sessionId}/segment-at-points`,
        {
          image_base64: imageBase64,
          points,
          label,
        },
        {
          timeout: 300000, // 5 minute timeout for SAM (Replicate cold starts can be slow)
        }
      );

      console.log('[segmentAtPoints] Segmentation complete:', {
        hasLayer: !!response.data?.layer,
        layerId: response.data?.layer?.id,
      });

      return response.data;
    } catch (error: any) {
      console.error('[segmentAtPoints] API error:', {
        message: error?.message,
        status: error?.response?.status,
        data: error?.response?.data,
      });
      throw error;
    }
  },

  /**
   * Finalize object movement using Gemini re-visualization.
   * Called when user clicks "Done" after dragging an object.
   *
   * @param sessionId - The session ID
   * @param originalImage - Original visualization image
   * @param mask - Mask of original object location
   * @param cutout - The extracted object PNG
   * @param originalPosition - Where object was
   * @param newPosition - Where object is now
   * @param scale - Scale factor applied
   * @param inpaintedBackground - Optional clean background with object removed
   * @param productId - Optional product ID to fetch clean product image from DB
   */
  finalizeMove: async (
    sessionId: string,
    originalImage: string,
    mask: string,
    cutout: string,
    originalPosition: { x: number; y: number },
    newPosition: { x: number; y: number },
    scale: number = 1.0,
    inpaintedBackground?: string | null,
    productId?: number | null
  ): Promise<{
    image: string;
    session_id: string;
    status: string;
    dimensions: { width: number; height: number };
  }> => {
    try {
      console.log('[finalizeMove] Finalizing object move...', {
        sessionId,
        originalPosition,
        newPosition,
        scale,
        hasInpaintedBackground: !!inpaintedBackground,
        productId,
      });

      const response = await api.post(
        `/api/visualization/sessions/${sessionId}/finalize-move`,
        {
          original_image: originalImage,
          mask,
          cutout,
          inpainted_background: inpaintedBackground || undefined,
          product_id: productId || undefined,
          original_position: originalPosition,
          new_position: newPosition,
          scale,
        },
        {
          timeout: 90000, // 90 seconds for Gemini re-visualization
        }
      );

      console.log('[finalizeMove] Move finalized:', {
        hasImage: !!response.data?.image,
        dimensions: response.data?.dimensions,
      });

      return response.data;
    } catch (error: any) {
      console.error('[finalizeMove] API error:', {
        message: error?.message,
        status: error?.response?.status,
        data: error?.response?.data,
      });
      throw error;
    }
  },

  /**
   * Re-visualize the entire scene with products at specified positions.
   * This is the proper way to handle furniture repositioning - regenerates
   * the entire visualization from scratch with all products at their new positions.
   *
   * @param sessionId - Session ID
   * @param roomImage - Clean room image (without furniture)
   * @param positions - Array of {product_id, x, y, scale} for all products
   * @param curatedLookId - Optional curated look ID
   */
  revisualizeWithPositions: async (
    sessionId: string,
    roomImage: string,
    positions: Array<{ product_id: number; x: number; y: number; scale?: number }>,
    curatedLookId?: number
  ): Promise<{
    image: string;
    session_id: string;
    status: string;
    processing_time?: number;
    quality_score?: number;
  }> => {
    try {
      console.log('[revisualizeWithPositions] Starting full scene re-visualization...', {
        sessionId,
        positionCount: positions.length,
        curatedLookId,
      });

      const response = await api.post(
        `/api/visualization/sessions/${sessionId}/revisualize-with-positions`,
        {
          room_image: roomImage,
          products: positions.map(p => ({ id: p.product_id })),
          positions: positions.map(p => ({
            product_id: p.product_id,
            x: p.x,
            y: p.y,
            scale: p.scale || 1.0,
          })),
          curated_look_id: curatedLookId,
        },
        {
          timeout: 120000, // 2 minutes for full re-visualization
        }
      );

      console.log('[revisualizeWithPositions] Re-visualization complete:', {
        hasImage: !!response.data?.image,
        processingTime: response.data?.processing_time,
      });

      return response.data;
    } catch (error: any) {
      console.error('[revisualizeWithPositions] API error:', {
        message: error?.message,
        status: error?.response?.status,
        data: error?.response?.data,
      });
      throw error;
    }
  },
};

// Admin Curated Looks API
export interface AdminCuratedLookSummary {
  id: number;
  title: string;
  style_theme: string;
  style_description: string | null;
  style_labels: string[];
  room_type: string;
  visualization_image: string | null;
  total_price: number;
  is_published: boolean;
  display_order: number;
  product_count: number;
  created_at: string;
}

export interface AdminCuratedLookProduct {
  id: number;
  name: string;
  price: number | null;
  image_url: string | null;
  source_website: string;
  source_url: string | null;
  product_type: string | null;
  description: string | null;
  quantity?: number;
}

export interface AdminCuratedLook {
  id: number;
  title: string;
  style_theme: string;
  style_description: string | null;
  style_labels: string[];
  room_type: string;
  room_image: string | null;
  visualization_image: string | null;
  total_price: number;
  is_published: boolean;
  display_order: number;
  products: AdminCuratedLookProduct[];
  created_at: string;
  updated_at: string;
}

export interface AdminCuratedLooksListResponse {
  items: AdminCuratedLookSummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface AdminCuratedLookCreate {
  title: string;
  style_theme: string;
  style_description?: string;
  style_labels?: string[];
  room_type: 'living_room' | 'bedroom';
  room_image?: string;
  visualization_image?: string;
  is_published?: boolean;
  display_order?: number;
  product_ids: number[];
  product_types?: string[];
}

export const adminCuratedAPI = {
  /**
   * List all curated looks (admin view)
   */
  list: async (params?: { page?: number; size?: number; room_type?: string; is_published?: boolean }): Promise<AdminCuratedLooksListResponse> => {
    try {
      const response = await api.get('/api/admin/curated/', { params });
      return response.data;
    } catch (error) {
      console.error('Error listing curated looks:', error);
      throw error;
    }
  },

  /**
   * Get a single curated look with full details
   */
  get: async (lookId: number): Promise<AdminCuratedLook> => {
    try {
      const response = await api.get(`/api/admin/curated/${lookId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting curated look:', error);
      throw error;
    }
  },

  /**
   * Create a new curated look
   */
  create: async (data: AdminCuratedLookCreate): Promise<AdminCuratedLook> => {
    try {
      console.log('[adminCuratedAPI.create] Starting request...');
      const startTime = Date.now();
      const response = await api.post('/api/admin/curated/', data);
      console.log(`[adminCuratedAPI.create] Success in ${Date.now() - startTime}ms`);
      return response.data;
    } catch (error: any) {
      console.error('[adminCuratedAPI.create] Error:', error.message);
      console.error('[adminCuratedAPI.create] Response:', error.response?.status, error.response?.data);
      throw error;
    }
  },

  /**
   * Update a curated look
   */
  update: async (lookId: number, data: Partial<AdminCuratedLookCreate>): Promise<AdminCuratedLook> => {
    try {
      const response = await api.put(`/api/admin/curated/${lookId}`, data);
      return response.data;
    } catch (error) {
      console.error('Error updating curated look:', error);
      throw error;
    }
  },

  /**
   * Update products in a curated look
   */
  updateProducts: async (lookId: number, productIds: number[], productTypes?: string[]): Promise<AdminCuratedLook> => {
    try {
      const response = await api.put(`/api/admin/curated/${lookId}/products`, {
        product_ids: productIds,
        product_types: productTypes
      });
      return response.data;
    } catch (error) {
      console.error('Error updating curated look products:', error);
      throw error;
    }
  },

  /**
   * Delete a curated look
   */
  delete: async (lookId: number): Promise<void> => {
    try {
      await api.delete(`/api/admin/curated/${lookId}`);
    } catch (error) {
      console.error('Error deleting curated look:', error);
      throw error;
    }
  },

  /**
   * Publish a curated look
   */
  publish: async (lookId: number): Promise<void> => {
    try {
      await api.post(`/api/admin/curated/${lookId}/publish`);
    } catch (error) {
      console.error('Error publishing curated look:', error);
      throw error;
    }
  },

  /**
   * Unpublish a curated look
   */
  unpublish: async (lookId: number): Promise<void> => {
    try {
      await api.post(`/api/admin/curated/${lookId}/unpublish`);
    } catch (error) {
      console.error('Error unpublishing curated look:', error);
      throw error;
    }
  },

  /**
   * Get product categories for filtering
   */
  getCategories: async (): Promise<{ categories: { id: number; name: string; slug: string }[] }> => {
    try {
      const response = await api.get('/api/admin/curated/categories');
      return response.data;
    } catch (error) {
      console.error('Error fetching categories:', error);
      throw error;
    }
  },

  /**
   * Search products for adding to a look (with pagination)
   */
  searchProducts: async (params: {
    query?: string;
    categoryId?: number;
    sourceWebsite?: string;
    minPrice?: number;
    maxPrice?: number;
    colors?: string;
    styles?: string;
    materials?: string;
    page?: number;
    pageSize?: number;
  }): Promise<{
    products: any[];
    total: number;
    total_primary: number;
    total_related: number;
    page: number;
    page_size: number;
    has_more: boolean;
  }> => {
    try {
      const response = await api.get('/api/admin/curated/search/products', {
        params: {
          query: params.query,
          category_id: params.categoryId,
          source_website: params.sourceWebsite,
          min_price: params.minPrice,
          max_price: params.maxPrice,
          colors: params.colors,
          styles: params.styles,
          materials: params.materials,
          page: params.page || 1,
          page_size: params.pageSize || 50,
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error searching products:', error);
      throw error;
    }
  }
};

// Get pre-curated looks from database (public endpoint)
// imageQuality: 'thumbnail' (400px), 'medium' (1200px - for landing page), 'full' (original)
// style: Filter by style label (modern, modern_luxury, indian_contemporary, etc.)
// budgetTier: Filter by budget tier (essential, value, mid, premium, ultra_luxury)
export const getCuratedLooks = async (
  roomType?: string,
  imageQuality: 'thumbnail' | 'medium' | 'full' = 'thumbnail',
  style?: string,
  budgetTier?: string
): Promise<CuratedLooksResponse> => {
  try {
    const params: Record<string, any> = { image_quality: imageQuality };
    if (roomType) {
      params.room_type = roomType;
    }
    if (style) {
      params.style = style;
    }
    if (budgetTier) {
      params.budget_tier = budgetTier;
    }
    const response = await api.get('/api/curated/looks', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching curated looks:', error);
    throw error;
  }
};

// Get a single curated look by ID with full images (for "Use Style" action)
export const getCuratedLookById = async (lookId: string | number): Promise<CuratedLook> => {
  try {
    const response = await api.get(`/api/curated/looks/${lookId}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching curated look:', error);
    throw error;
  }
};

// ==========================================
// Projects API
// ==========================================

export interface Project {
  id: string;
  name: string;
  status: 'draft' | 'published';  // Project status for draft mode
  room_image: string | null;
  clean_room_image: string | null;
  visualization_image: string | null;
  canvas_products: string | null; // JSON string
  visualization_history: string | null; // JSON string of visualization history for undo/redo
  chat_session_id: string | null; // Link to chat session for restoring conversation
  created_at: string;
  updated_at: string;
}

export interface ProjectListItem {
  id: string;
  name: string;
  status: 'draft' | 'published';  // Project status for draft mode
  has_room_image: boolean;
  has_visualization: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectsListResponse {
  projects: ProjectListItem[];
  total: number;
}

export interface CreateProjectData {
  name: string;
}

export interface UpdateProjectData {
  name?: string;
  status?: 'draft' | 'published';  // Project status for draft mode
  room_image?: string;
  clean_room_image?: string;
  visualization_image?: string;
  canvas_products?: string;
  visualization_history?: string;  // JSON string of visualization history for undo/redo
  chat_session_id?: string;  // Link to chat session for restoring conversation
}

export const projectsAPI = {
  /**
   * List all projects for the current user
   */
  list: async (): Promise<ProjectsListResponse> => {
    const response = await api.get('/api/projects');
    return response.data;
  },

  /**
   * Get a single project by ID
   */
  get: async (projectId: string): Promise<Project> => {
    const response = await api.get(`/api/projects/${projectId}`);
    return response.data;
  },

  /**
   * Create a new project
   */
  create: async (data: CreateProjectData): Promise<Project> => {
    const response = await api.post('/api/projects', data);
    return response.data;
  },

  /**
   * Update a project (used for auto-save)
   */
  update: async (projectId: string, data: UpdateProjectData): Promise<Project> => {
    const response = await api.put(`/api/projects/${projectId}`, data);
    return response.data;
  },

  /**
   * Delete a project
   */
  delete: async (projectId: string): Promise<void> => {
    await api.delete(`/api/projects/${projectId}`);
  },

  /**
   * Get project thumbnail (just the visualization image)
   */
  getThumbnail: async (projectId: string): Promise<{ visualization_image: string | null }> => {
    const response = await api.get(`/api/projects/${projectId}/thumbnail`);
    return response.data;
  },
};
