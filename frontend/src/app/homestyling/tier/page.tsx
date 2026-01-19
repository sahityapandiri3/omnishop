'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/utils/api';
import { useAuth } from '@/contexts/AuthContext';

type TierType = 'free' | 'basic' | 'premium';

const TIERS = [
  {
    value: 'free' as TierType,
    name: 'Free',
    views: 1,
    price: 0,
    description: 'Perfect for trying out',
    features: ['1 design visualization', 'Shoppable product list', 'Save to your account'],
    enabled: true,
  },
  {
    value: 'basic' as TierType,
    name: 'Basic',
    views: 3,
    price: 299,
    description: 'Compare different styles',
    features: ['3 design visualizations', 'Multiple style options', 'Shoppable product lists', 'Save to your account'],
    enabled: true,
  },
  {
    value: 'premium' as TierType,
    name: 'Premium',
    views: 6,
    price: 599,
    description: 'Full design experience',
    features: ['6 design visualizations', 'All style options', 'Priority generation', 'Shoppable product lists', 'Save to your account'],
    enabled: false,
    comingSoon: true,
  },
];

export default function TierSelectionPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedTier, setSelectedTier] = useState<TierType | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const storedSessionId = sessionStorage.getItem('homestyling_session_id');
    if (!storedSessionId) {
      router.push('/homestyling/preferences');
      return;
    }
    setSessionId(storedSessionId);
  }, [router]);

  const handleSelectTier = (tier: TierType) => {
    const tierData = TIERS.find((t) => t.value === tier);
    if (tierData?.enabled) {
      setSelectedTier(tier);
    }
  };

  const handleGenerate = async () => {
    if (!selectedTier || !sessionId) return;

    // Check if user is authenticated for paid tiers (in future)
    // For now, allow anonymous for free tier
    if (!isAuthenticated && !isLoading) {
      // Store current state and redirect to login
      sessionStorage.setItem('homestyling_return_to', '/homestyling/tier');
      router.push('/login');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Select tier
      await api.post(`/api/homestyling/sessions/${sessionId}/select-tier`, {
        tier: selectedTier,
      });

      // Navigate to results page immediately - generation will happen there
      router.push(`/homestyling/results/${sessionId}`);
    } catch (err: any) {
      console.error('Error selecting tier:', err);
      setError(err.response?.data?.detail || 'Failed to select tier. Please try again.');
      setIsSubmitting(false);
    }
  };

  const formatPrice = (price: number) => {
    if (price === 0) return 'Free';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="w-16 h-1 bg-emerald-600 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="w-16 h-1 bg-emerald-600 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
              3
            </div>
            <div className="w-16 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-sm font-bold">
              4
            </div>
          </div>
          <p className="text-center text-sm text-gray-500">Step 3 of 4: Choose Your Plan</p>
        </div>

        {/* Tier Selection */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Choose Your Plan</h1>
          <p className="text-gray-600">Select how many design views you'd like to see</p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mb-8">
          {TIERS.map((tier) => (
            <div
              key={tier.value}
              onClick={() => handleSelectTier(tier.value)}
              className={`relative bg-white rounded-xl border-2 p-6 transition-all ${
                tier.enabled
                  ? selectedTier === tier.value
                    ? 'border-emerald-500 shadow-lg'
                    : 'border-gray-200 hover:border-gray-300 cursor-pointer'
                  : 'border-gray-200 opacity-60 cursor-not-allowed'
              }`}
            >
              {tier.comingSoon && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-gray-800 text-white text-xs font-medium px-3 py-1 rounded-full">
                    Coming Soon
                  </span>
                </div>
              )}

              {selectedTier === tier.value && tier.enabled && (
                <div className="absolute top-4 right-4 w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              )}

              <h3 className="text-lg font-bold text-gray-900 mb-1">{tier.name}</h3>
              <p className="text-sm text-gray-500 mb-4">{tier.description}</p>

              <div className="mb-4">
                <span className="text-3xl font-bold text-gray-900">{formatPrice(tier.price)}</span>
              </div>

              <div className="text-lg font-semibold text-emerald-600 mb-4">
                {tier.views} {tier.views === 1 ? 'View' : 'Views'}
              </div>

              <ul className="space-y-2">
                {tier.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                    <svg
                      className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <button
            onClick={() => router.push('/homestyling/upload')}
            className="text-gray-600 hover:text-gray-800 font-medium"
          >
            Back
          </button>
          <button
            onClick={handleGenerate}
            disabled={!selectedTier || isSubmitting}
            className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all ${
              selectedTier
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }`}
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Generating...
              </>
            ) : (
              <>
                Generate My Designs
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
