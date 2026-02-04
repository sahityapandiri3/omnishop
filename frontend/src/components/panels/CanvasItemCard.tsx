'use client';

import Image from 'next/image';
import {
  CanvasItem,
  isProductData,
  isWallColorData,
  isWallTextureData,
  isFloorTileData,
  ProductCanvasData,
  WallColorCanvasData,
  WallTextureCanvasData,
  FloorTileCanvasData,
} from '@/hooks/useCanvas';

// Helper to format image source
const formatImageSrc = (src: string | null | undefined): string => {
  if (!src) return '';
  if (src.startsWith('http') || src.startsWith('data:')) return src;
  if (src.startsWith('/9j/') || src.startsWith('iVBOR')) {
    const isJpeg = src.startsWith('/9j/');
    return `data:image/${isJpeg ? 'jpeg' : 'png'};base64,${src}`;
  }
  return src;
};

interface CanvasItemCardProps {
  item: CanvasItem;
  onRemove: () => void;
  onQuantityChange?: (delta: number) => void;
  onRemoveAll?: () => void;
  onViewDetails?: () => void;
  viewMode?: 'grid' | 'list';
}

// Get image URL from a product
function getProductImageUrl(product: any): string {
  if (product.images && product.images.length > 0) {
    const primaryImage = product.images.find((img: any) => img.is_primary) || product.images[0];
    return primaryImage.large_url || primaryImage.medium_url || primaryImage.original_url || '/placeholder-product.jpg';
  }
  return product.image_url || '/placeholder-product.jpg';
}

/**
 * ProductCard in grid view
 */
