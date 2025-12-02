'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { getCuratedLooks, getCuratedLookById, CuratedLook, CuratedLooksResponse } from '@/utils/api';
import { CuratedLookCard } from '@/components/curated/CuratedLookCard';
import { LookDetailModal } from '@/components/curated/LookDetailModal';

type RoomType = 'all' | 'living_room' | 'bedroom';

export default function CuratedPage() {
  const router = useRouter();
  const [looksData, setLooksData] = useState<CuratedLooksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLook, setSelectedLook] = useState<CuratedLook | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [roomTypeFilter, setRoomTypeFilter] = useState<RoomType>('all');

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
      // Check if user has uploaded their own room image
      const userRoomImage = sessionStorage.getItem('roomImage');
      const hasUserRoom = !!userRoomImage;

      console.log('[CuratedPage] User has own room image:', hasUserRoom);

      // Clear session data for fresh start
      sessionStorage.removeItem('design_session_id');
      sessionStorage.removeItem('curatedVisualizationImage');
      sessionStorage.removeItem('curatedRoomImage');

      // Store selected look data in sessionStorage for design studio
      sessionStorage.setItem('preselectedProducts', JSON.stringify(look.products));
      sessionStorage.setItem('preselectedLookTheme', look.style_theme);

      if (hasUserRoom) {
        // User uploaded their own room - keep their room, leave visualization blank
        // They will hit "Visualize" to see products in their space
        console.log('[CuratedPage] Using user room image, visualization will be blank');
      } else {
        // No user room - fetch and use the curated look's images
        console.log('[CuratedPage] No user room, fetching curated look images for ID:', look.look_id);
        const fullLook = await getCuratedLookById(look.look_id);

        if (fullLook.room_image) {
          sessionStorage.setItem('curatedRoomImage', fullLook.room_image);
        }
        if (fullLook.visualization_image) {
          sessionStorage.setItem('curatedVisualizationImage', fullLook.visualization_image);
          console.log('[CuratedPage] Stored visualization_image, length:', fullLook.visualization_image.length);
        }
      }

      router.push('/design');
    } catch (error) {
      console.error('[CuratedPage] Error in handleStyleThisLook:', error);
      // Fallback: just use the products
      sessionStorage.removeItem('design_session_id');
      sessionStorage.setItem('preselectedProducts', JSON.stringify(look.products));
      sessionStorage.setItem('preselectedLookTheme', look.style_theme);
      router.push('/design');
    }
  }, [router]);

  const handleStyleFromScratch = useCallback(() => {
    // Clear any preselected products and curated images, go to design studio
    sessionStorage.removeItem('preselectedProducts');
    sessionStorage.removeItem('preselectedLookTheme');
    sessionStorage.removeItem('curatedRoomImage');
    sessionStorage.removeItem('curatedVisualizationImage');
    router.push('/design');
  }, [router]);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const roomTypes: { value: RoomType; label: string }[] = [
    { value: 'all', label: 'All Rooms' },
    { value: 'living_room', label: 'Living Room' },
    { value: 'bedroom', label: 'Bedroom' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 relative">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-200/20 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-pink-200/20 rounded-full blur-3xl"></div>
      </div>

      {/* Main content */}
      <div className="relative z-10 py-12 px-4">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-purple-600 via-pink-600 to-purple-600 bg-clip-text text-transparent mb-4 pb-1 leading-normal">
              Designer's Choice
            </h1>
            <p className="text-gray-600 text-lg max-w-2xl mx-auto">
              Browse our collection of professionally curated room designs.
              Find inspiration and style your space with a single click.
            </p>
          </div>

          {/* Room Type Filter Tabs */}
          <div className="flex justify-center mb-10">
            <div className="bg-white/70 backdrop-blur-sm rounded-2xl p-1.5 shadow-lg border border-white/20 inline-flex gap-1">
              {roomTypes.map((type) => (
                <button
                  key={type.value}
                  onClick={() => setRoomTypeFilter(type.value)}
                  className={`px-6 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    roomTypeFilter === type.value
                      ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-md'
                      : 'text-gray-600 hover:text-gray-800 hover:bg-white/50'
                  }`}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="relative mb-6">
                  <div className="animate-spin rounded-full h-16 w-16 border-4 border-purple-200 mx-auto"></div>
                  <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-purple-600 mx-auto absolute top-0 left-1/2 -translate-x-1/2"></div>
                </div>
                <p className="text-gray-600 font-medium">Loading curated looks...</p>
              </div>
            </div>
          )}

          {/* Error state */}
          {!loading && error && (
            <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 max-w-md mx-auto border border-white/20 text-center">
              <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-10 h-10 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-gray-800 mb-3">{error}</h2>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white py-3 px-6 rounded-xl hover:from-purple-700 hover:to-pink-700 transition-all shadow-lg font-medium"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && (!looksData?.looks || looksData.looks.length === 0) && (
            <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-xl p-12 max-w-lg mx-auto border border-white/20 text-center">
              <div className="w-24 h-24 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-12 h-12 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-3">No Looks Available Yet</h2>
              <p className="text-gray-600 mb-6">
                {roomTypeFilter !== 'all'
                  ? `No curated looks for ${roomTypeFilter.replace('_', ' ')} yet. Check back soon or try another room type!`
                  : 'Our design team is working on new curated looks. Check back soon!'}
              </p>
              {roomTypeFilter !== 'all' && (
                <button
                  onClick={() => setRoomTypeFilter('all')}
                  className="text-purple-600 hover:text-purple-700 font-medium"
                >
                  View all room types
                </button>
              )}
            </div>
          )}

          {/* Looks Grid */}
          {!loading && !error && looksData?.looks && looksData.looks.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
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
              <div className="text-center text-gray-500 text-sm mb-8">
                Showing {looksData.looks.length} curated {looksData.looks.length === 1 ? 'look' : 'looks'}
                {roomTypeFilter !== 'all' && ` for ${roomTypeFilter.replace('_', ' ')}`}
              </div>
            </>
          )}

          {/* Design from scratch section */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl shadow-xl border border-white/20 p-8 text-center mt-8">
            <div className="max-w-xl mx-auto">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-100 to-pink-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-3">Create Your Own Design</h2>
              <p className="text-gray-600 mb-6">
                Want something unique? Upload your room photo and design it from scratch
                with our full product catalog.
              </p>
              <button
                onClick={handleStyleFromScratch}
                className="bg-gradient-to-r from-gray-800 to-gray-900 hover:from-gray-900 hover:to-black text-white py-4 px-8 rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl inline-flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Open Design Studio
              </button>
            </div>
          </div>

          {/* Back to home */}
          <div className="mt-8 text-center">
            <button
              onClick={() => router.push('/')}
              className="text-gray-600 hover:text-gray-800 font-medium inline-flex items-center gap-2 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
