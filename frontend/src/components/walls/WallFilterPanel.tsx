'use client';

import { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { WallType } from '@/types/wall-textures';
import {
  WallColorFamily,
  WALL_COLOR_FAMILY_LABELS,
  WALL_COLOR_FAMILY_ORDER,
} from '@/types/wall-colors';

interface WallFilterPanelProps {
  /** Current wall type */
  wallType: WallType;
  /** Callback when wall type changes */
  onWallTypeChange: (type: WallType) => void;
  /** Selected color families */
  selectedFamilies: WallColorFamily[];
  /** Toggle color family selection */
  onToggleFamily: (family: WallColorFamily) => void;
  /** Selected texture brands */
  selectedBrands: string[];
  /** Available brands */
  availableBrands: Array<{ name: string; texture_count: number }>;
  /** Toggle brand selection */
  onToggleBrand: (brand: string) => void;
  /** Clear all filters */
  onClearFilters: () => void;
  /** Whether filters are active */
  hasActiveFilters: boolean;
  /** Compact mode */
  compact?: boolean;
}

/**
 * WallTypeToggle Component
 *
 * Toggle switch between Color and Textured wall types.
 */
function WallTypeToggle({
  value,
  onChange,
}: {
  value: WallType;
  onChange: (type: WallType) => void;
}) {
  return (
    <div className="flex items-center gap-1 p-0.5 bg-neutral-100 dark:bg-neutral-800 rounded-lg">
      <button
        onClick={() => onChange('color')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
          value === 'color'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        Color
      </button>
      <button
        onClick={() => onChange('textured')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
          value === 'textured'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        Textured
      </button>
    </div>
  );
}

/**
 * CollapsibleFilter Component
 *
 * Generic collapsible filter section with checkbox list.
 */
function CollapsibleFilter<T extends string>({
  title,
  items,
  selectedItems,
  onToggle,
  getLabel,
  getCount,
  defaultExpanded = false,
}: {
  title: string;
  items: T[];
  selectedItems: T[];
  onToggle: (item: T) => void;
  getLabel: (item: T) => string;
  getCount?: (item: T) => number;
  defaultExpanded?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const selectedCount = selectedItems.length;

  return (
    <div className="border-b border-neutral-200 dark:border-neutral-700 last:border-b-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDownIcon className="w-4 h-4 text-neutral-400" />
          ) : (
            <ChevronRightIcon className="w-4 h-4 text-neutral-400" />
          )}
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
            {title}
          </span>
          {selectedCount > 0 && (
            <span className="text-xs bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded-full">
              {selectedCount}
            </span>
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-3 pb-2.5 space-y-1">
          {items.map((item) => {
            const isSelected = selectedItems.includes(item);
            const count = getCount?.(item);

            return (
              <label
                key={item}
                className="flex items-center gap-2 py-1 cursor-pointer group"
              >
                <div
                  className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                    isSelected
                      ? 'bg-indigo-500 border-indigo-500'
                      : 'border-neutral-300 dark:border-neutral-600 group-hover:border-indigo-400'
                  }`}
                  onClick={() => onToggle(item)}
                >
                  {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                </div>
                <span
                  className="text-sm text-neutral-600 dark:text-neutral-400 flex-1"
                  onClick={() => onToggle(item)}
                >
                  {getLabel(item)}
                </span>
                {count !== undefined && count > 0 && (
                  <span className="text-xs text-neutral-400">{count}</span>
                )}
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * WallFilterPanel Component
 *
 * Filter panel for walls mode in Panel 1.
 * Shows Color/Textured toggle and relevant filters:
 * - Color mode: Color family checkboxes
 * - Textured mode: Brand and texture type checkboxes
 */
export function WallFilterPanel({
  wallType,
  onWallTypeChange,
  selectedFamilies,
  onToggleFamily,
  selectedBrands,
  availableBrands,
  onToggleBrand,
  onClearFilters,
  hasActiveFilters,
  compact = false,
}: WallFilterPanelProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Wall Type Toggle */}
      <div className={`${compact ? 'p-2' : 'p-3'} border-b border-neutral-200 dark:border-neutral-700`}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">
            Wall Type
          </span>
          {hasActiveFilters && (
            <button
              onClick={onClearFilters}
              className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
            >
              <XMarkIcon className="w-3 h-3" />
              Clear
            </button>
          )}
        </div>
        <WallTypeToggle value={wallType} onChange={onWallTypeChange} />
      </div>

      {/* Filters */}
      <div className="flex-1 overflow-y-auto">
        {wallType === 'color' ? (
          /* Color Family Filters */
          <CollapsibleFilter
            title="Color Family"
            items={WALL_COLOR_FAMILY_ORDER}
            selectedItems={selectedFamilies}
            onToggle={onToggleFamily}
            getLabel={(family) => WALL_COLOR_FAMILY_LABELS[family]}
            defaultExpanded={true}
          />
        ) : (
          /* Texture Filters - Brand only */
          availableBrands.length > 0 && (
            <CollapsibleFilter
              title="Brand"
              items={availableBrands.map((b) => b.name)}
              selectedItems={selectedBrands}
              onToggle={onToggleBrand}
              getLabel={(brand) => brand}
              getCount={(brand) =>
                availableBrands.find((b) => b.name === brand)?.texture_count ?? 0
              }
              defaultExpanded={true}
            />
          )
        )}
      </div>
    </div>
  );
}

export { WallTypeToggle };
