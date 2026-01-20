'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

const FEATURES = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
    title: 'Browse Curated Looks',
    description: 'Access our entire collection of professionally curated room designs with shoppable product lists.',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    title: 'AI Design Studio',
    description: 'Create custom visualizations with our AI-powered design tool. Add, remove, and arrange furniture in your space.',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    ),
    title: 'Save Your Projects',
    description: 'Keep all your design projects organized in one place. Access them anytime, anywhere.',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    ),
    title: 'Unlimited Visualizations',
    description: 'Generate as many room visualizations as you need with no limits on AI generations.',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: 'Full Product Access',
    description: 'Shop directly from designs with links to purchase every product you see.',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    title: 'Priority Generation',
    description: 'Skip the queue with faster AI processing for your design requests.',
  },
];

export default function UpgradePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  const [isProcessing, setIsProcessing] = useState(false);

  // Check if coming from purchase (Style This Further) or other sources
  const fromSource = searchParams?.get('from');
  const redirectTo = searchParams?.get('redirect');
  const [hasStyleThisFurtherData, setHasStyleThisFurtherData] = useState(false);

  useEffect(() => {
    // Check if we have Style This Further data in sessionStorage
    const data = sessionStorage.getItem('styleThisFurther');
    setHasStyleThisFurtherData(fromSource === 'purchase' && !!data);
  }, [fromSource]);

  const handleUpgrade = async () => {
    console.log('[Upgrade] handleUpgrade called, fromSource:', fromSource);

    if (!isAuthenticated && !isLoading) {
      // Redirect to login with return URL
      sessionStorage.setItem('upgrade_return_to', `/upgrade?from=${fromSource || ''}`);
      router.push('/login');
      return;
    }

    setIsProcessing(true);
    // TODO: Integrate with payment gateway (Razorpay/Stripe)
    // For now, simulate successful upgrade and redirect

    // If coming from purchase with "Style this further", redirect to design page
    const styleThisFurtherData = sessionStorage.getItem('styleThisFurther');
    console.log('[Upgrade] styleThisFurtherData exists:', !!styleThisFurtherData);
    if (styleThisFurtherData) {
      const parsed = JSON.parse(styleThisFurtherData);
      console.log('[Upgrade] styleThisFurther contents:', {
        hasPurchaseId: !!parsed.purchaseId,
        hasViewId: !!parsed.viewId,
        hasVisualization: !!parsed.visualization,
        vizLength: parsed.visualization?.length || 0,
        hasCleanRoomImage: !!parsed.cleanRoomImage,
        cleanRoomLength: parsed.cleanRoomImage?.length || 0,
        hasProducts: !!parsed.products,
        productsCount: parsed.products?.length || 0,
      });
    }
    if (fromSource === 'purchase' && styleThisFurtherData) {
      try {
        const data = JSON.parse(styleThisFurtherData);

        // Clear any existing design data to ensure fresh load
        sessionStorage.removeItem('roomImage');
        sessionStorage.removeItem('persistedCanvasProducts');

        // Transfer data to design page format
        // Use cleanRoomImage (furniture-removed version) for the design canvas
        if (data.cleanRoomImage) {
          sessionStorage.setItem('curatedRoomImage', data.cleanRoomImage);
          sessionStorage.setItem('cleanRoomImage', data.cleanRoomImage);
          console.log('[Upgrade] Set curatedRoomImage, length:', data.cleanRoomImage.length);
        } else {
          console.warn('[Upgrade] No cleanRoomImage in styleThisFurther data');
        }
        if (data.visualization) {
          sessionStorage.setItem('curatedVisualizationImage', data.visualization);
          console.log('[Upgrade] Set curatedVisualizationImage, length:', data.visualization.length);
        } else {
          console.warn('[Upgrade] No visualization in styleThisFurther data');
        }
        if (data.products && data.products.length > 0) {
          sessionStorage.setItem('preselectedProducts', JSON.stringify(data.products));
          console.log('[Upgrade] Set preselectedProducts, count:', data.products.length);
        } else {
          console.warn('[Upgrade] No products in styleThisFurther data');
        }
        // Clean up
        sessionStorage.removeItem('styleThisFurther');

        // Skip payment for testing - directly redirect to design
        router.push('/design');
      } catch (e) {
        console.error('Failed to parse styleThisFurther data:', e);
        alert('Payment integration coming soon! Contact support@omnishop.com for early access.');
      }
    } else if (redirectTo) {
      // Handle redirect param (e.g., redirect=curated for "Build Your Own")
      // Skip payment for testing - directly redirect
      router.push(`/${redirectTo}`);
    } else {
      alert('Payment integration coming soon! Contact support@omnishop.com for early access.');
    }
    setIsProcessing(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white py-12">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium mb-6">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            Premium
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">Build Your Own Designs</h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Take full control of your interior design journey with our professional tools
          </p>
        </div>

        {/* Pricing Card */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden mb-12">
          <div className="bg-gradient-to-r from-emerald-500 to-emerald-600 p-8 text-center text-white">
            <p className="text-emerald-100 mb-2">Build Your Own</p>
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-5xl font-bold">₹999</span>
              <span className="text-emerald-100">/month</span>
            </div>
            <p className="text-emerald-100 mt-2 text-sm">Cancel anytime</p>
          </div>

          <div className="p-8">
            {/* Features Grid */}
            <div className="grid md:grid-cols-2 gap-6 mb-8">
              {FEATURES.map((feature, index) => (
                <div key={index} className="flex gap-4">
                  <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center flex-shrink-0 text-emerald-600">
                    {feature.icon}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">{feature.title}</h3>
                    <p className="text-sm text-gray-600">{feature.description}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* CTA */}
            <button
              onClick={handleUpgrade}
              disabled={isProcessing}
              className="w-full py-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isProcessing ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                  Processing...
                </span>
              ) : (
                'Upgrade to Build Your Own'
              )}
            </button>

            <p className="text-center text-sm text-gray-500 mt-4">
              Secure payment powered by Razorpay
            </p>
          </div>
        </div>

        {/* Comparison */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Compare Plans</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-500">Feature</th>
                  <th className="px-6 py-3 text-center text-sm font-medium text-gray-500">Free</th>
                  <th className="px-6 py-3 text-center text-sm font-medium text-emerald-600">Build Your Own</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr>
                  <td className="px-6 py-4 text-sm text-gray-900">AI-generated room looks</td>
                  <td className="px-6 py-4 text-center text-sm text-gray-600">1-6 per session</td>
                  <td className="px-6 py-4 text-center text-sm text-emerald-600 font-medium">Unlimited</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-sm text-gray-900">Browse curated looks</td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-emerald-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-sm text-gray-900">AI Design Studio</td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-emerald-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-sm text-gray-900">Save projects</td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-emerald-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-sm text-gray-900">Priority processing</td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <svg className="w-5 h-5 text-emerald-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8.586 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Back Link */}
        <div className="text-center mt-8">
          <button
            onClick={() => router.back()}
            className="text-gray-600 hover:text-gray-800 font-medium"
          >
            ← Back
          </button>
        </div>
      </div>
    </div>
  );
}
