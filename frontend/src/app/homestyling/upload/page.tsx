'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/utils/api';

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [originalImage, setOriginalImage] = useState<string | null>(null);
  const [processedImage, setProcessedImage] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isProcessed, setIsProcessed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  useEffect(() => {
    // Get session ID from sessionStorage
    const storedSessionId = sessionStorage.getItem('homestyling_session_id');
    if (!storedSessionId) {
      router.push('/homestyling/preferences');
      return;
    }
    setSessionId(storedSessionId);
  }, [router]);

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
    } catch (err: any) {
      console.error('Error processing image:', err);
      setError(err.response?.data?.detail || 'Failed to process image. Please try again.');
      setOriginalImage(null);
      setProcessedImage(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFileSelect = (file: File) => {
    if (!file.type.startsWith('image/')) {
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

    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      setOriginalImage(result);
      // Immediately start processing - pass sessionId directly
      processImage(result, currentSessionId);
    };
    reader.onerror = () => {
      setError('Failed to read file');
    };
    reader.readAsDataURL(file);
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
    // Already processed, just navigate
    router.push('/homestyling/tier');
  };

  const handleRemoveImage = () => {
    setOriginalImage(null);
    setProcessedImage(null);
    setShowOriginal(false);
    setIsProcessed(false);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="w-16 h-1 bg-emerald-600 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
              2
            </div>
            <div className="w-16 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-sm font-bold">
              3
            </div>
            <div className="w-16 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-sm font-bold">
              4
            </div>
          </div>
          <p className="text-center text-sm text-gray-500">Step 2 of 4: Upload Your Room</p>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6 relative">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Upload Room Photo</h2>
          <p className="text-sm text-gray-500 mb-4">
            Upload a photo of your room. We'll automatically prepare it for styling.
          </p>

          {!originalImage ? (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
                isDragOver
                  ? 'border-emerald-500 bg-emerald-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <svg
                className={`w-12 h-12 mx-auto mb-4 ${
                  isDragOver ? 'text-emerald-500' : 'text-gray-400'
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
              <p className="text-gray-600 font-medium mb-1">
                {isDragOver ? 'Drop your image here' : 'Drag and drop your room photo'}
              </p>
              <p className="text-sm text-gray-500">or click to browse</p>
              <p className="text-xs text-gray-400 mt-2">PNG, JPG up to 10MB</p>
            </div>
          ) : (
            <div className="relative">
              <div className="aspect-video rounded-xl overflow-hidden bg-gray-100">
                <img
                  src={showOriginal ? originalImage : (processedImage || originalImage)}
                  alt={showOriginal ? "Original room" : "Processed room"}
                  className="w-full h-full object-contain"
                />
              </div>

              {/* Processing Overlay */}
              {isProcessing && (
                <div className="absolute inset-0 bg-white/90 rounded-xl flex flex-col items-center justify-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-200 border-t-emerald-600 mb-4" />
                  <p className="text-lg font-medium text-gray-900 mb-1">Processing Your Room</p>
                  <p className="text-sm text-gray-500">Removing existing furniture...</p>
                  <p className="text-xs text-gray-400 mt-2">This may take 15-30 seconds</p>
                </div>
              )}

              {/* Success Badge + Before/After Toggle */}
              {isProcessed && !isProcessing && (
                <div className="absolute top-3 left-3 flex items-center gap-2">
                  <div className="flex items-center gap-2 bg-emerald-500 text-white px-3 py-1.5 rounded-full text-sm font-medium">
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
                      className="bg-gray-800/80 text-white px-3 py-1.5 rounded-full text-sm font-medium hover:bg-gray-700 transition-colors"
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
                  className="absolute top-3 right-3 p-2 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors"
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
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {/* Tips */}
        <div className="bg-emerald-50 rounded-xl p-6 mb-6">
          <h3 className="font-medium text-emerald-800 mb-3">Tips for best results:</h3>
          <ul className="space-y-2 text-sm text-emerald-700">
            <li className="flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Take a wide-angle shot from a corner to capture more of the room
            </li>
            <li className="flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Ensure good lighting - natural light works best
            </li>
            <li className="flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
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
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <button
            onClick={() => router.push('/homestyling/preferences')}
            className="text-gray-600 hover:text-gray-800 font-medium"
          >
            Back
          </button>
          <button
            onClick={handleContinue}
            disabled={!isProcessed || isProcessing}
            className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all ${
              isProcessed && !isProcessing
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
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
