'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { adminCuratedAPI, AdminCuratedLookSummary } from '@/utils/api';
import { ProtectedRoute } from '@/components/ProtectedRoute';

type RoomType = 'all' | 'living_room' | 'bedroom';
type StyleOption = 'modern' | 'modern_luxury' | 'indian_contemporary';
type BudgetOption = 'all' | 'pocket_friendly' | 'mid_tier' | 'premium' | 'luxury';

// Session storage keys for scroll position and page
const SCROLL_POSITION_KEY = 'admin_curated_scroll_position';
const CURRENT_PAGE_KEY = 'admin_curated_current_page';

function AdminCuratedLooksContent() {
  const router = useRouter();
  const [looks, setLooks] = useState<AdminCuratedLookSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'published' | 'draft'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [roomTypeFilter, setRoomTypeFilter] = useState<RoomType>('all');
  const [selectedStyles, setSelectedStyles] = useState<StyleOption[]>([]);
  const [budgetFilter, setBudgetFilter] = useState<BudgetOption>('all');
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const hasRestoredScroll = useRef(false);
  const isInitialized = useRef(false);

  // Initialize page from session storage (synchronous to avoid double fetch)
  const getInitialPage = () => {
    if (typeof window === 'undefined') return 1;
    const savedPage = sessionStorage.getItem(CURRENT_PAGE_KEY);
    if (savedPage) {
      const pageNum = parseInt(savedPage, 10);
      if (pageNum > 0) return pageNum;
    }
    return 1;
  };

  const [page, setPage] = useState(getInitialPage);

  // Fetch looks when page or filter changes
  useEffect(() => {
    fetchLooks(page);
    isInitialized.current = true;
  }, [page, filter]);

  const fetchLooks = async (pageNum: number) => {
    try {
      setLoading(true);

      const params: { is_published?: boolean; page?: number; size?: number } = {
        page: pageNum,
        size: 20,
      };
      if (filter === 'published') params.is_published = true;
      if (filter === 'draft') params.is_published = false;

      const response = await adminCuratedAPI.list(params);

      setLooks(response.items);
      setTotalPages(response.pages);
      setTotalItems(response.total);
      setError(null);
    } catch (err) {
      console.error('Error fetching looks:', err);
      setError('Failed to load curated looks');
    } finally {
      setLoading(false);
    }
  };

  // Handle filter change - reset to page 1
  const handleFilterChange = (newFilter: 'all' | 'published' | 'draft') => {
    setFilter(newFilter);
    setPage(1);
    sessionStorage.removeItem(CURRENT_PAGE_KEY);
    hasRestoredScroll.current = false;
  };

  const roomTypes: { value: RoomType; label: string }[] = [
    { value: 'all', label: 'All Rooms' },
    { value: 'living_room', label: 'Living Room' },
    { value: 'bedroom', label: 'Bedroom' },
  ];

  const styleOptions: { value: StyleOption; label: string }[] = [
    { value: 'modern', label: 'Modern' },
    { value: 'modern_luxury', label: 'Modern Luxury' },
    { value: 'indian_contemporary', label: 'Indian Contemporary' },
  ];

  const budgetOptions: { value: BudgetOption; label: string }[] = [
    { value: 'all', label: 'All Budgets' },
    { value: 'pocket_friendly', label: '< ₹2L' },
    { value: 'mid_tier', label: '₹2L – 8L' },
    { value: 'premium', label: '₹8L – 15L' },
    { value: 'luxury', label: '₹15L+' },
  ];

  const toggleStyle = (style: StyleOption) => {
    setSelectedStyles(prev =>
      prev.includes(style)
        ? prev.filter(s => s !== style)
        : [...prev, style]
    );
  };

  // Handle page change
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
      sessionStorage.setItem(CURRENT_PAGE_KEY, newPage.toString());
      window.scrollTo(0, 0);
      hasRestoredScroll.current = true; // Don't restore scroll when changing pages
    }
  };

  // Restore scroll position after looks are loaded
  useEffect(() => {
    if (!loading && looks.length > 0 && !hasRestoredScroll.current) {
      const savedPosition = sessionStorage.getItem(SCROLL_POSITION_KEY);
      if (savedPosition) {
        const position = parseInt(savedPosition, 10);
        // Use setTimeout + requestAnimationFrame to ensure DOM is fully ready
        setTimeout(() => {
          requestAnimationFrame(() => {
            window.scrollTo(0, position);
          });
        }, 50);
        // Clear the saved position after restoring
        sessionStorage.removeItem(SCROLL_POSITION_KEY);
      }
      hasRestoredScroll.current = true;
    }
  }, [loading, looks.length]);

  // Save scroll position before navigating to a look detail page
  const handleLookClick = useCallback((lookId: number) => {
    // Save current scroll position and page
    sessionStorage.setItem(SCROLL_POSITION_KEY, window.scrollY.toString());
    sessionStorage.setItem(CURRENT_PAGE_KEY, page.toString());
    router.push(`/admin/curated/${lookId}`);
  }, [router, page]);

  const handlePublish = async (lookId: number) => {
    try {
      await adminCuratedAPI.publish(lookId);
      // Update local state instead of refetching
      setLooks(prev => prev.map(look =>
        look.id === lookId ? { ...look, is_published: true } : look
      ));
    } catch (err) {
      console.error('Error publishing look:', err);
    }
  };

  const handleUnpublish = async (lookId: number) => {
    try {
      await adminCuratedAPI.unpublish(lookId);
      // Update local state instead of refetching
      setLooks(prev => prev.map(look =>
        look.id === lookId ? { ...look, is_published: false } : look
      ));
    } catch (err) {
      console.error('Error unpublishing look:', err);
    }
  };

  const handleDelete = async (lookId: number) => {
    if (!confirm('Are you sure you want to delete this curated look?')) return;

    try {
      await adminCuratedAPI.delete(lookId);
      // Remove from local state instead of refetching
      setLooks(prev => prev.filter(look => look.id !== lookId));
      // If this was the last item on the page, go to previous page
      if (looks.length === 1 && page > 1) {
        handlePageChange(page - 1);
      }
    } catch (err) {
      console.error('Error deleting look:', err);
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = [];
    const maxVisible = 5;

    if (totalPages <= maxVisible + 2) {
      // Show all pages
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (page > 3) {
        pages.push('ellipsis');
      }

      // Show pages around current page
      const start = Math.max(2, page - 1);
      const end = Math.min(totalPages - 1, page + 1);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (page < totalPages - 2) {
        pages.push('ellipsis');
      }

      // Always show last page
      pages.push(totalPages);
    }

    return pages;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Link href="/admin" className="text-gray-500 hover:text-gray-700">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">Curated Looks</h1>
            </div>
            <p className="text-gray-600">Create and manage pre-designed room looks</p>
          </div>
          <Link
            href="/admin/curated/new"
            className="inline-flex items-center px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Create New Look
          </Link>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          {/* Search Bar */}
          <div className="relative mb-4">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-10 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Room Type + Budget Filter Row */}
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            {/* Room Type Filter */}
            <div className="bg-gray-50 rounded-lg p-1 inline-flex gap-1 border border-gray-200">
              {roomTypes.map((type) => (
                <button
                  key={type.value}
                  onClick={() => setRoomTypeFilter(type.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    roomTypeFilter === type.value
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {type.label}
                </button>
              ))}
            </div>

            {/* Budget Filter Dropdown */}
            <select
              value={budgetFilter}
              onChange={(e) => setBudgetFilter(e.target.value as BudgetOption)}
              className="bg-gray-50 rounded-lg pl-3 pr-8 py-1.5 text-xs font-medium border border-gray-200 text-gray-600 hover:border-gray-300 focus:ring-2 focus:ring-purple-500 focus:border-transparent cursor-pointer"
            >
              {budgetOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* Style Filter - Multi-select capsules */}
          <div className="flex flex-wrap gap-2 mb-4">
            {styleOptions.map((style) => {
              const isSelected = selectedStyles.includes(style.value);
              return (
                <button
                  key={style.value}
                  onClick={() => toggleStyle(style.value)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all border ${
                    isSelected
                      ? 'bg-purple-100 text-purple-700 border-purple-300'
                      : 'bg-white text-gray-500 border-gray-200 hover:border-gray-300 hover:text-gray-700'
                  }`}
                >
                  {isSelected && (
                    <svg className="w-3 h-3 inline mr-1 -ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                  {style.label}
                </button>
              );
            })}
            {selectedStyles.length > 0 && (
              <button
                onClick={() => setSelectedStyles([])}
                className="px-2 py-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {/* Status Filter Row */}
          <div className="flex items-center justify-between pt-3 border-t border-gray-100">
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-gray-700">Filter:</span>
              <div className="flex gap-2">
                {(['all', 'published', 'draft'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => handleFilterChange(f)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      filter === f
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            {totalItems > 0 && (
              <span className="text-sm text-gray-500">
                {totalItems} look{totalItems !== 1 ? 's' : ''} total
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-600">{error}</p>
            <button
              onClick={() => fetchLooks(page)}
              className="mt-4 text-purple-600 hover:text-purple-700 font-medium"
            >
              Try Again
            </button>
          </div>
        ) : looks.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No curated looks yet</h3>
            <p className="text-gray-600 mb-4">Get started by creating your first curated look</p>
            <Link
              href="/admin/curated/new"
              className="inline-flex items-center px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
            >
              Create First Look
            </Link>
          </div>
        ) : (() => {
          const filteredLooks = looks.filter(look => {
            // Search filter
            const matchesSearch = !searchQuery ||
              look.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
              look.style_theme?.toLowerCase().includes(searchQuery.toLowerCase());

            // Room type filter
            const matchesRoomType = roomTypeFilter === 'all' || look.room_type === roomTypeFilter;

            // Style filter (multi-select)
            const matchesStyle = selectedStyles.length === 0 ||
              selectedStyles.some(style => look.style_theme?.toLowerCase().includes(style.replace('_', ' ')));

            // Budget filter (based on total_price)
            let matchesBudget = budgetFilter === 'all';
            if (!matchesBudget) {
              const price = look.total_price;
              if (budgetFilter === 'pocket_friendly') matchesBudget = price < 200000;
              else if (budgetFilter === 'mid_tier') matchesBudget = price >= 200000 && price < 800000;
              else if (budgetFilter === 'premium') matchesBudget = price >= 800000 && price < 1500000;
              else if (budgetFilter === 'luxury') matchesBudget = price >= 1500000;
            }

            return matchesSearch && matchesRoomType && matchesStyle && matchesBudget;
          });

          const hasActiveFilters = searchQuery || roomTypeFilter !== 'all' || selectedStyles.length > 0 || budgetFilter !== 'all';

          if (filteredLooks.length === 0) {
            return (
              <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
                <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No matching looks</h3>
                <p className="text-gray-600 mb-4">
                  {searchQuery ? `No looks found for "${searchQuery}"` : 'No looks match the selected filters'}
                </p>
                {hasActiveFilters && (
                  <button
                    onClick={() => {
                      setSearchQuery('');
                      setRoomTypeFilter('all');
                      setSelectedStyles([]);
                      setBudgetFilter('all');
                    }}
                    className="text-purple-600 hover:text-purple-700 font-medium"
                  >
                    Clear all filters
                  </button>
                )}
              </div>
            );
          }

          return (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredLooks.map((look) => (
                <div
                  key={look.id}
                  className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
                >
                  {/* Clickable Image */}
                  <div onClick={() => handleLookClick(look.id)} className="block cursor-pointer">
                    <div className="aspect-[16/10] relative bg-gray-100 cursor-pointer group">
                      {look.visualization_image ? (
                        <Image
                          src={look.visualization_image.startsWith('data:') ? look.visualization_image : `data:image/png;base64,${look.visualization_image}`}
                          alt={look.title}
                          fill
                          className="object-cover group-hover:scale-105 transition-transform duration-300"
                          unoptimized
                        />
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                          <svg className="w-16 h-16 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          <span className="text-sm">No visualization</span>
                        </div>
                      )}

                      {/* Hover Overlay */}
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 px-4 py-2 rounded-lg font-medium text-gray-900">
                          View Details
                        </span>
                      </div>

                      {/* Status Badge */}
                      <div className="absolute top-3 left-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          look.is_published
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {look.is_published ? 'Published' : 'Draft'}
                        </span>
                      </div>

                      {/* Room Type Badge */}
                      <div className="absolute top-3 right-3">
                        <span className="px-2 py-1 bg-black/60 text-white rounded-full text-xs font-medium capitalize">
                          {look.room_type.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="p-4">
                    <div onClick={() => handleLookClick(look.id)} className="block hover:text-purple-600 transition-colors cursor-pointer">
                      <h3 className="font-semibold text-gray-900 text-base mb-0.5 line-clamp-1">{look.title}</h3>
                    </div>
                    {look.style_theme && (
                      <p className="text-xs text-gray-500 mb-2">{look.style_theme}</p>
                    )}

                    <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                      <span>{look.product_count} products</span>
                      <span className="text-base font-semibold text-gray-900">{formatPrice(look.total_price)}</span>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => handleLookClick(look.id)}
                        className="flex-1 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium rounded-lg text-center transition-colors"
                      >
                        View
                      </button>
                      {look.is_published ? (
                        <button
                          onClick={() => handleUnpublish(look.id)}
                          className="px-3 py-2 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 text-xs font-medium rounded-lg transition-colors"
                        >
                          Unpublish
                        </button>
                      ) : (
                        <button
                          onClick={() => handlePublish(look.id)}
                          className="px-3 py-2 bg-green-100 hover:bg-green-200 text-green-700 text-xs font-medium rounded-lg transition-colors"
                        >
                          Publish
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(look.id)}
                        className="px-2 py-2 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-medium rounded-lg transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-2">
                {/* Previous Button */}
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page === 1}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    page === 1
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                </button>

                {/* Page Numbers */}
                {getPageNumbers().map((pageNum, index) => (
                  pageNum === 'ellipsis' ? (
                    <span key={`ellipsis-${index}`} className="px-2 text-gray-500">...</span>
                  ) : (
                    <button
                      key={pageNum}
                      onClick={() => handlePageChange(pageNum)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        page === pageNum
                          ? 'bg-purple-600 text-white'
                          : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {pageNum}
                    </button>
                  )
                ))}

                {/* Next Button */}
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page === totalPages}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    page === totalPages
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            )}

            {/* Page Info */}
            {totalPages > 1 && (
              <div className="mt-4 text-center text-sm text-gray-500">
                Page {page} of {totalPages}
              </div>
            )}
          </>
          );
        })()}
      </div>
    </div>
  );
}

export default function AdminCuratedLooksPage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <AdminCuratedLooksContent />
    </ProtectedRoute>
  );
}