function ProductGridCard({
  item,
  onRemove,
  onQuantityChange,
  onRemoveAll,
  onViewDetails,
}: CanvasItemCardProps) {
  const data = item.data as ProductCanvasData;
  const product = data.product;
  const qty = item.quantity;
  const imageUrl = getProductImageUrl(product);

  return (
    <div className="relative bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden group">
      <div className="aspect-square bg-neutral-100 dark:bg-neutral-700 relative">
        {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
          <Image src={imageUrl} alt={product.name} fill className="object-cover" unoptimized />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
        {/* Quantity badge */}
        <div className="absolute top-0.5 left-0.5 bg-neutral-800 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
          {qty}x
        </div>
        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1.5">
          <div className="flex items-center gap-1 bg-white rounded-lg px-1.5 py-0.5">
            <button
              onClick={(e) => { e.stopPropagation(); onQuantityChange?.(-1); }}
              className="w-5 h-5 bg-neutral-200 hover:bg-neutral-300 rounded text-xs font-bold flex items-center justify-center"
              title={qty > 1 ? "Decrease quantity" : "Remove"}
            >-</button>
            <span className="w-4 text-center font-semibold text-xs">{qty}</span>
            <button
              onClick={(e) => { e.stopPropagation(); onQuantityChange?.(1); }}
              className="w-5 h-5 bg-neutral-800 hover:bg-neutral-900 text-white rounded text-xs font-bold flex items-center justify-center"
              title="Increase quantity"
            >+</button>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onRemoveAll?.(); }}
            className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] font-medium rounded-lg flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Remove
          </button>
          {onViewDetails && (
            <button
              onClick={(e) => { e.stopPropagation(); onViewDetails(); }}
              className="px-2 py-1 bg-white/90 hover:bg-white text-neutral-800 text-[10px] font-medium rounded-lg flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              View Details
            </button>
          )}
        </div>
      </div>
      <div className="p-1">
        <p className="text-[10px] font-medium text-neutral-900 dark:text-white line-clamp-1">{product.name}</p>
        {product.price && (
          <p className="text-[10px] text-neutral-700 dark:text-neutral-400 font-semibold">
            ₹{((product.price || 0) * qty).toLocaleString()}
            {qty > 1 && <span className="text-neutral-400 font-normal"> (₹{product.price.toLocaleString()} x {qty})</span>}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * ProductCard in list view
 */
function ProductListCard({
  item,
  onRemove,
  onQuantityChange,
  onRemoveAll,
}: CanvasItemCardProps) {
  const data = item.data as ProductCanvasData;
  const product = data.product;
  const qty = item.quantity;
  const imageUrl = getProductImageUrl(product);

  return (
    <div className="flex items-center gap-2 p-2 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg">
      <div className="w-12 h-12 bg-neutral-100 dark:bg-neutral-700 rounded relative flex-shrink-0">
        {imageUrl && imageUrl !== '/placeholder-product.jpg' && imageUrl.startsWith('http') ? (
          <Image src={imageUrl} alt={product.name} fill className="object-cover rounded" unoptimized />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-6 h-6 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
        {qty > 1 && (
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-neutral-800 text-white rounded-full flex items-center justify-center text-[9px] font-bold">
            {qty}
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-medium text-neutral-900 dark:text-white truncate">{product.name}</p>
        <p className="text-[10px] text-neutral-600 dark:text-neutral-400">{product.source}</p>
        {product.price && (
          <p className="text-xs font-semibold text-neutral-700 dark:text-neutral-400">
            ₹{((product.price || 0) * qty).toLocaleString()}
            {qty > 1 && <span className="text-neutral-400 font-normal text-[10px]"> (x{qty})</span>}
          </p>
        )}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onQuantityChange?.(-1)}
          className="w-6 h-6 bg-neutral-200 dark:bg-neutral-700 hover:bg-neutral-300 dark:hover:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded flex items-center justify-center text-sm font-bold"
          title={qty > 1 ? "Decrease quantity" : "Remove"}
        >−</button>
        <span className="w-5 text-center text-xs font-semibold text-neutral-900 dark:text-white">{qty}</span>
        <button
          onClick={() => onQuantityChange?.(1)}
          className="w-6 h-6 bg-neutral-200 dark:bg-neutral-700 hover:bg-neutral-300 dark:hover:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded flex items-center justify-center text-sm font-bold"
          title="Increase quantity"
        >+</button>
      </div>
      <button
        onClick={() => onRemoveAll?.()}
        className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 p-0.5"
        title="Remove all"
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      </button>
    </div>
  );
}

/**
 * WallColorCard — shown in the Wall subsection with hover overlay
 */
function WallColorCard({ item, onRemove, onViewDetails }: CanvasItemCardProps) {
  const data = item.data as WallColorCanvasData;
  const color = data.wallColor;

  return (
    <div className="relative flex items-center gap-3 p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg group overflow-hidden">
      <div
        className="w-16 h-16 rounded-lg flex-shrink-0 border border-neutral-200 dark:border-neutral-600"
        style={{ backgroundColor: color.hex_value }}
      />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">{color.name}</p>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">{color.code}</p>
      </div>
      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] font-medium rounded-lg flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          Remove
        </button>
        {onViewDetails && (
          <button
            onClick={(e) => { e.stopPropagation(); onViewDetails(); }}
            className="px-2 py-1 bg-white/90 hover:bg-white text-neutral-800 text-[10px] font-medium rounded-lg flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            View Details
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * WallTextureCard — shown in the Wall subsection with hover overlay
 */
function WallTextureCard({ item, onRemove, onViewDetails }: CanvasItemCardProps) {
  const data = item.data as WallTextureCanvasData;
  const variant = data.textureVariant;
  const texture = data.texture;

  return (
    <div className="relative flex items-center gap-3 p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg group overflow-hidden">
      <div className="w-16 h-16 rounded-lg flex-shrink-0 border border-neutral-200 dark:border-neutral-600 overflow-hidden">
        <img
          src={variant.image_data
            ? formatImageSrc(variant.image_data)
            : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/wall-textures/variant/${variant.id}/image`
          }
          alt={texture.name}
          className="w-full h-full object-cover"
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">{texture.name}</p>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">{variant.code}</p>
      </div>
      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] font-medium rounded-lg flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          Remove
        </button>
        {onViewDetails && (
          <button
            onClick={(e) => { e.stopPropagation(); onViewDetails(); }}
            className="px-2 py-1 bg-white/90 hover:bg-white text-neutral-800 text-[10px] font-medium rounded-lg flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            View Details
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * FloorTileCard — shown in the Flooring subsection with hover overlay
 */
function FloorTileCard({ item, onRemove, onViewDetails }: CanvasItemCardProps) {
  const data = item.data as FloorTileCanvasData;
  const tile = data.floorTile;
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  return (
    <div className="relative flex items-center gap-3 p-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg group overflow-hidden">
      <div className="w-16 h-16 rounded-lg flex-shrink-0 border border-neutral-200 dark:border-neutral-600 overflow-hidden">
        <img
          src={tile.image_data
            ? formatImageSrc(tile.image_data)
            : `${API_URL}/api/floor-tiles/${tile.id}/image`
          }
          alt={tile.name}
          className="w-full h-full object-cover"
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">{tile.name}</p>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">{tile.size}</p>
        {tile.finish && (
          <p className="text-xs text-neutral-400 dark:text-neutral-500">{tile.finish}</p>
        )}
      </div>
      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] font-medium rounded-lg flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          Remove
        </button>
        {onViewDetails && (
          <button
            onClick={(e) => { e.stopPropagation(); onViewDetails(); }}
            className="px-2 py-1 bg-white/90 hover:bg-white text-neutral-800 text-[10px] font-medium rounded-lg flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            View Details
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * CanvasItemCard — Unified card that renders based on item type and view mode.
 */
export default function CanvasItemCard(props: CanvasItemCardProps) {
  const { item, viewMode = 'grid' } = props;

  if (isWallColorData(item.data)) {
    return <WallColorCard {...props} />;
  }

  if (isWallTextureData(item.data)) {
    return <WallTextureCard {...props} />;
  }

  if (isFloorTileData(item.data)) {
    return <FloorTileCard {...props} />;
  }

  // Product
  if (viewMode === 'list') {
    return <ProductListCard {...props} />;
  }
  return <ProductGridCard {...props} />;
}
