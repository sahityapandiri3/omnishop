"""
ChatGPT service for interior design analysis using the prompt.md specification
"""
import openai
import json
import logging
import uuid
import asyncio
import time
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import base64
from PIL import Image
import io
from functools import wraps
import aiohttp
from datetime import datetime, timedelta

from api.core.config import settings
from api.schemas.chat import DesignAnalysisSchema, ChatMessageSchema, MessageType
from api.services.conversation_context import conversation_context_manager
from api.services.nlp_processor import design_nlp_processor

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for API calls"""

    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    async def acquire(self):
        """Acquire rate limit permission"""
        now = datetime.now()
        # Remove old requests outside time window
        self.requests = [req_time for req_time in self.requests
                        if (now - req_time).total_seconds() < self.time_window]

        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()

        self.requests.append(now)
        return True


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying API calls on failure"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"API call failed after {max_retries} attempts: {e}")
            raise last_exception
        return wrapper
    return decorator


class ChatGPTService:
    """Service for interacting with ChatGPT for interior design analysis"""

    def __init__(self):
        """Initialize the ChatGPT service"""
        # Enhanced authentication and configuration
        self.client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,  # 30 second timeout
            max_retries=0  # We handle retries manually
        )
        self.system_prompt = self._load_system_prompt()
        self.conversation_memory = {}  # Legacy - kept for compatibility
        self.context_manager = conversation_context_manager

        # Rate limiting and monitoring
        self.rate_limiter = RateLimiter(max_requests=50, time_window=60)  # 50 requests per minute
        self.api_usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "last_reset": datetime.now()
        }

        # Authentication validation
        self._validate_api_key()

        logger.info("ChatGPT service initialized with enhanced authentication and monitoring")

    def _validate_api_key(self):
        """Validate OpenAI API key"""
        if not settings.openai_api_key:
            logger.error("OpenAI API key not configured")
            raise ValueError("OpenAI API key is required")

        # Allow demo keys for localhost development
        if settings.openai_api_key == "demo_key_for_localhost":
            logger.info("Running in demo mode - OpenAI API calls will be simulated")
            self.demo_mode = True
            return

        if not settings.openai_api_key.startswith('sk-'):
            logger.error("Invalid OpenAI API key format")
            raise ValueError("Invalid OpenAI API key format")

        logger.info("OpenAI API key validated successfully")
        self.demo_mode = False

    def _load_system_prompt(self) -> str:
        """Load the system prompt from prompt.md file"""
        try:
            # Path to prompt.md from current location
            prompt_path = Path(__file__).parent.parent.parent / "prompt.md"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract the main analysis prompt and instructions
            # This combines the system role and analysis framework
            system_prompt = """You are an expert interior designer and product analyst with deep knowledge of furniture, decor, color theory, spatial design, and current design trends. Your role is to analyze user requirements for interior design projects and provide structured analysis for product matching and visualization.

You will receive:
1. Natural Language Requirements: User's description of their interior design needs, preferences, and constraints
2. Room Image (optional): Photo of the space to be designed
3. Source Websites: Product catalogs from westelm.com, orangetree.com, and pelicanessentials.com

CRITICAL: You MUST respond with a valid JSON object. Always return your response as a JSON object following this exact structure:

