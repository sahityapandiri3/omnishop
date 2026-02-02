'use client';

/**
 * VisualizationControls Component
 *
 * Shared control buttons for visualization:
 * - Undo/Redo
 * - Edit Positions
 * - Clear
 * - Improve Quality
 *
 * Used by both CanvasPanel and Admin Curation page.
 */

import React from 'react';

interface VisualizationControlsProps {
  // Undo/Redo
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;

  // Edit mode
  isEditingPositions: boolean;
  onEnterEditMode: () => void;
  onExitEditMode: () => void;
  isExtractingLayers?: boolean;

  // Clear
  onClear?: () => void;

  // Disabled state
  disabled?: boolean;
}

export function VisualizationControls({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  isEditingPositions,
  onEnterEditMode,
  onExitEditMode,
  isExtractingLayers = false,
  onClear,
  disabled = false,
}: VisualizationControlsProps) {
  return (
    <div className="flex items-center gap-2">
      {/* Edit Positions button */}
      {!isEditingPositions && (
        <button
          onClick={onEnterEditMode}
          disabled={disabled || isExtractingLayers}
          className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white text-xs font-medium transition-colors flex items-center gap-1.5 disabled:cursor-not-allowed"
          title="Edit furniture positions"
        >
          {isExtractingLayers ? (
            <>
              <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Extracting Layers...
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit Positions
            </>
          )}
        </button>
      )}

      {/* Undo button */}
      <button
        onClick={onUndo}
        disabled={!canUndo || isEditingPositions || disabled}
        className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        title="Undo (Remove last added product)"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
        </svg>
      </button>

      {/* Redo button */}
      <button
        onClick={onRedo}
        disabled={!canRedo || isEditingPositions || disabled}
        className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        title="Redo (Add back removed product)"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6" />
        </svg>
      </button>

      {/* Clear button */}
      {onClear && (
        <button
          onClick={onClear}
          disabled={isEditingPositions || disabled}
          className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Clear
        </button>
      )}
    </div>
  );
}

/**
 * ImproveQualityButton Component
 *
 * Separate button for the "Improve Quality" feature.
 */
interface ImproveQualityButtonProps {
  onClick: () => void;
  isImproving: boolean;
  disabled?: boolean;
}

export function ImproveQualityButton({
  onClick,
  isImproving,
  disabled = false,
}: ImproveQualityButtonProps) {
  return (
    <div className="mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700">
      <button
        onClick={onClick}
        disabled={isImproving || disabled}
        className="w-full py-2 px-3 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 disabled:bg-neutral-50 dark:disabled:bg-neutral-900 disabled:cursor-not-allowed text-neutral-600 dark:text-neutral-300 disabled:text-neutral-400 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        title="Re-visualize all products on the original room image to improve quality. Resets undo/redo history."
      >
        {isImproving ? (
          <>
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Improving Quality...
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Improve Quality
          </>
        )}
      </button>
      <p className="text-xs text-neutral-400 dark:text-neutral-500 text-center mt-1">
        Re-renders from original room image. Resets undo/redo.
      </p>
    </div>
  );
}

/**
 * VisualizeButton Component
 *
 * Main visualization button with smart states.
 */
interface VisualizeButtonProps {
  onClick: () => void;
  isVisualizing: boolean;
  isUpToDate: boolean;
  isReady: boolean;
  isEditMode?: boolean;
  editModeLabel?: string;
}

export function VisualizeButton({
  onClick,
  isVisualizing,
  isUpToDate,
  isReady,
  isEditMode = false,
  editModeLabel,
}: VisualizeButtonProps) {
  if (isEditMode && editModeLabel) {
    return (
      <button
        onClick={onClick}
        disabled={isVisualizing}
        className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-neutral-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
      >
        {isVisualizing ? (
          <>
            <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-sm">Processing...</span>
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {editModeLabel}
          </>
        )}
      </button>
    );
  }

  if (isUpToDate) {
    return (
      <button
        disabled
        className="w-full py-3 px-4 bg-neutral-600 dark:bg-neutral-700 text-white font-semibold rounded-lg flex items-center justify-center gap-2 cursor-not-allowed opacity-90"
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
        Up to date
      </button>
    );
  }

  if (isReady) {
    return (
      <button
        onClick={onClick}
        disabled={isVisualizing}
        className="w-full py-3 px-4 bg-gradient-to-r from-neutral-700 to-neutral-800 hover:from-neutral-800 hover:to-neutral-900 disabled:from-neutral-400 disabled:to-neutral-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg"
      >
        {isVisualizing ? (
          <>
            <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-sm">Visualizing...</span>
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
              <path
                fillRule="evenodd"
                d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"
                clipRule="evenodd"
              />
            </svg>
            Visualize Room
          </>
        )}
      </button>
    );
  }

  // Not ready state
  return (
    <button
      disabled
      className="w-full py-3 px-4 bg-neutral-300 dark:bg-neutral-700 text-neutral-500 dark:text-neutral-400 font-semibold rounded-lg cursor-not-allowed flex items-center justify-center gap-2"
    >
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
        <path
          fillRule="evenodd"
          d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"
          clipRule="evenodd"
        />
      </svg>
      Visualize Room
    </button>
  );
}

/**
 * OutdatedWarning Component
 */
interface OutdatedWarningProps {
  visible: boolean;
}

export function OutdatedWarning({ visible }: OutdatedWarningProps) {
  if (!visible) return null;

  return (
    <div className="mb-2 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg flex items-center gap-2">
      <svg className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
      <p className="text-xs text-amber-800 dark:text-amber-200 font-medium">
        Canvas changed - Re-visualize to update
      </p>
    </div>
  );
}

/**
 * TextBasedEditControls Component
 *
 * Controls for text-based position editing mode.
 */
interface TextBasedEditControlsProps {
  instructions: string;
  onInstructionsChange: (value: string) => void;
  onApply: () => void;
  onExit: () => void;
  isProcessing: boolean;
  error?: string | null;
}

export function TextBasedEditControls({
  instructions,
  onInstructionsChange,
  onApply,
  onExit,
  isProcessing,
  error,
}: TextBasedEditControlsProps) {
  return (
    <div className="mt-3 space-y-3">
      <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-700">
        <label className="block text-xs font-medium text-purple-800 dark:text-purple-200 mb-2">
          Describe how to reposition items:
        </label>
        <textarea
          value={instructions}
          onChange={(e) => onInstructionsChange(e.target.value)}
          placeholder="e.g., Move the sofa to the left corner, place the lamp next to the armchair..."
          className="w-full px-3 py-2 text-sm border border-purple-300 dark:border-purple-600 rounded-lg bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white placeholder-neutral-400 focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
          rows={3}
          disabled={isProcessing}
        />
        {error && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onApply}
          disabled={isProcessing || !instructions.trim()}
          className="flex-1 py-2 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2 text-sm disabled:cursor-not-allowed"
        >
          {isProcessing ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Applying...
            </>
          ) : (
            'Apply Changes'
          )}
        </button>
        <button
          onClick={onExit}
          disabled={isProcessing}
          className="py-2 px-4 border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 font-medium rounded-lg transition-colors text-sm disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
