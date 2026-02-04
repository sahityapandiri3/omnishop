'use client';

import { XMarkIcon } from '@heroicons/react/24/outline';
import { FloorTileFilterOptions } from '@/types/floor-tiles';

interface FloorTileFilterPanelProps {
  filterOptions: FloorTileFilterOptions;
  selectedVendors: string[];
  selectedSizes: string[];
  selectedFinishes: string[];
  selectedLooks: string[];
  selectedColors: string[];
  onToggleVendor: (vendor: string) => void;
  onToggleSize: (size: string) => void;
  onToggleFinish: (finish: string) => void;
  onToggleLook: (look: string) => void;
  onToggleColor: (color: string) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
}

/**
 * MultiSelectChips — a vertical filter section with toggleable chips.
 */
function MultiSelectChips({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (val: string) => void;
}) {
  if (options.length === 0) return null;

  return (
    <div>
      <label className="text-[10px] font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide mb-1.5 block">
        {label}
        {selected.length > 0 && (
          <span className="ml-1 text-neutral-800 dark:text-neutral-200">({selected.length})</span>
        )}
      </label>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => {
          const isActive = selected.includes(opt);
          return (
            <button
              key={opt}
              onClick={() => onToggle(opt)}
              className={`px-2 py-1 text-[11px] rounded-md border transition-colors ${
                isActive
                  ? 'bg-neutral-800 dark:bg-neutral-200 text-white dark:text-neutral-900 border-neutral-800 dark:border-neutral-200'
                  : 'bg-white dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 border-neutral-200 dark:border-neutral-700 hover:border-neutral-400 dark:hover:border-neutral-500'
              }`}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * FloorTileFilterPanel Component
 *
 * Vertical multi-select filter panel with toggleable chips.
 * Shows vendor, size, finish, look, and color filters.
 */
export function FloorTileFilterPanel({
  filterOptions,
  selectedVendors,
  selectedSizes,
  selectedFinishes,
  selectedLooks,
  selectedColors,
  onToggleVendor,
  onToggleSize,
  onToggleFinish,
  onToggleLook,
  onToggleColor,
  onClearFilters,
  hasActiveFilters,
}: FloorTileFilterPanelProps) {
  return (
    <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-700">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400 uppercase tracking-wide">
          Filters
        </span>
        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
          >
            <XMarkIcon className="w-3 h-3" />
            Clear all
          </button>
        )}
      </div>
      <div className="flex flex-col gap-3">
        <MultiSelectChips
          label="Vendor"
          options={filterOptions.vendors}
          selected={selectedVendors}
          onToggle={onToggleVendor}
        />
        <MultiSelectChips
          label="Look"
          options={filterOptions.looks}
          selected={selectedLooks}
          onToggle={onToggleLook}
        />
        <MultiSelectChips
          label="Finish"
          options={filterOptions.finishes}
          selected={selectedFinishes}
          onToggle={onToggleFinish}
        />
        <MultiSelectChips
          label="Size"
          options={filterOptions.sizes}
          selected={selectedSizes}
          onToggle={onToggleSize}
        />
        <MultiSelectChips
          label="Color"
          options={filterOptions.colors}
          selected={selectedColors}
          onToggle={onToggleColor}
        />
      </div>
    </div>
  );
}
