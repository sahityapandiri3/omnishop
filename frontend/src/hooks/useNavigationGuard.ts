import { useEffect, useCallback, useRef } from 'react';

interface UseNavigationGuardOptions {
  enabled?: boolean;
  message?: string;
  onNavigationAttempt?: () => void;
}

/**
 * Hook to prevent accidental navigation away from the page.
 *
 * Blocks:
 * - Mouse back/forward buttons (buttons 3 & 4)
 * - Backspace key outside input fields
 * - Alt+Arrow keyboard shortcuts
 * - Browser back button (popstate)
 * - Page unload (shows browser warning)
 *
 * @param options - Configuration options
 * @param options.enabled - Whether the guard is active (default: true)
 * @param options.message - Custom message for the unload warning
 * @param options.onNavigationAttempt - Callback when navigation is attempted
 */
export function useNavigationGuard(options: UseNavigationGuardOptions = {}) {
  const {
    enabled = true,
    message = 'You have unsaved changes. Are you sure you want to leave?',
    onNavigationAttempt,
  } = options;

  // Track if we've pushed a history entry to prevent duplicate pushes
  const historyPushedRef = useRef(false);

  // Handle beforeunload event (browser refresh/close)
  const handleBeforeUnload = useCallback(
    (e: BeforeUnloadEvent) => {
      if (!enabled) return;

      e.preventDefault();
      // Modern browsers ignore custom messages, but we still need to set returnValue
      e.returnValue = message;
      onNavigationAttempt?.();
      return message;
    },
    [enabled, message, onNavigationAttempt]
  );

  // Handle mouse button events (back/forward buttons)
  const handleMouseDown = useCallback(
    (e: MouseEvent) => {
      if (!enabled) return;

      // Mouse button 3 = back, button 4 = forward
      if (e.button === 3 || e.button === 4) {
        e.preventDefault();
        e.stopPropagation();
        onNavigationAttempt?.();
        console.log('[NavigationGuard] Blocked mouse navigation button');
      }
    },
    [enabled, onNavigationAttempt]
  );

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled) return;

      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' ||
                     target.tagName === 'TEXTAREA' ||
                     target.isContentEditable;

      // Block Backspace outside of input fields (browser back navigation)
      if (e.key === 'Backspace' && !isInput) {
        e.preventDefault();
        onNavigationAttempt?.();
        console.log('[NavigationGuard] Blocked Backspace navigation');
        return;
      }

      // Block Alt+Left/Right Arrow (browser back/forward)
      if (e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
        e.preventDefault();
        onNavigationAttempt?.();
        console.log('[NavigationGuard] Blocked Alt+Arrow navigation');
        return;
      }

      // Block Cmd/Ctrl + [ or ] (browser back/forward on Mac)
      if ((e.metaKey || e.ctrlKey) && (e.key === '[' || e.key === ']')) {
        e.preventDefault();
        onNavigationAttempt?.();
        console.log('[NavigationGuard] Blocked Cmd+[/] navigation');
        return;
      }
    },
    [enabled, onNavigationAttempt]
  );

  // Handle popstate event (browser back button)
  const handlePopState = useCallback(
    (e: PopStateEvent) => {
      if (!enabled) return;

      // Push a new history entry to stay on the page
      window.history.pushState(null, '', window.location.href);
      onNavigationAttempt?.();
      console.log('[NavigationGuard] Blocked popstate navigation');
    },
    [enabled, onNavigationAttempt]
  );

  // Setup and cleanup
  useEffect(() => {
    if (!enabled) return;

    // Push initial history state to enable popstate blocking
    if (!historyPushedRef.current) {
      window.history.pushState(null, '', window.location.href);
      historyPushedRef.current = true;
    }

    // Add event listeners
    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('mousedown', handleMouseDown, { capture: true });
    window.addEventListener('keydown', handleKeyDown, { capture: true });
    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('mousedown', handleMouseDown, { capture: true });
      window.removeEventListener('keydown', handleKeyDown, { capture: true });
      window.removeEventListener('popstate', handlePopState);
    };
  }, [enabled, handleBeforeUnload, handleMouseDown, handleKeyDown, handlePopState]);

  // Reset function to allow navigation
  const allowNavigation = useCallback(() => {
    // Remove the beforeunload handler temporarily
    window.removeEventListener('beforeunload', handleBeforeUnload);
    historyPushedRef.current = false;
  }, [handleBeforeUnload]);

  return { allowNavigation };
}

export default useNavigationGuard;
