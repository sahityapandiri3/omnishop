'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth, canAccessDesignStudio } from '@/contexts/AuthContext';
import { purchasesAPI, PurchaseDetail, PurchaseView } from '@/utils/api';

export default function PurchaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const purchaseId = params?.id as string;

  // Check if user has Advanced tier (can access design studio directly)
  const hasStudioAccess = canAccessDesignStudio(user);

  const [purchase, setPurchase] = useState<PurchaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedViewIndex, setSelectedViewIndex] = useState(0);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push(`/login?redirect=/purchases/${purchaseId}`);
    }
  }, [authLoading, isAuthenticated, router, purchaseId]);

  // Fetch purchase details
  useEffect(() => {
    if (isAuthenticated && purchaseId) {
      fetchPurchase();
    }
  }, [isAuthenticated, purchaseId]);

  const fetchPurchase = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await purchasesAPI.get(purchaseId);
      setPurchase(data);
    } catch (err: any) {
      console.error('Failed to fetch purchase:', err);
      if (err.response?.status === 404) {
        setError('Purchase not found');
      } else {
        setError('Failed to load purchase. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatStyle = (style: string | null) => {
    if (!style) return '';
    return style
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-neutral-800" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-neutral-200 border-t-neutral-800 mx-auto mb-4" />
          <p className="text-neutral-500">Loading purchase...</p>
        </div>
      </div>
    );
  }

  if (error || !purchase) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-accent-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-accent-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-neutral-500 mb-4">{error || 'Purchase not found'}</p>
          <Link
            href="/purchases"
            className="text-neutral-700 hover:text-neutral-800 font-medium"
          >
            Back to Purchases
          </Link>
        </div>
      </div>
    );
  }

  const currentView = purchase.views[selectedViewIndex];

  return (
    <div className="min-h-screen bg-neutral-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* Back Link */}
        <Link
          href="/purchases"
          className="inline-flex items-center gap-2 text-neutral-500 hover:text-neutral-700 mb-6"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Purchases
        </Link>

        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="font-display text-2xl font-light text-neutral-800 mb-2">{purchase.title}</h1>
          <p className="text-neutral-500">
            {purchase.views.length} {purchase.views.length === 1 ? 'design' : 'designs'} for your{' '}
            {formatStyle(purchase.style)} {purchase.room_type?.replace('_', ' ')}
          </p>
        </div>

        {purchase.views.length === 0 ? (
          <div className="bg-white rounded-xl shadow-soft border border-neutral-200 p-12 text-center">
            <p className="text-neutral-500">No designs available.</p>
          </div>
        ) : (
          <>
            {/* View Selector */}
            {purchase.views.length > 1 && (
              <div className="flex justify-center gap-2 mb-6">
                {purchase.views.map((view, index) => (
                  <button
                    key={view.id}
                    onClick={() => setSelectedViewIndex(index)}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${
                      selectedViewIndex === index
                        ? 'bg-neutral-800 text-white'
                        : 'bg-white text-neutral-600 hover:bg-neutral-50 border border-neutral-200'
                    }`}
                  >
                    View {view.view_number}
                    {view.style_theme && (
                      <span className="text-xs ml-1 opacity-75">({view.style_theme})</span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Main Content */}
            <div className="grid lg:grid-cols-3 gap-6">
              {/* Visualization */}
              <div className="lg:col-span-2">
                <div className="bg-white rounded-xl shadow-soft border border-neutral-200 overflow-hidden">
                  <div className="aspect-[4/3] relative bg-neutral-100">
                    {currentView?.visualization_image ? (
                      <img
                        src={
                          currentView.visualization_image.startsWith('data:')
                            ? currentView.visualization_image
                            : `data:image/png;base64,${currentView.visualization_image}`
                        }
                        alt={`Design View ${currentView.view_number}`}
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-neutral-400">
                        <svg className="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={1.5}
                            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                          />
                        </svg>
                      </div>
                    )}
                  </div>
                  {/* AI Visualization Disclaimer */}
                  <div className="px-4 py-2 bg-neutral-50 border-t border-neutral-100">
                    <p className="text-xs text-neutral-500 flex items-center gap-1.5">
                      <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      AI-generated visualization. Actual products may vary slightly in appearance.
                    </p>
                  </div>
                  <div className="p-4 border-t border-neutral-100">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="font-display font-normal text-neutral-800">
                          {currentView?.style_theme || 'Design'} Look
                        </h2>
                        <p className="text-sm text-neutral-500">
                          {currentView?.products.length || 0} products
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-neutral-500">Total Value</p>
                        <p className="text-lg font-bold text-neutral-700">
                          {formatPrice(currentView?.total_price || 0)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Products List */}
              <div className="lg:col-span-1">
                <div className="bg-white rounded-xl shadow-soft border border-neutral-200 overflow-hidden">
                  <div className="p-4 border-b border-neutral-100">
                    <h3 className="font-display font-normal text-neutral-800">Products in this Design</h3>
                  </div>
                  <div className="divide-y divide-neutral-100 max-h-[600px] overflow-y-auto">
                    {currentView?.products.map((product) => (
                      <div key={product.id} className="p-4 hover:bg-neutral-50 transition-colors">
                        <div className="flex gap-3">
                          {/* Product Image */}
                          <div className="w-16 h-16 flex-shrink-0 rounded-lg bg-neutral-100 overflow-hidden">
                            {product.image_url ? (
                              <img
                                src={product.image_url}
                                alt={product.name}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-neutral-400">
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={1.5}
                                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                                  />
                                </svg>
                              </div>
                            )}
                          </div>

                          {/* Product Info */}
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium text-neutral-800 text-sm truncate">
                              {product.name}
                            </h4>
                            <p className="text-xs text-neutral-500 truncate">
                              {product.source_website}
                            </p>
                            <div className="flex items-center justify-between mt-1">
                              <p className="text-neutral-700 font-semibold text-sm">
                                {product.price ? formatPrice(product.price) : 'Price N/A'}
                              </p>
                              {product.source_url && (
                                <a
                                  href={product.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-neutral-700 hover:text-neutral-800 font-medium"
                                >
                                  View
                                </a>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                    {(!currentView?.products || currentView.products.length === 0) && (
                      <div className="p-8 text-center text-neutral-500">
                        No products available
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons - Tier-based CTAs */}
            <div className="flex flex-wrap justify-center gap-4 mt-8">
              {/* Style This Further - behavior depends on tier */}
              <button
                onClick={() => {
                  // Clear ALL design-related sessionStorage to free up quota (5MB limit)
                  sessionStorage.removeItem('curatedRoomImage');
                  sessionStorage.removeItem('curatedVisualizationImage');
                  sessionStorage.removeItem('preselectedProducts');
                  sessionStorage.removeItem('roomImage');
                  sessionStorage.removeItem('persistedCanvasProducts');
                  sessionStorage.removeItem('cleanRoomImage');
                  sessionStorage.removeItem('styleThisFurther');
                  sessionStorage.removeItem('preselectedLookTheme');
                  sessionStorage.removeItem('design_session_id');
                  sessionStorage.removeItem('furnitureRemovalJobId');
                  sessionStorage.removeItem('pendingFurnitureRemoval');

                  // Set data directly for design page (no intermediate storage)
                  const roomImage = purchase.clean_room_image || purchase.original_room_image;
                  const visualization = currentView?.visualization_image;
                  const products = currentView?.products;

                  console.log('[PurchaseDetail] Style This Further - setting design data:', {
                    hasRoomImage: !!roomImage,
                    roomImageLength: roomImage?.length || 0,
                    hasVisualization: !!visualization,
                    vizLength: visualization?.length || 0,
                    productsCount: products?.length || 0,
                    hasStudioAccess,
                  });

                  try {
                    if (roomImage) {
                      sessionStorage.setItem('curatedRoomImage', roomImage);
                      console.log('[PurchaseDetail] Set curatedRoomImage');
                    }
                    if (visualization) {
                      sessionStorage.setItem('curatedVisualizationImage', visualization);
                      console.log('[PurchaseDetail] Set curatedVisualizationImage');
                    }
                    if (products && products.length > 0) {
                      sessionStorage.setItem('preselectedProducts', JSON.stringify(products));
                      console.log('[PurchaseDetail] Set preselectedProducts');
                    }
                    // Set persistent bypass key for tier check - this key is NOT cleared by design page
                    // when loading the data, so ProtectedRoute can use it for the tier bypass check
                    sessionStorage.setItem('designAccessGranted', 'true');
                    console.log('[PurchaseDetail] Set designAccessGranted for tier bypass');
                  } catch (e) {
                    console.error('[PurchaseDetail] SessionStorage quota error:', e);
                    alert('Storage quota exceeded. Please close other tabs or clear browser data.');
                    return;
                  }

                  // Route based on tier
                  if (hasStudioAccess) {
                    // Advanced/Curator users: go directly to design with context loaded
                    router.push('/design');
                  } else {
                    // Free/Basic/Basic+ users: go to pricing with Advanced highlighted
                    // Set flag so payment page knows to redirect to /design after upgrade
                    sessionStorage.setItem('upgradeSource', 'styleThisFurther');
                    router.push('/pricing?highlight=advanced');
                  }
                }}
                className="inline-flex items-center gap-2 px-6 py-3 bg-neutral-800 text-white font-medium rounded-lg hover:bg-neutral-900 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Style This Further
              </button>

              {/* Secondary CTA - different based on tier */}
              {hasStudioAccess ? (
                // Advanced/Curator: "See more looks" goes to curated gallery
                <Link
                  href="/curated"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-white text-neutral-700 font-medium rounded-lg border border-neutral-300 hover:bg-neutral-50 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  See More Looks
                </Link>
              ) : (
                // Free/Basic/Basic+: "Get more looks" goes to pricing
                <Link
                  href="/pricing"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-white text-neutral-700 font-medium rounded-lg border border-neutral-300 hover:bg-neutral-50 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                  Get More Looks
                </Link>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
