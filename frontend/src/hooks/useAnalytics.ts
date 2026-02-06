'use client';

import { useEffect, useRef, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { analyticsAPI } from '@/utils/api';

/**
 * Event batching hook for first-party analytics.
 *
 * Tech tip: Instead of sending one HTTP request per event (which would flood
 * the server), we collect events in an in-memory queue and flush them in a
 * single batch request every 5 seconds. On page unload we use
 * navigator.sendBeacon() which is a browser API specifically designed to
 * reliably deliver data even when the page is being closed.
 */

interface QueuedEvent {
  event_type: string;
  step_name?: string;
  event_data?: Record<string, unknown>;
  page_url?: string;
  timestamp: string;
}

export type TrackEventFn = (
  eventType: string,
  stepName?: string,
  eventData?: Record<string, unknown>
) => void;

const FLUSH_INTERVAL_MS = 5_000;
const ANALYTICS_ENABLED = process.env.NEXT_PUBLIC_ENABLE_ANALYTICS !== 'false';

export function useAnalytics() {
  const pathname = usePathname();
  const { user } = useAuth();
  const queueRef = useRef<QueuedEvent[]>([]);
  const pageEnteredAtRef = useRef<number>(Date.now());
  const prevPathnameRef = useRef<string | null>(null);

  // --- flush helper ---
  const flush = useCallback(() => {
    const events = queueRef.current.splice(0);
    if (events.length === 0) return;

    // Fire-and-forget: analytics should never block UI
    analyticsAPI.trackBatch(events).catch(() => {
      // silently discard — analytics failures must not affect the user
    });
  }, []);

  // --- sendBeacon flush for page unload ---
  const beaconFlush = useCallback(() => {
    const events = queueRef.current.splice(0);
    if (events.length === 0) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const url = `${apiUrl}/api/analytics/track/batch`;
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

    // sendBeacon doesn't support custom headers, so we include
    // a simple JSON blob. The backend accepts optional auth via JWT
    // in Authorization header; for beacon we'll rely on server-side
    // user association if the batch was sent before unload.
    const body = JSON.stringify({ events });
    const blob = new Blob([body], { type: 'application/json' });
    navigator.sendBeacon(url, blob);
  }, []);

  // --- trackEvent function ---
  const trackEvent: TrackEventFn = useCallback(
    (eventType: string, stepName?: string, eventData?: Record<string, unknown>) => {
      if (!ANALYTICS_ENABLED) return;

      const event: QueuedEvent = {
        event_type: eventType,
        step_name: stepName,
        event_data: eventData,
        page_url: typeof window !== 'undefined' ? window.location.pathname : undefined,
        timestamp: new Date().toISOString(),
      };
      queueRef.current.push(event);
    },
    []
  );

  // --- auto-track page.view on route change ---
  useEffect(() => {
    if (!ANALYTICS_ENABLED || !pathname) return;

    // Avoid duplicate tracking of the same pathname
    if (prevPathnameRef.current === pathname) return;

    // Track page.exit for the previous page
    if (prevPathnameRef.current !== null) {
      const timeOnPage = Date.now() - pageEnteredAtRef.current;
      trackEvent('page.exit', undefined, {
        path: prevPathnameRef.current,
        time_on_page_ms: timeOnPage,
      });
    }

    // Track page.view for the new page
    trackEvent('page.view', undefined, {
      path: pathname,
      referrer: typeof document !== 'undefined' ? document.referrer : '',
      title: typeof document !== 'undefined' ? document.title : '',
    });

    prevPathnameRef.current = pathname;
    pageEnteredAtRef.current = Date.now();
  }, [pathname, trackEvent]);

  // --- periodic flush + cleanup ---
  useEffect(() => {
    if (!ANALYTICS_ENABLED) return;

    const interval = setInterval(flush, FLUSH_INTERVAL_MS);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // Track page.exit when tab is hidden
        if (prevPathnameRef.current) {
          const timeOnPage = Date.now() - pageEnteredAtRef.current;
          trackEvent('page.exit', undefined, {
            path: prevPathnameRef.current,
            time_on_page_ms: timeOnPage,
          });
        }
        beaconFlush();
      }
    };

    const handleBeforeUnload = () => {
      if (prevPathnameRef.current) {
        const timeOnPage = Date.now() - pageEnteredAtRef.current;
        trackEvent('page.exit', undefined, {
          path: prevPathnameRef.current,
          time_on_page_ms: timeOnPage,
        });
      }
      beaconFlush();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Flush any remaining events on unmount
      flush();
    };
  }, [flush, beaconFlush, trackEvent]);

  return { trackEvent };
}
