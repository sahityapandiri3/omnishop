'use client';

import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { useState } from 'react';

export default function HomeStylingLandingPage() {
  const router = useRouter();
  const [isStarting, setIsStarting] = useState(false);

  const handleStartStyling = async () => {
    setIsStarting(true);
    // Navigate to preferences page
    router.push('/homestyling/preferences');
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 to-white">
      {/* Hero Section */}
      <div className="max-w-6xl mx-auto px-4 py-12 sm:py-16">
        <div className="text-center mb-12">
          <span className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium mb-4">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
            Beta
          </span>
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            See Your Room{' '}
            <span className="text-emerald-600">Transformed</span>
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-8">
            Upload a photo of your room and get personalized design visualizations
            with real, shoppable furniture. Powered by AI and curated by professional stylists.
          </p>
          <button
            onClick={handleStartStyling}
            disabled={isStarting}
            className="inline-flex items-center gap-2 px-8 py-4 bg-emerald-600 hover:bg-emerald-700 text-white text-lg font-semibold rounded-xl transition-all shadow-lg hover:shadow-xl disabled:opacity-50"
          >
            {isStarting ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                Starting...
              </>
            ) : (
              <>
                Start Styling
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>

        {/* How It Works */}
        <div className="mb-16">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">
            How It Works
          </h2>
          <div className="grid md:grid-cols-4 gap-6">
            {[
              {
                step: '1',
                title: 'Choose Your Style',
                description: 'Select your preferred room type, design style, and color palette.',
                icon: (
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                  </svg>
                ),
              },
              {
                step: '2',
                title: 'Upload Your Room',
                description: 'Take a photo of your empty room or upload an existing one.',
                icon: (
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                ),
              },
              {
                step: '3',
                title: 'Choose Your Plan',
                description: 'Select how many design views you want to see.',
                icon: (
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                ),
              },
              {
                step: '4',
                title: 'Get Your Designs',
                description: 'Receive AI-generated visualizations with shoppable products.',
                icon: (
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                ),
              },
            ].map((item) => (
              <div key={item.step} className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mb-4">
                  {item.icon}
                </div>
                <div className="text-sm text-emerald-600 font-medium mb-1">Step {item.step}</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{item.title}</h3>
                <p className="text-sm text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Styles Preview */}
        <div className="mb-16">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-4">
            Explore Design Styles
          </h2>
          <p className="text-gray-600 text-center mb-8 max-w-xl mx-auto">
            Choose from professionally curated styles that match your taste
          </p>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                name: 'Modern',
                description: 'Clean lines, neutral tones, and minimalist aesthetics',
                color: 'from-gray-700 to-gray-900',
              },
              {
                name: 'Modern Luxury',
                description: 'Premium finishes, rich textures, and elegant details',
                color: 'from-amber-600 to-amber-800',
              },
              {
                name: 'Indian Contemporary',
                description: 'Warm tones, artisanal crafts, and cultural elements',
                color: 'from-orange-600 to-red-700',
              },
            ].map((style) => (
              <div
                key={style.name}
                className={`relative overflow-hidden rounded-xl p-6 bg-gradient-to-br ${style.color} text-white h-48 flex flex-col justify-end`}
              >
                <h3 className="text-xl font-bold mb-1">{style.name}</h3>
                <p className="text-sm text-white/80">{style.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center bg-emerald-600 rounded-2xl p-8 sm:p-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4">
            Ready to Transform Your Space?
          </h2>
          <p className="text-emerald-100 mb-6 max-w-lg mx-auto">
            Get started for free with one design view. No credit card required.
          </p>
          <button
            onClick={handleStartStyling}
            disabled={isStarting}
            className="inline-flex items-center gap-2 px-8 py-4 bg-white text-emerald-600 text-lg font-semibold rounded-xl hover:bg-emerald-50 transition-all shadow-lg disabled:opacity-50"
          >
            Get Started Free
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
