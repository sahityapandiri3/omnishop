'use client'

import { useState } from 'react'
import ChatInterface from '@/components/ChatInterface'
import SpaceVisualization from '@/components/SpaceVisualization'
import { Product } from '@/types'

export default function VisualizePage() {
  const [recommendedProducts, setRecommendedProducts] = useState<Product[]>([])
  const [roomImage, setRoomImage] = useState<string | null>(null)

  // This would be connected to chat responses in a real implementation
  const handleProductRecommendations = (products: Product[]) => {
    setRecommendedProducts(products)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Space Visualizer</h1>
          <p className="text-gray-600">
            Chat with our AI assistant and visualize how recommended products would look in your space.
          </p>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Chat Interface */}
          <div className="space-y-6">
            <div className="h-[500px]">
              <ChatInterface className="h-full" />
            </div>

            {/* Instructions */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
              <h3 className="font-semibold text-gray-900 mb-3">How it works:</h3>
              <ol className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium mr-3 mt-0.5">1</span>
                  Describe your room and style preferences to our AI assistant
                </li>
                <li className="flex items-start">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium mr-3 mt-0.5">2</span>
                  Upload a photo of your space for better recommendations (optional)
                </li>
                <li className="flex items-start">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium mr-3 mt-0.5">3</span>
                  Get personalized product recommendations in the chat
                </li>
                <li className="flex items-start">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium mr-3 mt-0.5">4</span>
                  Visualize how products would look in your room using the visualizer
                </li>
              </ol>
            </div>
          </div>

          {/* Space Visualization */}
          <div>
            <SpaceVisualization
              roomImage={roomImage}
              recommendedProducts={recommendedProducts}
              className="h-fit"
            />
          </div>
        </div>

        {/* Sample Prompts */}
        <div className="mt-12 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Try these prompts to get started:</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm text-blue-800 font-medium mb-2">Living Room Design</p>
              <p className="text-sm text-blue-700">
                "I have a 15x12 living room with large windows. I love modern minimalist style with neutral colors. Help me choose a sofa, coffee table, and lighting."
              </p>
            </div>
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4">
              <p className="text-sm text-green-800 font-medium mb-2">Bedroom Makeover</p>
              <p className="text-sm text-green-700">
                "I want to create a cozy, Scandinavian-style bedroom. I need a bed frame, nightstands, and some decor. My budget is $1500."
              </p>
            </div>
            <div className="bg-gradient-to-r from-purple-50 to-violet-50 border border-purple-200 rounded-lg p-4">
              <p className="text-sm text-purple-800 font-medium mb-2">Dining Room Setup</p>
              <p className="text-sm text-purple-700">
                "Help me design a dining room that can seat 6 people. I prefer warm, rustic style with wood furniture."
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}