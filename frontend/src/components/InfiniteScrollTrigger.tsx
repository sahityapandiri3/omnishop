'use client';

import { useEffect } from 'react';
import { useInView } from 'react-intersection-observer';

interface InfiniteScrollTriggerProps {
  onLoadMore: () => void;
  hasMore: boolean;
  isLoading: boolean;
  loadedCount?: number;
  totalCount?: number;
  threshold?: number;
  rootMargin?: string;
}

/**
 * Invisible trigger element that detects when scrolled into view.
 * When visible, triggers the onLoadMore callback to fetch the next page.
 *
 * Uses react-intersection-observer for efficient scroll detection.
 *
 * @example
 * ```tsx
 * <InfiniteScrollTrigger
 *   onLoadMore={fetchNextPage}
 *   hasMore={hasNextPage}
 *   isLoading={isFetchingNextPage}
 *   loadedCount={products.length}
 *   totalCount={totalEstimated}
 * />
 * ```
 */
export default function InfiniteScrollTrigger({
  onLoadMore,
  hasMore,
  isLoading,
  loadedCount,
  totalCount,
  threshold = 0.1,
  rootMargin = '100px',
}: InfiniteScrollTriggerProps) {
  const { ref, inView } = useInView({
    threshold,
    rootMargin,
    triggerOnce: false,
  });

  // Trigger load when element comes into view
  useEffect(() => {
    if (inView && hasMore && !isLoading) {
      onLoadMore();
    }
  }, [inView, hasMore, isLoading, onLoadMore]);

  // Don't render anything if no more items
  if (!hasMore && !isLoading) {
    return null;
  }

  return (
    <div ref={ref} className="w-full py-4 flex flex-col items-center justify-center">
      {isLoading ? (
        <div className="flex items-center gap-2 text-gray-500">
          <svg
            className="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span className="text-sm">Loading more products...</span>
        </div>
      ) : hasMore ? (
        <div className="text-xs text-gray-400">
          {loadedCount !== undefined && totalCount !== undefined && totalCount > 0 && (
            <span>
              Showing {loadedCount} of ~{totalCount} products
            </span>
          )}
        </div>
      ) : null}
    </div>
  );
}
