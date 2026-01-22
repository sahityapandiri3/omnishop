'use client';

import { useEffect } from 'react';

/**
 * Suppresses ResizeObserver loop errors that can crash React apps.
 *
 * The "ResizeObserver loop limit exceeded" and "ResizeObserver loop completed
 * with undelivered notifications" errors are benign - they happen when resize
 * callbacks take too long, but don't affect functionality. However, they can
 * crash React apps if unhandled.
 *
 * This is a known issue with libraries like react-resizable-panels when the
 * viewport changes rapidly (e.g., opening/closing browser DevTools).
 */
export function ResizeObserverErrorSuppressor() {
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      if (
        event.message?.includes('ResizeObserver loop') ||
        event.message?.includes('ResizeObserver loop limit exceeded') ||
        event.message?.includes('ResizeObserver loop completed with undelivered notifications')
      ) {
        event.stopPropagation();
        event.preventDefault();
        return true;
      }
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const message = event.reason?.message || String(event.reason);
      if (message?.includes('ResizeObserver loop')) {
        event.stopPropagation();
        event.preventDefault();
        return true;
      }
    };

    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  return null;
}

export default ResizeObserverErrorSuppressor;
