'use client';

import React, { useState, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { startFurnitureRemoval } from '@/utils/api';

export default function HomePage() {
  const router = useRouter();
  const [roomImage, setRoomImage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isStartingRemoval, setIsStartingRemoval] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle file selection
  const handleFileSelect = (file: File) => {
    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file (JPG, PNG, WEBP)');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    // Read file as base64
    const reader = new FileReader();
    reader.onload = (event) => {
      const imageData = event.target?.result as string;
      setRoomImage(imageData);
    };
    reader.readAsDataURL(file);
  };

  // Handle drag and drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  // Handle file input change
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  // Navigate to curated looks page with image and start furniture removal
  const handleContinueWithImage = async () => {
    if (!roomImage) {
      console.warn('[HomePage] No room image to upload');
      alert('Please upload a room image first');
      return;
    }

    try {
      setIsStartingRemoval(true);
      console.log('[HomePage] Starting furniture removal process...');

      // Start async furniture removal in background
      const response = await startFurnitureRemoval(roomImage);
      console.log('[HomePage] Furniture removal started:', response);

      // Store job_id and original image in sessionStorage
      sessionStorage.setItem('furnitureRemovalJobId', response.job_id);
      sessionStorage.setItem('roomImage', roomImage);

      console.log('[HomePage] Navigating to /curated...');
      // Navigate to curated looks page (processing continues in background)
      router.push('/curated');
    } catch (error) {
      console.error('[HomePage] Error starting furniture removal:', error);
      // On error, still allow user to proceed with original image
      sessionStorage.setItem('roomImage', roomImage);
      sessionStorage.removeItem('furnitureRemovalJobId'); // Clear any existing job
      router.push('/curated');
    } finally {
      setIsStartingRemoval(false);
    }
  };

  // Navigate to curated page without image
  const handleSkipUpload = () => {
    sessionStorage.removeItem('roomImage');
    sessionStorage.removeItem('furnitureRemovalJobId');
    router.push('/curated');
  };

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Hero Section with Upload */}
      <section className="relative overflow-hidden bg-neutral-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 lg:py-12">
          <div className="text-center mb-6">
            <h1 className="heading-1 text-neutral-900 mb-3">
              Visualize Furniture in{' '}
              <span className="text-primary-600">Your Space</span>
            </h1>
            <p className="body-medium max-w-2xl mx-auto">
              Upload a photo and get AI-powered recommendations with room visualizations.
            </p>
          </div>

          {/* Room Image Upload Section */}
          <div className="max-w-2xl mx-auto">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-xl p-5 transition-all duration-200 ${
                isDragging
                  ? 'border-primary-500 bg-primary-50 scale-[1.01]'
                  : roomImage
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-neutral-300 bg-white hover:border-primary-400'
              }`}
            >
              {!roomImage ? (
                <div className="text-center">
                  {/* Upload Icon */}
                  <div className="w-14 h-14 mx-auto mb-3 bg-primary-100 rounded-full flex items-center justify-center">
                    <svg
                      className="w-7 h-7 text-primary-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                  </div>

                  <h3 className="text-base font-medium text-neutral-800 mb-1">
                    Drag & drop your room image
                  </h3>
                  <p className="text-sm text-neutral-500 mb-4">
                    or click to browse
                  </p>

                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-primary px-6 text-sm"
                  >
                    Choose File
                  </button>

                  <p className="text-xs text-neutral-400 mt-3">
                    JPG, PNG, WEBP • Max 10MB
                  </p>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleFileInputChange}
                    className="hidden"
                  />
                </div>
              ) : (
                <div className="text-center">
                  {/* Preview */}
                  <div className="relative w-full aspect-video mb-4 rounded-lg overflow-hidden bg-neutral-100">
                    <Image
                      src={roomImage}
                      alt="Room preview"
                      fill
                      className="object-cover"
                    />
                  </div>

                  <div className="flex items-center justify-center gap-2 mb-3">
                    <svg
                      className="w-5 h-5 text-primary-600"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-sm font-medium text-primary-700">
                      Image uploaded
                    </span>
                  </div>

                  <button
                    onClick={() => {
                      setRoomImage(null);
                      if (fileInputRef.current) {
                        fileInputRef.current.value = '';
                      }
                    }}
                    className="text-xs text-neutral-500 hover:text-neutral-700 underline"
                  >
                    Change image
                  </button>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="mt-5 flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={handleContinueWithImage}
                disabled={!roomImage || isStartingRemoval}
                className="btn btn-primary px-6 py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isStartingRemoval ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 inline-block" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing...
                  </>
                ) : (
                  'Continue'
                )}
              </button>
              <button
                onClick={handleSkipUpload}
                disabled={isStartingRemoval}
                className="btn btn-outline px-6 py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Skip for now
              </button>
            </div>

            <p className="text-center mt-3 text-xs text-neutral-400">
              You can upload later in the design studio
            </p>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-10 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-8">
            <h2 className="heading-2 text-neutral-800 mb-2">
              How It Works
            </h2>
            <p className="text-sm text-neutral-500">
              Three simple steps to transform your space
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Step 1 */}
            <div className="text-center p-4">
              <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">1. Chat with AI</h3>
              <p className="text-xs text-neutral-500">
                Share your style preferences and get personalized recommendations.
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center p-4">
              <div className="w-10 h-10 bg-secondary-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-5 h-5 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">2. Select Products</h3>
              <p className="text-xs text-neutral-500">
                Browse curated furniture from premium brands.
              </p>
            </div>

            {/* Step 3 */}
            <div className="text-center p-4">
              <div className="w-10 h-10 bg-accent-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-5 h-5 text-accent-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">3. Visualize</h3>
              <p className="text-xs text-neutral-500">
                See products in your space with AI visualization.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-6 bg-neutral-900 text-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-lg font-bold text-primary-400">10K+</div>
              <div className="text-xs text-neutral-400">Products</div>
            </div>
            <div>
              <div className="text-lg font-bold text-secondary-400">5</div>
              <div className="text-xs text-neutral-400">Brands</div>
            </div>
            <div>
              <div className="text-lg font-bold text-primary-400">AI</div>
              <div className="text-xs text-neutral-400">Powered</div>
            </div>
            <div>
              <div className="text-lg font-bold text-secondary-400">24/7</div>
              <div className="text-xs text-neutral-400">Available</div>
            </div>
          </div>
        </div>
      </section>

      {/* Quick Access Section */}
      <section className="py-8 bg-neutral-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-5">
            <h2 className="text-base font-semibold text-neutral-700">
              Other ways to get started
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              href="/products"
              className="p-4 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow border border-neutral-200"
            >
              <div className="w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center mb-2">
                <svg className="w-4 h-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">Browse Products</h3>
              <p className="text-xs text-neutral-500">
                Explore our furniture catalog
              </p>
            </Link>

            <Link
              href="/chat"
              className="p-4 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow border border-neutral-200"
            >
              <div className="w-8 h-8 bg-secondary-100 rounded-lg flex items-center justify-center mb-2">
                <svg className="w-4 h-4 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">Chat with AI</h3>
              <p className="text-xs text-neutral-500">
                Get personalized recommendations
              </p>
            </Link>

            <Link
              href="/visualize"
              className="p-4 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow border border-neutral-200"
            >
              <div className="w-8 h-8 bg-accent-100 rounded-lg flex items-center justify-center mb-2">
                <svg className="w-4 h-4 text-accent-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">Visualize</h3>
              <p className="text-xs text-neutral-500">
                See products in your space
              </p>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-neutral-900 text-neutral-400 py-6">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="text-center md:text-left">
              <h3 className="text-sm font-semibold text-white">Omnishop</h3>
              <p className="text-xs text-neutral-500">AI-powered interior design</p>
            </div>
            <div className="flex gap-6 text-xs">
              <Link href="/products" className="hover:text-white transition-colors">Products</Link>
              <Link href="/chat" className="hover:text-white transition-colors">AI Chat</Link>
              <Link href="/design" className="hover:text-white transition-colors">Studio</Link>
            </div>
          </div>
          <div className="border-t border-neutral-800 mt-4 pt-4 text-center">
            <p className="text-xs text-neutral-500">
              © 2024 Omnishop
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
