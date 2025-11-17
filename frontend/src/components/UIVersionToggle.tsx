'use client';

import { useState, useEffect } from 'react';
import { getFeatureFlags, toggleNewUI } from '@/config/features';

/**
 * Developer toggle for switching between old and new UI
 * Only shown when showUIToggle feature flag is enabled
 */
export default function UIVersionToggle() {
  const [flags, setFlags] = useState(getFeatureFlags());
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Update flags when component mounts
    setFlags(getFeatureFlags());
  }, []);

  // Don't render if toggle is disabled
  if (!flags.showUIToggle) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* Toggle button */}
      <button
        onClick={() => setIsVisible(!isVisible)}
        className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white px-4 py-2 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 flex items-center gap-2"
        title="Toggle UI Version"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        <span className="font-medium">UI Version</span>
      </button>

      {/* Settings panel */}
      {isVisible && (
        <div className="absolute bottom-16 right-0 bg-white dark:bg-neutral-800 rounded-lg shadow-2xl p-6 w-80 border border-neutral-200 dark:border-neutral-700">
          <h3 className="text-lg font-semibold mb-4 text-neutral-900 dark:text-white">
            UI Version Control
          </h3>

          {/* Current version indicator */}
          <div className="mb-4 p-3 bg-neutral-50 dark:bg-neutral-700 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                Current UI:
              </span>
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold ${
                  flags.useNewUI
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                }`}
              >
                {flags.useNewUI ? 'New UI (V2)' : 'Classic UI (V1)'}
              </span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400">
              {flags.useNewUI
                ? '3-panel layout with canvas & click-to-move'
                : 'Original chat-based interface'}
            </p>
          </div>

          {/* Toggle button */}
          <button
            onClick={toggleNewUI}
            className="w-full bg-primary-600 hover:bg-primary-700 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center gap-2"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
              />
            </svg>
            Switch to {flags.useNewUI ? 'Classic UI' : 'New UI'}
          </button>

          {/* Feature flags info */}
          <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-700">
            <h4 className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-2">
              Active Features:
            </h4>
            <div className="space-y-1">
              {flags.enableThreePanelLayout && (
                <div className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span>Three-panel layout</span>
                </div>
              )}
              {flags.enableCanvasPanel && (
                <div className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span>Canvas panel</span>
                </div>
              )}
              {flags.enableClickToMove && (
                <div className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span>Click-to-move furniture</span>
                </div>
              )}
            </div>
          </div>

          {/* Note */}
          <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <p className="text-xs text-amber-800 dark:text-amber-200">
              <strong>Note:</strong> Page will reload when switching UI versions.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
