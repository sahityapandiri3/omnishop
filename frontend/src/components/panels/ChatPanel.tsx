'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { sendChatMessage, startChatSession, getChatHistory, OnboardingPreferences } from '@/utils/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// Response type for product recommendations (supports both legacy and category-based)
interface ProductRecommendationResponse {
  // Legacy format
  products?: any[];
  recommended_products?: any[];
  // New category-based format
  selected_categories?: any[];
  products_by_category?: Record<string, any[]>;
  total_budget?: number | null;
  conversation_state?: string;
  follow_up_question?: string | null;
}

interface ChatPanelProps {
  onProductRecommendations: (response: ProductRecommendationResponse) => void;
  roomImage: string | null;
  selectedStores?: string[];
  initialSessionId?: string | null;  // For restoring existing chat session from saved project
  onSessionIdChange?: (sessionId: string) => void;  // Callback when session ID changes (for saving)
}

/**
 * Panel 1: Chat Interface
 * Focused conversational UI without product selection
 */
export default function ChatPanel({
  onProductRecommendations,
  roomImage,
  selectedStores = [],
  initialSessionId = null,
  onSessionIdChange,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Hi! I'm Omni, your AI interior stylist. I'd love to help you transform your space. Upload a photo of your room, or tell me what you're looking for!",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pendingMessages, setPendingMessages] = useState<string[]>([]);
  const [imageSentToBackend, setImageSentToBackend] = useState(false); // Track if image was already sent
  const [conversationState, setConversationState] = useState<string>('INITIAL'); // Track conversation state for two-phase flow
  const [isRestoringSession, setIsRestoringSession] = useState(false); // Flag to prevent processing during restore
  const [onboardingPreferences, setOnboardingPreferences] = useState<OnboardingPreferences | null>(null);
  const onboardingProcessedRef = useRef(false); // Track if onboarding was already processed

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionInitializedRef = useRef(false); // Prevent double initialization

  // Initialize chat session (use existing or create new)
  useEffect(() => {
    // Guard against double initialization (React StrictMode)
    if (sessionInitializedRef.current) {
      console.log('[ChatPanel] Session already initialized, skipping');
      return;
    }

    const initSession = async () => {
      try {
        // If we have an initial session ID (from saved project), use it and load history
        if (initialSessionId) {
          console.log('[ChatPanel] Restoring existing session:', initialSessionId);
          setIsRestoringSession(true); // Mark as restoring to prevent processing
          sessionInitializedRef.current = true;
          setSessionId(initialSessionId);

          // Load chat history from the existing session
          try {
            const history = await getChatHistory(initialSessionId);
            if (history.messages && history.messages.length > 0) {
              // Convert backend messages to frontend format
              const restoredMessages: Message[] = history.messages.map((msg: any) => ({
                role: msg.type as 'user' | 'assistant',
                content: msg.content,
                timestamp: new Date(msg.timestamp),
              }));
              setMessages(restoredMessages);

              // Restore conversation state from last assistant message if available
              // Find the last message with conversation_state in the analysis_data
              // For now, assume we're in BROWSING state if there are messages
              if (restoredMessages.length > 1) {
                setConversationState('BROWSING');
                setImageSentToBackend(true); // Image was already sent in previous session
              }

              console.log('[ChatPanel] Restored', restoredMessages.length, 'messages from history');
            }
          } catch (historyError) {
            console.error('[ChatPanel] Failed to load chat history:', historyError);
            // Session might be invalid/expired, create a new one
            const response = await startChatSession();
            setSessionId(response.session_id);
            if (onSessionIdChange) {
              onSessionIdChange(response.session_id);
            }
          } finally {
            // Done restoring - allow normal processing
            setIsRestoringSession(false);
          }
        } else {
          sessionInitializedRef.current = true;
          // No initial session, create a new one
          const response = await startChatSession();
          console.log('[ChatPanel] Created new session:', response.session_id);
          setSessionId(response.session_id);
          if (onSessionIdChange) {
            console.log('[ChatPanel] Calling onSessionIdChange with:', response.session_id);
            onSessionIdChange(response.session_id);
          } else {
            console.log('[ChatPanel] WARNING: onSessionIdChange callback is not provided!');
          }
        }
      } catch (error) {
        console.error('Failed to start chat session:', error);
      }
    };
    initSession();
  }, [initialSessionId, onSessionIdChange]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Reset state when roomImage changes (new image uploaded)
  useEffect(() => {
    if (roomImage) {
      setImageSentToBackend(false);
      // Don't reset conversationState here - let the guided flow continue naturally
      // The user may upload a new image during the conversation
    }
  }, [roomImage]);

  // Load and process onboarding preferences from sessionStorage
  useEffect(() => {
    // Debug: Log all conditions
    console.log('[ChatPanel] Onboarding effect check:', {
      sessionId: !!sessionId,
      isRestoringSession,
      alreadyProcessed: onboardingProcessedRef.current,
      hasPrefs: !!sessionStorage.getItem('onboardingPreferences'),
    });

    // Only run once when session is ready and not restoring
    if (!sessionId || isRestoringSession || onboardingProcessedRef.current) return;

    try {
      const prefsJson = sessionStorage.getItem('onboardingPreferences');
      if (!prefsJson) {
        console.log('[ChatPanel] No onboarding preferences in sessionStorage');
        return;
      }

      const prefs: OnboardingPreferences = JSON.parse(prefsJson);
      console.log('[ChatPanel] Found onboarding preferences:', prefs);

      // Mark as processed to prevent re-running
      onboardingProcessedRef.current = true;

      // Clear from sessionStorage
      sessionStorage.removeItem('onboardingPreferences');

      // Store preferences in state
      setOnboardingPreferences(prefs);

      // Build a natural language message from preferences
      const parts: string[] = [];

      // Room type
      if (prefs.roomType) {
        const roomName = prefs.roomType === 'living_room' ? 'living room' :
                        prefs.roomType === 'bedroom' ? 'bedroom' : prefs.roomType;
        parts.push(`I'm designing my ${roomName}`);
      }

      // Style
      if (prefs.primaryStyle) {
        const styleName = prefs.primaryStyle.replace(/_/g, ' ');
        if (prefs.secondaryStyle) {
          const secondaryName = prefs.secondaryStyle.replace(/_/g, ' ');
          parts.push(`I love ${styleName} style with some ${secondaryName} touches`);
        } else {
          parts.push(`I love ${styleName} style`);
        }
      }

      // Budget
      if (prefs.budget && !prefs.budgetFlexible) {
        const budgetStr = prefs.budget >= 100000
          ? `₹${(prefs.budget / 100000).toFixed(prefs.budget % 100000 === 0 ? 0 : 1)} lakh`
          : `₹${prefs.budget.toLocaleString('en-IN')}`;
        parts.push(`My budget is around ${budgetStr}`);
      } else if (prefs.budgetFlexible) {
        parts.push(`I'm flexible on budget`);
      }

      // Construct the message
      if (parts.length > 0) {
        let message = parts.join('. ') + '.';
        if (prefs.roomImage) {
          message += ' Here is my room photo.';
        }
        message += ' Please help me find furniture!';

        // Update welcome message to be personalized
        const roomName = prefs.roomType === 'living_room' ? 'living room' :
                        prefs.roomType === 'bedroom' ? 'bedroom' : 'space';
        const welcomeMessage = prefs.primaryStyle
          ? `Welcome! I see you're looking to create a beautiful ${prefs.primaryStyle.replace(/_/g, ' ')} ${roomName}. Let me help you find the perfect pieces!`
          : `Welcome! I'm excited to help you design your ${roomName}. Let me find some great options for you!`;

        console.log('[ChatPanel] Setting welcome message:', welcomeMessage);
        setMessages([{
          role: 'assistant',
          content: welcomeMessage,
          timestamp: new Date(),
        }]);

        // Auto-send the preferences as a user message (with image if provided)
        setTimeout(() => {
          // Add user message
          setMessages(prev => [...prev, {
            role: 'user',
            content: message,
            timestamp: new Date(),
          }]);

          // Send to backend
          setIsLoading(true);
          const sendPreferences = async () => {
            try {
              // Use the PROCESSED image (clean room) for room analysis, not the original
              // The processed image has furniture removed, allowing proper analysis of:
              // wall colors, space, lighting, ceiling, etc.
              const imageForAnalysis = prefs.processedImage || prefs.roomImage;

              const response = await sendChatMessage(sessionId, {
                message,
                image: imageForAnalysis || undefined,
                selected_stores: selectedStores.length > 0 ? selectedStores : undefined,
                onboarding_preferences: prefs,
              });

              // Handle response
              if (response.message) {
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: response.message.content,
                  timestamp: new Date(),
                }]);
              }

              // Handle product recommendations
              if (response.selected_categories || response.products_by_category) {
                onProductRecommendations(response);
              }

              // Update conversation state
              if (response.conversation_state) {
                setConversationState(response.conversation_state);
              }

              // Mark image as sent
              if (imageForAnalysis) {
                setImageSentToBackend(true);
              }
            } catch (error) {
              console.error('[ChatPanel] Error sending onboarding preferences:', error);
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: "I had trouble processing your preferences. Could you tell me more about what you're looking for?",
                timestamp: new Date(),
              }]);
            } finally {
              setIsLoading(false);
            }
          };
          sendPreferences();
        }, 500); // Small delay for better UX
      }
    } catch (error) {
      console.error('[ChatPanel] Error loading onboarding preferences:', error);
    }
  }, [sessionId, isRestoringSession, selectedStores, onProductRecommendations]);

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

      // TWO-PHASE FLOW: Only send image when transitioning to READY_TO_RECOMMEND
      // Phase 1 (GATHERING_*): Fast mode, no image - just gather user preferences
      // Phase 2 (READY_TO_RECOMMEND): Full mode WITH image - analyze room and recommend products
      // Image should be sent when:
      // 1. We're in GATHERING_BUDGET state (next response will be READY_TO_RECOMMEND)
      // 2. OR we're already in READY_TO_RECOMMEND and haven't sent image yet (edge case)
      // 3. AND we have an image to send
      const isReadyForAnalysis = conversationState === 'GATHERING_BUDGET' || conversationState === 'READY_TO_RECOMMEND';
      const shouldSendImage = roomImage && !imageSentToBackend && isReadyForAnalysis;

      console.log('[ChatPanel] Sending message:', {
        conversationState,
        isReadyForAnalysis,
        hasRoomImage: !!roomImage,
        imageSentToBackend,
        shouldSendImage,
      });

      const response = await sendChatMessage(sessionId, {
        message: combinedMessage,
        image: shouldSendImage ? roomImage : undefined,
        selected_stores: selectedStores.length > 0 ? selectedStores : undefined,
      });

      // Mark image as sent so subsequent messages don't resend it
      if (shouldSendImage) {
        setImageSentToBackend(true);
      }

      // Update conversation state from response
      if (response.conversation_state) {
        setConversationState(response.conversation_state);
      }

      // Check if request was aborted
      if (abortControllerRef.current?.signal.aborted) {
        return;
      }

      // Extract message content and products from response
      const messageData = response.message || response;
      const products = response.recommended_products || messageData.products || [];

      // Build the assistant message content
      // Include the follow-up question if present (this is the guided conversation flow)
      let messageContent = messageData.content || response.response || '';
      const followUpQuestion = response.follow_up_question;

      // Debug logging for conversation flow
      console.log('[ChatPanel] Response received:', {
        conversation_state: response.conversation_state,
        follow_up_question: followUpQuestion,
        hasCategories: !!response.selected_categories,
        hasProductsByCategory: !!response.products_by_category,
      });

      // If there's a follow-up question, append it to the message
      // This creates the conversational flow where AI asks questions
      if (followUpQuestion) {
        if (messageContent) {
          messageContent = `${messageContent}\n\n${followUpQuestion}`;
        } else {
          messageContent = followUpQuestion;
        }
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: messageContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Emit full response to parent (supports both legacy and category-based formats)
      // Check if we have category-based data OR legacy products
      const hasProducts = products && products.length > 0;
      const hasCategoryData = response.selected_categories && response.products_by_category;

      console.log('[ChatPanel] Product check:', {
        hasProducts,
        hasCategoryData,
        productsLength: products?.length,
        hasSelectedCategories: !!response.selected_categories,
        hasProductsByCategory: !!response.products_by_category,
        productsByCategoryKeys: response.products_by_category ? Object.keys(response.products_by_category) : [],
        productsByCategoryTotal: response.products_by_category
          ? (Object.values(response.products_by_category) as any[][]).reduce((sum: number, prods: any[]) => sum + (prods?.length || 0), 0)
          : 0,
      });

      if (hasProducts || hasCategoryData) {
        console.log('[ChatPanel] Calling onProductRecommendations with:', {
          categoriesCount: response.selected_categories?.length,
          productsByCategory: response.products_by_category ? Object.keys(response.products_by_category) : null,
        });
        onProductRecommendations({
          // Legacy format
          products: products,
          recommended_products: response.recommended_products,
          // New category-based format
          selected_categories: response.selected_categories,
          products_by_category: response.products_by_category,
          total_budget: response.total_budget,
          conversation_state: response.conversation_state,
          follow_up_question: response.follow_up_question,
        });
      } else {
        console.log('[ChatPanel] NOT calling onProductRecommendations - no products or category data');
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
  }, [sessionId, pendingMessages, roomImage, onProductRecommendations, conversationState, imageSentToBackend, selectedStores]);

  // Auto-process when new messages are added (but not during session restore)
  useEffect(() => {
    if (pendingMessages.length > 0 && !isLoading && sessionId && !isRestoringSession) {
      processPendingMessages();
    }
  }, [pendingMessages, isLoading, sessionId, processPendingMessages, isRestoringSession]);

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
              Omni
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Your AI Interior Stylist
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
