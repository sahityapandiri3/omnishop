/**
 * Style configuration for the onboarding wizard
 * Images are served from the API at /api/styles/
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface StyleOption {
  id: string;
  displayName: string;
  description: string;
  imagePath: string;
}

export const STYLE_OPTIONS: StyleOption[] = [
  {
    id: 'modern',
    displayName: 'Modern',
    description: 'Clean lines, neutral tones, functional elegance',
    imagePath: `${API_URL}/api/styles/Style_Modern.jpg`,
  },
  {
    id: 'minimalist',
    displayName: 'Minimalist',
    description: 'Simple, uncluttered, less is more',
    imagePath: `${API_URL}/api/styles/Style_Minimalist.jpg`,
  },
  {
    id: 'scandinavian',
    displayName: 'Scandinavian',
    description: 'Light woods, cozy textiles, hygge comfort',
    imagePath: `${API_URL}/api/styles/Style_Scandanavian.jpg`,
  },
  {
    id: 'japandi',
    displayName: 'Japandi',
    description: 'Zen-like calm meets warm minimalism',
    imagePath: `${API_URL}/api/styles/Style_Japandi.jpg`,
  },
  {
    id: 'mid_century_modern',
    displayName: 'Mid-Century Modern',
    description: 'Retro curves, tapered legs, bold accents',
    imagePath: `${API_URL}/api/styles/Style_MidCentuaryModern.png`,
  },
  {
    id: 'boho',
    displayName: 'Bohemian',
    description: 'Layered textures, natural materials, eclectic',
    imagePath: `${API_URL}/api/styles/Style_Boho.jpg`,
  },
  {
    id: 'industrial',
    displayName: 'Industrial',
    description: 'Raw materials, metal accents, urban edge',
    imagePath: `${API_URL}/api/styles/Style_Industrial.jpg`,
  },
  {
    id: 'indian_contemporary',
    displayName: 'Indian Contemporary',
    description: 'Warm tones, crafted details, modern heritage',
    imagePath: `${API_URL}/api/styles/Style_Indian.jpg`,
  },
  {
    id: 'modern_luxury',
    displayName: 'Modern Luxury',
    description: 'Premium finishes, sophisticated elegance',
    imagePath: `${API_URL}/api/styles/Style_Luxury.jpg`,
  },
  {
    id: 'contemporary',
    displayName: 'Contemporary',
    description: 'Trend-forward, fresh, current aesthetic',
    imagePath: `${API_URL}/api/styles/Style_Contemporary.jpg`,
  },
  {
    id: 'eclectic',
    displayName: 'Eclectic',
    description: 'Curated mix, personality-driven design',
    imagePath: `${API_URL}/api/styles/Style_Eclectic.jpg`,
  },
];

// Room type options for onboarding
export interface RoomTypeOption {
  id: string;
  displayName: string;
  description: string;
  imagePath: string;
}

export const ROOM_TYPE_OPTIONS: RoomTypeOption[] = [
  {
    id: 'living_room',
    displayName: 'Living Room',
    description: 'Sofas, coffee tables, accent chairs & more',
    imagePath: `${API_URL}/api/rooms/Room_LivingRoom.png`,
  },
  {
    id: 'bedroom',
    displayName: 'Bedroom',
    description: 'Beds, nightstands, dressers & more',
    imagePath: `${API_URL}/api/rooms/Room_Bedroom.png`,
  },
];

// Budget presets
export interface BudgetOption {
  value: number;
  label: string;
  description: string;
}

export const BUDGET_OPTIONS: BudgetOption[] = [
  { value: 25000, label: '₹25,000', description: 'Essential pieces' },
  { value: 50000, label: '₹50,000', description: 'Complete styling' },
  { value: 100000, label: '₹1,00,000', description: 'Premium selection' },
  { value: 200000, label: '₹2,00,000+', description: 'Luxury finishes' },
];
