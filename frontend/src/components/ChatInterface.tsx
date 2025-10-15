'use client'

import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChatMessage, ChatMessageRequest, ChatMessageResponse } from '@/types'
import { startChatSession, sendChatMessage, getChatHistory, undoVisualization, redoVisualization } from '@/utils/api'
import { PaperAirplaneIcon, PhotoIcon, ArrowUturnLeftIcon, ArrowUturnRightIcon } from '@heroicons/react/24/outline'
import ProductCard from './ProductCard'

interface ChatInterfaceProps {
  sessionId?: string
  className?: string
}

export function ChatInterface({ sessionId: initialSessionId, className = '' }: ChatInterfaceProps) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [userUploadedNewImage, setUserUploadedNewImage] = useState(false) // Track if user explicitly uploaded new image
  const [selectedProducts, setSelectedProducts] = useState<Set<number>>(new Set())
  const [isVisualizing, setIsVisualizing] = useState(false)
  const [lastAnalysis, setLastAnalysis] = useState<any>(null)
  const [pendingVisualization, setPendingVisualization] = useState<{
    products: any[],
    image: string,
    analysis: any,
    existingFurniture: any[]
  } | null>(null)
  // BUG #9 FIX: Undo/Redo state management
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)
  const [lastVisualizationMessage, setLastVisualizationMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<HTMLFormElement>(null)

  // Start new session if none provided
  const startSessionMutation = useMutation({
    mutationFn: startChatSession,
    onSuccess: (response) => {
      setSessionId(response.session_id)
    },
    onError: (error) => {
      console.error('Failed to start session:', error)
      // Create a temporary session ID if backend fails
      const tempSessionId = `temp-session-${Date.now()}`
      setSessionId(tempSessionId)
    }
  })

  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: ({ sessionId, message, image }: { sessionId: string; message: string; image?: string }) =>
      sendChatMessage(sessionId, { message, image }),
    onSuccess: (response) => {
      console.log('Chat API response:', response)
      // Backend returns ChatMessageResponse with message object
      const messageData = response.message || response
      const products = response.recommended_products || messageData.products || []
      console.log('Products received:', products)
      const aiMessage: ChatMessage = {
        id: messageData.id || response.message_id || `ai-${Date.now()}`,
        type: 'assistant',
        content: messageData.content || '',
        timestamp: new Date(messageData.timestamp || Date.now()),
        session_id: sessionId || undefined,
        products: products,
        image_url: messageData.image_url
      }
      setMessages(prev => [...prev, aiMessage])
      // Store the analysis for visualization
      if (response.analysis) {
        setLastAnalysis(response.analysis)
      }
      // PRODUCT PERSISTENCE FIX: Clear product selections when new products arrive
      // This ensures users don't accidentally visualize old products with new ones
      if (products && products.length > 0) {
        setSelectedProducts(new Set())
      }
    },
    onError: (error: any) => {
      console.error('Failed to send message:', error)

      // Extract detailed error message
      let errorDetail = 'An unknown error occurred.'
      if (error?.response?.data?.detail) {
        errorDetail = error.response.data.detail
      } else if (error?.message) {
        errorDetail = error.message
      } else if (typeof error === 'string') {
        errorDetail = error
      }

      // Show detailed error message to user
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: `❌ Error: ${errorDetail}\n\nPlease try again or contact support if the issue persists.`,
        timestamp: new Date(),
        session_id: sessionId || ''
      }
      setMessages(prev => [...prev, errorMessage])
    }
  })

  // Load chat history if session exists
  const { data: chatHistory, error: chatHistoryError } = useQuery({
    queryKey: ['chatHistory', sessionId],
    queryFn: () => sessionId ? getChatHistory(sessionId) : null,
    enabled: !!sessionId
  })

  // Handle chat history data changes
  useEffect(() => {
    if (chatHistory && chatHistory.messages && Array.isArray(chatHistory.messages)) {
      // Ensure all messages have proper structure and id field
      const validMessages = chatHistory.messages
        .filter((msg: any) => msg && typeof msg === 'object')
        .map((msg: any) => ({
          id: msg.id || msg.message_id || `msg-${Date.now()}-${Math.random()}`,
          type: msg.message_type || msg.type || 'assistant',
          content: msg.content || '',
          timestamp: new Date(msg.timestamp || Date.now()),
          session_id: msg.session_id || sessionId,
          products: msg.recommendations || msg.products || []
        }))
      setMessages(validMessages)
    }
  }, [chatHistory, sessionId])

  // Handle chat history errors
  useEffect(() => {
    if (chatHistoryError) {
      console.error('Failed to load chat history:', chatHistoryError)
      // Start with empty messages if history fails to load
      setMessages([])
    }
  }, [chatHistoryError])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Initialize session if none exists
  useEffect(() => {
    if (!sessionId && !startSessionMutation.isPending) {
      startSessionMutation.mutate({ user_id: undefined })
    }
  }, [sessionId])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!sessionId || !inputMessage.trim()) return

    // Check if we're waiting for clarification response
    if (pendingVisualization) {
      const response = inputMessage.trim().toLowerCase()

      // Map user response to action
      const actionMap: { [key: string]: string } = {
        'a': 'replace_one',
        'b': 'replace_all',
        'c': 'add'
      }

      if (actionMap[response]) {
        // Add user message to show their choice
        const userMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          type: 'user',
          content: inputMessage,
          timestamp: new Date(),
          session_id: sessionId || undefined
        }
        setMessages(prev => [...prev, userMessage])

        // Clear input
        setInputMessage('')

        // Call visualization with action
        await executeVisualization(
          pendingVisualization.products,
          pendingVisualization.image,
          pendingVisualization.analysis,
          pendingVisualization.existingFurniture,
          actionMap[response]
        )

        // Clear pending visualization
        setPendingVisualization(null)
        return
      }
    }

    // Add user message immediately for better UX
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
      session_id: sessionId || undefined,
      image_url: imagePreview || undefined
    }

    setMessages(prev => [...prev, userMessage])

    // Clear input immediately for better UX
    setInputMessage('')
    setSelectedImage(null)
    setImagePreview(null)
    setUserUploadedNewImage(false) // Reset flag after sending message with image

    // Send to API
    sendMessageMutation.mutate({
      sessionId,
      message: inputMessage,
      image: selectedImage || undefined
    })
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (event) => {
        const result = event.target?.result as string
        setSelectedImage(result)
        setImagePreview(result)
        setUserUploadedNewImage(true) // Mark that user uploaded a new image
      }
      reader.readAsDataURL(file)

      // Reset the input value so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const removeImage = () => {
    setSelectedImage(null)
    setImagePreview(null)
    setUserUploadedNewImage(false) // Reset flag when image is removed
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const toggleProductSelection = (productId: number) => {
    console.log('toggleProductSelection called with:', productId)
    setSelectedProducts(prev => {
      const newSet = new Set(prev)
      if (newSet.has(productId)) {
        console.log('Removing product:', productId)
        newSet.delete(productId)
      } else {
        console.log('Adding product:', productId)
        newSet.add(productId)
      }
      console.log('New selected products:', Array.from(newSet))
      return newSet
    })
  }

  const executeVisualization = async (
    productDetails: any[],
    imageToUse: string,
    analysis: any,
    existingFurniture?: any[],
    action?: string,
    isUserUploadedImage?: boolean
  ) => {
    setIsVisualizing(true)
    try {
      console.log('Visualize request:', {
        hasImage: !!imageToUse,
        productsCount: productDetails.length,
        hasAnalysis: !!analysis,
        action: action || 'none',
        existingFurniture: existingFurniture?.length || 0
      })

      // Prepare visualization request with full product details
      const requestBody: any = {
        image: imageToUse,
        products: productDetails.map(p => ({
          id: p.id,
          name: p.name,
          full_name: p.name,
          style: p.recommendation_data?.style_match || 0.8,
          category: 'furniture'
        })),
        analysis: analysis
      }

      // Add action and existing furniture if provided
      if (action) {
        requestBody.action = action
      }
      if (existingFurniture) {
        requestBody.existing_furniture = existingFurniture
      }
      // USE CASE 1 & 3: Pass flag if user explicitly uploaded a new image
      if (isUserUploadedImage !== undefined) {
        requestBody.user_uploaded_new_image = isUserUploadedImage
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/chat/sessions/${sessionId}/visualize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Visualization failed')
      }

      const data = await response.json()
      console.log('Visualization response:', data)

      // Check if visualization was successful
      if (!data.rendered_image) {
        // Check if clarification is needed (Issue 6 - existing furniture)
        if (data.needs_clarification) {
          const clarificationMessage: ChatMessage = {
            id: `clarification-${Date.now()}`,
            type: 'assistant',
            content: data.message,
            timestamp: new Date(),
            session_id: sessionId || undefined
          }
          setMessages(prev => [...prev, clarificationMessage])

          // Store visualization context for when user responds
          setPendingVisualization({
            products: productDetails,
            image: imageToUse,
            analysis: analysis,
            existingFurniture: data.existing_furniture || []
          })

          return
        }

        throw new Error('No visualization image was generated')
      }

      // Add visualization result as a new message
      const vizMessage: ChatMessage = {
        id: `viz-${Date.now()}`,
        type: 'assistant',
        content: '✨ Here\'s your personalized room visualization with the selected products!',
        timestamp: new Date(),
        session_id: sessionId || undefined,
        image_url: data.rendered_image
      }

      setMessages(prev => [...prev, vizMessage])

      // Clear selected products after successful visualization
      setSelectedProducts(new Set())

      // BUG #9 FIX: Track this as last visualization for undo/redo
      setLastVisualizationMessage(vizMessage.id)
      setCanUndo(true)
      setCanRedo(false)
    } catch (error) {
      console.error('Visualization error:', error)
      alert(`Failed to generate visualization: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setIsVisualizing(false)
    }
  }

  // BUG #9 FIX: Undo/Redo handlers
  const handleUndo = async () => {
    if (!sessionId || !canUndo) return

    try {
      const response = await undoVisualization(sessionId)

      if (response.success) {
        // Add new message showing the undone visualization
        const undoMessage: ChatMessage = {
          id: `undo-${Date.now()}`,
          type: 'assistant',
          content: `↩️ ${response.message}`,
          timestamp: new Date(),
          session_id: sessionId || undefined,
          image_url: response.rendered_image
        }

        setMessages(prev => [...prev, undoMessage])
        setCanUndo(response.can_undo)
        setCanRedo(response.can_redo)
        setLastVisualizationMessage(undoMessage.id)
      } else {
        alert(response.message || 'Cannot undo: already at the beginning')
      }
    } catch (error) {
      console.error('Undo error:', error)
      alert('Failed to undo visualization')
    }
  }

  const handleRedo = async () => {
    if (!sessionId || !canRedo) return

    try {
      const response = await redoVisualization(sessionId)

      if (response.success) {
        // Add new message showing the redone visualization
        const redoMessage: ChatMessage = {
          id: `redo-${Date.now()}`,
          type: 'assistant',
          content: `↪️ ${response.message}`,
          timestamp: new Date(),
          session_id: sessionId || undefined,
          image_url: response.rendered_image
        }

        setMessages(prev => [...prev, redoMessage])
        setCanUndo(response.can_undo)
        setCanRedo(response.can_redo)
        setLastVisualizationMessage(redoMessage.id)
      } else {
        alert(response.message || 'Cannot redo: already at the latest state')
      }
    } catch (error) {
      console.error('Redo error:', error)
      alert('Failed to redo visualization')
    }
  }

  const handleVisualize = async () => {
    if (!sessionId || selectedProducts.size === 0) {
      alert('Please select at least one product to visualize')
      return
    }

    // Check if we have an image from any message in the conversation
    const hasImageInConversation = messages.some(m => m.image_url)

    if (!imagePreview && !selectedImage && !hasImageInConversation) {
      alert('Please upload an image to visualize')
      return
    }

    // PRODUCT PERSISTENCE FIX: Get products only from the most recent assistant message
    // This prevents products from previous searches appearing in new product type requests
    const messagesWithProducts = messages.filter(m => m.products && m.products.length > 0)
    const allProducts = messagesWithProducts.length > 0
      ? messagesWithProducts[messagesWithProducts.length - 1].products || []
      : []

    const selectedProductDetails = allProducts.filter(p => selectedProducts.has(p.id))

    // Get the image to use - priority: newly uploaded > user message image > assistant message image
    let imageToUse = selectedImage || imagePreview
    if (!imageToUse) {
      // Find the last user or assistant message with an image
      const messageWithImage = [...messages].reverse().find(m => m.image_url)
      if (messageWithImage) {
        imageToUse = messageWithImage.image_url || null
      }
    }

    // Call the extracted visualization function
    // Pass userUploadedNewImage flag if we're using the newly uploaded image
    const isUsingNewUpload = userUploadedNewImage && (imageToUse === selectedImage || imageToUse === imagePreview)
    await executeVisualization(selectedProductDetails, imageToUse!, lastAnalysis, undefined, undefined, isUsingNewUpload)

    // Reset the flag after visualization (user's new image has been used)
    if (isUsingNewUpload) {
      setUserUploadedNewImage(false)
    }
  }

  const isLoading = sendMessageMutation.isPending

  return (
    <div className={`flex flex-col h-full bg-white rounded-xl shadow-sm border border-gray-200 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">AI Design Assistant</h3>
          <p className="text-sm text-gray-500">Get personalized interior design recommendations</p>
        </div>
        {selectedProducts.size > 0 && (
          <div className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
            {selectedProducts.size} selected
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-8">
            <div className="bg-blue-50 rounded-lg p-6 max-w-md mx-auto">
              <h4 className="font-medium text-blue-900 mb-2">Welcome! 👋</h4>
              <p className="text-blue-700 text-sm">
                I'm your AI interior design assistant. Share your space, style preferences, or upload a photo to get started!
              </p>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <ChatMessageBubble
            key={message.id}
            message={message}
            isLast={index === messages.length - 1}
            selectedProducts={selectedProducts}
            onToggleProduct={toggleProductSelection}
            canUndo={canUndo}
            canRedo={canRedo}
            onUndo={handleUndo}
            onRedo={handleRedo}
            showUndoRedo={message.id === lastVisualizationMessage}
          />
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-2 max-w-xs">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Visualize Button - Persistent at bottom */}
      {selectedProducts.size > 0 && (
        <div className="border-t border-gray-200 px-4 py-2 bg-blue-50">
          <button
            onClick={handleVisualize}
            disabled={isVisualizing}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md flex items-center justify-center space-x-2"
          >
            {isVisualizing ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                <span>Generating Visualization...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <span>Visualize Selected Products ({selectedProducts.size})</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        {imagePreview && (
          <div className="mb-3 relative inline-block">
            <img
              src={imagePreview}
              alt="Preview"
              className="w-20 h-20 object-cover rounded-lg border border-gray-300"
            />
            <button
              onClick={removeImage}
              className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-red-600"
            >
              ×
            </button>
          </div>
        )}

        <form ref={formRef} onSubmit={handleSendMessage} className="flex items-end space-x-2">
          <div className="flex-1">
            <div className="relative">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Describe your space, style preferences, or ask for design advice..."
                rows={2}
                className="w-full px-4 py-2 pr-12 border border-gray-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    formRef.current?.requestSubmit()
                  }
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="absolute right-2 bottom-2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <PhotoIcon className="h-5 w-5" />
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={!inputMessage.trim() || isLoading}
            className="bg-blue-600 text-white p-2 rounded-xl hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PaperAirplaneIcon className="h-5 w-5" />
          </button>
        </form>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleImageSelect}
          className="hidden"
        />
      </div>
    </div>
  )
}

interface ChatMessageBubbleProps {
  message: ChatMessage
  isLast: boolean
  selectedProducts: Set<number>
  onToggleProduct: (productId: number) => void
  canUndo?: boolean
  canRedo?: boolean
  onUndo?: () => void
  onRedo?: () => void
  showUndoRedo?: boolean
}

function ChatMessageBubble({
  message,
  isLast,
  selectedProducts,
  onToggleProduct,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  showUndoRedo
}: ChatMessageBubbleProps) {
  const isUser = message.type === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-xs lg:max-w-md xl:max-w-lg ${isUser ? 'ml-auto' : 'mr-auto'}`}>
        <div
          className={`rounded-2xl px-4 py-2 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-900'
          }`}
        >
          {message.image_url && (
            <div className="mb-2">
              <img
                src={message.image_url}
                alt={isUser ? "Uploaded room" : "Transformed design"}
                className="w-full rounded-lg max-w-md"
              />
              {!isUser && (
                <p className="text-xs text-gray-500 mt-1 italic">
                  ✨ AI-transformed design visualization
                </p>
              )}

              {/* BUG #9 FIX: Undo/Redo buttons for visualizations */}
              {!isUser && showUndoRedo && (onUndo || onRedo) && (
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={onUndo}
                    disabled={!canUndo}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                      canUndo
                        ? 'bg-blue-500 hover:bg-blue-600 text-white shadow-sm hover:shadow'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                    title="Undo last action (Ctrl+Z)"
                  >
                    <ArrowUturnLeftIcon className="w-4 h-4" />
                    Undo
                  </button>
                  <button
                    onClick={onRedo}
                    disabled={!canRedo}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                      canRedo
                        ? 'bg-blue-500 hover:bg-blue-600 text-white shadow-sm hover:shadow'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                    title="Redo undone action (Ctrl+Y)"
                  >
                    Redo
                    <ArrowUturnRightIcon className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          )}
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Product recommendations */}
        {!isUser && message.products && message.products.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-medium text-gray-600 mb-2">Recommended products:</p>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {message.products.map((product) => {
                console.log('Product data:', {
                  id: product.id,
                  name: product.name,
                  primary_image: product.primary_image,
                  images: product.images
                })
                return (
                <div
                  key={product.id}
                  className={`bg-white border-2 rounded-lg overflow-hidden hover:shadow-lg transition-all ${
                    selectedProducts.has(product.id) ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200'
                  }`}
                >
                  <div className="relative">
                    {product.primary_image?.url ? (
                      <img
                        src={product.primary_image.url}
                        alt={product.primary_image?.alt_text || product.name}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          console.log('Image failed to load:', product.primary_image?.url)
                          e.currentTarget.style.display = 'none'
                          const parent = e.currentTarget.parentElement
                          if (parent) {
                            const fallback = document.createElement('div')
                            fallback.className = 'w-full h-32 bg-gray-100 flex items-center justify-center'
                            fallback.innerHTML = '<span class="text-gray-400 text-xs">No image</span>'
                            parent.appendChild(fallback)
                          }
                        }}
                      />
                    ) : (
                      <div className="w-full h-32 bg-gray-100 flex items-center justify-center">
                        <span className="text-gray-400 text-xs">No image</span>
                      </div>
                    )}
                    <div className="absolute top-2 right-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedProducts.has(product.id)}
                        onChange={() => {
                          console.log('Toggling product:', product.id)
                          onToggleProduct(product.id)
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-5 h-5 text-blue-600 bg-white border-gray-300 rounded focus:ring-blue-500 cursor-pointer shadow-md"
                      />
                    </div>
                  </div>
                  <div className="p-2">
                    <p className="text-sm font-medium text-gray-900 truncate" title={product.name}>
                      {product.name}
                    </p>
                    <p className="text-sm font-semibold text-blue-600 mt-1">
                      ₹{product.price.toLocaleString('en-IN')}
                    </p>
                    {product.source_url ? (
                      <a
                        href={product.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs text-blue-500 hover:text-blue-700 underline truncate block mt-1"
                        title={`View on ${product.source_website}`}
                      >
                        {product.source_website}
                      </a>
                    ) : (
                      <p className="text-xs text-gray-500 truncate mt-1" title={product.source_website}>
                        {product.source_website}
                      </p>
                    )}
                  </div>
                </div>
              )})}
            </div>
            {selectedProducts.size > 0 && (
              <p className="text-xs text-blue-600 font-medium mt-2">
                {selectedProducts.size} product{selectedProducts.size !== 1 ? 's' : ''} selected
              </p>
            )}
          </div>
        )}

        <p className="text-xs text-gray-400 mt-1">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}

export default ChatInterface