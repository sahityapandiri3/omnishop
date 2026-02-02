'use client';

import { useState, ReactNode } from 'react';
import { ExtendedProduct } from '@/utils/product-transforms';
import { KeywordSearchPanel } from './KeywordSearchPanel';
import { WallColorPanel } from '@/components/wall-colors';
import { WallColor } from '@/types/wall-colors';

type SearchMode = 'keyword' | 'ai' | 'wallColor';

interface ProductSearchPanelProps {
  /** Callback when product is added to canvas */
  onAddProduct: (product: ExtendedProduct) => void;
  /** Products currently in canvas */
  canvasProducts: Array<{ id: string | number; quantity?: number }>;
  /** Whether to enable mode toggle (false = keyword only) */
  enableModeToggle?: boolean;
  /** Default search mode */
  defaultMode?: SearchMode;
  /** Render prop for AI assistant panel */
  renderAIAssistant?: () => ReactNode;
  /** Compact mode for smaller panels */
  compact?: boolean;
  /** Custom header content */
  headerContent?: ReactNode;
  /** Whether to enable wall color tab */
  enableWallColors?: boolean;
  /** Callback when wall color is added to canvas */
  onAddWallColorToCanvas?: (color: WallColor) => void;
  /** Wall color currently on canvas */
  canvasWallColor?: WallColor | null;
  /** Currently selected/previewing wall color */
  selectedWallColor?: WallColor | null;
  /** Callback when wall color is selected (for preview) */
  onSelectWallColor?: (color: WallColor) => void;
}

/**
 * ModeToggle Component
 *
 * Toggle switch between AI Assistant, Keyword Search, and Wall Colors modes.
 */
function ModeToggle({
  mode,
  onModeChange,
  showWallColors = false,
}: {
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  showWallColors?: boolean;
}) {
  return (
    <div className="inline-flex items-center p-0.5 bg-neutral-100 dark:bg-neutral-800 rounded-lg">
      <button
        onClick={() => onModeChange('keyword')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center ${
          mode === 'keyword'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        Furniture
      </button>
      <button
        onClick={() => onModeChange('ai')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center ${
          mode === 'ai'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        AI Stylist
      </button>
      {showWallColors && (
        <button
          onClick={() => onModeChange('wallColor')}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center ${
            mode === 'wallColor'
              ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
              : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
          }`}
        >
          Wall Colors
        </button>
      )}
    </div>
  );
}

/**
 * ProductSearchPanel Component
 *
 * Unified search panel with optional mode toggle between:
 * - Furniture (Keyword Search): Direct search with filters
 * - AI Stylist: Conversational product discovery
 * - Wall Colors: Asian Paints color selection for wall visualization
 *
 * For admin pages, use enableModeToggle={false} to show only keyword search.
 * For design pages, use enableModeToggle={true} and enableWallColors={true}.
 */
export function ProductSearchPanel({
  onAddProduct,
  canvasProducts,
  enableModeToggle = false,
  defaultMode = 'keyword',
  renderAIAssistant,
  compact = false,
  headerContent,
  enableWallColors = false,
  onAddWallColorToCanvas,
  canvasWallColor,
  selectedWallColor,
  onSelectWallColor,
}: ProductSearchPanelProps) {
  const [mode, setMode] = useState<SearchMode>(defaultMode);

  // If AI mode is selected but no AI assistant renderer is provided, fall back to keyword
  // If wall color mode is selected but no handler is provided, fall back to keyword
  let effectiveMode = mode;
  if (mode === 'ai' && !renderAIAssistant) {
    effectiveMode = 'keyword';
  }
  if (mode === 'wallColor' && !onAddWallColorToCanvas) {
    effectiveMode = 'keyword';
  }

  const getModeDescription = () => {
    switch (effectiveMode) {
      case 'ai':
        return 'Chat with our AI to get personalized furniture recommendations';
      case 'wallColor':
        return 'Browse and apply wall paint colors to your room';
      default:
        return 'Search and filter furniture to add to your design';
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header with Mode Toggle */}
      {(enableModeToggle || headerContent) && (
        <div className={`${compact ? 'px-3 py-2' : 'px-4 py-3'} border-b border-neutral-200 dark:border-neutral-700`}>
          <div className="flex items-center justify-between">
            {headerContent ? (
              headerContent
            ) : (
              <h2 className="font-semibold text-neutral-900 dark:text-white">
                {effectiveMode === 'wallColor' ? 'Wall Colors' : 'Product Discovery'}
              </h2>
            )}
            {enableModeToggle && (
              <ModeToggle
                mode={effectiveMode}
                onModeChange={setMode}
                showWallColors={enableWallColors && !!onAddWallColorToCanvas}
              />
            )}
          </div>

          {/* Mode Description */}
          {enableModeToggle && (
            <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
              {getModeDescription()}
            </p>
          )}
        </div>
      )}

      {/* Content based on mode */}
      <div className="flex-1 overflow-hidden">
        {effectiveMode === 'wallColor' && onAddWallColorToCanvas ? (
          <WallColorPanel
            onAddToCanvas={onAddWallColorToCanvas}
            canvasWallColor={canvasWallColor}
            selectedColor={selectedWallColor}
            onSelectColor={onSelectWallColor}
          />
        ) : effectiveMode === 'keyword' ? (
          <KeywordSearchPanel
            onAddProduct={onAddProduct}
            canvasProducts={canvasProducts}
            compact={compact}
            showSearchInput={true}
          />
        ) : renderAIAssistant ? (
          renderAIAssistant()
        ) : (
          <KeywordSearchPanel
            onAddProduct={onAddProduct}
            canvasProducts={canvasProducts}
            compact={compact}
            showSearchInput={true}
          />
        )}
      </div>
    </div>
  );
}

/**
 * KeywordOnlySearchPanel Component
 *
 * Simplified wrapper for admin pages that only need keyword search.
 * No mode toggle, just search with filters.
 */
export function KeywordOnlySearchPanel({
  onAddProduct,
  canvasProducts,
  title = 'Product Discovery',
  compact = false,
}: {
  onAddProduct: (product: ExtendedProduct) => void;
  canvasProducts: Array<{ id: string | number; quantity?: number }>;
  title?: string;
  compact?: boolean;
}) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className={`flex-shrink-0 ${compact ? 'px-3 py-2' : 'px-4 py-3'} border-b border-neutral-200 dark:border-neutral-700`}>
        <h2 className="font-semibold text-neutral-900 dark:text-white">
          {title}
        </h2>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          Search and filter products to add to your look
        </p>
      </div>

      {/* Search Panel - flex-1 with min-h-0 to allow proper flex shrinking */}
      <div className="flex-1 min-h-0">
        <KeywordSearchPanel
          onAddProduct={onAddProduct}
          canvasProducts={canvasProducts}
          compact={compact}
          showSearchInput={true}
          showResultsInline={true}
        />
      </div>
    </div>
  );
}

export { ModeToggle };
