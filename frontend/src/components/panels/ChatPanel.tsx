'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { sendChatMessage, startChatSession } from '@/utils/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatPanelProps {
  onProductRecommendations: (products: any[]) => void;
  roomImage: string | null;
  selectedStores?: string[];
}

/**
 * Panel 1: Chat Interface
 * Focused conversational UI without product selection
 */
export default function ChatPanel({
  onProductRecommendations,
  roomImage,
  selectedStores = [],
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Hi! I'm your interior styling assistant. Tell me about your space and what you're looking for!",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pendingMessages, setPendingMessages] = useState<string[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Initialize chat session
  useEffect(() => {
    const initSession = async () => {
      try {
        const response = await startChatSession();
        setSessionId(response.session_id);
      } catch (error) {
        console.error('Failed to start chat session:', error);
      }
    };
    initSession();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Process pending messages (ChatGPT-style: cancels previous, processes all pending)
  const processPendingMessages = useCallback(async () => {
    if (!sessionId || pendingMessages.length === 0) return;

    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();

    // Get all pending messages
    const messagesToProcess = [...pendingMessages];
    setPendingMessages([]);

    // Add all user messages to UI
    const newUserMessages = messagesToProcess.map(msg => ({
      role: 'user' as const,
      content: msg,
      timestamp: new Date(),
    }));
    setMessages(prev => [...prev, ...newUserMessages]);

    setIsLoading(true);

    try {
      // Combine all pending messages into one message for the backend
      const combinedMessage = messagesToProcess.join('\n\n');

      const response = await sendChatMessage(sessionId, {
        message: combinedMessage,
        image: roomImage || undefined,
        selected_stores: selectedStores.length > 0 ? selectedStores : undefined,
      });

      // Check if request was aborted
      if (abortControllerRef.current?.signal.aborted) {
        return;
      }

      // V1 APPROACH: Get products directly from chat response
      const messageData = response.message || response;
      const products = response.recommended_products || messageData.products || [];

      const assistantMessage: Message = {
        role: 'assistant',
        content: messageData.content || response.response || '',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Emit products to parent
      if (products && products.length > 0) {
        onProductRecommendations(products);
      }
    } catch (error: any) {
      // Don't show error if request was aborted (user sent new message)
      if (error.name === 'AbortError' || abortControllerRef.current?.signal.aborted) {
        return;
      }

      console.error('Chat error:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [sessionId, pendingMessages, roomImage, onProductRecommendations]);

  // Auto-process when new messages are added
  useEffect(() => {
    if (pendingMessages.length > 0 && !isLoading && sessionId) {
      processPendingMessages();
    }
  }, [pendingMessages, isLoading, sessionId, processPendingMessages]);

  const handleSend = () => {
    if (!input.trim() || !sessionId) return;

    // Add message to pending queue
    setPendingMessages(prev => [...prev, input]);
    setInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-secondary-500 rounded-full flex items-center justify-center">
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
          </div>
          <div>
            <h2 className="font-semibold text-neutral-900 dark:text-white">
              Styling Assistant
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Ask me anything about furniture
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[85%] rounded-lg p-3 ${
                message.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-900 dark:text-white'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              <p
                className={`text-xs mt-1 ${
                  message.role === 'user'
                    ? 'text-primary-100'
                    : 'text-neutral-500 dark:text-neutral-400'
                }`}
              >
                {message.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-neutral-100 dark:bg-neutral-700 rounded-lg p-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce"></div>
                <div
                  className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce"
                  style={{ animationDelay: '0.1s' }}
                ></div>
                <div
                  className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce"
                  style={{ animationDelay: '0.2s' }}
                ></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Describe your space or ask for recommendations..."
            className="flex-1 resize-none rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700 px-4 py-2 text-sm text-neutral-900 dark:text-white placeholder-neutral-500 dark:placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-neutral-300 dark:disabled:bg-neutral-700 text-white rounded-lg transition-colors duration-200 flex items-center justify-center"
          >
            {isLoading ? (
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            )}
          </button>
        </div>

        {/* Suggested Prompts */}
        {messages.length === 1 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => setInput('I need a modern sofa for my living room')}
              className="text-xs px-3 py-1.5 bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded-full transition-colors"
            >
              Modern sofa
            </button>
            <button
              onClick={() => setInput('Show me minimalist furniture')}
              className="text-xs px-3 py-1.5 bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded-full transition-colors"
            >
              Minimalist style
            </button>
            <button
              onClick={() => setInput('I want center tables under ₹20,000')}
              className="text-xs px-3 py-1.5 bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 text-neutral-700 dark:text-neutral-300 rounded-full transition-colors"
            >
              Budget tables
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