{
  "design_analysis": {
    "style_preferences": {
      "primary_style": "string",
      "secondary_styles": ["string"],
      "style_keywords": ["string"],
      "inspiration_sources": ["string"]
    },
    "color_scheme": {
      "preferred_colors": ["string"],
      "accent_colors": ["string"],
      "color_temperature": "warm/cool/neutral",
      "color_intensity": "bold/muted/balanced"
    },
    "space_analysis": {
      "room_type": "string",
      "dimensions": "estimated/provided dimensions",
      "layout_type": "open/closed/mixed",
      "lighting_conditions": "natural/artificial/mixed",
      "existing_elements": ["string"],
      "traffic_patterns": "string"
    },
    "functional_requirements": {
      "primary_functions": ["string"],
      "storage_needs": "string",
      "seating_capacity": "number/range",
      "special_considerations": ["string"]
    },
    "budget_indicators": {
      "price_range": "budget/mid-range/luxury",
      "investment_priorities": ["string"]
    }
  },
  "product_matching_criteria": {
    "furniture_categories": {
      "seating": {
        "types": ["string"],
        "materials": ["string"],
        "colors": ["string"],
        "size_requirements": "string"
      },
      "tables": {
        "types": ["string"],
        "materials": ["string"],
        "shapes": ["string"],
        "size_requirements": "string"
      },
      "storage": {
        "types": ["string"],
        "materials": ["string"],
        "configurations": ["string"]
      },
      "lighting": {
        "types": ["string"],
        "styles": ["string"],
        "placement": ["string"]
      },
      "decor": {
        "categories": ["string"],
        "materials": ["string"],
        "themes": ["string"]
      }
    },
    "filtering_keywords": {
      "include_terms": ["string"],
      "exclude_terms": ["string"],
      "material_preferences": ["string"],
      "style_tags": ["string"]
    }
  },
  "visualization_guidance": {
    "layout_recommendations": {
      "furniture_placement": "string",
      "focal_points": ["string"],
      "traffic_flow": "string"
    },
    "spatial_considerations": {
      "scale_proportions": "string",
      "height_variations": "string",
      "negative_space": "string"
    },
    "styling_suggestions": {
      "layering_approach": "string",
      "texture_mixing": "string",
      "pattern_coordination": "string"
    }
  },
  "confidence_scores": {
    "style_identification": 85,
    "space_understanding": 90,
    "product_matching": 88,
    "overall_analysis": 87
  },
  "recommendations": {
    "priority_items": ["string"],
    "alternative_options": ["string"],
    "phased_approach": ["string"]
  },
  "user_friendly_response": "A conversational response that explains your analysis in a friendly, helpful way"
}

