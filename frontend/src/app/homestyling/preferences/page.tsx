'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import api from '@/utils/api';

type RoomType = 'living_room' | 'bedroom';
type StyleType = 'modern' | 'modern_luxury' | 'indian_contemporary';
type ColorPalette = 'warm' | 'neutral' | 'cool' | 'bold';

const ROOM_TYPES = [
  {
    value: 'living_room' as RoomType,
    label: 'Living Room',
    description: 'Sofas, coffee tables, entertainment',
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
    gradient: 'from-gray-700 to-gray-900',
  },
  {
    value: 'modern_luxury' as StyleType,
    label: 'Modern Luxury',
    description: 'Premium finishes, elegant details',
    gradient: 'from-amber-600 to-amber-800',
  },
  {
    value: 'indian_contemporary' as StyleType,
    label: 'Indian Contemporary',
    description: 'Warm tones, artisanal crafts',
    gradient: 'from-orange-600 to-red-700',
  },
];

const COLORS = [
  { value: 'warm' as ColorPalette, label: 'Warm', colors: ['#D4A574', '#C17F59', '#8B4513'] },
  { value: 'neutral' as ColorPalette, label: 'Neutral', colors: ['#E8E4E1', '#B5B0AC', '#6B6762'] },
  { value: 'cool' as ColorPalette, label: 'Cool', colors: ['#7EA8BE', '#4A7C8E', '#2C5F6E'] },
  { value: 'bold' as ColorPalette, label: 'Bold', colors: ['#C7522A', '#E5C185', '#4A6C6F'] },
];

export default function PreferencesPage() {
  const router = useRouter();
  const [roomType, setRoomType] = useState<RoomType | null>(null);
  const [style, setStyle] = useState<StyleType | null>(null);
  const [colorPalette, setColorPalette] = useState<ColorPalette[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleColor = (color: ColorPalette) => {
    setColorPalette((prev) =>
      prev.includes(color) ? prev.filter((c) => c !== color) : [...prev, color]
    );
  };

  const canContinue = roomType && style;

  const handleContinue = async () => {
    if (!canContinue) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // Create session with preferences
      const response = await api.post('/api/homestyling/sessions', {
        room_type: roomType,
        style: style,
        color_palette: colorPalette,
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
                onClick={() => setRoomType(room.value)}
                className={`p-4 rounded-xl border-2 transition-all text-left ${
                  roomType === room.value
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div
                  className={`mb-2 ${
                    roomType === room.value ? 'text-emerald-600' : 'text-gray-400'
                  }`}
                >
                  {room.icon}
                </div>
                <h3 className="font-medium text-gray-900">{room.label}</h3>
                <p className="text-xs text-gray-500">{room.description}</p>
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
                className={`relative rounded-xl overflow-hidden h-32 transition-all ${
                  style === s.value ? 'ring-4 ring-emerald-500 ring-offset-2' : ''
                }`}
              >
                <div
                  className={`absolute inset-0 bg-gradient-to-br ${s.gradient} flex flex-col justify-end p-3 text-white`}
                >
                  <h3 className="font-semibold text-sm">{s.label}</h3>
                  <p className="text-xs text-white/80">{s.description}</p>
                </div>
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

        {/* Color Palette */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Color Preferences</h2>
          <p className="text-sm text-gray-500 mb-4">Optional: Select preferred color palettes</p>

          <div className="grid grid-cols-4 gap-4">
            {COLORS.map((color) => (
              <button
                key={color.value}
                onClick={() => toggleColor(color.value)}
                className={`p-3 rounded-xl border-2 transition-all ${
                  colorPalette.includes(color.value)
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex gap-1 mb-2 justify-center">
                  {color.colors.map((c, i) => (
                    <div
                      key={i}
                      className="w-5 h-5 rounded-full"
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
                <p className="text-xs font-medium text-gray-700 text-center">{color.label}</p>
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
              canContinue
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }`}
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Saving...
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
