/**
 * Shared test data for Playwright E2E tests.
 *
 * This module contains sample products, room images, and curated look data
 * that mirror what the real app uses. Keeping test data in one place means
 * if the data shape changes (e.g., a new field is added to products), we
 * only update it here.
 */

// A tiny 1x1 JPEG — just enough bytes to be a valid image file.
// We use this instead of a real room photo to keep tests fast and small.
export const SAMPLE_ROOM_IMAGE_BASE64 =
  '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AKwA//9k=';

export const SAMPLE_ROOM_IMAGE_DATA_URL = `data:image/jpeg;base64,${SAMPLE_ROOM_IMAGE_BASE64}`;

/** Sample products that match the structure the design studio sends to the API. */
export const SAMPLE_PRODUCTS = [
  {
    id: 101,
    name: 'Modern Gray Sofa',
    full_name: 'Modern Gray Sofa - 3 Seater',
    furniture_type: 'sofa',
    quantity: 1,
    image_url: 'https://example.com/sofa.jpg',
    dimensions: { width: 84, depth: 36, height: 32 },
    price: 45000,
    source_website: 'teststore',
  },
  {
    id: 102,
    name: 'Wooden Coffee Table',
    full_name: 'Wooden Coffee Table - Oak',
    furniture_type: 'coffee_table',
    quantity: 1,
    image_url: 'https://example.com/table.jpg',
    dimensions: { width: 48, depth: 24, height: 18 },
    price: 22000,
    source_website: 'teststore',
  },
  {
    id: 103,
    name: 'Floor Lamp',
    full_name: 'Minimalist Floor Lamp - Black',
    furniture_type: 'lamp',
    quantity: 1,
    image_url: 'https://example.com/lamp.jpg',
    dimensions: { width: 12, depth: 12, height: 60 },
    price: 8000,
    source_website: 'teststore',
  },
];

/** A single new product used in incremental-add tests. */
export const SAMPLE_NEW_PRODUCT = {
  id: 104,
  name: 'Accent Chair',
  full_name: 'Accent Chair - Blue Velvet',
  furniture_type: 'accent_chair',
  quantity: 1,
  image_url: 'https://example.com/chair.jpg',
  dimensions: { width: 28, depth: 30, height: 34 },
  price: 18000,
  source_website: 'teststore',
};

/** Wall color option matching the WallColor type in the frontend. */
export const SAMPLE_WALL_COLOR = {
  name: 'Warm Beige',
  code: 'WB-01',
  hex_value: '#F5F5DC',
};

/** Wall texture variant (references a DB record). */
export const SAMPLE_WALL_TEXTURE = {
  texture_variant_id: 42,
  texture_name: 'Exposed Brick',
  texture_type: 'brick',
};

/** Floor tile (references a DB record). */
export const SAMPLE_FLOOR_TILE = {
  tile_id: 17,
  tile_name: 'Italian Marble',
  tile_type: 'marble',
};

/** Sample curated look data for curation tests. */
export const SAMPLE_CURATED_LOOK = {
  id: 1,
  title: 'Modern Living Room',
  description: 'A clean, modern living space with neutral tones.',
  room_type: 'living_room',
  style_labels: ['modern', 'minimalist'],
  products: SAMPLE_PRODUCTS.slice(0, 2),
  tags: ['modern', 'neutral'],
};
