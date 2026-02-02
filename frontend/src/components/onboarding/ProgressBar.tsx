'use client';

interface ProgressBarProps {
  currentStep: number;
  totalSteps: number;
}

const STEP_LABELS = ['Room', 'Style', 'Budget', 'Photo'];

export function ProgressBar({ currentStep, totalSteps }: ProgressBarProps) {
  return (
    <div className="bg-white border-b border-neutral-100 px-6 py-4">
      <div className="max-w-3xl mx-auto">
        {/* Step indicators */}
        <div className="flex items-center justify-between mb-2">
          {Array.from({ length: totalSteps }, (_, i) => {
            const stepNum = i + 1;
            const isCompleted = stepNum < currentStep;
            const isCurrent = stepNum === currentStep;

            return (
              <div key={stepNum} className="flex items-center">
                {/* Step circle */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                      isCompleted
                        ? 'bg-neutral-800 text-white'
                        : isCurrent
                        ? 'bg-neutral-900 text-white'
                        : 'bg-neutral-200 text-neutral-500'
                    }`}
                  >
                    {isCompleted ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      stepNum
                    )}
                  </div>
                  <span
                    className={`mt-1.5 text-xs font-medium ${
                      isCurrent ? 'text-neutral-900' : 'text-neutral-500'
                    }`}
                  >
                    {STEP_LABELS[i]}
                  </span>
                </div>

                {/* Connector line */}
                {stepNum < totalSteps && (
                  <div
                    className={`w-16 sm:w-24 md:w-32 h-0.5 mx-2 transition-colors ${
                      isCompleted ? 'bg-neutral-800' : 'bg-neutral-200'
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div className="mt-4 h-1 bg-neutral-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-neutral-700 to-neutral-600 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${((currentStep - 1) / (totalSteps - 1)) * 100}%` }}
          />
        </div>

        {/* Step counter */}
        <p className="text-center text-xs text-neutral-500 mt-2">
          Step {currentStep} of {totalSteps}
        </p>
      </div>
    </div>
  );
}
