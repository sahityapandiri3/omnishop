'use client'

import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChatMessage, ChatMessageRequest, ChatMessageResponse } from '@/types'
import { startChatSession, sendChatMessage, getChatHistory } from '@/utils/api'
import { PaperAirplaneIcon, PhotoIcon } from '@heroicons/react/24/outline'
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
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Start new session if none provided
  const startSessionMutation = useMutation({
    mutationFn: startChatSession,
    onSuccess: (response) => {
      setSessionId(response.session_id)
    }
  })

  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: ({ sessionId, message, image }: { sessionId: string; message: string; image?: string }) =>
      sendChatMessage(sessionId, { message, image }),
    onSuccess: (response) => {
      setMessages(prev => [...prev, response.message])
      setInputMessage('')
      setSelectedImage(null)
      setImagePreview(null)
    }
  })

  // Load chat history if session exists
  const { data: chatHistory } = useQuery({
    queryKey: ['chatHistory', sessionId],
    queryFn: () => sessionId ? getChatHistory(sessionId) : null,
    enabled: !!sessionId,
    onSuccess: (data) => {
      if (data) {
        setMessages(data.messages)
      }
    }
  })

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

    // Add user message immediately for better UX
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
      session_id: sessionId,
      image_url: imagePreview || undefined
    }

    setMessages(prev => [...prev, userMessage])

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
      }
      reader.readAsDataURL(file)
    }
  }

  const removeImage = () => {
    setSelectedImage(null)
    setImagePreview(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
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
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-96">
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

        <form onSubmit={handleSendMessage} className="flex items-end space-x-2">
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
                    handleSendMessage(e)
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
}

function ChatMessageBubble({ message, isLast }: ChatMessageBubbleProps) {
  const isUser = message.type === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-xs lg:max-w-md ${isUser ? 'ml-auto' : 'mr-auto'}`}>
        <div
          className={`rounded-2xl px-4 py-2 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-900'
          }`}
        >
          {message.image_url && (
            <img
              src={message.image_url}
              alt="Uploaded"
              className="w-full rounded-lg mb-2 max-w-xs"
            />
          )}
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Product recommendations */}
        {!isUser && message.products && message.products.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-gray-600">Recommended products:</p>
            <div className="grid grid-cols-1 gap-2">
              {message.products.slice(0, 3).map((product) => (
                <div key={product.id} className="bg-white border border-gray-200 rounded-lg p-3">
                  <div className="flex items-center space-x-3">
                    {product.primary_image?.url && (
                      <img
                        src={product.primary_image.url}
                        alt={product.name}
                        className="w-12 h-12 object-cover rounded"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
                      <p className="text-sm text-gray-500">${product.price}</p>
                      <p className="text-xs text-gray-400">{product.source_website}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
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