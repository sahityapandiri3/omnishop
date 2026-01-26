'use client';

import { useState, ReactNode } from 'react';
import { ExtendedProduct } from '@/utils/product-transforms';
import { KeywordSearchPanel } from './KeywordSearchPanel';

type SearchMode = 'keyword' | 'ai';

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
}

/**
 * ModeToggle Component
 *
 * Toggle switch between AI Assistant and Keyword Search modes.
 */
function ModeToggle({
  mode,
  onModeChange,
}: {
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
}) {
  return (
    <div className="flex items-center gap-1 p-1 bg-neutral-100 dark:bg-neutral-800 rounded-lg">
      <button
        onClick={() => onModeChange('keyword')}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
          mode === 'keyword'
            ? 'bg-white dark:bg-neutral-700 text-primary-600 dark:text-primary-400 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        Keyword Search
      </button>
      <button
        onClick={() => onModeChange('ai')}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
          mode === 'ai'
            ? 'bg-white dark:bg-neutral-700 text-primary-600 dark:text-primary-400 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
        AI Stylist
      </button>
    </div>
  );
}

/**
 * ProductSearchPanel Component
 *
 * Unified search panel with optional mode toggle between:
 * - AI Assistant: Conversational product discovery
 * - Keyword Search: Direct search with filters
 *
 * For admin pages, use enableModeToggle={false} to show only keyword search.
 * For design pages, use enableModeToggle={true} to allow switching.
 */
export function ProductSearchPanel({
  onAddProduct,
  canvasProducts,
  enableModeToggle = false,
  defaultMode = 'keyword',
  renderAIAssistant,
  compact = false,
  headerContent,
}: ProductSearchPanelProps) {
  const [mode, setMode] = useState<SearchMode>(defaultMode);

  // If AI mode is selected but no AI assistant renderer is provided, fall back to keyword
  const effectiveMode = mode === 'ai' && !renderAIAssistant ? 'keyword' : mode;

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
                Product Discovery
              </h2>
            )}
            {enableModeToggle && (
              <ModeToggle mode={effectiveMode} onModeChange={setMode} />
            )}
          </div>

          {/* Mode Description */}
          {enableModeToggle && (
            <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
              {effectiveMode === 'ai'
                ? 'Chat with our AI to get personalized furniture recommendations'
                : 'Search and filter products directly'}
            </p>
          )}
        </div>
      )}

      {/* Content based on mode */}
      <div className="flex-1 overflow-hidden">
        {effectiveMode === 'keyword' ? (
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
      <div className={`${compact ? 'px-3 py-2' : 'px-4 py-3'} border-b border-neutral-200 dark:border-neutral-700`}>
        <h2 className="font-semibold text-neutral-900 dark:text-white">
          {title}
        </h2>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          Search and filter products to add to your look
        </p>
      </div>

      {/* Search Panel */}
      <div className="flex-1 overflow-hidden">
        <KeywordSearchPanel
          onAddProduct={onAddProduct}
          canvasProducts={canvasProducts}
          compact={compact}
          showSearchInput={true}
        />
      </div>
    </div>
  );
}

export { ModeToggle };