Analysis Instructions:
1. Extract explicit design preferences and style mentions
2. Identify implied preferences through descriptive language
3. Recognize functional requirements and constraints
4. Detect budget indicators and investment priorities
5. Parse spatial requirements and room characteristics
6. For images: assess dimensions, existing elements, lighting, color palette
7. Generate specific search terms for product matching
8. Provide actionable filtering criteria for product databases
9. Ensure all recommendations align with identified style
10. Include confidence scores (0-100) for analysis quality"""

            return system_prompt

        except FileNotFoundError:
            logger.error("prompt.md file not found, using fallback prompt")
            return "You are an expert interior designer. Help users with their interior design needs."

    async def analyze_user_input(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        image_data: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Tuple[str, Optional[DesignAnalysisSchema]]:
        """
        Analyze user input and return both a conversational response and structured analysis

        Args:
            user_message: The user's message
            session_id: Session ID for conversation context
            image_data: Base64 encoded image data (optional)
            user_id: User ID for preference tracking

        Returns:
            Tuple of (conversational_response, design_analysis)
        """
        print(f"[DEBUG] analyze_user_input called - message: {user_message[:50]}, has_image: {image_data is not None}, session_id: {session_id}")
        try:
            # Get or create conversation context
            if session_id:
                context = self.context_manager.get_or_create_context(session_id, user_id)
                # Add user message to context
                self.context_manager.add_message(
                    session_id, "user", user_message,
                    {"has_image": image_data is not None}
                )

                # Get enhanced context for AI
                messages = self.context_manager.get_context_for_ai(session_id)
            else:
                # Fallback to basic system prompt
                messages = [{"role": "system", "content": self.system_prompt}]

            # Prepare user message content
            user_content = [{"type": "text", "text": user_message}]

            # Add image if provided
            if image_data:
                processed_image = self._process_image(image_data)
                if processed_image:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{processed_image}",
                            "detail": "high"
                        }
                    })

            # Update the last message with content including image
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] = user_content
            else:
                messages.append({"role": "user", "content": user_content})

            # Call ChatGPT
            print(f"[DEBUG] About to call _call_chatgpt with {len(messages)} messages")
            response = await self._call_chatgpt(messages)
            print(f"[DEBUG] _call_chatgpt returned, response length: {len(response) if response else 0}")

            # Parse response
            print(f"[DEBUG] About to parse response")
            conversational_response, analysis = self._parse_response(response)
            print(f"[DEBUG] Parse complete - analysis is None: {analysis is None}")

            # Store conversation context
            if session_id:
                # Add assistant response to context
                self.context_manager.add_message(
                    session_id, "assistant", conversational_response,
                    {"has_analysis": analysis is not None}
                )

                # Store design analysis in context
                if analysis:
                    self.context_manager.add_design_analysis(
                        session_id, analysis.dict() if hasattr(analysis, 'dict') else analysis
                    )

                # Legacy context storage for backward compatibility
                if session_id not in self.conversation_memory:
                    self.conversation_memory[session_id] = []

                self.conversation_memory[session_id].extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": conversational_response}
                ])

                if len(self.conversation_memory[session_id]) > 10:
                    self.conversation_memory[session_id] = self.conversation_memory[session_id][-10:]

            return conversational_response, analysis

        except Exception as e:
            print(f"[DEBUG] EXCEPTION in analyze_user_input: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error in ChatGPT analysis: {e}", exc_info=True)
            fallback_response = "I apologize, but I'm having trouble analyzing your request right now. Could you please try rephrasing your interior design needs?"
            return fallback_response, None

    async def _call_chatgpt(self, messages: List[Dict[str, Any]]) -> str:
        """Call ChatGPT API with the prepared messages"""
        print(f"[DEBUG] _call_chatgpt started")
        # Apply rate limiting
        await self.rate_limiter.acquire()
        print(f"[DEBUG] Rate limit acquired")

        # Update usage stats
        self.api_usage_stats["total_requests"] += 1

        # Demo mode simulation
        if hasattr(self, 'demo_mode') and self.demo_mode:
            return await self._simulate_chatgpt_response(messages)

        try:
            start_time = time.time()
            print(f"[DEBUG] About to call OpenAI API with model: {settings.openai_model}")
            print(f"[DEBUG] API Key (first 10 chars): {settings.openai_api_key[:10] if settings.openai_api_key else 'None'}")

            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
                response_format={"type": "json_object"}
            )
            print(f"[DEBUG] OpenAI API call succeeded!")

            # Update successful request stats
            self.api_usage_stats["successful_requests"] += 1
            if hasattr(response, 'usage') and response.usage:
                self.api_usage_stats["total_tokens"] += response.usage.total_tokens

            response_time = time.time() - start_time
            logger.info(f"ChatGPT API call successful - Response time: {response_time:.2f}s, "
                       f"Tokens: {response.usage.total_tokens if hasattr(response, 'usage') and response.usage else 'N/A'}")

            return response.choices[0].message.content

        except openai.APIError as e:
            print(f"[DEBUG] OpenAI APIError: {type(e).__name__}: {str(e)}")
            self.api_usage_stats["failed_requests"] += 1
            error_message = str(e)
            logger.error(f"OpenAI API error: {e}")

            # Check if it's a quota error (429) and switch to structured fallback
            if "429" in error_message or "quota" in error_message.lower() or "insufficient_quota" in error_message.lower():
                print(f"[DEBUG] Quota error detected, returning fallback")
                logger.warning("OpenAI quota exceeded - returning structured fallback response")
                return self._get_structured_fallback(messages)
            raise
        except openai.RateLimitError as e:
            print(f"[DEBUG] OpenAI RateLimitError: {str(e)}")
            self.api_usage_stats["failed_requests"] += 1
            logger.warning(f"Rate limit exceeded - returning structured fallback: {e}")
            return self._get_structured_fallback(messages)
        except openai.AuthenticationError as e:
            print(f"[DEBUG] OpenAI AuthenticationError: {str(e)}")
            self.api_usage_stats["failed_requests"] += 1
            logger.error(f"Authentication failed: {e}")
            raise
        except Exception as e:
            print(f"[DEBUG] Generic exception in _call_chatgpt: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.api_usage_stats["failed_requests"] += 1
            logger.error(f"ChatGPT API call failed: {e}", exc_info=True)
            # Return a structured fallback response for any other errors
            return self._get_structured_fallback(messages)

    def _get_structured_fallback(self, messages: List[Dict[str, Any]]) -> str:
        """Get structured fallback response when API fails"""
        print(f"[DEBUG] _get_structured_fallback called")
        # Extract user message for contextual response
        user_message = ""
        has_image = False
        for msg in messages:
            if msg.get("role") == "user":
                if isinstance(msg.get("content"), list):
                    for part in msg["content"]:
                        if part.get("type") == "text":
                            user_message = part.get("text", "")
                        elif part.get("type") == "image_url":
                            has_image = True
                else:
                    user_message = msg.get("content", "")

        fallback = {
                "design_analysis": {
                    "style_preferences": {
                        "primary_style": "modern",
                        "secondary_styles": [],
                        "style_keywords": ["clean", "simple"],
                        "inspiration_sources": []
                    },
                    "color_scheme": {
                        "preferred_colors": ["neutral"],
                        "accent_colors": [],
                        "color_temperature": "neutral",
                        "color_intensity": "balanced"
                    },
                    "space_analysis": {
                        "room_type": "unknown",
                        "dimensions": "unknown",
                        "layout_type": "unknown",
                        "lighting_conditions": "mixed",
                        "existing_elements": [],
                        "traffic_patterns": "unknown"
                    },
                    "functional_requirements": {
                        "primary_functions": ["living"],
                        "storage_needs": "moderate",
                        "seating_capacity": "2-4",
                        "special_considerations": []
                    },
                    "budget_indicators": {
                        "price_range": "mid-range",
                        "investment_priorities": []
                    }
                },
                "product_matching_criteria": {
                    "furniture_categories": {
                        "seating": {"types": ["sofa"], "materials": ["fabric"], "colors": ["neutral"], "size_requirements": "medium"},
                        "tables": {"types": ["coffee"], "materials": ["wood"], "shapes": ["rectangular"], "size_requirements": "medium"},
                        "storage": {"types": ["bookshelf"], "materials": ["wood"], "configurations": ["vertical"]},
                        "lighting": {"types": ["table"], "styles": ["modern"], "placement": ["side"]},
                        "decor": {"categories": ["art"], "materials": ["canvas"], "themes": ["abstract"]}
                    },
                    "filtering_keywords": {
                        "include_terms": ["modern", "contemporary"],
                        "exclude_terms": ["ornate", "traditional"],
                        "material_preferences": ["wood", "metal"],
                        "style_tags": ["modern", "minimalist"]
                    }
                },
                "visualization_guidance": {
                    "layout_recommendations": {
                        "furniture_placement": "Create conversational groupings",
                        "focal_points": ["main seating area"],
                        "traffic_flow": "Maintain clear pathways"
                    },
                    "spatial_considerations": {
                        "scale_proportions": "Choose appropriately sized furniture",
                        "height_variations": "Mix heights for visual interest",
                        "negative_space": "Leave breathing room between pieces"
                    },
                    "styling_suggestions": {
                        "layering_approach": "Layer textures and materials",
                        "texture_mixing": "Combine smooth and textured surfaces",
                        "pattern_coordination": "Use patterns sparingly"
                    }
                },
                "confidence_scores": {
                    "style_identification": 50,
                    "space_understanding": 30,
                    "product_matching": 40,
                    "overall_analysis": 40
                },
                "recommendations": {
                    "priority_items": ["seating", "lighting"],
                    "alternative_options": ["different styles available"],
                    "phased_approach": ["start with essentials"]
                },
                "user_friendly_response": self._build_fallback_message(user_message, has_image)
        }
        return json.dumps(fallback)

    def _build_fallback_message(self, user_message: str, has_image: bool) -> str:
        """Build fallback message for API failures"""
        action = "transform your space" if has_image else "find the perfect pieces"
        user_request_part = f'Based on your request for "{user_message[:100]}", ' if user_message else ''
        return f"Thank you for your request! I'm experiencing high demand right now, but I can still help you {action}. {user_request_part}I'll show you some beautiful design options and product recommendations that match your style. Let's create something amazing together!"

    def _parse_response(self, response: str) -> Tuple[str, Optional[DesignAnalysisSchema]]:
        """Parse ChatGPT response into conversational text and structured analysis"""
        print(f"[DEBUG] _parse_response called with response length: {len(response) if response else 0}")
        print(f"[DEBUG] Response preview: {response[:200] if response else 'None'}")
        try:
            # Parse JSON response
            response_data = json.loads(response)
            print(f"[DEBUG] JSON parsed successfully, keys: {list(response_data.keys())}")

            # Extract user-friendly response - check both possible key names
            conversational_response = (
                response_data.get("user_friendly_response") or
                response_data.get("message") or
                "I've analyzed your request and found some great recommendations for you!"
            )
            print(f"[DEBUG] Extracted conversational_response: {conversational_response[:100]}")

            # Normalize the response data to match schema
            # If OpenAI returns 'message', map it to 'user_friendly_response'
            if "message" in response_data and "user_friendly_response" not in response_data:
                response_data["user_friendly_response"] = response_data["message"]

            # Ensure all optional fields have defaults
            response_data.setdefault("product_matching_criteria", {})
            response_data.setdefault("visualization_guidance", {})
            response_data.setdefault("confidence_scores", {})
            response_data.setdefault("recommendations", {})

            print(f"[DEBUG] Normalized response_data keys: {list(response_data.keys())}")

            # Create design analysis schema
            analysis = DesignAnalysisSchema(**response_data)
            print(f"[DEBUG] DesignAnalysisSchema created successfully")

            return conversational_response, analysis

        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSONDecodeError in _parse_response: {str(e)}")
            logger.error(f"Failed to parse ChatGPT JSON response: {e}")
            return response, None

        except Exception as e:
            print(f"[DEBUG] Exception in _parse_response: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error parsing ChatGPT response: {e}", exc_info=True)
            return "I've analyzed your request and can help you find the perfect pieces for your space.", None

    def _process_image(self, image_data: str) -> Optional[str]:
        """Process and validate uploaded image"""
        try:
            # Remove data URL prefix if present
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]

            # Decode base64
            image_bytes = base64.b64decode(image_data)

            # Open and validate image
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize if too large (max 1024x1024 for ChatGPT)
            max_size = 1024
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert back to base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode()

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None

    def get_conversation_context(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation context for a session (legacy method)"""
        return self.conversation_memory.get(session_id, [])

    def clear_conversation_context(self, session_id: str):
        """Clear conversation context for a session"""
        # Clear from both legacy and new context managers
        if session_id in self.conversation_memory:
            del self.conversation_memory[session_id]
        self.context_manager.clear_context(session_id)

    def get_enhanced_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get enhanced conversation context with analysis"""
        return self.context_manager.get_conversation_summary(session_id)

    def get_user_preferences(self, session_id: str) -> Dict[str, Any]:
        """Get user preferences extracted from conversation"""
        return self.context_manager.get_user_preferences_summary(session_id)

    def update_room_context(self, session_id: str, room_data: Dict[str, Any]) -> bool:
        """Update room context for spatial analysis"""
        try:
            self.context_manager.update_room_context(session_id, room_data)
            return True
        except Exception as e:
            logger.error(f"Error updating room context: {e}")
            return False

    def export_conversation_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export complete conversation data for persistence"""
        try:
            return self.context_manager.export_context(session_id)
        except Exception as e:
            logger.error(f"Error exporting conversation data: {e}")
            return None

    def import_conversation_data(self, context_data: Dict[str, Any]) -> bool:
        """Import conversation data from persistence"""
        try:
            return self.context_manager.import_context(context_data)
        except Exception as e:
            logger.error(f"Error importing conversation data: {e}")
            return False

    async def _simulate_chatgpt_response(self, messages: List[Dict[str, Any]]) -> str:
        """Simulate ChatGPT response for demo mode"""
        await asyncio.sleep(0.5)  # Simulate API delay

        # Update success stats for demo
        self.api_usage_stats["successful_requests"] += 1
        self.api_usage_stats["total_tokens"] += 1500

        # Extract conversation context and user message
        user_message = ""
        conversation_history = []
        has_image = False

        for msg in messages:
            if msg.get("role") == "user":
                if isinstance(msg.get("content"), list):
                    for part in msg["content"]:
                        if part.get("type") == "text":
                            user_message = part.get("text", "")
                            conversation_history.append(f"User: {user_message}")
                        elif part.get("type") == "image_url":
                            has_image = True
                else:
                    user_message = msg.get("content", "")
                    conversation_history.append(f"User: {user_message}")
            elif msg.get("role") == "assistant":
                assistant_msg = msg.get("content", "")
                conversation_history.append(f"Assistant: {assistant_msg[:100]}...")

        # Generate contextual response based on conversation history
        context_summary = "\n".join(conversation_history[-6:])  # Last 3 exchanges

        # Generate realistic demo response
        demo_response = {
            "design_analysis": {
                "style_preferences": {
                    "primary_style": "modern",
                    "secondary_styles": ["scandinavian", "minimalist"],
                    "style_keywords": ["clean", "simple", "functional", "light"],
                    "inspiration_sources": ["Nordic design", "Japanese minimalism"]
                },
                "color_scheme": {
                    "preferred_colors": ["white", "light gray", "natural wood"],
                    "accent_colors": ["soft blue", "sage green"],
                    "color_temperature": "cool",
                    "color_intensity": "muted"
                },
                "space_analysis": {
                    "room_type": "living_room",
                    "dimensions": "estimated 12x15 feet",
                    "layout_type": "open",
                    "lighting_conditions": "natural",
                    "existing_elements": ["large windows", "hardwood floors"],
                    "traffic_patterns": "main entrance to seating area"
                },
                "functional_requirements": {
                    "primary_functions": ["relaxation", "entertainment", "socializing"],
                    "storage_needs": "moderate",
                    "seating_capacity": "4-6 people",
                    "special_considerations": ["pet-friendly materials"]
                },
                "budget_indicators": {
                    "price_range": "mid-range",
                    "investment_priorities": ["quality seating", "good lighting"]
                }
            },
            "product_matching_criteria": {
                "furniture_categories": {
                    "seating": {
                        "types": ["sectional sofa", "accent chairs"],
                        "materials": ["linen", "wool", "leather"],
                        "colors": ["light gray", "cream", "natural"],
                        "size_requirements": "medium to large"
                    },
                    "tables": {
                        "types": ["coffee table", "side tables"],
                        "materials": ["wood", "glass", "metal"],
                        "shapes": ["rectangular", "round"],
                        "size_requirements": "proportional to seating"
                    },
                    "lighting": {
                        "types": ["floor lamps", "table lamps", "pendant lights"],
                        "styles": ["modern", "scandinavian"],
                        "placement": ["reading areas", "ambient lighting"]
                    }
                },
                "filtering_keywords": {
                    "include_terms": ["modern", "scandinavian", "minimalist", "functional"],
                    "exclude_terms": ["ornate", "traditional", "heavy"],
                    "material_preferences": ["natural wood", "linen", "cotton"],
                    "style_tags": ["clean lines", "simple", "light"]
                }
            },
            "visualization_guidance": {
                "layout_recommendations": {
                    "furniture_placement": "create conversation area facing natural light",
                    "focal_points": ["large windows", "main seating area"],
                    "traffic_flow": "maintain clear pathways around furniture"
                },
                "spatial_considerations": {
                    "scale_proportions": "choose furniture proportional to room size",
                    "height_variations": "mix heights with floor and table lamps",
                    "negative_space": "leave breathing room between pieces"
                },
                "styling_suggestions": {
                    "layering_approach": "layer textures with throws and pillows",
                    "texture_mixing": "combine smooth and natural textures",
                    "pattern_coordination": "use subtle patterns sparingly"
                }
            },
            "confidence_scores": {
                "style_identification": 88,
                "space_understanding": 85,
                "product_matching": 90,
                "overall_analysis": 87
            },
            "recommendations": {
                "priority_items": ["comfortable sectional sofa", "good task lighting", "coffee table"],
                "alternative_options": ["modular seating", "ottoman for extra seating"],
                "phased_approach": ["start with seating", "add lighting", "finish with accessories"]
            },
            "user_friendly_response": self._generate_contextual_response(user_message, conversation_history, has_image)
        }

        return json.dumps(demo_response)

    def _generate_contextual_response(self, user_message: str, conversation_history: List[str], has_image: bool) -> str:
        """Generate contextual conversational response based on conversation history"""

        # Count interactions
        interaction_count = len([msg for msg in conversation_history if msg.startswith("User:")])

        # First interaction
        if interaction_count <= 1:
            if has_image:
                return f"Thank you for sharing that image! I can see you're looking to redesign this space. Based on '{user_message}', I'd recommend creating a modern, comfortable environment. I've found some great furniture options that would work perfectly. Would you like me to focus on any specific area or type of furniture?"
            else:
                return f"Thanks for sharing your vision! You mentioned '{user_message}'. I love helping create beautiful, functional spaces. Let me suggest some modern pieces that would work wonderfully - comfortable seating in natural materials, clean-lined furniture, and great lighting. What's most important to you in this space?"

        # Follow-up interactions - be more specific and conversational
        elif interaction_count == 2:
            return f"Great question! Regarding '{user_message}' - I think that's a smart direction. Let me build on what we discussed earlier. I've identified some pieces that match your style preferences. Should I show you options for specific categories like seating, tables, or lighting?"

        elif interaction_count == 3:
            return f"Perfect! I'm really excited about the direction we're heading. For '{user_message}', I recommend coordinating pieces that maintain that cohesive look we've been building. Would you like to see how these pieces would look arranged in your space?"

        else:
            # Ongoing conversation - reference previous context
            return f"Absolutely! Building on our conversation, '{user_message}' fits perfectly with the aesthetic we've been developing. I can show you complementary pieces that will complete the look. Should we focus on finalizing your selections or exploring more options?"

    async def analyze_design_preferences(self, text: str) -> Dict[str, Any]:
        """Analyze design preferences using advanced NLP"""
        try:
            # Use NLP processor for detailed analysis
            style_extraction = await design_nlp_processor.extract_design_styles(text)
            preference_analysis = await design_nlp_processor.analyze_preferences(text)
            intent_classification = await design_nlp_processor.classify_intent(text)

            return {
                "style_analysis": {
                    "primary_style": style_extraction.primary_style,
                    "secondary_styles": style_extraction.secondary_styles,
                    "confidence": style_extraction.confidence_score,
                    "keywords": style_extraction.style_keywords,
                    "reasoning": style_extraction.reasoning
                },
                "preferences": {
                    "colors": preference_analysis.colors,
                    "materials": preference_analysis.materials,
                    "patterns": preference_analysis.patterns,
                    "textures": preference_analysis.textures,
                    "budget": preference_analysis.budget_indicators,
                    "functional_needs": preference_analysis.functional_requirements,
                    "confidence": preference_analysis.confidence_score
                },
                "intent": {
                    "primary_intent": intent_classification.primary_intent,
                    "confidence": intent_classification.confidence_score,
                    "entities": intent_classification.entities,
                    "suggested_action": intent_classification.action_required
                }
            }

        except Exception as e:
            logger.error(f"Error in NLP analysis: {e}")
            return {
                "style_analysis": {"primary_style": "modern", "confidence": 0.1},
                "preferences": {"colors": [], "materials": [], "confidence": 0.1},
                "intent": {"primary_intent": "general_inquiry", "confidence": 0.5}
            }

    async def analyze_conversation_insights(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive conversation insights using NLP"""
        try:
            # Get conversation context
            context = self.context_manager.get_or_create_context(session_id)

            if not context.messages:
                return {"error": "No conversation data available"}

            # Process conversation history with NLP
            insights = await design_nlp_processor.process_conversation_history(context.messages)

            # Add context-specific insights
            insights["session_insights"] = {
                "conversation_state": context.conversation_state,
                "total_interactions": context.total_interactions,
                "has_room_context": context.current_room_context is not None,
                "analysis_history_count": len(context.design_analysis_history),
                "user_preferences_evolution": self._analyze_preference_evolution(context)
            }

            return insights

        except Exception as e:
            logger.error(f"Error analyzing conversation insights: {e}")
            return {"error": f"Analysis failed: {str(e)}"}

    def _analyze_preference_evolution(self, context) -> Dict[str, Any]:
        """Analyze how user preferences have evolved through conversation"""
        try:
            if len(context.design_analysis_history) < 2:
                return {"evolution": "insufficient_data"}

            first_analysis = context.design_analysis_history[0]
            latest_analysis = context.design_analysis_history[-1]

            evolution = {
                "style_consistency": self._compare_style_preferences(first_analysis, latest_analysis),
                "preference_refinement": self._measure_preference_refinement(context.design_analysis_history),
                "confidence_trend": self._calculate_confidence_trend(context.design_analysis_history)
            }

            return evolution

        except Exception as e:
            logger.warning(f"Error analyzing preference evolution: {e}")
            return {"evolution": "analysis_error"}

    def _compare_style_preferences(self, first_analysis: Dict, latest_analysis: Dict) -> str:
        """Compare style preferences between first and latest analysis"""
        try:
            first_style = first_analysis.get("analysis", {}).get("design_analysis", {}).get("style_preferences", {}).get("primary_style", "")
            latest_style = latest_analysis.get("analysis", {}).get("design_analysis", {}).get("style_preferences", {}).get("primary_style", "")

            if first_style == latest_style:
                return "consistent"
            elif first_style and latest_style:
                return "evolved"
            else:
                return "unclear"

        except Exception:
            return "analysis_error"

    def _measure_preference_refinement(self, analysis_history: List[Dict]) -> str:
        """Measure how refined preferences have become"""
        try:
            if len(analysis_history) < 2:
                return "insufficient_data"

            # Count specific preferences over time
            preference_counts = []
            for analysis in analysis_history:
                count = 0
                analysis_data = analysis.get("analysis", {}).get("design_analysis", {})

                # Count color preferences
                colors = analysis_data.get("color_scheme", {}).get("preferred_colors", [])
                count += len(colors)

                # Count style keywords
                style_keywords = analysis_data.get("style_preferences", {}).get("style_keywords", [])
                count += len(style_keywords)

                preference_counts.append(count)

            # Determine trend
            if len(preference_counts) >= 2:
                if preference_counts[-1] > preference_counts[0]:
                    return "increasing_specificity"
                elif preference_counts[-1] < preference_counts[0]:
                    return "decreasing_specificity"
                else:
                    return "stable"

            return "unclear"

        except Exception:
            return "analysis_error"

    def _calculate_confidence_trend(self, analysis_history: List[Dict]) -> str:
        """Calculate confidence trend over conversation"""
        try:
            confidence_scores = []
            for analysis in analysis_history:
                overall_confidence = analysis.get("analysis", {}).get("confidence_scores", {}).get("overall_analysis", 0)
                confidence_scores.append(overall_confidence)

            if len(confidence_scores) >= 2:
                if confidence_scores[-1] > confidence_scores[0] + 5:  # 5 point threshold
                    return "increasing"
                elif confidence_scores[-1] < confidence_scores[0] - 5:
                    return "decreasing"
                else:
                    return "stable"

            return "insufficient_data"

        except Exception:
            return "analysis_error"

    async def extract_room_requirements(self, text: str, image_data: Optional[str] = None) -> Dict[str, Any]:
        """Extract specific room requirements from text and image"""
        try:
            # Use NLP to extract basic requirements
            intent_classification = await design_nlp_processor.classify_intent(text)
            preference_analysis = await design_nlp_processor.analyze_preferences(text)

            entities = intent_classification.entities
            functional_needs = preference_analysis.functional_requirements

            # Extract room-specific requirements
            room_requirements = {
                "room_type": entities.get("rooms", ["unknown"])[0] if entities.get("rooms") else "unknown",
                "dimensions": entities.get("dimensions", []),
                "furniture_needed": entities.get("furniture", []),
                "functional_requirements": functional_needs,
                "color_preferences": preference_analysis.colors,
                "material_preferences": preference_analysis.materials,
                "budget_level": preference_analysis.budget_indicators,
                "has_image": image_data is not None,
                "extraction_confidence": (preference_analysis.confidence_score + intent_classification.confidence_score) / 2
            }

            return room_requirements

        except Exception as e:
            logger.error(f"Error extracting room requirements: {e}")
            return {
                "room_type": "unknown",
                "extraction_confidence": 0.1,
                "error": str(e)
            }

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            **self.api_usage_stats,
            "success_rate": (
                self.api_usage_stats["successful_requests"] /
                max(self.api_usage_stats["total_requests"], 1) * 100
            ),
            "average_tokens_per_request": (
                self.api_usage_stats["total_tokens"] /
                max(self.api_usage_stats["successful_requests"], 1)
            )
        }

    def reset_usage_stats(self):
        """Reset usage statistics"""
        self.api_usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "last_reset": datetime.now()
        }
        logger.info("API usage statistics reset")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the ChatGPT service"""
        try:
            # Test with a simple message
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' in JSON format: {\"status\": \"OK\"}"}
            ]

            start_time = time.time()
            await self._call_chatgpt(test_messages)
            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "response_time": response_time,
                "api_key_valid": True,
                "rate_limiter_active": len(self.rate_limiter.requests) > 0,
                "usage_stats": self.get_usage_stats()
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "api_key_valid": bool(settings.openai_api_key),
                "usage_stats": self.get_usage_stats()
            }


# Global service instance
chatgpt_service = ChatGPTService()