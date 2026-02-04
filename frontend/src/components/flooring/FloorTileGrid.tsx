'use client';

import { useState } from 'react';
import { FloorTile } from '@/types/floor-tiles';
import { FloorTileCard } from './FloorTileCard';
import { FloorTileDetailModal } from './FloorTileDetailModal';

interface FloorTileGridProps {
  tiles: FloorTile[];
  selectedTileId: number | null;
  onSelectTile: (tile: FloorTile) => void;
  isLoading?: boolean;
  error?: string | null;
}

/**
 * FloorTileGrid Component
 *
 * Responsive grid of floor tile cards for the ProductDiscoveryPanel.
 * Matches the WallTextureGrid pattern.
 */
export function FloorTileGrid({
  tiles,
  selectedTileId,
  onSelectTile,
  isLoading = false,
  error = null,
}: FloorTileGridProps) {
  const [detailTile, setDetailTile] = useState<FloorTile | null>(null);
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <svg
            className="animate-spin h-8 w-8 text-neutral-400 mx-auto"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
            Loading floor tiles...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (tiles.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            No floor tiles match the selected filters
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {tiles.map((tile) => (
          <FloorTileCard
            key={tile.id}
            tile={tile}
            isSelected={tile.id === selectedTileId}
            onSelect={onSelectTile}
            onViewDetails={() => setDetailTile(tile)}
          />
        ))}
      </div>

      {/* Floor Tile Detail Modal */}
      {detailTile && (
        <FloorTileDetailModal
          tile={detailTile}
          isOpen={!!detailTile}
          onClose={() => setDetailTile(null)}
          onAddToCanvas={() => {
            onSelectTile(detailTile);
            setDetailTile(null);
          }}
          inCanvas={detailTile.id === selectedTileId}
        />
      )}
    </div>
  );
}
