'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

type PricingTier = 'free' | 'basic' | 'basic_plus' | 'advanced' | 'curator';
type UserType = 'homeowner' | 'professional';

interface TierInfo {
  id: PricingTier;
  name: string;
  price: string;
  priceSubtext: string;
  description: string;
  features: string[];
  highlighted?: boolean;
  ctaText: string;
  userType: UserType; // Which user type this tier is for
}

const tiers: TierInfo[] = [
  {
    id: 'free',
    name: 'Free',
    price: '₹0',
    priceSubtext: 'one-time',
    description: 'Try our AI styling with a sample room',
    features: [
      '1 curated look',
      'Uses sample room image',
      'Real shoppable products',
      'Basic style matching',
    ],
    ctaText: 'Get Started',
    userType: 'homeowner',
  },
  {
    id: 'basic',
    name: 'Basic',
    price: '₹399',
    priceSubtext: 'one-time',
    description: 'Style your own room with AI',
    features: [
      '3 curated looks',
      'Upload your room photo',
      'Real shoppable products',
      'Style preference matching',
    ],
    ctaText: 'Choose Basic',
    userType: 'homeowner',
  },
  {
    id: 'basic_plus',
    name: 'Basic+',
    price: '₹699',
    priceSubtext: 'one-time',
    description: 'More options for your space',
    features: [
      '6 curated looks',
      'Upload your room photo',
      'Real shoppable products',
      'Advanced style matching',
      'Budget-based recommendations',
    ],
    highlighted: true,
    ctaText: 'Choose Basic+',
    userType: 'homeowner',
  },
  {
    id: 'advanced',
    name: 'Advanced',
    price: '₹11,999',
    priceSubtext: '/month',
    description: 'Full design studio access',
    features: [
      'Omni Studio access',
      'AI Stylist assistant',
      '100+ curated looks library',
      'Unlimited room uploads',
      'Save & manage projects',
      'Priority support',
    ],
    ctaText: 'Go Advanced',
    userType: 'homeowner',
  },
  {
    id: 'curator',
    name: 'Curator',
    price: '₹14,999',
    priceSubtext: '/month',
    description: 'For design professionals',
    features: [
      'Full Omni Studio access',
      'Publish looks to platform',
      'Build your portfolio',
      'Curator badge & profile',
      'Analytics dashboard',
      'Early access to features',
    ],
    ctaText: 'Become a Curator',
    userType: 'professional',
  },
];

