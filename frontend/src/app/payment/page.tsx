'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { authAPI } from '@/utils/api';

type PricingTier = 'free' | 'basic' | 'basic_plus' | 'advanced' | 'curator';

interface TierDetails {
  name: string;
  price: string;
  priceValue: number;
  isMonthly: boolean;
  description: string;
}

const tierDetails: Record<PricingTier, TierDetails> = {
  free: {
    name: 'Free',
    price: '₹0',
    priceValue: 0,
    isMonthly: false,
    description: '1 curated look with a sample room',
  },
  basic: {
    name: 'Basic',
    price: '₹399',
    priceValue: 399,
    isMonthly: false,
    description: '3 curated looks of your space',
  },
  basic_plus: {
    name: 'Basic+',
    price: '₹699',
    priceValue: 699,
    isMonthly: false,
    description: '6 curated looks of your room',
  },
  advanced: {
    name: 'Advanced',
    price: '₹11,999',
    priceValue: 11999,
    isMonthly: true,
    description: 'Omni Studio + AI Stylist + 100+ curated looks',
  },
  curator: {
    name: 'Curator',
    price: '₹14,999',
    priceValue: 14999,
    isMonthly: true,
    description: 'Full Omni Studio + Publish to platform',
  },
};

function PaymentPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, refreshUser } = useAuth();
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedTier, setSelectedTier] = useState<PricingTier>('basic');

  // Get tier from URL or sessionStorage
  useEffect(() => {
    const tierParam = searchParams?.get('tier') as PricingTier;
    if (tierParam && tierDetails[tierParam]) {
      setSelectedTier(tierParam);
    } else {
      // Check sessionStorage
      const storedTier = sessionStorage.getItem('selectedPricingTier') as PricingTier;
      if (storedTier && tierDetails[storedTier]) {
        setSelectedTier(storedTier);
      }
    }
  }, [searchParams]);

  const currentTier = tierDetails[selectedTier];

  const handlePayment = async () => {
    setIsProcessing(true);

    try {
      // Upgrade user's subscription tier via API
      await authAPI.upgrade(selectedTier);

      // Refresh user data to get updated tier
      if (refreshUser) {
        await refreshUser();
      }

      // Store payment info in sessionStorage
      sessionStorage.setItem('paymentCompleted', 'true');
      sessionStorage.setItem('paidTier', selectedTier);

      // Check if this upgrade is coming from "Style this further" on purchases page
      const upgradeSource = sessionStorage.getItem('upgradeSource');
      // Clear the flag after reading
      sessionStorage.removeItem('upgradeSource');

      // Navigate to next step based on tier and source
      if (selectedTier === 'curator') {
        // Curator: go directly to curated looks (they don't need the homestyling flow)
        router.push('/curated');
      } else if (selectedTier === 'advanced' && upgradeSource === 'styleThisFurther') {
        // Advanced from "Style this further": go directly to design studio
        // The design context (room image, visualization, products) is already in sessionStorage
        router.push('/design');
      } else if (selectedTier === 'advanced') {
        // Advanced from other sources (e.g., direct from pricing page): go to curated looks
        router.push('/curated');
      } else {
        // Free, Basic, Basic+: go to preferences to set up their styling session
        router.push('/homestyling/preferences');
      }
    } catch (error: any) {
      console.error('Payment/upgrade failed:', error);
      // Show more specific error message
      const errorMessage = error?.response?.data?.detail
        || error?.response?.data?.message
        || error?.message
        || 'Failed to process payment. Please try again.';
      alert(errorMessage);
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Main Content */}
      <div className="max-w-2xl mx-auto px-4 py-12">
        <div className="text-center mb-8">
          <h1 className="font-display text-3xl font-light text-neutral-800 mb-2">
            Complete Your Purchase
          </h1>
          <p className="text-neutral-500">
            You&apos;re one step away from transforming your space
          </p>
        </div>

        {/* Order Summary */}
        <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden mb-6">
          <div className="p-6 border-b border-neutral-100">
            <h2 className="font-medium text-neutral-800 mb-4">Order Summary</h2>
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium text-neutral-900">{currentTier.name} Plan</p>
                <p className="text-sm text-neutral-500 mt-1">{currentTier.description}</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-semibold text-neutral-900">{currentTier.price}</p>
                {currentTier.isMonthly && (
                  <p className="text-sm text-neutral-500">per month</p>
                )}
              </div>
            </div>
          </div>

          {/* Total */}
          <div className="p-6 bg-neutral-50">
            <div className="flex justify-between items-center">
              <span className="font-medium text-neutral-800">Total</span>
              <span className="text-xl font-semibold text-neutral-900">{currentTier.price}</span>
            </div>
            {currentTier.isMonthly && (
              <p className="text-xs text-neutral-500 mt-2">
                Billed monthly. Cancel anytime.
              </p>
            )}
          </div>
        </div>

        {/* Payment Form (Placeholder) */}
        <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-6 mb-6">
          <h2 className="font-medium text-neutral-800 mb-4">Payment Details</h2>

          {/* Demo Notice */}
          <div className="bg-secondary-50 border border-secondary-200 rounded-lg p-4 mb-6">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-secondary-600 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-secondary-800">Demo Mode</p>
                <p className="text-sm text-secondary-600 mt-1">
                  This is a placeholder payment page. No actual payment will be processed.
                  Click &quot;Pay Now&quot; to continue with the flow.
                </p>
              </div>
            </div>
          </div>

          {/* Mock Card Fields */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-600 mb-1.5">
                Card Number
              </label>
              <input
                type="text"
                placeholder="4242 4242 4242 4242"
                disabled
                className="w-full h-12 px-4 rounded-lg border border-neutral-200 bg-neutral-50 text-neutral-400 cursor-not-allowed"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-600 mb-1.5">
                  Expiry Date
                </label>
                <input
                  type="text"
                  placeholder="MM/YY"
                  disabled
                  className="w-full h-12 px-4 rounded-lg border border-neutral-200 bg-neutral-50 text-neutral-400 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-600 mb-1.5">
                  CVV
                </label>
                <input
                  type="text"
                  placeholder="123"
                  disabled
                  className="w-full h-12 px-4 rounded-lg border border-neutral-200 bg-neutral-50 text-neutral-400 cursor-not-allowed"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Pay Button */}
        <button
          onClick={handlePayment}
          disabled={isProcessing}
          className="w-full py-4 bg-neutral-800 text-white text-sm font-medium rounded-lg hover:bg-neutral-900 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md"
        >
          {isProcessing ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Processing...
            </span>
          ) : (
            `Pay ${currentTier.price}${currentTier.isMonthly ? '/month' : ''}`
          )}
        </button>

        {/* Security Note */}
        <div className="flex items-center justify-center gap-2 mt-6 text-neutral-400">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
          <span className="text-xs">Secure checkout powered by Razorpay</span>
        </div>

        {/* Back to Pricing */}
        <div className="text-center mt-8">
          <Link
            href="/pricing"
            className="text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
          >
            Change plan
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return (
    <ProtectedRoute requiredRole="user">
      <PaymentPageContent />
    </ProtectedRoute>
  );
}
