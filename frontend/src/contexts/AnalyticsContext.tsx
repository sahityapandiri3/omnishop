'use client';

import React, { createContext, useContext } from 'react';
import { useAnalytics, TrackEventFn } from '@/hooks/useAnalytics';

/**
 * Analytics Context — makes the trackEvent function available to every
 * component in the tree without prop-drilling.
 *
 * Tech tip: React Context is a dependency-injection mechanism. By wrapping
 * the app in AnalyticsProvider, any child component can call useTrackEvent()
 * to fire analytics events without importing the hook directly.
 */

interface AnalyticsContextValue {
  trackEvent: TrackEventFn;
}

const AnalyticsContext = createContext<AnalyticsContextValue | null>(null);

export function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  const { trackEvent } = useAnalytics();

  return (
    <AnalyticsContext.Provider value={{ trackEvent }}>
      {children}
    </AnalyticsContext.Provider>
  );
}

export function useTrackEvent(): TrackEventFn {
  const ctx = useContext(AnalyticsContext);
  if (!ctx) {
    // Return a no-op if used outside the provider (e.g. in tests)
    return () => {};
  }
  return ctx.trackEvent;
}
