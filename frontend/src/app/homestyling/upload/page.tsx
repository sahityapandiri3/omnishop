'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/utils/api';
import { useTrackEvent } from '@/contexts/AnalyticsContext';

interface PreviousRoom {
  session_id: string;
  room_type: string | null;
  style: string | null;
  clean_room_image: string;
  created_at: string;
}

export default function UploadPage() {
  const router = useRouter();
  const trackEvent = useTrackEvent();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [originalImage, setOriginalImage] = useState<string | null>(null);
  const [processedImage, setProcessedImage] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isProcessed, setIsProcessed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'previous'>('upload');
  const [previousRooms, setPreviousRooms] = useState<PreviousRoom[]>([]);
  const [loadingPrevious, setLoadingPrevious] = useState(false);
  const [selectedPreviousRoom, setSelectedPreviousRoom] = useState<string | null>(null);

  useEffect(() => {
    // Get session ID from sessionStorage
    const storedSessionId = sessionStorage.getItem('homestyling_session_id');
    if (!storedSessionId) {
      router.push('/homestyling/preferences');
      return;
    }
    setSessionId(storedSessionId);

    // Fetch previous rooms
    fetchPreviousRooms();
  }, [router]);

  const fetchPreviousRooms = async () => {
    setLoadingPrevious(true);
    try {
      const response = await api.get('/api/homestyling/previous-rooms?limit=50');
      setPreviousRooms(response.data.rooms || []);
    } catch (err) {
      console.error('Failed to fetch previous rooms:', err);
    } finally {
      setLoadingPrevious(false);
    }
  };

  const processImage = async (imageData: string, sid: string) => {
    setIsProcessing(true);
    setError(null);

    try {
      console.log('Uploading image to session:', sid);
      // Upload and process image (furniture removal happens on backend)
      const response = await api.post(`/api/homestyling/sessions/${sid}/upload`, {
        image: imageData,
      });

      console.log('Image processed successfully');

      // Get the processed image from the response
      const cleanImage = response.data.clean_room_image;
      if (cleanImage) {
        // Ensure it has the data URL prefix
        const cleanImageUrl = cleanImage.startsWith('data:')
          ? cleanImage
          : `data:image/jpeg;base64,${cleanImage}`;
        setProcessedImage(cleanImageUrl);
        console.log('Processed image received');
      }

      setIsProcessed(true);
      trackEvent('homestyling.upload_complete', undefined, { image_size_kb: Math.round(imageData.length * 0.75 / 1024) });
    } catch (err: any) {
      console.error('Error processing image:', err);
      setError(err.response?.data?.detail || 'Failed to process image. Please try again.');
      setOriginalImage(null);
      setProcessedImage(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFileSelect = async (file: File) => {
    // Check if it's an image file (including HEIC)
    const isHeic = file.name.toLowerCase().endsWith('.heic') || file.name.toLowerCase().endsWith('.heif');
    if (!file.type.startsWith('image/') && !isHeic) {
      setError('Please select an image file');
      return;
    }

    // Get session ID directly from sessionStorage to avoid stale closure
    const currentSessionId = sessionStorage.getItem('homestyling_session_id');
    if (!currentSessionId) {
      setError('Session not found. Please go back and start again.');
      return;
    }

    // Reset state
    setIsProcessed(false);
    setError(null);

    let fileToProcess = file;

    // Convert HEIC to JPEG if needed
    if (isHeic) {
      setIsProcessing(true);
      try {
        console.log('Converting HEIC to JPEG...');
        // Dynamically import heic2any to avoid SSR issues
        const heic2any = (await import('heic2any')).default;
        const convertedBlob = await heic2any({
          blob: file,
          toType: 'image/jpeg',
          quality: 0.9,
        });
        // heic2any can return an array of blobs for multi-image HEIC, take the first
        const blob = Array.isArray(convertedBlob) ? convertedBlob[0] : convertedBlob;
        fileToProcess = new File([blob], file.name.replace(/\.heic$/i, '.jpg').replace(/\.heif$/i, '.jpg'), {
          type: 'image/jpeg',
        });
        console.log('HEIC conversion complete');
      } catch (heicError) {
        console.error('HEIC conversion failed:', heicError);
        setError('Failed to convert HEIC image. Please try a different format (JPG, PNG).');
        setIsProcessing(false);
        return;
      }
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      setOriginalImage(result);
      // Immediately start processing - pass sessionId directly
      processImage(result, currentSessionId);
    };
    reader.onerror = () => {
      setError('Failed to read file');
      setIsProcessing(false);
    };
    reader.readAsDataURL(fileToProcess);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
  };

  const handleContinue = () => {
    // Already processed, skip tier page and go directly to generate
    const currentSessionId = sessionStorage.getItem('homestyling_session_id');
    if (currentSessionId) {
      router.push(`/homestyling/results/${currentSessionId}`);
    } else {
      router.push('/homestyling/preferences');
    }
  };

  const handleRemoveImage = () => {
    setOriginalImage(null);
    setProcessedImage(null);
    setShowOriginal(false);
    setIsProcessed(false);
    setError(null);
    setSelectedPreviousRoom(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSelectPreviousRoom = async (room: PreviousRoom) => {
    setSelectedPreviousRoom(room.session_id);
    setIsProcessing(true);
    setError(null);

    try {
      const currentSessionId = sessionStorage.getItem('homestyling_session_id');
      if (!currentSessionId) {
        setError('Session not found. Please go back and start again.');
        return;
      }

      // Copy the clean room image to the current session
      const response = await api.post(`/api/homestyling/sessions/${currentSessionId}/use-previous-room`, {
        previous_session_id: room.session_id,
      });

      const cleanImage = response.data.clean_room_image;
      if (cleanImage) {
        const cleanImageUrl = cleanImage.startsWith('data:')
          ? cleanImage
          : `data:image/jpeg;base64,${cleanImage}`;
        setProcessedImage(cleanImageUrl);
        setOriginalImage(cleanImageUrl); // Use clean as original since we're reusing
      }

      setIsProcessed(true);
      setActiveTab('upload'); // Switch back to upload tab to show the result
    } catch (err: any) {
      console.error('Error using previous room:', err);
      setError(err.response?.data?.detail || 'Failed to use previous room. Please try again.');
      setSelectedPreviousRoom(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatRoomType = (type: string | null) => {
    if (!type) return 'Room';
    return type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  return (
    <div className="min-h-screen bg-neutral-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-neutral-800 text-white flex items-center justify-center text-sm font-bold">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="w-16 h-1 bg-neutral-800 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-neutral-800 text-white flex items-center justify-center text-sm font-bold">
              2
            </div>
            <div className="w-16 h-1 bg-neutral-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-neutral-200 text-neutral-400 flex items-center justify-center text-sm font-bold">
              3
            </div>
          </div>
          <p className="text-center text-sm text-neutral-500">Step 2 of 3: Upload Your Room</p>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-xl shadow-soft border border-neutral-200/80 p-6 mb-6 relative">
          <h2 className="font-display text-lg font-normal text-neutral-800 mb-1">Upload Room Photo</h2>
          <p className="text-sm text-neutral-500 mb-4">
            Upload a new photo or select from your previously uploaded rooms.
          </p>

          {/* Tabs */}
          {!originalImage && (
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setActiveTab('upload')}
                className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                  activeTab === 'upload'
                    ? 'bg-neutral-800 text-white shadow-sm'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  Upload New
                </span>
              </button>
              <button
                onClick={() => setActiveTab('previous')}
                className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                  activeTab === 'previous'
                    ? 'bg-neutral-800 text-white shadow-sm'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  Previously Uploaded
                  {previousRooms.length > 0 && (
                    <span className="bg-white/20 text-xs px-1.5 py-0.5 rounded-full">
                      {previousRooms.length}
                    </span>
                  )}
                </span>
              </button>
            </div>
          )}

          {/* Upload New Tab Content */}
          {activeTab === 'upload' && !originalImage && (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
                isDragOver
                  ? 'border-neutral-800 bg-neutral-100'
                  : 'border-neutral-300 hover:border-neutral-400'
              }`}
            >
              <svg
                className={`w-12 h-12 mx-auto mb-4 ${
                  isDragOver ? 'text-neutral-700' : 'text-neutral-400'
                }`}
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
              <p className="text-neutral-600 font-medium mb-1">
                {isDragOver ? 'Drop your image here' : 'Drag and drop your room photo'}
              </p>
              <p className="text-sm text-neutral-500">or click to browse</p>
              <p className="text-xs text-neutral-400 mt-2">PNG, JPG up to 10MB</p>
            </div>
          )}

          {/* Previously Uploaded Tab Content */}
          {activeTab === 'previous' && !originalImage && (
            <div>
              {loadingPrevious ? (
                <div className="flex justify-center items-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-2 border-neutral-800 border-t-transparent" />
                </div>
              ) : previousRooms.length === 0 ? (
                <div className="text-center py-12">
                  <svg className="w-12 h-12 mx-auto mb-4 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <p className="text-neutral-500 font-medium">No previous rooms yet</p>
                  <p className="text-sm text-neutral-400 mt-1">Upload your first room to get started</p>
                  <button
                    onClick={() => setActiveTab('upload')}
                    className="mt-4 text-neutral-700 hover:text-neutral-900 font-medium text-sm"
                  >
                    Upload Now
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {previousRooms.map((room) => (
                    <button
                      key={room.session_id}
                      onClick={() => handleSelectPreviousRoom(room)}
                      disabled={isProcessing}
                      className={`group relative aspect-[4/3] rounded-xl overflow-hidden border-2 transition-all ${
                        selectedPreviousRoom === room.session_id
                          ? 'border-neutral-800 ring-2 ring-neutral-300'
                          : 'border-transparent hover:border-neutral-400'
                      } ${isProcessing && selectedPreviousRoom === room.session_id ? 'opacity-75' : ''}`}
                    >
                      <img
                        src={room.clean_room_image.startsWith('data:')
                          ? room.clean_room_image
                          : `data:image/jpeg;base64,${room.clean_room_image}`}
                        alt={formatRoomType(room.room_type)}
                        className="w-full h-full object-cover"
                      />
                      {/* Hover overlay */}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      {/* Room info */}
                      <div className="absolute bottom-0 left-0 right-0 p-2 translate-y-2 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all">
                        <p className="text-white text-xs font-medium truncate">{formatRoomType(room.room_type)}</p>
                        <p className="text-white/70 text-[10px]">{formatDate(room.created_at)}</p>
                      </div>
                      {/* Selected indicator */}
                      {selectedPreviousRoom === room.session_id && (
                        <div className="absolute top-2 right-2">
                          {isProcessing ? (
                            <div className="w-6 h-6 bg-neutral-800 rounded-full flex items-center justify-center">
                              <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" />
                            </div>
                          ) : (
                            <div className="w-6 h-6 bg-neutral-800 rounded-full flex items-center justify-center">
                              <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            </div>
                          )}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Image Preview (shown after upload or selection) */}
          {originalImage && (
            <div className="relative">
              <div className="aspect-video rounded-xl overflow-hidden bg-neutral-100">
                <img
                  src={showOriginal ? originalImage : (processedImage || originalImage)}
                  alt={showOriginal ? "Original room" : "Processed room"}
                  className="w-full h-full object-contain"
                />
              </div>

              {/* Processing Overlay */}
              {isProcessing && (
                <div className="absolute inset-0 bg-white/90 rounded-xl flex flex-col items-center justify-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-4 border-neutral-200 border-t-neutral-800 mb-4" />
                  <p className="text-lg font-medium text-neutral-800 mb-1">Processing Your Room</p>
                  <p className="text-sm text-neutral-500">Removing existing furniture...</p>
                  <p className="text-xs text-neutral-400 mt-2">This may take 15-30 seconds</p>
                </div>
              )}

              {/* Success Badge + Before/After Toggle */}
              {isProcessed && !isProcessing && (
                <div className="absolute top-3 left-3 flex items-center gap-2">
                  <div className="flex items-center gap-2 bg-neutral-800 text-white px-3 py-1.5 rounded-full text-sm font-medium">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Furniture Removed
                  </div>
                  {processedImage && (
                    <button
                      onClick={() => setShowOriginal(!showOriginal)}
                      className="bg-neutral-800/80 text-white px-3 py-1.5 rounded-full text-sm font-medium hover:bg-neutral-700 transition-colors"
                    >
                      {showOriginal ? 'Show After' : 'Show Before'}
                    </button>
                  )}
                </div>
              )}

              {/* Remove button */}
              {!isProcessing && (
                <button
                  onClick={handleRemoveImage}
                  className="absolute top-3 right-3 p-2 bg-accent-500 text-white rounded-full hover:bg-accent-600 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.heic,.heif"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {/* Tips */}
        <div className="bg-neutral-100 rounded-xl p-6 mb-6">
          <h3 className="font-medium text-neutral-800 mb-3">Tips for best results:</h3>
          <ul className="space-y-2 text-sm text-neutral-600">
            <li className="flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-neutral-500" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Take a wide-angle shot from a corner to capture more of the room
            </li>
            <li className="flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-neutral-500" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Ensure good lighting - natural light works best
            </li>
            <li className="flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-neutral-500" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Keep the room tidy for cleaner visualizations
            </li>
          </ul>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-accent-50 border border-accent-200 rounded-lg text-accent-700 text-sm">
            {error}
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <button
            onClick={() => router.push('/homestyling/preferences')}
            className="text-neutral-500 hover:text-neutral-700 font-medium"
          >
            Back
          </button>
          <button
            onClick={handleContinue}
            disabled={!isProcessed || isProcessing}
            className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all ${
              isProcessed && !isProcessing
                ? 'bg-neutral-800 hover:bg-neutral-900 text-white'
                : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
            }`}
          >
            {isProcessing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Processing...
              </>
            ) : (
              <>
                Continue
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
