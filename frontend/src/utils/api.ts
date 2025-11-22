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

// Stores API
export const getAvailableStores = async (): Promise<{ stores: string[] }> => {
  try {
    const response = await api.get('/api/stores');
    return response.data;
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
  }
};
