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
    <div className="min-h-screen bg-gradient-to-br from-neutral-50 to-neutral-100">
      {/* Hero Section with Upload */}
      <section className="relative overflow-hidden bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          <div className="text-center mb-12">
            <h1 className="heading-1 text-neutral-900 mb-6">
              Visualize Furniture in{' '}
              <span className="bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
                Your Space
              </span>
              <br />
              Before You Buy
            </h1>
            <p className="body-large max-w-3xl mx-auto mb-4">
              Chat with our AI to find perfect pieces for your room. Upload a photo of your space
              to get personalized recommendations and see products visualized in your room.
            </p>
          </div>

          {/* Room Image Upload Section */}
          <div className="max-w-3xl mx-auto">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-2xl p-8 transition-all duration-200 ${
                isDragging
                  ? 'border-primary-500 bg-primary-50 scale-[1.02]'
                  : roomImage
                  ? 'border-green-500 bg-green-50'
                  : 'border-neutral-300 bg-neutral-50 hover:border-neutral-400 hover:bg-white'
              }`}
            >
              {!roomImage ? (
                <div className="text-center">
                  {/* Upload Icon */}
                  <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-primary-100 to-secondary-100 rounded-full flex items-center justify-center">
                    <svg
                      className="w-10 h-10 text-primary-600"
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

                  <h3 className="heading-4 text-neutral-900 mb-2">
                    📸 Drag & drop your room image here
                  </h3>
                  <p className="body-medium text-neutral-600 mb-6">
                    or click to browse files
                  </p>

                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-primary px-8 mb-4"
                  >
                    Choose File
                  </button>

                  <p className="body-small text-neutral-500">
                    Accepted formats: JPG, PNG, WEBP • Max size: 10MB
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
                  <div className="relative w-full aspect-video mb-6 rounded-lg overflow-hidden bg-neutral-100">
                    <Image
                      src={roomImage}
                      alt="Room preview"
                      fill
                      className="object-cover"
                    />
                  </div>

                  <div className="flex items-center justify-center gap-2 mb-4">
                    <svg
                      className="w-6 h-6 text-green-600"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="font-semibold text-green-700">
                      Image uploaded successfully!
                    </span>
                  </div>

                  <button
                    onClick={() => {
                      setRoomImage(null);
                      if (fileInputRef.current) {
                        fileInputRef.current.value = '';
                      }
                    }}
                    className="text-sm text-neutral-600 hover:text-neutral-900 underline"
                  >
                    Upload a different image
                  </button>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
              <button
                onClick={handleContinueWithImage}
                disabled={!roomImage || isStartingRemoval}
                className="btn btn-primary btn-lg px-8 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isStartingRemoval ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 inline-block" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing...
                  </>
                ) : (
                  'Upload & Continue'
                )}
              </button>
              <button
                onClick={handleSkipUpload}
                disabled={isStartingRemoval}
                className="btn btn-outline btn-lg px-8 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Upload Later
              </button>
            </div>

            <p className="text-center mt-4 text-sm text-neutral-600">
              You can always upload your room image later in the design studio
            </p>
          </div>
        </div>

        {/* Background decoration */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-gradient-to-br from-primary-100/50 to-secondary-100/50 rounded-full blur-3xl"></div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="heading-2 text-neutral-900 mb-4">
              How Omnishop Works
            </h2>
            <p className="body-large text-neutral-600 max-w-2xl mx-auto">
              Three simple steps to transform your space with AI-powered interior design
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Step 1 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="heading-4 text-neutral-900 mb-3">1. Chat with AI Designer</h3>
              <p className="body-medium text-neutral-600">
                Tell our AI about your style preferences, room dimensions, and functional needs.
                Get instant product recommendations tailored to your space.
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-secondary-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-8 h-8 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <h3 className="heading-4 text-neutral-900 mb-3">2. Select Products</h3>
              <p className="body-medium text-neutral-600">
                Browse curated furniture from West Elm, Orange Tree, and Pelican Essentials.
                Add your favorite pieces to the canvas.
              </p>
            </div>

            {/* Step 3 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </div>
              <h3 className="heading-4 text-neutral-900 mb-3">3. Visualize Your Room</h3>
              <p className="body-medium text-neutral-600">
                See how products look in your actual space with AI-powered visualization.
                Adjust placement until it's perfect.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-neutral-900 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <div className="heading-2 text-primary-400 mb-2">10,000+</div>
              <div className="body-medium text-neutral-300">Products</div>
            </div>
            <div>
              <div className="heading-2 text-secondary-400 mb-2">3</div>
              <div className="body-medium text-neutral-300">Premium Brands</div>
            </div>
            <div>
              <div className="heading-2 text-primary-400 mb-2">AI</div>
              <div className="body-medium text-neutral-300">Powered Design</div>
            </div>
            <div>
              <div className="heading-2 text-secondary-400 mb-2">24/7</div>
              <div className="body-medium text-neutral-300">Design Assistant</div>
            </div>
          </div>
        </div>
      </section>

      {/* Quick Access Section */}
      <section className="py-16 bg-neutral-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="heading-3 text-neutral-900 mb-4">
              Or explore other ways to get started
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Link
              href="/products"
              className="p-6 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-neutral-200"
            >
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-neutral-900 mb-2">Browse Products</h3>
              <p className="text-sm text-neutral-600">
                Explore our full catalog of furniture and decor
              </p>
            </Link>

            <Link
              href="/chat"
              className="p-6 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-neutral-200"
            >
              <div className="w-12 h-12 bg-secondary-100 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="font-semibold text-neutral-900 mb-2">Chat Assistant</h3>
              <p className="text-sm text-neutral-600">
                Get instant recommendations from our AI
              </p>
            </Link>

            <Link
              href="/visualize"
              className="p-6 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-neutral-200"
            >
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="font-semibold text-neutral-900 mb-2">Quick Visualize</h3>
              <p className="text-sm text-neutral-600">
                Jump straight to room visualization
              </p>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-neutral-900 text-neutral-300 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="md:col-span-2">
              <h3 className="text-xl font-bold text-white mb-4">Omnishop</h3>
              <p className="body-medium text-neutral-400 max-w-md">
                AI-powered interior design platform helping you transform your space
                with thousands of curated furniture and decor items.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2">
                <li><Link href="/products" className="hover:text-white transition-colors">Browse Products</Link></li>
                <li><Link href="/chat" className="hover:text-white transition-colors">AI Designer</Link></li>
                <li><Link href="/visualize" className="hover:text-white transition-colors">Room Visualizer</Link></li>
                <li><Link href="/design" className="hover:text-white transition-colors">Design Studio</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2">
                <li><a href="#" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Privacy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-neutral-800 mt-8 pt-8 text-center">
            <p className="body-small text-neutral-500">
              © 2024 Omnishop. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
