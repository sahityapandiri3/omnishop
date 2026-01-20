'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { purchasesAPI, Purchase } from '@/utils/api';

export default function PurchasesPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login?redirect=/purchases');
    }
  }, [authLoading, isAuthenticated, router]);

  // Fetch purchases
  useEffect(() => {
    if (isAuthenticated) {
      fetchPurchases();
    }
  }, [isAuthenticated]);

  const fetchPurchases = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await purchasesAPI.list();
      setPurchases(response.purchases);
    } catch (err: any) {
      console.error('Failed to fetch purchases:', err);
      setError('Failed to load purchases. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const formatStyle = (style: string | null) => {
    if (!style) return null;
    return style
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatRoomType = (roomType: string | null) => {
    if (!roomType) return null;
    return roomType
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">My Purchases</h1>
            <p className="mt-1 text-gray-600">
              {purchases.length === 0
                ? 'Your design results will appear here'
                : `${purchases.length} purchase${purchases.length === 1 ? '' : 's'}`}
            </p>
          </div>
          <Link
            href="/homestyling/preferences"
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors shadow-sm"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Get More Looks
          </Link>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 text-red-500 hover:text-red-700"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-xl border border-gray-200 overflow-hidden animate-pulse"
              >
                <div className="aspect-video bg-gray-200" />
                <div className="p-4">
                  <div className="h-5 bg-gray-200 rounded w-3/4 mb-2" />
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : purchases.length === 0 ? (
          /* Empty State */
          <div className="text-center py-16">
            <div className="mx-auto w-24 h-24 bg-emerald-100 rounded-full flex items-center justify-center mb-6">
              <svg className="w-12 h-12 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              No purchases yet
            </h2>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Generate your first home styling designs to see them here.
            </p>
            <Link
              href="/homestyling/preferences"
              className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors shadow-lg shadow-emerald-500/25"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
              Start Styling
            </Link>
          </div>
        ) : (
          /* Purchases Grid */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {purchases.map((purchase) => (
              <Link
                key={purchase.id}
                href={`/purchases/${purchase.id}`}
                className="group bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-lg hover:border-emerald-300 transition-all"
              >
                {/* Thumbnail */}
                <div className="aspect-video relative bg-gray-100">
                  {purchase.thumbnail && (
                    <img
                      src={purchase.thumbnail}
                      alt={purchase.title}
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                  )}

                  {/* Views Count Badge */}
                  <div className="absolute top-2 right-2">
                    <span className="px-2 py-1 bg-black/60 text-white text-xs font-medium rounded-full backdrop-blur-sm">
                      {purchase.views_count} {purchase.views_count === 1 ? 'look' : 'looks'}
                    </span>
                  </div>

                  {/* Style Badge */}
                  {purchase.style && (
                    <div className="absolute bottom-2 left-2">
                      <span className="px-2 py-1 bg-emerald-600/90 text-white text-xs font-medium rounded-full backdrop-blur-sm">
                        {formatStyle(purchase.style)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Purchase Info */}
                <div className="p-4">
                  <h3 className="font-medium text-gray-900 group-hover:text-emerald-600 transition-colors">
                    {purchase.title}
                  </h3>
                  {purchase.room_type && (
                    <p className="text-sm text-gray-500 mt-1">
                      {formatRoomType(purchase.room_type)}
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
