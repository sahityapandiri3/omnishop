'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { getCuratedLooks, CuratedLook, CuratedLooksResponse, projectsAPI } from '@/utils/api';
import { CuratedLookCard } from '@/components/curated/CuratedLookCard';
import { LookDetailModal } from '@/components/curated/LookDetailModal';
import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';

type RoomType = 'all' | 'living_room' | 'bedroom';

function CuratedPageContent() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [looksData, setLooksData] = useState<CuratedLooksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLook, setSelectedLook] = useState<CuratedLook | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [roomTypeFilter, setRoomTypeFilter] = useState<RoomType>('all');
  const [isCreatingProject, setIsCreatingProject] = useState(false);

  // Fetch curated looks when filter changes
  useEffect(() => {
    const fetchLooks = async () => {
      try {
        setLoading(true);
        setError(null);
        const roomType = roomTypeFilter === 'all' ? undefined : roomTypeFilter;
        const result = await getCuratedLooks(roomType);
        setLooksData(result);
      } catch (err: any) {
        console.error('Error fetching looks:', err);
        setError('Failed to load curated looks. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchLooks();
  }, [roomTypeFilter]);

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
    // Clear any preselected products and curated images, go to design studio
    sessionStorage.removeItem('preselectedProducts');
    sessionStorage.removeItem('preselectedLookTheme');
    sessionStorage.removeItem('curatedRoomImage');
    sessionStorage.removeItem('curatedVisualizationImage');
    router.push('/design');
  }, [router]);

  const roomTypes: { value: RoomType; label: string }[] = [
    { value: 'all', label: 'All Rooms' },
    { value: 'living_room', label: 'Living Room' },
    { value: 'bedroom', label: 'Bedroom' },
  ];

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Main content */}
      <div className="py-6 px-4">
        <div className="max-w-6xl mx-auto">
          {/* Header with Create Your Own button */}
          <div className="relative mb-5">
            <div className="text-center">
              <h1 className="text-xl md:text-2xl font-bold text-neutral-800 mb-2">
                Designer's Choice
              </h1>
              <p className="text-sm text-neutral-500 max-w-xl mx-auto">
                Professionally curated room designs. Style your space with a click.
              </p>
            </div>
            <button
              onClick={handleStyleFromScratch}
              className="absolute right-0 top-0 inline-flex items-center gap-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-900 text-white text-xs font-medium rounded-lg transition-all shadow-sm"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create Your Own
            </button>
          </div>

          {/* Room Type Filter Tabs */}
          <div className="flex justify-center mb-6">
            <div className="bg-white rounded-lg p-1 shadow-sm border border-neutral-200 inline-flex gap-1">
              {roomTypes.map((type) => (
                <button
                  key={type.value}
                  onClick={() => setRoomTypeFilter(type.value)}
                  className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${
                    roomTypeFilter === type.value
                      ? 'bg-primary-600 text-white'
                      : 'text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50'
                  }`}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="relative mb-4">
                  <div className="animate-spin rounded-full h-10 w-10 border-3 border-primary-200 mx-auto"></div>
                  <div className="animate-spin rounded-full h-10 w-10 border-t-3 border-primary-600 mx-auto absolute top-0 left-1/2 -translate-x-1/2"></div>
                </div>
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
                className="mt-2 bg-primary-600 text-white py-2 px-4 rounded-lg hover:bg-primary-700 transition-all text-sm font-medium"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && (!looksData?.looks || looksData.looks.length === 0) && (
            <div className="bg-white rounded-xl shadow-sm p-8 max-w-sm mx-auto border border-neutral-200 text-center">
              <div className="w-14 h-14 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-base font-semibold text-neutral-800 mb-2">No Looks Available</h2>
              <p className="text-xs text-neutral-500 mb-4">
                {roomTypeFilter !== 'all'
                  ? `No looks for ${roomTypeFilter.replace('_', ' ')} yet.`
                  : 'Check back soon for new curated looks!'}
              </p>
              {roomTypeFilter !== 'all' && (
                <button
                  onClick={() => setRoomTypeFilter('all')}
                  className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                >
                  View all rooms
                </button>
              )}
            </div>
          )}

          {/* Looks Grid */}
          {!loading && !error && looksData?.looks && looksData.looks.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                {looksData.looks.map((look) => (
                  <CuratedLookCard
                    key={look.look_id}
                    look={look}
                    onViewDetails={handleViewDetails}
                    onStyleThisLook={handleStyleThisLook}
                  />
                ))}
              </div>

              {/* Results count */}
              <div className="text-center text-neutral-400 text-xs mb-6">
                {looksData.looks.length} {looksData.looks.length === 1 ? 'look' : 'looks'}
                {roomTypeFilter !== 'all' && ` • ${roomTypeFilter.replace('_', ' ')}`}
              </div>
            </>
          )}

          {/* Design from scratch section */}
          <div className="bg-white rounded-xl shadow-sm border border-neutral-200 p-5 text-center mt-4">
            <div className="max-w-md mx-auto">
              <div className="w-10 h-10 bg-neutral-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                <svg className="w-5 h-5 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-neutral-800 mb-1">Create Your Own</h2>
              <p className="text-xs text-neutral-500 mb-3">
                Design from scratch with our full catalog
              </p>
              <button
                onClick={handleStyleFromScratch}
                className="bg-neutral-800 hover:bg-neutral-900 text-white py-2 px-4 rounded-lg text-sm font-medium transition-all inline-flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Design Studio
              </button>
            </div>
          </div>

          {/* Back to home */}
          <div className="mt-4 text-center">
            <button
              onClick={() => router.push('/')}
              className="text-neutral-400 hover:text-neutral-600 text-xs font-medium inline-flex items-center gap-1 transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back
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
    <ProtectedRoute>
      <CuratedPageContent />
    </ProtectedRoute>
  );
}
