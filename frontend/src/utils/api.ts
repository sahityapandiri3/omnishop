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

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        // Optionally redirect to login
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

export const sendChatMessage = async (sessionId: string, data: { message: string; image?: string; selected_product_id?: string; selected_stores?: string[] }) => {
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
}) => {
  try {
    const response = await api.post(`/api/chat/sessions/${sessionId}/visualize`, data);
    return response.data;
  } catch (error) {
    console.error('Error visualizing room:', error);
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

export const checkFurnitureRemovalStatus = async (jobId: string): Promise<{ job_id: string; status: string; image?: string }> => {
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
const STORES_CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

interface StoresCache {
  stores: string[];
  timestamp: number;
}

export const getAvailableStores = async (): Promise<{ stores: string[] }> => {
  try {
    // Check if we're in a browser environment
    if (typeof window !== 'undefined' && window.localStorage) {
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
  uploadRoomImage: async (file: File) => {
    // Mock implementation
    return {
      url: URL.createObjectURL(file),
      id: "mock-image-" + Date.now()
    };
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
   * Extract furniture layers from a visualization
   * Returns base layer (empty room) and individual furniture layers
   */
  extractLayers: async (sessionId: string, visualizationImage: string, products: any[]) => {
    try {
      const response = await api.post(`/api/visualization/sessions/${sessionId}/extract-layers`, {
        visualization_image: visualizationImage,
        products: products
      });
      return response.data;
    } catch (error) {
      console.error('Error extracting furniture layers:', error);
      throw error;
    }
  }
};

// Admin Curated Looks API
export interface AdminCuratedLookSummary {
  id: number;
  title: string;
  style_theme: string;
  style_description: string | null;
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
}

export interface AdminCuratedLook {
  id: number;
  title: string;
  style_theme: string;
  style_description: string | null;
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
   * Search products for adding to a look
   */
  searchProducts: async (params: {
    query?: string;
    categoryId?: number;
    sourceWebsite?: string;
    minPrice?: number;
    maxPrice?: number;
    colors?: string;
    limit?: number;
  }): Promise<{ products: any[] }> => {
    try {
      const response = await api.get('/api/admin/curated/search/products', {
        params: {
          query: params.query,
          category_id: params.categoryId,
          source_website: params.sourceWebsite,
          min_price: params.minPrice,
          max_price: params.maxPrice,
          colors: params.colors,
          limit: params.limit
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
export const getCuratedLooks = async (roomType?: string, imageQuality: 'thumbnail' | 'medium' | 'full' = 'thumbnail'): Promise<CuratedLooksResponse> => {
  try {
    const params: Record<string, any> = { image_quality: imageQuality };
    if (roomType) {
      params.room_type = roomType;
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
