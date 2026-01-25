import { useInfiniteQuery } from '@tanstack/react-query';
import {
  PaginationCursor,
  PaginatedProductsRequest,
  PaginatedProductsResponse,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface UsePaginatedProductsOptions {
  sessionId: string;
  categoryId: string;
  styleAttributes?: {
    style_keywords?: string[];
    colors?: string[];
    materials?: string[];
    size_keywords?: string[];
  };
  budgetMin?: number;
  budgetMax?: number;
  selectedStores?: string[];
  pageSize?: number;
  enabled?: boolean;
  /**
   * Search query for vector similarity ranking (e.g., "accent chairs").
   * When provided, products are ranked by embedding similarity instead of keyword matching.
   * This ensures semantic relevance - e.g., actual accent chairs rank higher than office chairs.
   */
  semanticQuery?: string;
}

/**
 * Hook for fetching paginated products with infinite scroll support.
 * Uses cursor-based pagination for efficient and consistent ordering.
 *
 * @example
 * ```tsx
 * const {
 *   data,
 *   fetchNextPage,
 *   hasNextPage,
 *   isFetchingNextPage,
 *   isLoading,
 * } = usePaginatedProducts({
 *   sessionId: 'abc123',
 *   categoryId: 'sofas',
 *   enabled: isExpanded,
 * });
 *
 * // Flatten all pages into a single array
 * const allProducts = data?.pages.flatMap(page => page.products) ?? [];
 * ```
 */
export function usePaginatedProducts({
  sessionId,
  categoryId,
  styleAttributes,
  budgetMin,
  budgetMax,
  selectedStores,
  pageSize = 24,
  enabled = true,
  semanticQuery,
}: UsePaginatedProductsOptions) {
  return useInfiniteQuery<PaginatedProductsResponse, Error>({
    queryKey: [
      'paginatedProducts',
      sessionId,
      categoryId,
      styleAttributes,
      budgetMin,
      budgetMax,
      selectedStores,
      semanticQuery,
    ],
    queryFn: async ({ pageParam }): Promise<PaginatedProductsResponse> => {
      const cursor = pageParam as PaginationCursor | undefined;

      const requestBody: PaginatedProductsRequest = {
        category_id: categoryId,
        page_size: pageSize,
        cursor: cursor || null,
        style_attributes: styleAttributes,
        budget_min: budgetMin,
        budget_max: budgetMax,
        selected_stores: selectedStores,
        semantic_query: semanticQuery,
      };

      const response = await fetch(
        `${API_URL}/api/chat/sessions/${sessionId}/products/paginated`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Failed to fetch products: ${response.status}`);
      }

      return response.json();
    },
    getNextPageParam: (lastPage) => {
      // Return the cursor for the next page, or undefined if no more pages
      return lastPage.has_more ? lastPage.next_cursor : undefined;
    },
    initialPageParam: undefined,
    enabled: enabled && !!sessionId && !!categoryId,
    staleTime: 5 * 60 * 1000, // Consider data stale after 5 minutes
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes (formerly cacheTime)
  });
}

/**
 * Helper to get total estimated count from paginated query result
 */
export function getTotalEstimated(
  data: { pages: PaginatedProductsResponse[] } | undefined
): number {
  return data?.pages[0]?.total_estimated ?? 0;
}

/**
 * Helper to flatten all pages into a single product array
 */
export function flattenPaginatedProducts(
  data: { pages: PaginatedProductsResponse[] } | undefined
): any[] {
  return data?.pages.flatMap((page) => page.products) ?? [];
}
