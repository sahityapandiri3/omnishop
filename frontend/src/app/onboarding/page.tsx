'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ProgressBar } from '@/components/onboarding/ProgressBar';
import { RoomTypeStep } from '@/components/onboarding/RoomTypeStep';
import { StylePreferenceStep } from '@/components/onboarding/StylePreferenceStep';
import { BudgetStep } from '@/components/onboarding/BudgetStep';
import { PhotoUploadStep } from '@/components/onboarding/PhotoUploadStep';
import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { projectsAPI } from '@/utils/api';

export interface OnboardingPreferences {
  roomType: string | null;
  primaryStyle: string | null;
  secondaryStyle: string | null;
  budget: number | null;
  budgetFlexible: boolean;
  roomImage: string | null;
  processedImage: string | null;
}

const TOTAL_STEPS = 4;

function OnboardingPageContent() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Image processing state
  const [isProcessingImage, setIsProcessingImage] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [processingError, setProcessingError] = useState<string | null>(null);

  const [preferences, setPreferences] = useState<OnboardingPreferences>({
    roomType: null,
    primaryStyle: null,
    secondaryStyle: null,
    budget: null,
    budgetFlexible: false,
    roomImage: null,
    processedImage: null,
  });

  const updatePreferences = useCallback((updates: Partial<OnboardingPreferences>) => {
    setPreferences(prev => ({ ...prev, ...updates }));
  }, []);

  const handleNext = useCallback(() => {
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep(prev => prev + 1);
    }
  }, [currentStep]);

  const handleBack = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
    }
  }, [currentStep]);

  const handleSkip = useCallback(() => {
    handleNext();
  }, [handleNext]);

  const handleComplete = useCallback(async () => {
    setIsSubmitting(true);

    try {
      // Clear any existing session data
      sessionStorage.removeItem('design_session_id');
      sessionStorage.removeItem('curatedVisualizationImage');
      sessionStorage.removeItem('curatedRoomImage');
      sessionStorage.removeItem('preselectedProducts');
      sessionStorage.removeItem('preselectedLookTheme');
      sessionStorage.removeItem('pendingFurnitureRemoval');

      // Store preferences in sessionStorage for design studio
      sessionStorage.setItem('onboardingPreferences', JSON.stringify(preferences));

      // Store room images - use processed image as the base for design
      if (preferences.processedImage) {
        // Store the processed (clean) image as both roomImage and cleanRoomImage
        // This ensures the design page shows the furniture-removed image
        console.log('[Onboarding] Storing PROCESSED image as roomImage, length:', preferences.processedImage.length);
        sessionStorage.setItem('cleanRoomImage', preferences.processedImage);
        sessionStorage.setItem('roomImage', preferences.processedImage);
      } else if (preferences.roomImage) {
        // No processed image - use original (furniture removal may not have completed)
        console.log('[Onboarding] No processed image, storing ORIGINAL image as roomImage');
        sessionStorage.setItem('roomImage', preferences.roomImage);
      }

      // If authenticated, create a new project
      if (isAuthenticated) {
        try {
          const roomName = preferences.roomType === 'living_room' ? 'Living Room' :
                          preferences.roomType === 'bedroom' ? 'Bedroom' : 'Room';
          const styleName = preferences.primaryStyle ?
            preferences.primaryStyle.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : '';
          const projectName = styleName ? `${styleName} ${roomName}` : `My ${roomName}`;

          const project = await projectsAPI.create({ name: projectName });
          router.push(`/design?projectId=${project.id}`);
        } catch (error) {
          console.error('[Onboarding] Failed to create project:', error);
          router.push('/design');
        }
      } else {
        router.push('/design');
      }
    } catch (error) {
      console.error('[Onboarding] Error completing onboarding:', error);
      router.push('/design');
    } finally {
      setIsSubmitting(false);
    }
  }, [preferences, isAuthenticated, router]);

  const canProceed = useCallback(() => {
    switch (currentStep) {
      case 1:
        return preferences.roomType !== null;
      case 2:
        return true; // Style is optional
      case 3:
        return true; // Budget is optional
      case 4:
        // Can proceed if no image, or if image is processed
        // Cannot proceed if processing is in progress
        if (isProcessingImage) return false;
        return true;
      default:
        return false;
    }
  }, [currentStep, preferences.roomType, isProcessingImage]);

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <button
            onClick={() => router.push('/curated')}
            className="text-neutral-500 hover:text-neutral-700 transition-colors flex items-center gap-2 text-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Close
          </button>
          <h1 className="text-lg font-medium text-neutral-900">Create Your Design</h1>
          <div className="w-16" /> {/* Spacer for centering */}
        </div>
      </header>

      {/* Progress Bar */}
      <ProgressBar currentStep={currentStep} totalSteps={TOTAL_STEPS} />

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        <div className={`flex-1 mx-auto w-full px-6 py-8 ${currentStep === 2 ? 'max-w-6xl' : 'max-w-3xl'}`}>
          {/* Step Content */}
          <div className="flex-1">
            {currentStep === 1 && (
              <RoomTypeStep
                selectedRoom={preferences.roomType}
                onSelect={(roomType) => updatePreferences({ roomType })}
              />
            )}
            {currentStep === 2 && (
              <StylePreferenceStep
                primaryStyle={preferences.primaryStyle}
                secondaryStyle={preferences.secondaryStyle}
                onSelect={(primary, secondary) =>
                  updatePreferences({ primaryStyle: primary, secondaryStyle: secondary })
                }
              />
            )}
            {currentStep === 3 && (
              <BudgetStep
                budget={preferences.budget}
                isFlexible={preferences.budgetFlexible}
                onSelect={(budget, flexible) =>
                  updatePreferences({ budget, budgetFlexible: flexible })
                }
              />
            )}
            {currentStep === 4 && (
              <PhotoUploadStep
                image={preferences.roomImage}
                processedImage={preferences.processedImage}
                isProcessing={isProcessingImage}
                processingStatus={processingStatus}
                onUpload={(original, processed) => {
                  setProcessingError(null);
                  updatePreferences({ roomImage: original, processedImage: processed });
                }}
                onProcessingStart={() => {
                  setIsProcessingImage(true);
                  setProcessingStatus('Preparing your room...');
                  setProcessingError(null);
                }}
                onProcessingComplete={(processedImage) => {
                  console.log('[Onboarding] Processing complete, setting processedImage, length:', processedImage.length);
                  setIsProcessingImage(false);
                  setProcessingStatus('');
                  updatePreferences({ processedImage });
                }}
                onProcessingError={(error) => {
                  setIsProcessingImage(false);
                  setProcessingStatus('');
                  setProcessingError(error);
                }}
              />
            )}
            {processingError && currentStep === 4 && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm text-center">
                {processingError}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Footer */}
        <footer className="bg-white border-t border-neutral-200 px-6 py-4">
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            {/* Back Button */}
            <button
              onClick={handleBack}
              disabled={currentStep === 1}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                currentStep === 1
                  ? 'text-neutral-300 cursor-not-allowed'
                  : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>

            {/* Right Side Buttons */}
            <div className="flex items-center gap-3">
              {/* Skip Button (not shown on step 1 or last step) */}
              {currentStep > 1 && currentStep < TOTAL_STEPS && (
                <button
                  onClick={handleSkip}
                  className="px-4 py-2 text-sm font-medium text-neutral-500 hover:text-neutral-700 transition-colors"
                >
                  Skip
                </button>
              )}

              {/* Next / Start Button */}
              {currentStep < TOTAL_STEPS ? (
                <button
                  onClick={handleNext}
                  disabled={!canProceed()}
                  className={`flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-lg transition-all ${
                    canProceed()
                      ? 'bg-neutral-900 text-white hover:bg-neutral-800 shadow-sm'
                      : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                  }`}
                >
                  Next
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              ) : (
                <button
                  onClick={handleComplete}
                  disabled={isSubmitting || isProcessingImage}
                  className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-lg bg-neutral-800 text-white hover:bg-neutral-900 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <>
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Creating...
                    </>
                  ) : isProcessingImage ? (
                    <>
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Processing Image...
                    </>
                  ) : (
                    <>
                      Start Designing
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <ProtectedRoute>
      <OnboardingPageContent />
    </ProtectedRoute>
  );
}
