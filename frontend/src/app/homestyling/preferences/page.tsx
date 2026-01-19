'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/utils/api';

type RoomType = 'living_room' | 'bedroom';
type StyleType = 'modern' | 'modern_luxury' | 'indian_contemporary';
type BudgetTier = 'pocket_friendly' | 'mid_tier' | 'premium' | 'luxury';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const ROOM_TYPES = [
  {
    value: 'living_room' as RoomType,
    label: 'Living Room',
    description: 'Sofas, coffee tables, entertainment',
    comingSoon: false,
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
      </svg>
    ),
  },
  {
    value: 'bedroom' as RoomType,
    label: 'Bedroom',
    description: 'Beds, dressers, nightstands',
    comingSoon: true,
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h14a2 2 0 012 2v4zM3 18v-2h18v2M5 8V6a2 2 0 012-2h10a2 2 0 012 2v2" />
      </svg>
    ),
  },
];

const STYLES = [
  {
    value: 'modern' as StyleType,
    label: 'Modern',
    description: 'Clean lines, neutral tones',
    imagePath: `${API_URL}/api/styles/Style_Modern.jpg`,
  },
  {
    value: 'modern_luxury' as StyleType,
    label: 'Modern Luxury',
    description: 'Premium finishes, elegant details',
    imagePath: `${API_URL}/api/styles/Style_Luxury.jpg`,
  },
  {
    value: 'indian_contemporary' as StyleType,
    label: 'Indian Contemporary',
    description: 'Warm tones, artisanal crafts',
    imagePath: `${API_URL}/api/styles/Style_Indian.jpg`,
  },
];

const BUDGET_TIERS = [
  {
    value: 'pocket_friendly' as BudgetTier,
    label: 'Budget Friendly',
    range: 'Under ₹2L',
    description: 'Essential quality pieces',
  },
  {
    value: 'mid_tier' as BudgetTier,
    label: 'Mid Range',
    range: '₹2L – ₹8L',
    description: 'Balance of quality & value',
  },
  {
    value: 'premium' as BudgetTier,
    label: 'Premium',
    range: '₹8L – ₹15L',
    description: 'High-end designer pieces',
  },
  {
    value: 'luxury' as BudgetTier,
    label: 'Luxury',
    range: '₹15L+',
    description: 'Exclusive luxury brands',
  },
];

export default function PreferencesPage() {
  const router = useRouter();
  const [roomType, setRoomType] = useState<RoomType | null>(null);
  const [style, setStyle] = useState<StyleType | null>(null);
  const [budgetTier, setBudgetTier] = useState<BudgetTier | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canContinue = roomType && style && budgetTier;

  const handleContinue = async () => {
    if (!canContinue) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // Create session with preferences via API
      const response = await api.post('/api/homestyling/sessions', {
        room_type: roomType,
        style: style,
        budget_tier: budgetTier,
        color_palette: [],
      });

      const sessionId = response.data.id;
      // Store session ID in sessionStorage
      sessionStorage.setItem('homestyling_session_id', sessionId);

      // Navigate to upload page
      router.push('/homestyling/upload');
    } catch (err: any) {
      console.error('Error creating session:', err);
      setError(err.response?.data?.detail || 'Failed to save preferences. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
              1
            </div>
            <div className="w-16 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-sm font-bold">
              2
            </div>
            <div className="w-16 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-sm font-bold">
              3
            </div>
            <div className="w-16 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-sm font-bold">
              4
            </div>
          </div>
          <p className="text-center text-sm text-gray-500">Step 1 of 4: Choose Your Preferences</p>
        </div>

        {/* Room Type */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Select Room Type</h2>
          <p className="text-sm text-gray-500 mb-4">What room are you styling?</p>

          <div className="grid grid-cols-2 gap-4">
            {ROOM_TYPES.map((room) => (
              <button
                key={room.value}
                onClick={() => !room.comingSoon && setRoomType(room.value)}
                disabled={room.comingSoon}
                className={`relative p-4 rounded-xl border-2 transition-all text-left ${
                  room.comingSoon
                    ? 'border-gray-100 bg-gray-50 cursor-not-allowed opacity-60'
                    : roomType === room.value
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div
                  className={`mb-2 ${
                    room.comingSoon
                      ? 'text-gray-300'
                      : roomType === room.value
                      ? 'text-emerald-600'
                      : 'text-gray-400'
                  }`}
                >
                  {room.icon}
                </div>
                <h3 className={`font-medium ${room.comingSoon ? 'text-gray-400' : 'text-gray-900'}`}>
                  {room.label}
                </h3>
                <p className={`text-xs ${room.comingSoon ? 'text-gray-400' : 'text-gray-500'}`}>
                  {room.description}
                </p>
                {room.comingSoon && (
                  <span className="absolute top-2 right-2 px-2 py-0.5 bg-gray-200 text-gray-500 text-xs font-medium rounded-full">
                    Coming Soon
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Style */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Select Design Style</h2>
          <p className="text-sm text-gray-500 mb-4">What aesthetic speaks to you?</p>

          <div className="grid grid-cols-3 gap-4">
            {STYLES.map((s) => (
              <button
                key={s.value}
                onClick={() => setStyle(s.value)}
                className={`relative rounded-xl overflow-hidden transition-all ${
                  style === s.value ? 'ring-4 ring-emerald-500 ring-offset-2' : 'hover:shadow-lg'
                }`}
              >
                {/* Thumbnail Image */}
                <div className="aspect-[4/3] relative overflow-hidden bg-gray-100">
                  <img
                    src={s.imagePath}
                    alt={s.label}
                    className="w-full h-full object-cover"
                  />
                  {/* Gradient overlay for text readability */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />

                  {/* Label overlay */}
                  <div className="absolute bottom-0 left-0 right-0 p-3 text-white text-left">
                    <h3 className="font-semibold text-sm">{s.label}</h3>
                    <p className="text-xs text-white/80">{s.description}</p>
                  </div>
                </div>

                {/* Selection checkmark */}
                {style === s.value && (
                  <div className="absolute top-2 right-2 w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center">
                    <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Budget Tier */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Select Your Budget</h2>
          <p className="text-sm text-gray-500 mb-4">We'll show you looks that match your budget range</p>

          <div className="grid grid-cols-2 gap-3">
            {BUDGET_TIERS.map((tier) => (
              <button
                key={tier.value}
                onClick={() => setBudgetTier(tier.value)}
                className={`relative p-4 rounded-xl border-2 transition-all text-left ${
                  budgetTier === tier.value
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <h3 className={`font-medium ${budgetTier === tier.value ? 'text-emerald-700' : 'text-gray-900'}`}>
                    {tier.label}
                  </h3>
                  {budgetTier === tier.value && (
                    <svg className="w-5 h-5 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </div>
                <p className={`text-sm font-medium ${budgetTier === tier.value ? 'text-emerald-600' : 'text-gray-600'}`}>
                  {tier.range}
                </p>
                <p className="text-xs text-gray-500">{tier.description}</p>
              </button>
            ))}
          </div>
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
            onClick={() => router.push('/homestyling')}
            className="text-gray-600 hover:text-gray-800 font-medium"
          >
            Back
          </button>
          <button
            onClick={handleContinue}
            disabled={!canContinue || isSubmitting}
            className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all ${
              !canContinue
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : isSubmitting
                ? 'bg-emerald-700 text-white cursor-wait opacity-80'
                : 'bg-emerald-600 hover:bg-emerald-700 text-white'
            }`}
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Creating session...
              </>
            ) : (
              <>
                Continue
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
