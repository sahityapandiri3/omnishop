'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import api from '@/utils/api';

interface ProductInView {
  id: number;
  name: string;
  price: number | null;
  image_url: string | null;
  source_website: string;
  source_url: string | null;
  product_type: string | null;
}

interface HomeStylingView {
  id: number;
  view_number: number;
  visualization_image: string | null;
  curated_look_id: number | null;
  style_theme: string | null;
  generation_status: string;
  error_message: string | null;
  is_fallback: boolean;
  products: ProductInView[];
  total_price: number;
}

interface SessionData {
  id: string;
  room_type: string | null;
  style: string | null;
  status: string;
  views_count: number;
  views: HomeStylingView[];
  original_room_image: string | null;
  clean_room_image: string | null;
}

type GenerationStage = 'starting' | 'finding_looks' | 'generating' | 'completed' | 'failed';

const STAGE_MESSAGES: Record<GenerationStage, string> = {
  starting: 'Starting design generation...',
  finding_looks: 'Finding matching furniture sets for your style...',
  generating: 'AI is creating your personalized room visualization...',
  completed: 'Your designs are ready!',
  failed: 'Generation failed. Please try again.',
};

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params?.sessionId as string;

  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedViewIndex, setSelectedViewIndex] = useState(0);

  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState<GenerationStage>('starting');
  const [currentViewNumber, setCurrentViewNumber] = useState(0);
  const [totalViews, setTotalViews] = useState(1);
  const [currentRetry, setCurrentRetry] = useState(0);

  const generationStarted = useRef(false);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const retryCount = useRef(0);
  const MAX_RETRIES = 3;

  // Timer for elapsed time display
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerInterval = useRef<NodeJS.Timeout | null>(null);

  // Fetch session data
  const fetchSession = useCallback(async (includeImages: boolean = true) => {
    try {
      const response = await api.get(`/api/homestyling/sessions/${sessionId}?include_images=${includeImages}`);
      return response.data as SessionData;
    } catch (err: any) {
      console.error('Error fetching session:', err);
      throw err;
    }
  }, [sessionId]);

  // Start generation with retry logic
  const startGeneration = useCallback(async (isRetry: boolean = false) => {
    if (generationStarted.current && !isRetry) return;
    generationStarted.current = true;

    setIsGenerating(true);
    setGenerationStage('starting');
    setError(null);
    setElapsedSeconds(0);

    // Start timer
    if (timerInterval.current) {
      clearInterval(timerInterval.current);
    }
    timerInterval.current = setInterval(() => {
      setElapsedSeconds(prev => prev + 1);
    }, 1000);

    try {
      // Start the generation request (this will take a while)
      setGenerationStage('finding_looks');

      // Make the generate API call
      const generatePromise = api.post(`/api/homestyling/sessions/${sessionId}/generate`);

      // Poll for status while generation is running
      setGenerationStage('generating');

      let pollCount = 0;
      pollingInterval.current = setInterval(async () => {
        try {
          const sessionData = await fetchSession(false); // Don't fetch images while polling

          // Update view count as they come in
          const completedViews = sessionData.views.filter(v => v.generation_status === 'completed').length;
          const generatingViews = sessionData.views.filter(v => v.generation_status === 'generating').length;

          setCurrentViewNumber(completedViews);
          setTotalViews(sessionData.views_count || 1);

          if (sessionData.status === 'completed') {
            if (pollingInterval.current) {
              clearInterval(pollingInterval.current);
            }
            if (timerInterval.current) {
              clearInterval(timerInterval.current);
            }
            // Generation complete - redirect to purchase page
            setGenerationStage('completed');
            setIsGenerating(false);
            retryCount.current = 0;
            router.push(`/purchases/${sessionId}`);
            return;
          } else if (sessionData.status === 'failed') {
            if (pollingInterval.current) {
              clearInterval(pollingInterval.current);
            }
            if (timerInterval.current) {
              clearInterval(timerInterval.current);
            }
            setGenerationStage('failed');
            setError('Generation failed. Please try again.');
            setIsGenerating(false);
            return;
          }

          pollCount++;
        } catch (e) {
          console.error('Polling error:', e);
        }
      }, 3000); // Poll every 3 seconds

      // Wait for generate API to return (now returns immediately with "started")
      const generateResponse = await generatePromise;
      console.log('Generate response:', generateResponse.data);

      // The generate endpoint now returns immediately - don't redirect yet!
      // Continue polling until session status is 'completed'
      // The polling interval above will handle the redirect when complete

    } catch (err: any) {
      console.error('Error during generation:', err);
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
      }
      if (timerInterval.current) {
        clearInterval(timerInterval.current);
      }

      // IMPORTANT: Check if session actually completed successfully before retrying
      // The frontend might timeout even though backend succeeded
      try {
        const checkSession = await fetchSession(true);
        if (checkSession.status === 'completed') {
          console.log('Session already completed - redirecting to purchase page');
          router.push(`/purchases/${sessionId}`);
          return;
        }
      } catch (checkErr) {
        console.error('Failed to check session status:', checkErr);
      }

      // Auto-retry if we haven't exceeded max retries
      if (retryCount.current < MAX_RETRIES) {
        retryCount.current++;
        setCurrentRetry(retryCount.current);
        console.log(`Retrying generation (attempt ${retryCount.current}/${MAX_RETRIES})...`);

        // Reset session status to allow retry
        try {
          await api.post(`/api/homestyling/sessions/${sessionId}/reset-for-retry`);
        } catch (resetErr) {
          console.error('Failed to reset session:', resetErr);
        }

        // Wait a moment before retrying
        setGenerationStage('starting');
        setTimeout(() => {
          generationStarted.current = false;
          startGeneration(true);
        }, 2000);
        return;
      }

      // Max retries exceeded, show error
      setGenerationStage('failed');
      setError(err.response?.data?.detail || 'Failed to generate designs. Please try again.');
      setIsGenerating(false);
    }
  }, [sessionId, fetchSession]);

  // Initial load
  useEffect(() => {
    if (!sessionId) return;

    const init = async () => {
      try {
        setLoading(true);
        const sessionData = await fetchSession(true);
        setSession(sessionData);
        setTotalViews(sessionData.views_count || 1);

        // Check if we need to start generation
        if (sessionData.status === 'tier_selection' || sessionData.status === 'upload') {
          // Generation hasn't started yet - start it
          setLoading(false);
          startGeneration();
        } else if (sessionData.status === 'generating') {
          // Generation is in progress - poll for updates
          setIsGenerating(true);
          setGenerationStage('generating');
          setLoading(false);

          // Start timer for elapsed time
          timerInterval.current = setInterval(() => {
            setElapsedSeconds(prev => prev + 1);
          }, 1000);

          // Start polling
          pollingInterval.current = setInterval(async () => {
            try {
              const updatedSession = await fetchSession(true);
              setSession(updatedSession);

              const completedViews = updatedSession.views.filter(v => v.generation_status === 'completed').length;
              setCurrentViewNumber(completedViews);

              if (updatedSession.status === 'completed') {
                if (pollingInterval.current) {
                  clearInterval(pollingInterval.current);
                }
                if (timerInterval.current) {
                  clearInterval(timerInterval.current);
                }
                router.push(`/purchases/${sessionId}`);
              } else if (updatedSession.status === 'failed') {
                if (pollingInterval.current) {
                  clearInterval(pollingInterval.current);
                }
                if (timerInterval.current) {
                  clearInterval(timerInterval.current);
                }
                setIsGenerating(false);
                setGenerationStage('failed');
              }
            } catch (e) {
              console.error('Polling error:', e);
            }
          }, 3000);
        } else if (sessionData.status === 'completed') {
          // Already completed - redirect to purchase page
          router.push(`/purchases/${sessionId}`);
        } else {
          // Failed
          setGenerationStage('failed');
          setLoading(false);
        }
      } catch (err: any) {
        console.error('Error loading session:', err);
        setError(err.response?.data?.detail || 'Failed to load session');
        setLoading(false);
      }
    };

    init();

    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
      }
      if (timerInterval.current) {
        clearInterval(timerInterval.current);
      }
    };
  }, [sessionId, fetchSession, startGeneration]);

  const formatPrice = (price: number | null) => {
    if (price === null || price === 0) return 'Price on request';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatStyle = (style: string | null) => {
    if (!style) return 'Custom Style';
    return style.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-200 border-t-emerald-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Generating state - show progress with stage indicators
  if (isGenerating) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-2xl mx-auto px-4">
          {/* Progress Header */}
          <div className="text-center mb-12">
            <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-emerald-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {currentRetry > 0 ? 'Retrying Generation...' : 'Creating Your Designs'}
            </h1>
            <p className="text-gray-600">{STAGE_MESSAGES[generationStage]}</p>
          </div>

          {/* Progress Card */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
            {/* Progress Bar */}
            <div className="mb-6">
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>Progress</span>
                <span>{currentViewNumber} of {totalViews} views</span>
              </div>
              <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${totalViews > 0 ? (currentViewNumber / totalViews) * 100 : 0}%` }}
                />
              </div>
            </div>

            {/* Stage Indicators */}
            <div className="space-y-4">
              <StageIndicator
                label="Upload room image"
                status="completed"
              />
              <StageIndicator
                label="Finding furniture sets"
                status={generationStage === 'starting' || generationStage === 'finding_looks' ? 'active' : 'completed'}
              />
              <StageIndicator
                label="Generating AI visualizations"
                status={generationStage === 'generating' ? 'active' : generationStage === 'completed' ? 'completed' : 'pending'}
                subtitle={generationStage === 'generating' ? `Creating view ${currentViewNumber + 1} of ${totalViews}... (${elapsedSeconds}s)` : undefined}
              />
              <StageIndicator
                label="Finalizing designs"
                status={generationStage === 'completed' ? 'completed' : 'pending'}
              />
            </div>

            {/* Retry indicator */}
            {currentRetry > 0 && (
              <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-700">
                  Retry attempt {currentRetry + 1} of {MAX_RETRIES + 1}
                </p>
              </div>
            )}

            {/* Estimated Time */}
            <div className="mt-8 pt-6 border-t border-gray-100 text-center">
              <p className="text-sm text-gray-500">
                Estimated time: {totalViews * 30}-{totalViews * 45} seconds
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Each visualization is uniquely generated with AI
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !session) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-gray-600 mb-4">{error || 'Results not found'}</p>
          <button
            onClick={() => router.push('/homestyling/preferences')}
            className="text-emerald-600 hover:text-emerald-700 font-medium"
          >
            Start Over
          </button>
        </div>
      </div>
    );
  }

  const currentView = session.views[selectedViewIndex];

  // Results view
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium mb-4">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            Complete
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Your Design Views</h1>
          <p className="text-gray-600">
            {session.views.length} {session.views.length === 1 ? 'design' : 'designs'} for your{' '}
            {formatStyle(session.style)} {session.room_type?.replace('_', ' ')}
          </p>
        </div>

        {session.views.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <p className="text-gray-600">No designs available yet.</p>
          </div>
        ) : (
          <>
            {/* View Selector */}
            {session.views.length > 1 && (
              <div className="flex justify-center gap-2 mb-6">
                {session.views.map((view, index) => (
                  <button
                    key={view.id}
                    onClick={() => setSelectedViewIndex(index)}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${
                      selectedViewIndex === index
                        ? 'bg-emerald-600 text-white'
                        : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
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
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                  <div className="aspect-[4/3] relative bg-gray-100">
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
                      <div className="w-full h-full flex items-center justify-center text-gray-400">
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
                  {/* Fallback Warning Banner */}
                  {currentView?.is_fallback && (
                    <div className="bg-amber-50 border-t border-amber-200 px-4 py-3">
                      <div className="flex items-center gap-2">
                        <svg className="w-5 h-5 text-amber-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <div className="flex-1">
                          <p className="text-sm text-amber-800">
                            Showing with a different background.{' '}
                            <button
                              onClick={() => router.push(`/homestyling/upload?session_id=${sessionId}&retry_view=${currentView.view_number}`)}
                              className="font-medium text-amber-700 hover:text-amber-900 underline"
                            >
                              Click here to visualize in your space
                            </button>
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  {/* AI Visualization Disclaimer */}
                  <div className="px-4 py-2 bg-gray-50 border-t border-gray-100">
                    <p className="text-xs text-gray-500 flex items-center gap-1.5">
                      <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      AI-generated visualization. Actual products may vary slightly in appearance.
                    </p>
                  </div>
                  <div className="p-4 border-t border-gray-100">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="font-semibold text-gray-900">
                          {currentView?.style_theme || 'Design'} Look
                        </h2>
                        <p className="text-sm text-gray-500">
                          {currentView?.products.length || 0} products
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Total Value</p>
                        <p className="text-lg font-bold text-emerald-600">
                          {formatPrice(currentView?.total_price || 0)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Products List */}
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Products in This Look</h3>
                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                  {currentView?.products.map((product) => (
                    <div
                      key={product.id}
                      className="bg-white rounded-lg shadow-sm border border-gray-200 p-3 flex gap-3"
                    >
                      <div className="w-16 h-16 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                        {product.image_url ? (
                          <img
                            src={product.image_url}
                            alt={product.name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-300">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2 2v12a2 2 0 002 2z"
                              />
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-gray-900 text-sm line-clamp-2">
                          {product.name}
                        </h4>
                        <p className="text-xs text-gray-500 capitalize">{product.source_website}</p>
                        <div className="flex items-center justify-between mt-1">
                          <span className="font-semibold text-gray-900 text-sm">
                            {formatPrice(product.price)}
                          </span>
                          {product.source_url && (
                            <a
                              href={product.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-emerald-600 hover:text-emerald-700 text-xs font-medium"
                            >
                              View Product
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-8 flex flex-wrap justify-center gap-4">
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

                  // Set data directly for design page
                  if (session.clean_room_image) {
                    sessionStorage.setItem('curatedRoomImage', session.clean_room_image);
                  }
                  if (currentView?.visualization_image) {
                    sessionStorage.setItem('curatedVisualizationImage', currentView.visualization_image);
                  }
                  if (currentView?.products && currentView.products.length > 0) {
                    sessionStorage.setItem('preselectedProducts', JSON.stringify(currentView.products));
                  }

                  router.push('/upgrade?from=purchase');
                }}
                className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg transition-all flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Style This Further
              </button>
              <button
                onClick={() => router.push('/homestyling/preferences')}
                className="px-6 py-3 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 font-semibold rounded-lg transition-all flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
                Get More Looks
              </button>
              <button
                onClick={() => router.push('/upgrade?redirect=design')}
                className="px-6 py-3 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 font-semibold rounded-lg transition-all flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                Build Your Own
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Stage Indicator Component
function StageIndicator({
  label,
  status,
  subtitle
}: {
  label: string;
  status: 'pending' | 'active' | 'completed';
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
        status === 'completed'
          ? 'bg-emerald-500'
          : status === 'active'
            ? 'bg-emerald-100 border-2 border-emerald-500'
            : 'bg-gray-100'
      }`}>
        {status === 'completed' ? (
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        ) : status === 'active' ? (
          <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse" />
        ) : (
          <div className="w-3 h-3 bg-gray-300 rounded-full" />
        )}
      </div>
      <div>
        <p className={`font-medium ${status === 'active' ? 'text-emerald-600' : status === 'completed' ? 'text-gray-900' : 'text-gray-400'}`}>
          {label}
        </p>
        {subtitle && (
          <p className="text-sm text-gray-500">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
