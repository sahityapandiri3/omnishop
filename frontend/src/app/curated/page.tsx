'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { getCuratedLooks, CuratedLook, CuratedLooksResponse, projectsAPI } from '@/utils/api';
import { CuratedLookCard } from '@/components/curated/CuratedLookCard';
import { LookDetailModal } from '@/components/curated/LookDetailModal';
import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';

type RoomType = 'all' | 'living_room' | 'bedroom' | 'foyer';
type StyleOption = 'modern' | 'modern_luxury' | 'indian_contemporary';
type BudgetOption = 'all' | 'pocket_friendly' | 'mid_tier' | 'premium' | 'luxury';

const LOOKS_PER_PAGE = 12;

function CuratedPageContent() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [looksData, setLooksData] = useState<CuratedLooksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [selectedLook, setSelectedLook] = useState<CuratedLook | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [roomTypeFilter, setRoomTypeFilter] = useState<RoomType>('all');
  const [selectedStyles, setSelectedStyles] = useState<StyleOption[]>([]);
  const [budgetFilter, setBudgetFilter] = useState<BudgetOption>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreatingProject, setIsCreatingProject] = useState(false);

  // Fetch curated looks when filter changes (reset pagination)
  useEffect(() => {
    const fetchLooks = async () => {
      try {
        setLoading(true);
        setError(null);
        setOffset(0);
        const roomType = roomTypeFilter === 'all' ? undefined : roomTypeFilter;
        const style = selectedStyles.length > 0 ? selectedStyles.join(',') : undefined;
        const budget = budgetFilter === 'all' ? undefined : budgetFilter;
        const result = await getCuratedLooks(roomType, 'thumbnail', style, budget, LOOKS_PER_PAGE, 0);
        setLooksData(result);
        setHasMore(result.looks.length >= LOOKS_PER_PAGE);
      } catch (err: any) {
        console.error('Error fetching looks:', err);
        setError('Failed to load curated looks. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchLooks();
  }, [roomTypeFilter, selectedStyles, budgetFilter]);

  // Load more looks
  const handleLoadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;

    try {
      setLoadingMore(true);
      const newOffset = offset + LOOKS_PER_PAGE;
      const roomType = roomTypeFilter === 'all' ? undefined : roomTypeFilter;
      const style = selectedStyles.length > 0 ? selectedStyles.join(',') : undefined;
      const budget = budgetFilter === 'all' ? undefined : budgetFilter;
      const result = await getCuratedLooks(roomType, 'thumbnail', style, budget, LOOKS_PER_PAGE, newOffset);

      if (result.looks.length > 0) {
        setLooksData(prev => prev ? {
          ...prev,
          looks: [...prev.looks, ...result.looks]
        } : result);
        setOffset(newOffset);
        setHasMore(result.looks.length >= LOOKS_PER_PAGE);
      } else {
        setHasMore(false);
      }
    } catch (err: any) {
      console.error('Error loading more looks:', err);
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, offset, roomTypeFilter, selectedStyles, budgetFilter]);

  const handleViewDetails = useCallback((look: CuratedLook) => {
    setSelectedLook(look);
    setIsModalOpen(true);
  }, []);

  const handleStyleThisLook = useCallback(async (look: CuratedLook) => {
    try {
      setIsCreatingProject(true);

      // Clear session data for fresh start
      // IMPORTANT: Clear room image too so user is prompted to upload their own
      sessionStorage.removeItem('design_session_id');
      sessionStorage.removeItem('curatedVisualizationImage');
      sessionStorage.removeItem('curatedRoomImage');
      sessionStorage.removeItem('roomImage');
      sessionStorage.removeItem('cleanRoomImage');
      sessionStorage.removeItem('_projectConsumed');

      console.log('[CuratedPage] Use Style clicked - cleared all images, user will upload their own');

      // Store selected look data in sessionStorage for design studio
      // Products will be loaded into canvas, but visualization will be blank
      // User needs to upload their own room image and hit "Visualize"
      sessionStorage.setItem('preselectedProducts', JSON.stringify(look.products));
      sessionStorage.setItem('preselectedLookTheme', look.style_theme);

      // If user is authenticated, create a new project
      if (isAuthenticated) {
        try {
          const projectName = `${look.style_theme} Design`;
          console.log('[CuratedPage] Creating new project:', projectName);
          const project = await projectsAPI.create({ name: projectName });
          console.log('[CuratedPage] Project created:', project.id);
          // Mark as newly created so design page loads sessionStorage data
          sessionStorage.setItem('newlyCreatedProjectId', project.id);
          // Navigate to design page with project ID
          router.push(`/design?projectId=${project.id}`);
        } catch (projectError) {
          console.error('[CuratedPage] Failed to create project, continuing without:', projectError);
          router.push('/design');
        }
      } else {
        router.push('/design');
      }
    } catch (error) {
      console.error('[CuratedPage] Error in handleStyleThisLook:', error);
      // Fallback: just use the products
      sessionStorage.removeItem('design_session_id');
      sessionStorage.setItem('preselectedProducts', JSON.stringify(look.products));
      sessionStorage.setItem('preselectedLookTheme', look.style_theme);
      router.push('/design');
    } finally {
      setIsCreatingProject(false);
    }
  }, [router, isAuthenticated]);

  const handleStyleFromScratch = useCallback(() => {
    // Clear any preselected products and curated images, go to onboarding wizard
    sessionStorage.removeItem('preselectedProducts');
    sessionStorage.removeItem('preselectedLookTheme');
    sessionStorage.removeItem('curatedRoomImage');
    sessionStorage.removeItem('curatedVisualizationImage');
    sessionStorage.removeItem('onboardingPreferences');
    router.push('/onboarding');
  }, [router]);

  const roomTypes: { value: RoomType; label: string }[] = [
    { value: 'all', label: 'All Rooms' },
    { value: 'living_room', label: 'Living Room' },
    { value: 'bedroom', label: 'Bedroom' },
    { value: 'foyer', label: 'Foyer' },
  ];

  const styleOptions: { value: StyleOption; label: string }[] = [
    { value: 'modern', label: 'Modern' },
    { value: 'modern_luxury', label: 'Modern Luxury' },
    { value: 'indian_contemporary', label: 'Indian Contemporary' },
  ];

  const budgetOptions: { value: BudgetOption; label: string; shortLabel: string }[] = [
    { value: 'all', label: 'All Budgets', shortLabel: 'All' },
    { value: 'pocket_friendly', label: '< ₹2L', shortLabel: '< 2L' },
    { value: 'mid_tier', label: '₹2L – 8L', shortLabel: '2-8L' },
    { value: 'premium', label: '₹8L – 15L', shortLabel: '8-15L' },
    { value: 'luxury', label: '₹15L+', shortLabel: '15L+' },
  ];

  const toggleStyle = (style: StyleOption) => {
    setSelectedStyles(prev =>
      prev.includes(style)
        ? prev.filter(s => s !== style)
        : [...prev, style]
    );
  };

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Main content */}
      <div className="py-8 px-4">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="text-center mb-6">
            <h1 className="font-display text-3xl md:text-4xl font-light text-neutral-800 mb-2">
              Designer's Choice
            </h1>
            <p className="text-sm text-neutral-500 max-w-xl mx-auto">
              Professionally curated room designs. Style your space with a click.
            </p>
          </div>

          {/* Search Bar */}
          <div className="flex justify-center mb-5">
            <div className="relative w-full max-w-md">
              <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search looks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-white border border-neutral-200 rounded-lg text-sm text-neutral-700 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-500/20 focus:border-neutral-800 shadow-sm transition-all duration-200"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Filters + Create Your Own */}
          <div className="flex flex-col gap-4 mb-6">
            {/* Room Type + Budget Filter Row */}
            <div className="flex justify-center items-center gap-3 flex-wrap">
              {/* Room Type Filter */}
              <div className="bg-white rounded-lg p-1 shadow-sm border border-neutral-200/80 inline-flex gap-1">
                {roomTypes.map((type) => (
                  <button
                    key={type.value}
                    onClick={() => setRoomTypeFilter(type.value)}
                    className={`px-4 py-2 rounded-md text-xs font-medium transition-all duration-200 ${
                      roomTypeFilter === type.value
                        ? 'bg-neutral-800 text-white shadow-sm'
                        : 'text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50'
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
                className="bg-white rounded-lg pl-4 pr-8 py-2 text-xs font-medium shadow-sm border border-neutral-200/80 text-neutral-600 hover:border-neutral-300 focus:ring-2 focus:ring-neutral-500/20 focus:border-neutral-800 cursor-pointer transition-all duration-200"
              >
                {budgetOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Style Filter - Multi-select capsules */}
            <div className="flex justify-center">
              <div className="flex flex-wrap justify-center gap-2">
                {styleOptions.map((style) => {
                  const isSelected = selectedStyles.includes(style.value);
                  return (
                    <button
                      key={style.value}
                      onClick={() => toggleStyle(style.value)}
                      className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border ${
                        isSelected
                          ? 'bg-neutral-100 text-neutral-800 border-neutral-400'
                          : 'bg-white text-neutral-500 border-neutral-200 hover:border-neutral-400 hover:text-neutral-700'
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
                    className="px-2 py-1.5 text-xs text-neutral-400 hover:text-neutral-700 transition-colors"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            {/* Create Your Own Button - Centered */}
            <div className="flex justify-center">
              <button
                onClick={handleStyleFromScratch}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-neutral-800 hover:bg-neutral-900 text-white text-sm font-medium rounded-lg transition-all duration-200 shadow-sm hover:shadow-md"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Create Your Own
              </button>
            </div>
          </div>

          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-neutral-200 border-t-neutral-800 mx-auto mb-4"></div>
                <p className="text-sm text-neutral-500">Loading looks...</p>
              </div>
            </div>
          )}

          {/* Error state */}
          {!loading && error && (
            <div className="bg-white rounded-xl shadow-sm p-6 max-w-sm mx-auto border border-neutral-200 text-center">
              <div className="w-12 h-12 bg-accent-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-accent-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-neutral-800 mb-2">{error}</h2>
              <button
                onClick={() => window.location.reload()}
                className="mt-2 bg-neutral-800 text-white py-2 px-4 rounded-lg hover:bg-neutral-900 transition-all text-sm font-medium"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && (!looksData?.looks || looksData.looks.length === 0) && (
            <div className="bg-white rounded-xl shadow-sm p-8 max-w-sm mx-auto border border-neutral-200 text-center">
              <div className="w-14 h-14 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-base font-semibold text-neutral-800 mb-2">No Looks Available</h2>
              <p className="text-xs text-neutral-500 mb-4">
                {roomTypeFilter !== 'all' || selectedStyles.length > 0 || budgetFilter !== 'all'
                  ? `No looks found for the selected filters.`
                  : 'Check back soon for new curated looks!'}
              </p>
              {(roomTypeFilter !== 'all' || selectedStyles.length > 0 || budgetFilter !== 'all') && (
                <button
                  onClick={() => {
                    setRoomTypeFilter('all');
                    setSelectedStyles([]);
                    setBudgetFilter('all');
                  }}
                  className="text-neutral-700 hover:text-neutral-800 text-sm font-medium"
                >
                  Clear filters
                </button>
              )}
            </div>
          )}

          {/* Looks Grid */}
          {!loading && !error && looksData?.looks && looksData.looks.length > 0 && (() => {
            const filteredLooks = looksData.looks.filter(look =>
              look.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
              look.style_theme?.toLowerCase().includes(searchQuery.toLowerCase())
            );

            if (filteredLooks.length === 0) {
              return (
                <div className="bg-white rounded-xl shadow-sm p-8 max-w-sm mx-auto border border-neutral-200 text-center">
                  <div className="w-14 h-14 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="w-7 h-7 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </div>
                  <h2 className="text-base font-semibold text-neutral-800 mb-2">No Matching Looks</h2>
                  <p className="text-xs text-neutral-500 mb-4">
                    No looks found for &quot;{searchQuery}&quot;
                  </p>
                  <button
                    onClick={() => setSearchQuery('')}
                    className="text-neutral-700 hover:text-neutral-800 text-sm font-medium"
                  >
                    Clear search
                  </button>
                </div>
              );
            }

            return (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                  {filteredLooks.map((look) => (
                    <CuratedLookCard
                      key={look.look_id}
                      look={look}
                      onViewDetails={handleViewDetails}
                      onStyleThisLook={handleStyleThisLook}
                    />
                  ))}
                </div>

                {/* Results count */}
                <div className="text-center text-neutral-400 text-xs mb-4">
                  {filteredLooks.length} {filteredLooks.length === 1 ? 'look' : 'looks'}
                  {searchQuery && ` • "${searchQuery}"`}
                  {roomTypeFilter !== 'all' && ` • ${roomTypeFilter.replace('_', ' ')}`}
                  {selectedStyles.length > 0 && ` • ${selectedStyles.map(s => s.replace('_', ' ')).join(', ')}`}
                  {budgetFilter !== 'all' && ` • ${budgetOptions.find(b => b.value === budgetFilter)?.label}`}
                </div>

                {/* Load More button */}
                {hasMore && !searchQuery && (
                  <div className="text-center mb-6">
                    <button
                      onClick={handleLoadMore}
                      disabled={loadingMore}
                      className="px-6 py-2.5 bg-neutral-100 hover:bg-neutral-200 disabled:bg-neutral-50 text-neutral-700 disabled:text-neutral-400 rounded-lg font-medium text-sm transition-colors inline-flex items-center gap-2"
                    >
                      {loadingMore ? (
                        <>
                          <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Loading...
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                          Load More Looks
                        </>
                      )}
                    </button>
                  </div>
                )}
              </>
            );
          })()}

          {/* Design from scratch section */}
          <div className="bg-secondary-50/50 rounded-xl border border-neutral-200/60 p-6 text-center mt-6">
            <div className="max-w-md mx-auto">
              <div className="w-12 h-12 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </div>
              <h2 className="font-display text-xl font-light text-neutral-800 mb-2">Create Your Own</h2>
              <p className="text-sm text-neutral-500 mb-4">
                Design from scratch with our full catalog
              </p>
              <button
                onClick={handleStyleFromScratch}
                className="bg-neutral-800 hover:bg-neutral-900 text-white py-2.5 px-6 rounded-lg text-sm font-medium transition-all duration-200 inline-flex items-center gap-2 shadow-sm hover:shadow-md"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Design Studio
              </button>
            </div>
          </div>

          {/* Back to home */}
          <div className="mt-6 text-center">
            <button
              onClick={() => router.push('/')}
              className="text-neutral-400 hover:text-neutral-700 text-sm font-medium inline-flex items-center gap-1.5 transition-colors duration-200"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Home
            </button>
          </div>
        </div>
      </div>

      {/* Look Detail Modal */}
      {selectedLook && (
        <LookDetailModal
          look={selectedLook}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedLook(null);
          }}
          onStyleThisLook={handleStyleThisLook}
        />
      )}
    </div>
  );
}

export default function CuratedPage() {
  return (
    <ProtectedRoute
      requiredRole="user"
      requiredTiers={['advanced', 'curator']}
      allowAdmin={true}
    >
      <CuratedPageContent />
    </ProtectedRoute>
  );
}
