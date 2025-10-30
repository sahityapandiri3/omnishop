// Core product types
export interface Product {
  id: number;
  external_id: string;
  name: string;
  description?: string;
  price: number;
  original_price?: number;
  currency: string;
  brand?: string;
  model?: string;
  sku?: string;
  source_website: string;
  source_url: string;
  is_available: boolean;
  is_on_sale: boolean;
  stock_status: string;
  category_id?: number;
  category?: Category;
  images: ProductImage[];
  attributes: ProductAttribute[];
  scraped_at: string;
  last_updated: string;
  // Additional fields from recommendation API
  primary_image?: {
    url: string;
    alt_text: string;
  };
  recommendation_data?: {
    confidence_score: number;
    reasoning: string[];
    style_match: number;
    functional_match: number;
    price_score: number;
    overall_score: number;
  };
}

export interface ProductImage {
  id: number;
  product_id: number;
  original_url: string;
  thumbnail_url?: string;
  medium_url?: string;
  large_url?: string;
  alt_text?: string;
  width?: number;
  height?: number;
  display_order: number;
  is_primary: boolean;
}

export interface ProductAttribute {
  id: number;
  product_id: number;
  attribute_name: string;
  attribute_value: string;
  attribute_type: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  parent_id?: number;
  description?: string;
  parent?: Category;
  children?: Category[];
  product_count?: number;
}

// API response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface ProductFilters {
  category_id?: number;
  min_price?: number;
  max_price?: number;
  brand?: string[];
  source_website?: string[];
  is_available?: boolean;
  is_on_sale?: boolean;
  search?: string;
}

export interface ProductSortOptions {
  field: 'price' | 'name' | 'created_at' | 'popularity';
  direction: 'asc' | 'desc';
}

// Chat and AI types
export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  session_id?: string;
  products?: Product[];
  image?: string;
  image_url?: string;
  recommendations?: any[]; // For compatibility with backend
  analysis?: any; // For backend analysis data
  detected_furniture?: DetectedFurniture[];
  action_options?: ActionOptions;
  requires_action_choice?: boolean;
}

export interface ChatSession {
  id: string;
  messages: ChatMessage[];
  created_at: Date;
  updated_at: Date;
}

export interface DesignAnalysis {
  style_preferences: {
    primary_style: string;
    secondary_styles: string[];
    style_keywords: string[];
    inspiration_sources: string[];
  };
  color_scheme: {
    preferred_colors: string[];
    accent_colors: string[];
    color_temperature: 'warm' | 'cool' | 'neutral';
    color_intensity: 'bold' | 'muted' | 'balanced';
  };
  space_analysis: {
    room_type: string;
    dimensions?: string;
    layout_type: 'open' | 'closed' | 'mixed';
    lighting_conditions: 'natural' | 'artificial' | 'mixed';
    existing_elements: string[];
    traffic_patterns: string;
  };
  functional_requirements: {
    primary_functions: string[];
    storage_needs: string;
    seating_capacity?: number;
    special_considerations: string[];
  };
  product_matching_criteria: {
    furniture_categories: Record<string, any>;
    filtering_keywords: {
      include_terms: string[];
      exclude_terms: string[];
      material_preferences: string[];
      style_tags: string[];
    };
  };
  confidence_scores: {
    style_identification: number;
    space_understanding: number;
    product_matching: number;
    overall_analysis: number;
  };
}

// Visualization types
export interface RoomVisualization {
  id: string;
  name: string;
  room_image: string;
  placed_products: PlacedProduct[];
  created_at: Date;
  updated_at: Date;
}

export interface PlacedProduct {
  id: string;
  product: Product;
  position: {
    x: number;
    y: number;
  };
  scale: number;
  rotation: number;
  z_index: number;
}

// UI State types
export interface AppState {
  products: {
    items: Product[];
    loading: boolean;
    error?: string;
    filters: ProductFilters;
    sort: ProductSortOptions;
    pagination: {
      page: number;
      size: number;
      total: number;
    };
  };
  chat: {
    session?: ChatSession;
    loading: boolean;
    error?: string;
  };
  visualization: {
    current?: RoomVisualization;
    loading: boolean;
    error?: string;
  };
  ui: {
    sidebar_open: boolean;
    chat_open: boolean;
    mobile_menu_open: boolean;
    selected_product?: Product;
  };
}

// API Error types
export interface APIError {
  message: string;
  code?: string;
  details?: Record<string, any>;
}

// Form types
export interface SearchFormData {
  query: string;
  filters: ProductFilters;
}

export interface ChatFormData {
  message: string;
  image?: File;
}

export interface VisualizationFormData {
  room_image: File;
  room_name: string;
}

// API Response types for Chat
export interface ChatMessageRequest {
  content?: string;
  message?: string;
  image?: string;
  image_data?: string;
}

export interface DetectedFurniture {
  object_type: string;
  position: string;
  size: string;
  style: string;
  color: string;
  material: string;
  condition: string;
  confidence: number;
  furniture_id: string;
}

export interface ActionOptions {
  add?: {
    available: boolean;
    description: string;
  };
  replace?: {
    available: boolean;
    count?: number;
    items?: Array<{
      furniture_id: string;
      type: string;
      position: string;
      description: string;
    }>;
    description: string;
  };
}

export interface ChatMessageResponse {
  id: string;
  message_id?: string;
  content: string;
  message_type?: string;
  type?: string;
  timestamp: string;
  session_id: string;
  analysis?: any;
  recommendations?: any[];
  products?: any[];
  recommended_products?: any[];
  detected_furniture?: DetectedFurniture[];
  similar_furniture_items?: DetectedFurniture[];
  action_options?: ActionOptions;
  requires_action_choice?: boolean;
  processing_time?: number;
  message?: any;
}