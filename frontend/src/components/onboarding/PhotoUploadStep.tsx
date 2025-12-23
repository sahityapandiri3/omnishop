'use client';

import { useState, useCallback, useRef } from 'react';

interface PhotoUploadStepProps {
  image: string | null;
  onUpload: (image: string | null) => void;
}

export function PhotoUploadStep({ image, onUpload }: PhotoUploadStepProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

      setIsProcessing(true);

      try {
        // Convert to base64
        const reader = new FileReader();
        reader.onload = (e) => {
          const base64 = e.target?.result as string;
          onUpload(base64);
          setIsProcessing(false);
        };
        reader.onerror = () => {
          setError('Failed to read the image file');
          setIsProcessing(false);
        };
        reader.readAsDataURL(file);
      } catch (err) {
        setError('Failed to process the image');
        setIsProcessing(false);
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
    onUpload(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [onUpload]);

  return (
    <div className="flex flex-col items-center">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-2xl md:text-3xl font-light text-neutral-900 mb-3">
          Upload your room photo
        </h2>
        <p className="text-neutral-500 font-light">
          We'll visualize furniture right in your space
        </p>
      </div>

      {/* Upload Area */}
      <div className="w-full max-w-xl">
        {image ? (
          // Preview
          <div className="relative rounded-2xl overflow-hidden shadow-lg">
            <img
              src={image}
              alt="Uploaded room"
              className="w-full aspect-video object-cover"
            />
            {/* Overlay with actions */}
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
            {/* Success indicator */}
            <div className="absolute top-3 right-3 bg-green-500 text-white px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Photo ready
            </div>
          </div>
        ) : (
          // Drop zone
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200 ${
              isDragging
                ? 'border-primary-500 bg-primary-50'
                : 'border-neutral-300 bg-white hover:border-neutral-400 hover:bg-neutral-50'
            }`}
          >
            {isProcessing ? (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 border-3 border-primary-200 border-t-primary-600 rounded-full animate-spin mb-4" />
                <p className="text-neutral-600">Processing image...</p>
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

      {/* Tips */}
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

      {/* Skip note */}
      <p className="mt-6 text-xs text-neutral-400 text-center">
        You can also upload a photo later in the Design Studio
      </p>
    </div>
  );
}
