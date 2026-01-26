'use client';

/**
 * VisualizationCanvas Component
 *
 * Shared component for displaying visualization results:
 * - Room image display (with optional collapse)
 * - Visualization result with angle switching
 * - Loading/progress states
 * - Edit mode overlays
 *
 * Used by both CanvasPanel and Admin Curation page.
 */

import React, { forwardRef } from 'react';
import Image from 'next/image';
import { ViewingAngle, AngleSelector } from '@/components/AngleSelector';
import { formatImageSrc, isBase64Image } from '@/utils/visualization-helpers';
import {
  VisualizationControls,
  OutdatedWarning,
  TextBasedEditControls,
} from './VisualizationControls';

// ============================================================================
// VisualizationPreview - Shows during initial visualization
// ============================================================================

interface VisualizationPreviewProps {
  roomImage: string;
  progress: string;
}

export function VisualizationPreview({ roomImage, progress }: VisualizationPreviewProps) {
  return (
    <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
          Generating Visualization...
        </h3>
      </div>
      <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden">
        {/* Room image as preview background */}
        {isBase64Image(roomImage) ? (
          <img
            src={formatImageSrc(roomImage)}
            alt="Room preview"
            className="w-full h-full object-cover opacity-60"
          />
        ) : (
          <Image
            src={roomImage}
            alt="Room preview"
            fill
            className="object-cover opacity-60"
          />
        )}
        {/* Shimmer overlay animation */}
        <div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
          style={{ backgroundSize: '200% 100%' }}
        />
        {/* Progress indicator */}
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20">
          <div className="bg-black/60 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center">
            <svg className="animate-spin h-8 w-8 text-white mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-white font-medium text-sm">{progress || 'Placing furniture...'}</span>
            <span className="text-white/70 text-xs mt-1">Omni is styling your space</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// VisualizationResult - Shows the completed visualization
// ============================================================================

interface VisualizationResultProps {
  visualizationImage: string;
  currentAngle: ViewingAngle;
  angleImages: Record<ViewingAngle, string | null>;
  loadingAngle: ViewingAngle | null;
  onAngleSelect: (angle: ViewingAngle) => void;
  needsRevisualization: boolean;
  isEditingPositions: boolean;
  isVisualizing: boolean;
  isImprovingQuality: boolean;

  // Controls
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onEnterEditMode: () => void;
  onExitEditMode: () => void;
  onClear?: () => void;

  // Text-based editing (optional)
  enableTextBasedEdits?: boolean;
  editInstructions?: string;
  onEditInstructionsChange?: (value: string) => void;
  onApplyEditInstructions?: () => void;
  editError?: string | null;

  // Children slot for custom edit mode content
  children?: React.ReactNode;
}

export const VisualizationResult = forwardRef<HTMLDivElement, VisualizationResultProps>(
  function VisualizationResult(
    {
      visualizationImage,
      currentAngle,
      angleImages,
      loadingAngle,
      onAngleSelect,
      needsRevisualization,
      isEditingPositions,
      isVisualizing,
      isImprovingQuality,
      canUndo,
      canRedo,
      onUndo,
      onRedo,
      onEnterEditMode,
      onExitEditMode,
      onClear,
      enableTextBasedEdits = false,
      editInstructions = '',
      onEditInstructionsChange,
      onApplyEditInstructions,
      editError,
      children,
    },
    ref
  ) {
    // Determine which image to display
    const displayImage = currentAngle === 'front'
      ? visualizationImage
      : (angleImages[currentAngle] || visualizationImage);

    // Get available angles (ones that have been generated)
    const availableAngles = Object.entries(angleImages)
      .filter(([_, img]) => img !== null)
      .map(([angle]) => angle as ViewingAngle);

    return (
      <div ref={ref} className="p-4 border-b border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
            Visualization Result
          </h3>
          <VisualizationControls
            canUndo={canUndo}
            canRedo={canRedo}
            onUndo={onUndo}
            onRedo={onRedo}
            isEditingPositions={isEditingPositions}
            onEnterEditMode={onEnterEditMode}
            onExitEditMode={onExitEditMode}
            onClear={onClear}
            disabled={isVisualizing || isImprovingQuality}
          />
        </div>

        {/* Multi-Angle Viewer */}
        {!isEditingPositions && (
          <div className="mb-3">
            <AngleSelector
              currentAngle={currentAngle}
              loadingAngle={loadingAngle}
              availableAngles={availableAngles}
              onAngleSelect={onAngleSelect}
              disabled={isVisualizing || needsRevisualization}
            />
          </div>
        )}

        {/* Outdated Warning Banner */}
        <OutdatedWarning visible={needsRevisualization} />

        {/* Image/Canvas Container */}
        <div
          className={`relative ${isEditingPositions ? '' : 'aspect-video'} bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden ${needsRevisualization ? 'ring-2 ring-amber-400 dark:ring-amber-600' : ''} ${isEditingPositions ? 'ring-2 ring-purple-400 dark:ring-purple-600' : ''}`}
        >
          {isEditingPositions && children ? (
            // Custom edit mode content (e.g., DraggableFurnitureCanvas)
            children
          ) : (
            <>
              {/* Display current angle image */}
              {isBase64Image(displayImage) ? (
                <img
                  src={formatImageSrc(displayImage)}
                  alt={`Visualization result - ${currentAngle} view`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <Image
                  src={displayImage!}
                  alt={`Visualization result - ${currentAngle} view`}
                  fill
                  className="object-cover"
                  unoptimized
                />
              )}

              {/* Angle indicator badge */}
              {currentAngle !== 'front' && (
                <div className="absolute top-2 left-2 px-2 py-1 bg-black/60 text-white text-xs font-medium rounded-md">
                  {currentAngle.charAt(0).toUpperCase() + currentAngle.slice(1)} View
                </div>
              )}

              {/* Processing overlay */}
              {(isVisualizing || isImprovingQuality) && (
                <>
                  <div
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
                    style={{ backgroundSize: '200% 100%' }}
                  />
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20">
                    <div className="bg-black/60 backdrop-blur-sm rounded-xl px-6 py-4 flex flex-col items-center">
                      <svg className="animate-spin h-8 w-8 text-white mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className="text-white font-medium text-sm">
                        {isImprovingQuality ? 'Improving quality...' : 'Updating visualization...'}
                      </span>
                      <span className="text-white/70 text-xs mt-1">
                        {isImprovingQuality ? 'Re-rendering from original room' : 'Omni is updating your space'}
                      </span>
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Text-based Edit Controls */}
        {isEditingPositions && enableTextBasedEdits && onEditInstructionsChange && onApplyEditInstructions && (
          <TextBasedEditControls
            instructions={editInstructions}
            onInstructionsChange={onEditInstructionsChange}
            onApply={onApplyEditInstructions}
            onExit={onExitEditMode}
            isProcessing={isVisualizing}
            error={editError}
          />
        )}

        {/* Status messages */}
        {!needsRevisualization && !isEditingPositions && (
          <p className="text-xs text-green-600 dark:text-green-400 mt-2 text-center">
            Visualization up to date
          </p>
        )}
      </div>
    );
  }
);

// ============================================================================
// RoomImageSection - Collapsible room image display
// ============================================================================

interface RoomImageSectionProps {
  roomImage: string | null;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onUpload: () => void;
  onReplace?: () => void;
  isProcessing?: boolean;
  processingLabel?: string;
}

export function RoomImageSection({
  roomImage,
  isCollapsed,
  onToggleCollapse,
  onUpload,
  onReplace,
  isProcessing = false,
  processingLabel = 'Processing...',
}: RoomImageSectionProps) {
  if (!roomImage) {
    return (
      <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
        <h3 className="text-sm font-medium text-neutral-900 dark:text-white mb-3">
          Room Image
        </h3>
        <button
          onClick={onUpload}
          className="w-full p-6 border-2 border-dashed border-neutral-300 dark:border-neutral-600 rounded-lg hover:border-primary-500 dark:hover:border-primary-400 transition-colors"
        >
          <div className="flex flex-col items-center text-neutral-500 dark:text-neutral-400">
            <svg className="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-sm font-medium">Upload room image</span>
            <span className="text-xs mt-1">Click to browse</span>
          </div>
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
          Room Image
        </h3>
        <div className="flex items-center gap-2">
          {onReplace && (
            <button
              onClick={onReplace}
              className="text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium"
            >
              Replace
            </button>
          )}
          <button
            onClick={onToggleCollapse}
            className="p-1 text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
          >
            <svg
              className={`w-5 h-5 transition-transform ${isCollapsed ? '' : 'rotate-180'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden">
          {isBase64Image(roomImage) ? (
            <img
              src={formatImageSrc(roomImage)}
              alt="Room image"
              className="w-full h-full object-cover"
            />
          ) : (
            <Image
              src={roomImage}
              alt="Room image"
              fill
              className="object-cover"
            />
          )}
          {isProcessing && (
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
              <div className="bg-black/60 backdrop-blur-sm rounded-lg px-4 py-2 flex items-center gap-2">
                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-white text-sm">{processingLabel}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
