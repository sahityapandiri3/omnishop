import React from 'react';
import { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Omnishop - Transform Your Space with AI Interior Design',
  description: 'Discover thousands of furniture and decor items. Chat with our AI designer to get personalized recommendations and visualize your dream room.',
};

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-neutral-50 to-neutral-100">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
          <div className="text-center">
            <h1 className="heading-1 text-neutral-900 mb-6">
              Transform Your Space with{' '}
              <span className="bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
                AI Interior Design
              </span>
            </h1>
            <p className="body-large max-w-3xl mx-auto mb-8">
              Discover thousands of furniture and decor items from top brands. Chat with our AI designer
              to get personalized recommendations and visualize your dream room in minutes.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link href="/chat" className="btn btn-primary btn-lg px-8">
                Start Designing
              </Link>
              <Link href="/products" className="btn btn-outline btn-lg px-8">
                Browse Products
              </Link>
            </div>
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
              <h3 className="heading-4 text-neutral-900 mb-3">Chat with AI Designer</h3>
              <p className="body-medium text-neutral-600">
                Tell our AI about your style preferences, room dimensions, and functional needs.
                Upload a photo of your space for personalized recommendations.
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-secondary-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-8 h-8 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="heading-4 text-neutral-900 mb-3">Browse Curated Products</h3>
              <p className="body-medium text-neutral-600">
                Explore thousands of furniture and decor items from West Elm, Orange Tree,
                and Pelican Essentials, filtered based on your preferences.
              </p>
            </div>

            {/* Step 3 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="heading-4 text-neutral-900 mb-3">Visualize Your Room</h3>
              <p className="body-medium text-neutral-600">
                See how products look in your space with our AI-powered visualization tool.
                Adjust placement, scale, and combinations until it's perfect.
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

      {/* CTA Section */}
      <section className="py-24 bg-gradient-primary">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="heading-2 text-white mb-6">
            Ready to Transform Your Space?
          </h2>
          <p className="body-large text-primary-100 mb-8">
            Join thousands of users who have already created their dream rooms with Omnishop's AI designer.
          </p>
          <Link href="/visualize" className="btn btn-lg bg-white text-primary-700 hover:bg-neutral-50 px-8">
            Get Started Free
          </Link>
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
                <li><a href="#" className="hover:text-white transition-colors">Browse Products</a></li>
                <li><a href="#" className="hover:text-white transition-colors">AI Designer</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Room Visualizer</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Style Guide</a></li>
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