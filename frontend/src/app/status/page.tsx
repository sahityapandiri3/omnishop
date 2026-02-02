'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';

const GENERATION_STEPS = [
  { id: 1, label: 'Analyzing your preferences', duration: 2000 },
  { id: 2, label: 'Finding matching products', duration: 2500 },
  { id: 3, label: 'Creating your curated look', duration: 3000 },
  { id: 4, label: 'Finalizing visualization', duration: 2000 },
];

function StatusPageContent() {
  const router = useRouter();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  // Simulate generation progress
  useEffect(() => {
    let totalDuration = GENERATION_STEPS.reduce((acc, step) => acc + step.duration, 0);
    let elapsed = 0;

    const updateProgress = () => {
      let stepElapsed = 0;
      let stepIndex = 0;

      for (let i = 0; i < GENERATION_STEPS.length; i++) {
        if (elapsed < stepElapsed + GENERATION_STEPS[i].duration) {
          stepIndex = i;
          break;
        }
        stepElapsed += GENERATION_STEPS[i].duration;
        if (i === GENERATION_STEPS.length - 1) {
          stepIndex = i;
        }
      }

      setCurrentStep(stepIndex);
      setProgress(Math.min((elapsed / totalDuration) * 100, 100));
    };

    const interval = setInterval(() => {
      elapsed += 100;
      updateProgress();

      if (elapsed >= totalDuration) {
        clearInterval(interval);
        setIsComplete(true);
        // Auto-redirect to purchases after a brief delay
        setTimeout(() => {
          router.push('/purchases');
        }, 1500);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [router]);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <svg className="h-7 w-7 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z" />
            </svg>
            <span className="font-display text-xl font-medium text-neutral-800">Omnishop</span>
          </Link>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-xl mx-auto px-4 py-16">
        <div className="text-center">
          {/* Animation Container */}
          <div className="relative w-32 h-32 mx-auto mb-8">
            {/* Outer ring */}
            <div className="absolute inset-0 rounded-full border-4 border-neutral-200" />

            {/* Progress ring */}
            <svg className="absolute inset-0 w-32 h-32 -rotate-90">
              <circle
                cx="64"
                cy="64"
                r="60"
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                strokeDasharray={`${2 * Math.PI * 60}`}
                strokeDashoffset={`${2 * Math.PI * 60 * (1 - progress / 100)}`}
                className="text-neutral-800 transition-all duration-300"
              />
            </svg>

            {/* Center icon */}
            <div className="absolute inset-0 flex items-center justify-center">
              {isComplete ? (
                <svg className="w-12 h-12 text-green-500 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-10 h-10 text-neutral-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              )}
            </div>
          </div>

          {/* Title */}
          <h1 className="font-display text-2xl font-light text-neutral-800 mb-2">
            {isComplete ? 'Your Look is Ready!' : 'Creating Your Curated Look'}
          </h1>

          {/* Subtitle */}
          <p className="text-neutral-500 mb-8">
            {isComplete
              ? 'Redirecting you to your purchases...'
              : 'This usually takes less than a minute'}
          </p>

          {/* Progress Steps */}
          <div className="space-y-3 max-w-sm mx-auto">
            {GENERATION_STEPS.map((step, index) => (
              <div
                key={step.id}
                className={`flex items-center gap-3 p-3 rounded-lg transition-all duration-300 ${
                  index === currentStep
                    ? 'bg-neutral-100'
                    : index < currentStep
                    ? 'bg-green-50'
                    : 'bg-white'
                }`}
              >
                {/* Step indicator */}
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                    index < currentStep
                      ? 'bg-green-500'
                      : index === currentStep
                      ? 'bg-neutral-800'
                      : 'bg-neutral-200'
                  }`}
                >
                  {index < currentStep ? (
                    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : index === currentStep ? (
                    <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                  ) : (
                    <span className="text-xs text-neutral-400">{step.id}</span>
                  )}
                </div>

                {/* Step label */}
                <span
                  className={`text-sm transition-colors duration-300 ${
                    index <= currentStep ? 'text-neutral-800' : 'text-neutral-400'
                  }`}
                >
                  {step.label}
                </span>

                {/* Loading dots for current step */}
                {index === currentStep && !isComplete && (
                  <div className="ml-auto flex gap-1">
                    <div className="w-1.5 h-1.5 bg-neutral-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-1.5 h-1.5 bg-neutral-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-1.5 h-1.5 bg-neutral-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Progress percentage */}
          <div className="mt-8 text-sm text-neutral-400">
            {Math.round(progress)}% complete
          </div>

          {/* Skip button (for demo) */}
          {!isComplete && (
            <button
              onClick={() => router.push('/purchases')}
              className="mt-6 text-sm text-neutral-400 hover:text-neutral-600 transition-colors underline"
            >
              Skip (Demo)
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function StatusPage() {
  return (
    <ProtectedRoute requiredRole="user">
      <StatusPageContent />
    </ProtectedRoute>
  );
}