export default function PricingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  const [selectedTier, setSelectedTier] = useState<PricingTier | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [userType, setUserType] = useState<UserType>('homeowner');
  const [highlightedTier, setHighlightedTier] = useState<PricingTier | null>(null);

  // Check for highlight parameter (e.g., from purchase page "Style this further" CTA)
  useEffect(() => {
    const highlight = searchParams?.get('highlight') as PricingTier | null;
    if (highlight && ['free', 'basic', 'basic_plus', 'advanced', 'curator'].includes(highlight)) {
      setHighlightedTier(highlight);
      // Auto-select professional tab if highlighting curator
      if (highlight === 'curator') {
        setUserType('professional');
      }
      // Scroll to the tier after a short delay
      setTimeout(() => {
        const element = document.getElementById(`tier-${highlight}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);
    }
  }, [searchParams]);

  // Filter tiers based on user type
  const filteredTiers = tiers.filter(tier => tier.userType === userType);

  const handleSelectTier = async (tier: PricingTier) => {
    setSelectedTier(tier);
    setIsProcessing(true);

    // Store selected tier in sessionStorage for the flow
    sessionStorage.setItem('selectedPricingTier', tier);

    // Determine the next step based on tier and auth status
    if (!isAuthenticated) {
      // Not logged in - redirect to login with the appropriate next step
      const nextStep = getNextStepForTier(tier);
      router.push(`/login?redirect=${encodeURIComponent(nextStep)}`);
      return;
    }

    // User is logged in - route based on tier
    const nextStep = getNextStepForTier(tier);
    router.push(nextStep);
  };

  // NEW FLOW: All tiers go to payment first, then route appropriately after payment
  const getNextStepForTier = (tier: PricingTier): string => {
    // All tiers now go to payment first (including Free with ₹0)
    return '/payment?tier=' + tier;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-neutral-200 border-t-neutral-800" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Hero */}
      <div className="max-w-7xl mx-auto px-4 py-12 text-center">
        <h1 className="font-display text-4xl md:text-5xl font-light text-neutral-800 mb-4">
          Choose Your Styling Experience
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto mb-8">
          From a free preview to professional design tools, find the perfect plan for your space
        </p>

        {/* User Type Toggle */}
        <div className="inline-flex items-center bg-neutral-100 rounded-full p-1 mb-4">
          <button
            onClick={() => setUserType('homeowner')}
            className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${
              userType === 'homeowner'
                ? 'bg-white text-neutral-800 shadow-sm'
                : 'text-neutral-500 hover:text-neutral-700'
            }`}
          >
            I&apos;m a Home Owner/Renter
          </button>
          <button
            onClick={() => setUserType('professional')}
            className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${
              userType === 'professional'
                ? 'bg-white text-neutral-800 shadow-sm'
                : 'text-neutral-500 hover:text-neutral-700'
            }`}
          >
            I&apos;m a Professional Stylist
          </button>
        </div>
      </div>

      {/* Pricing Cards */}
      <div className="max-w-7xl mx-auto px-4 pb-16">
        {/* Dynamic grid based on number of tiers */}
        <div className={`grid grid-cols-1 gap-4 ${
          filteredTiers.length === 1
            ? 'md:grid-cols-1 max-w-md mx-auto'
            : filteredTiers.length === 2
            ? 'md:grid-cols-2 max-w-2xl mx-auto'
            : filteredTiers.length === 3
            ? 'md:grid-cols-3 max-w-4xl mx-auto'
            : 'md:grid-cols-2 lg:grid-cols-4'
        }`}>
          {filteredTiers.map((tier) => {
            const isHighlighted = tier.highlighted || highlightedTier === tier.id;
            return (
            <div
              key={tier.id}
              id={`tier-${tier.id}`}
              className={`relative bg-white rounded-xl border transition-all duration-300 ${
                isHighlighted
                  ? 'border-neutral-800 shadow-lg ring-2 ring-neutral-800'
                  : 'border-neutral-200 shadow-sm'
              } ${
                highlightedTier === tier.id ? 'animate-pulse-once' : ''
              } p-6 flex flex-col`}
            >
              {tier.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-neutral-800 text-white text-xs font-medium px-3 py-1 rounded-full">
                    Most Popular
                  </span>
                </div>
              )}
              {highlightedTier === tier.id && !tier.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-secondary-600 text-white text-xs font-medium px-3 py-1 rounded-full whitespace-nowrap">
                    Upgrade to style further
                  </span>
                </div>
              )}

              <div className="mb-4">
                <h3 className="font-display text-lg font-medium text-neutral-800 mb-1">
                  {tier.name}
                </h3>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-semibold text-neutral-900">{tier.price}</span>
                  <span className="text-sm text-neutral-500">{tier.priceSubtext}</span>
                </div>
                <p className="text-sm text-neutral-500 mt-2">{tier.description}</p>
              </div>

              <ul className="space-y-2.5 mb-6 flex-grow">
                {tier.features.map((feature, index) => (
                  <li key={index} className="flex items-start gap-2 text-sm text-neutral-600">
                    <svg
                      className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleSelectTier(tier.id)}
                disabled={isProcessing && selectedTier === tier.id}
                className={`w-full py-3 px-4 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isHighlighted
                    ? 'bg-neutral-800 text-white hover:bg-neutral-900 shadow-sm'
                    : 'bg-neutral-100 text-neutral-800 hover:bg-neutral-200'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {isProcessing && selectedTier === tier.id ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Processing...
                  </span>
                ) : (
                  tier.ctaText
                )}
              </button>
            </div>
          )})}
        </div>

        {/* Comparison Note */}
        <div className="mt-12 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-secondary-50 rounded-lg border border-secondary-200">
            <svg className="w-5 h-5 text-secondary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm text-secondary-700">
              All plans include real, shoppable products from top Indian brands
            </span>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="mt-16 max-w-3xl mx-auto">
          <h2 className="font-display text-2xl font-light text-neutral-800 text-center mb-8">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            <div className="bg-white rounded-lg border border-neutral-200 p-5">
              <h3 className="font-medium text-neutral-800 mb-2">What&apos;s the difference between Basic and Basic+?</h3>
              <p className="text-sm text-neutral-600">
                Basic gives you 3 curated looks for your room, while Basic+ gives you 6 looks with more variety in styles and budget ranges.
              </p>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-5">
              <h3 className="font-medium text-neutral-800 mb-2">What is Omni Studio?</h3>
              <p className="text-sm text-neutral-600">
                Omni Studio is our full-featured design tool where you can create custom room layouts, browse our entire product catalog, and get AI-powered styling recommendations.
              </p>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-5">
              <h3 className="font-medium text-neutral-800 mb-2">Can I upgrade my plan later?</h3>
              <p className="text-sm text-neutral-600">
                Yes! You can upgrade to a higher tier at any time. For monthly plans, the difference will be prorated.
              </p>
            </div>
            <div className="bg-white rounded-lg border border-neutral-200 p-5">
              <h3 className="font-medium text-neutral-800 mb-2">What does &quot;Publish to platform&quot; mean for Curators?</h3>
              <p className="text-sm text-neutral-600">
                Curators can submit their best designs to our curated gallery, where they&apos;ll be showcased to all users and can inspire others.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-neutral-800 py-6">
        <div className="max-w-5xl mx-auto px-6 text-center">
          <p className="text-xs text-neutral-400">
            © 2025 Omnishop. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
