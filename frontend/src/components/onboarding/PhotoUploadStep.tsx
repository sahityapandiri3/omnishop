'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { startFurnitureRemoval, checkFurnitureRemovalStatus, projectsAPI, PreviousRoomImage } from '@/utils/api';
import { useAuth } from '@/contexts/AuthContext';

interface PhotoUploadStepProps {
  image: string | null;
  processedImage: string | null;
  isProcessing: boolean;
  processingStatus: string;
  onUpload: (original: string | null, processed: string | null) => void;
  onProcessingStart: () => void;
  onProcessingComplete: (processedImage: string) => void;
  onProcessingError: (error: string) => void;
}

export function PhotoUploadStep({
  image,
  processedImage,
  isProcessing,
  processingStatus,
  onUpload,
  onProcessingStart,
  onProcessingComplete,
  onProcessingError,
}: PhotoUploadStepProps) {
  const { isAuthenticated, user } = useAuth();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // Track original image for save-to-DB after furniture removal
  const originalImageRef = useRef<string | null>(null);

  // Tab state for upload vs previously uploaded
  const [uploadTab, setUploadTab] = useState<'upload' | 'previous'>('upload');
  const [previousRooms, setPreviousRooms] = useState<PreviousRoomImage[]>([]);
  const [loadingPreviousRooms, setLoadingPreviousRooms] = useState(false);
  const [previousRoomsFetched, setPreviousRoomsFetched] = useState(false);
  const [loadingRoomId, setLoadingRoomId] = useState<string | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Fetch previous rooms when tab switches to "previous"
  useEffect(() => {
    if (uploadTab === 'previous' && !previousRoomsFetched) {
      let cancelled = false;
      const fetchPreviousRooms = async () => {
        setLoadingPreviousRooms(true);
        try {
          const response = await projectsAPI.getPreviousRooms(undefined, 10);
          if (!cancelled) {
            setPreviousRooms(response.rooms);
            setPreviousRoomsFetched(true);
          }
        } catch (err) {
          console.error('Failed to fetch previous rooms:', err);
        } finally {
          if (!cancelled) {
            setLoadingPreviousRooms(false);
          }
        }
      };
      fetchPreviousRooms();
      return () => { cancelled = true; };
    }
  }, [uploadTab, previousRoomsFetched]);

  const startProcessing = async (imageData: string) => {
    originalImageRef.current = imageData;
    onProcessingStart();

    try {
      // Start furniture removal
      const response = await startFurnitureRemoval(imageData);
      const jobId = response.job_id;

      // Poll for completion
      let attempts = 0;
      const maxAttempts = 150; // 5 minutes max (2s intervals)

      const poll = async () => {
        attempts++;

        if (attempts > maxAttempts) {
          onProcessingError('Processing timed out. Please try again.');
          return;
        }

        try {
          const status = await checkFurnitureRemovalStatus(jobId);

          if (status.status === 'completed' && status.image) {
            const processedImg = status.image.startsWith('data:')
              ? status.image
              : `data:image/png;base64,${status.image}`;
            console.log('[PhotoUploadStep] Furniture removal completed, image length:', processedImg.length);
            onProcessingComplete(processedImg);
            // Fire-and-forget save to DB (so it appears in "Previously Uploaded")
            if (isAuthenticated && user && originalImageRef.current) {
              const rawOrig = originalImageRef.current.startsWith('data:') ? originalImageRef.current.split(',')[1] : originalImageRef.current;
              const rawClean = status.image.startsWith('data:') ? status.image.split(',')[1] : status.image;
              projectsAPI.saveRoomImage(rawOrig, rawClean).catch(err => console.warn('Failed to save room image to DB:', err));
            }
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          } else if (status.status === 'failed') {
            onProcessingError(status.error || 'Processing failed. Please try again.');
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          }
          // Still processing, continue polling
        } catch (err) {
          console.error('Polling error:', err);
          // Continue polling on transient errors
        }
      };

      // Start polling every 2 seconds
      pollIntervalRef.current = setInterval(poll, 2000);
      poll(); // Initial poll

    } catch (err) {
      console.error('Failed to start processing:', err);
      onProcessingError('Failed to start image processing. Please try again.');
    }
  };

  const processFile = useCallback(
    async (file: File) => {
      setError(null);

      // Validate file type
      if (!file.type.startsWith('image/')) {
        setError('Please upload an image file (JPG, PNG, etc.)');
        return;
      }

      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError('Image size must be less than 10MB');
        return;
      }

      setIsUploading(true);

      try {
        // Convert to base64
        const reader = new FileReader();
        reader.onload = async (e) => {
          const base64 = e.target?.result as string;
          onUpload(base64, null); // Store original, clear processed
          setIsUploading(false);

          // Start furniture removal processing
          await startProcessing(base64);
        };
        reader.onerror = () => {
          setError('Failed to read the image file');
          setIsUploading(false);
        };
        reader.readAsDataURL(file);
      } catch (err) {
        setError('Failed to process the image');
        setIsUploading(false);
      }
    },
    [onUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        processFile(files[0]);
      }
    },
    [processFile]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        processFile(files[0]);
      }
    },
    [processFile]
  );

  const handleRemove = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    onUpload(null, null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [onUpload]);

  // Handle selecting a previous room
  const handleSelectPreviousRoom = useCallback(async (room: PreviousRoomImage) => {
    setLoadingRoomId(room.id);
    setError(null);
    try {
      const response = await projectsAPI.getPreviousRoomImage(room.id, room.source as 'project' | 'homestyling');
      if (response.clean_room_image) {
        const imageData = response.clean_room_image.startsWith('data:')
          ? response.clean_room_image
          : `data:image/png;base64,${response.clean_room_image}`;
        // Previous rooms are already processed (furniture removed)
        onUpload(imageData, imageData);
      }
    } catch (err) {
      console.error('Failed to load previous room:', err);
      setError('Failed to load previous room. Please try again.');
    } finally {
      setLoadingRoomId(null);
    }
  }, [onUpload]);

  // Determine which image to show
  const displayImage = processedImage || image;
  const showingProcessed = !!processedImage;

  return (
    <div className="flex flex-col items-center">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-2xl md:text-3xl font-light text-neutral-900 mb-3">
          Upload your room photo
        </h2>
        <p className="text-neutral-500 font-light">
          We'll prepare your room for furniture visualization
        </p>
      </div>

      {/* Upload Area */}
      <div className="w-full max-w-xl">
        {displayImage ? (
          // Preview
          <div className="relative rounded-2xl overflow-hidden shadow-lg">
            <img
              src={displayImage}
              alt="Uploaded room"
              className="w-full aspect-video object-cover"
            />

            {/* Processing overlay */}
            {isProcessing && (
              <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center">
                <div className="w-16 h-16 border-4 border-white/30 border-t-white rounded-full animate-spin mb-4" />
                <p className="text-white font-medium text-lg mb-2">
                  {processingStatus || 'Preparing your room...'}
                </p>
                <p className="text-white/70 text-sm">
                  Removing existing furniture for visualization
                </p>
              </div>
            )}

            {/* Hover overlay with actions (only when not processing) */}
            {!isProcessing && (
              <div className="absolute inset-0 bg-black/40 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center gap-4">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 bg-white text-neutral-900 rounded-lg font-medium text-sm hover:bg-neutral-100 transition-colors"
                >
                  Change Photo
                </button>
                <button
                  onClick={handleRemove}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg font-medium text-sm hover:bg-red-700 transition-colors"
                >
                  Remove
                </button>
              </div>
            )}

            {/* Status indicator */}
            {!isProcessing && (
              <div className={`absolute top-3 right-3 px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1.5 ${
                showingProcessed
                  ? 'bg-neutral-700 text-white'
                  : 'bg-amber-500 text-white'
              }`}>
                {showingProcessed ? (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Room ready
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Processing...
                  </>
                )}
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Tab Toggle */}
            <div className="flex gap-1 p-1 bg-neutral-100 rounded-xl mb-4">
              <button
                onClick={() => setUploadTab('upload')}
                className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  uploadTab === 'upload'
                    ? 'bg-white text-neutral-900 shadow-sm'
                    : 'text-neutral-500 hover:text-neutral-700'
                }`}
              >
                Upload New
              </button>
              <button
                onClick={() => setUploadTab('previous')}
                className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  uploadTab === 'previous'
                    ? 'bg-white text-neutral-900 shadow-sm'
                    : 'text-neutral-500 hover:text-neutral-700'
                }`}
              >
                Previously Uploaded
                {previousRooms.length > 0 && (
                  <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-neutral-200 rounded-full">
                    {previousRooms.length}
                  </span>
                )}
              </button>
            </div>

            {/* Upload New Tab */}
            {uploadTab === 'upload' && (
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200 ${
                  isDragging
                    ? 'border-neutral-500 bg-neutral-100'
                    : 'border-neutral-300 bg-white hover:border-neutral-400 hover:bg-neutral-50'
                }`}
              >
                {isUploading ? (
                  <div className="flex flex-col items-center">
                    <div className="w-12 h-12 border-3 border-neutral-300 border-t-neutral-800 rounded-full animate-spin mb-4" />
                    <p className="text-neutral-600">Uploading image...</p>
                  </div>
                ) : (
                  <>
                    <div className="w-16 h-16 bg-neutral-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <svg
                        className="w-8 h-8 text-neutral-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                        />
                      </svg>
                    </div>
                    <p className="text-neutral-900 font-medium mb-1">
                      Drop your room photo here
                    </p>
                    <p className="text-neutral-500 text-sm mb-4">
                      or click to browse
                    </p>
                    <button
                      type="button"
                      className="px-4 py-2 bg-neutral-900 text-white rounded-lg text-sm font-medium hover:bg-neutral-800 transition-colors"
                    >
                      Choose Photo
                    </button>
                  </>
                )}
              </div>
            )}

            {/* Previously Uploaded Tab */}
            {uploadTab === 'previous' && (
              <div className="bg-white rounded-2xl border border-neutral-200 p-4">
                {loadingPreviousRooms ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-neutral-300 border-t-neutral-600"></div>
                  </div>
                ) : previousRooms.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <svg className="w-12 h-12 text-neutral-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="text-neutral-500 text-sm mb-1">No previous rooms yet</p>
                    <p className="text-neutral-400 text-xs mb-3">
                      Upload your first room to get started
                    </p>
                    <button
                      onClick={() => setUploadTab('upload')}
                      className="px-4 py-2 bg-neutral-900 text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
                    >
                      Upload New Room
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 max-h-[300px] overflow-y-auto">
                    {previousRooms.map((room) => (
                      <button
                        key={room.id}
                        onClick={() => handleSelectPreviousRoom(room)}
                        disabled={loadingRoomId === room.id}
                        className="relative aspect-[4/3] rounded-xl overflow-hidden border-2 border-transparent hover:border-neutral-400 transition-all"
                      >
                        <img
                          src={`data:image/jpeg;base64,${room.thumbnail}`}
                          alt={room.name || 'Previous room'}
                          className="w-full h-full object-cover"
                        />
                        {/* Loading overlay */}
                        {loadingRoomId === room.id && (
                          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
                          </div>
                        )}
                        {/* Info overlay */}
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                          <p className="text-white text-xs truncate">{room.name || 'Room'}</p>
                          <p className="text-white/70 text-[10px]">
                            {new Date(room.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Error message */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm text-center">
            {error}
          </div>
        )}
      </div>

      {/* Processing info */}
      {isProcessing && (
        <div className="mt-6 w-full max-w-xl">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p className="text-blue-900 font-medium text-sm">Preparing your room</p>
                <p className="text-blue-700 text-xs mt-1">
                  We're removing existing furniture from your photo to create a clean canvas.
                  This typically takes 30-60 seconds.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tips - only show when not processing and on upload tab */}
      {!isProcessing && !processedImage && uploadTab === 'upload' && (
        <div className="mt-8 w-full max-w-xl">
          <h3 className="text-sm font-medium text-neutral-700 mb-3 text-center">
            Tips for best results
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { icon: '📐', text: 'Wide-angle shot works best' },
              { icon: '💡', text: 'Good lighting helps' },
              { icon: '🪑', text: 'Clear floor space for visualization' },
            ].map((tip, i) => (
              <div
                key={i}
                className="flex items-center gap-2 p-3 bg-neutral-100 rounded-lg text-sm"
              >
                <span className="text-lg">{tip.icon}</span>
                <span className="text-neutral-600">{tip.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Success message */}
      {processedImage && !isProcessing && (
        <div className="mt-6 w-full max-w-xl">
          <div className="bg-neutral-100 border border-neutral-300 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-neutral-200 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-neutral-800 font-medium text-sm">Your room is ready!</p>
                <p className="text-neutral-600 text-xs mt-0.5">
                  Click "Start Designing" to visualize furniture in your space.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Skip note - only when no image */}
      {!image && (
        <p className="mt-6 text-xs text-neutral-400 text-center">
          You can also upload a photo later in the Design Studio
        </p>
      )}
    </div>
  );
}
