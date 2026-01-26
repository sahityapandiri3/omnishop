/**
 * useVisualizationHistory Hook
 *
 * Manages undo/redo history for visualization state.
 *
 * CRITICAL FIX: This hook stores visualizedQuantities in each history entry,
 * which fixes the bug where undo/redo doesn't restore quantity state,
 * causing false "needs revisualization" detection.
 */

import { useState, useCallback, useRef } from 'react';
import {
  VisualizationHistoryEntry,
  VisualizationProduct,
  SerializableHistoryEntry,
  serializeHistoryEntry,
  deserializeHistoryEntry,
} from '@/types/visualization';
import { buildQuantityMap, buildProductIdSet } from '@/utils/visualization-helpers';

export interface UseVisualizationHistoryOptions {
  /** Initial history entries (from saved project) */
  initialHistory?: SerializableHistoryEntry[];

  /** Maximum history size (default: 50) */
  maxHistorySize?: number;

  /** Callback when history changes */
  onHistoryChange?: (history: SerializableHistoryEntry[]) => void;
}

export interface UseVisualizationHistoryReturn {
  // State
  history: VisualizationHistoryEntry[];
  redoStack: VisualizationHistoryEntry[];
  canUndo: boolean;
  canRedo: boolean;
  historyInitialized: boolean;

  // Actions
  /**
   * Push a new state to history.
   * This should be called after each successful visualization.
   */
  pushState: (entry: {
    image: string;
    products: VisualizationProduct[];
  }) => void;

  /**
   * Undo to previous state.
   * Returns the state to restore, or null if nothing to undo.
   *
   * CRITICAL: The returned state includes visualizedQuantities which
   * MUST be restored to prevent false "needs revisualization" detection.
   */
  undo: () => VisualizationHistoryEntry | null;

  /**
   * Redo to next state.
   * Returns the state to restore, or null if nothing to redo.
   *
   * CRITICAL: The returned state includes visualizedQuantities which
   * MUST be restored to prevent false "needs revisualization" detection.
   */
  redo: () => VisualizationHistoryEntry | null;

  /**
   * Reset history (e.g., when room image changes)
   */
  reset: () => void;

  /**
   * Initialize history from existing entries (e.g., loading saved project)
   */
  initializeFromExisting: (history: SerializableHistoryEntry[]) => VisualizationHistoryEntry | null;

  /**
   * Get the current (most recent) state without modifying history
   */
  getCurrentState: () => VisualizationHistoryEntry | null;

  /**
   * Get serializable history for persistence
   */
  getSerializableHistory: () => SerializableHistoryEntry[];
}

