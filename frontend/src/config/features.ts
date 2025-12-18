// This file is used to control the feature flags for the application.
// It is used to control the UI versions and experimental features.
// It is also used to control the API endpoints and the data flow.
// It is also used to control the state management and the data flow.
// It is also used to control the UI versions and the data flow.
// It is also used to control the UI versions and the data flow.



/**
 * Feature flags for controlling UI versions and experimental features
 */

export interface FeatureFlags {
  // UI Version Control
  useNewUI: boolean;
  showUIToggle: boolean; // Show toggle button to switch between UIs

  // Phase 1 Features
  enableThreePanelLayout: boolean;
  enableCanvasPanel: boolean;
  enableClickToMove: boolean;

  // Phase 2 Features (future)
  enableProductSwap: boolean;
  enableSaveShare: boolean;
  enableHistory: boolean;
  enableBudgetTracker: boolean;
}

// Default feature flags
const defaultFlags: FeatureFlags = {
  // UI Version
  useNewUI: true, // Set to false to use old UI by default
  showUIToggle: false, // Disabled - was blocking Visualize button on mobile

  // Phase 1
  enableThreePanelLayout: true,
  enableCanvasPanel: true,
  enableClickToMove: true,

  // Phase 2 (disabled for now)
  enableProductSwap: false,
  enableSaveShare: false,
  enableHistory: false,
  enableBudgetTracker: false,
};

/**
 * Get feature flags from environment or localStorage
 */
export function getFeatureFlags(): FeatureFlags {
  // Check localStorage for overrides (useful for testing)
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('featureFlags');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        return { ...defaultFlags, ...parsed };
      } catch (e) {
        console.warn('Failed to parse feature flags from localStorage:', e);
      }
    }
  }

  // Return defaults
  return defaultFlags;
}

/**
 * Update feature flags in localStorage
 */
export function setFeatureFlags(flags: Partial<FeatureFlags>): void {
  if (typeof window !== 'undefined') {
    const current = getFeatureFlags();
    const updated = { ...current, ...flags };
    localStorage.setItem('featureFlags', JSON.stringify(updated));

    // Reload page to apply changes
    window.location.reload();
  }
}

/**
 * Toggle new UI on/off
 */
export function toggleNewUI(): void {
  const flags = getFeatureFlags();
  setFeatureFlags({ useNewUI: !flags.useNewUI });
}

/**
 * Reset feature flags to defaults
 */
export function resetFeatureFlags(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('featureFlags');
    window.location.reload();
  }
}

// Export singleton instance
export const featureFlags = getFeatureFlags();
