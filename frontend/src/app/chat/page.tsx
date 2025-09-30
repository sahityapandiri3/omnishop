'use client'

import ChatInterface from '@/components/ChatInterface'

export default function ChatPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">AI Design Assistant</h1>
          <p className="text-gray-600">
            Get personalized interior design recommendations and product suggestions from our AI assistant.
            Share your space, describe your style, or upload photos to get started.
          </p>
        </div>

        <div className="h-[600px]">
          <ChatInterface className="h-full" />
        </div>

        {/* Features */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Style Analysis</h3>
            <p className="text-gray-600 text-sm">
              Upload photos of your space and get detailed style recommendations based on your preferences and room characteristics.
            </p>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Product Matching</h3>
            <p className="text-gray-600 text-sm">
              Get curated product recommendations from West Elm, Orange Tree, and Pelican Essentials that match your style and needs.
            </p>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Expert Guidance</h3>
            <p className="text-gray-600 text-sm">
              Chat with our AI design expert for layout suggestions, color coordination, and professional design advice.
            </p>
          </div>
        </div>

        {/* Sample Questions */}
        <div className="mt-12 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Try asking me:</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
              "I have a small living room with lots of natural light. I love modern minimalist style. What furniture should I get?"
            </div>
            <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
              "Help me create a cozy bedroom with a warm, rustic feel. My budget is around $2000."
            </div>
            <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
              "I want to redecorate my dining room in Scandinavian style. What colors and materials work best?"
            </div>
            <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
              "My kitchen needs better storage solutions. Can you recommend some stylish organizers?"
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}