export function useVisualizationHistory({
  initialHistory = [],
  maxHistorySize = 50,
  onHistoryChange,
}: UseVisualizationHistoryOptions = {}): UseVisualizationHistoryReturn {
  // Convert initial history from serializable format
  const [history, setHistory] = useState<VisualizationHistoryEntry[]>(() =>
    initialHistory.map(deserializeHistoryEntry)
  );
  const [redoStack, setRedoStack] = useState<VisualizationHistoryEntry[]>([]);
  const [historyInitialized, setHistoryInitialized] = useState(initialHistory.length > 0);

  // Use ref to track if we've notified about history changes (prevent duplicate calls)
  const lastHistoryLengthRef = useRef(history.length);

  // Notify parent when history changes
  const notifyHistoryChange = useCallback((newHistory: VisualizationHistoryEntry[]) => {
    if (onHistoryChange && newHistory.length !== lastHistoryLengthRef.current) {
      lastHistoryLengthRef.current = newHistory.length;
      onHistoryChange(newHistory.map(serializeHistoryEntry));
    }
  }, [onHistoryChange]);

  // Push new state to history
  const pushState = useCallback(({
    image,
    products,
  }: {
    image: string;
    products: VisualizationProduct[];
  }) => {
    const newEntry: VisualizationHistoryEntry = {
      image,
      products: [...products],  // Copy to avoid mutation
      productIds: buildProductIdSet(products),
      visualizedQuantities: buildQuantityMap(products),  // CRITICAL: Store quantities
    };

    setHistory(prev => {
      // Limit history size
      const newHistory = prev.length >= maxHistorySize
        ? [...prev.slice(1), newEntry]
        : [...prev, newEntry];

      notifyHistoryChange(newHistory);
      return newHistory;
    });

    // Clear redo stack when new state is pushed
    setRedoStack([]);
    setHistoryInitialized(true);

    console.log('[useVisualizationHistory] Pushed state with', products.length, 'products');
  }, [maxHistorySize, notifyHistoryChange]);

  // Undo to previous state
  const undo = useCallback((): VisualizationHistoryEntry | null => {
    if (history.length === 0) {
      console.log('[useVisualizationHistory] Cannot undo: no history');
      return null;
    }

    console.log('[useVisualizationHistory] Undoing. Current history size:', history.length);

    // Pop current state from history
    const newHistory = [...history];
    const currentState = newHistory.pop();

    // Push current state to redo stack
    if (currentState) {
      setRedoStack(prev => [...prev, currentState]);
    }

    setHistory(newHistory);
    notifyHistoryChange(newHistory);

    // Return previous state (or null if going back to empty)
    if (newHistory.length > 0) {
      const previousState = newHistory[newHistory.length - 1];
      console.log('[useVisualizationHistory] Returning previous state with', previousState.products.length, 'products');
      console.log('[useVisualizationHistory] State includes visualizedQuantities:', previousState.visualizedQuantities.size, 'entries');
      return previousState;
    }

    console.log('[useVisualizationHistory] No previous state - returning null (will clear visualization)');
    return null;
  }, [history, notifyHistoryChange]);

  // Redo to next state
  const redo = useCallback((): VisualizationHistoryEntry | null => {
    if (redoStack.length === 0) {
      console.log('[useVisualizationHistory] Cannot redo: no redo history');
      return null;
    }

    console.log('[useVisualizationHistory] Redoing. Redo stack size:', redoStack.length);

    // Pop from redo stack
    const newRedoStack = [...redoStack];
    const stateToRestore = newRedoStack.pop();

    if (!stateToRestore) {
      return null;
    }

    // Push to history
    setHistory(prev => {
      const newHistory = [...prev, stateToRestore];
      notifyHistoryChange(newHistory);
      return newHistory;
    });
    setRedoStack(newRedoStack);

    console.log('[useVisualizationHistory] Restored state with', stateToRestore.products.length, 'products');
    console.log('[useVisualizationHistory] State includes visualizedQuantities:', stateToRestore.visualizedQuantities.size, 'entries');
    return stateToRestore;
  }, [redoStack, notifyHistoryChange]);

  // Reset history
  const reset = useCallback(() => {
    console.log('[useVisualizationHistory] Resetting history');
    setHistory([]);
    setRedoStack([]);
    setHistoryInitialized(false);
    notifyHistoryChange([]);
  }, [notifyHistoryChange]);

  // Initialize from existing history
  const initializeFromExisting = useCallback((
    existingHistory: SerializableHistoryEntry[]
  ): VisualizationHistoryEntry | null => {
    if (existingHistory.length === 0) {
      return null;
    }

    console.log('[useVisualizationHistory] Initializing from', existingHistory.length, 'existing entries');
    const convertedHistory = existingHistory.map(deserializeHistoryEntry);
    setHistory(convertedHistory);
    setRedoStack([]);
    setHistoryInitialized(true);

    // Return the last entry so caller can restore state
    const lastEntry = convertedHistory[convertedHistory.length - 1];
    console.log('[useVisualizationHistory] Last entry has', lastEntry.products.length, 'products');
    return lastEntry;
  }, []);

  // Get current state without modifying history
  const getCurrentState = useCallback((): VisualizationHistoryEntry | null => {
    if (history.length === 0) return null;
    return history[history.length - 1];
  }, [history]);

  // Get serializable history for persistence
  const getSerializableHistory = useCallback((): SerializableHistoryEntry[] => {
    return history.map(serializeHistoryEntry);
  }, [history]);

  return {
    // State
    history,
    redoStack,
    canUndo: history.length > 0,
    canRedo: redoStack.length > 0,
    historyInitialized,

    // Actions
    pushState,
    undo,
    redo,
    reset,
    initializeFromExisting,
    getCurrentState,
    getSerializableHistory,
  };
}
