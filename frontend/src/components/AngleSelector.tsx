'use client';

import React from 'react';

export type ViewingAngle = 'front' | 'left' | 'right' | 'back';

interface AngleSelectorProps {
  currentAngle: ViewingAngle;
  loadingAngle: ViewingAngle | null;
  availableAngles: ViewingAngle[];
  onAngleSelect: (angle: ViewingAngle) => void;
  disabled?: boolean;
}

export function AngleSelector({
  currentAngle,
  loadingAngle,
  availableAngles,
  onAngleSelect,
  disabled = false
}: AngleSelectorProps) {
  const angles: ViewingAngle[] = ['front', 'left', 'right', 'back'];

  const angleLabels: Record<ViewingAngle, string> = {
    front: 'Front',
    left: 'Left',
    right: 'Right',
    back: 'Back'
  };

  const angleIcons: Record<ViewingAngle, React.ReactNode> = {
    front: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
      </svg>
    ),
    left: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
    ),
    right: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
      </svg>
    ),
    back: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
      </svg>
    )
  };

  return (
    <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
      <span className="text-xs text-gray-500 px-2 font-medium">View:</span>
      {angles.map(angle => {
        const isSelected = currentAngle === angle;
        const isLoading = loadingAngle === angle;
        const isAvailable = availableAngles.includes(angle);
        const isDisabled = disabled || loadingAngle !== null;

        return (
          <button
            key={angle}
            onClick={() => onAngleSelect(angle)}
            disabled={isDisabled}
            title={`${angleLabels[angle]} view${!isAvailable && angle !== 'front' ? ' (click to generate)' : ''}`}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200
              ${isSelected
                ? 'bg-purple-600 text-white shadow-sm'
                : isAvailable
                  ? 'bg-white text-gray-700 hover:bg-gray-200 shadow-sm'
                  : 'bg-white/50 text-gray-400 hover:bg-gray-200 hover:text-gray-600'
              }
              ${isDisabled && !isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                <span>Loading...</span>
              </>
            ) : (
              <>
                {angleIcons[angle]}
                <span>{angleLabels[angle]}</span>
                {!isAvailable && angle !== 'front' && (
                  <span className="text-[10px] opacity-60">+</span>
                )}
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}
