"""
ChatGPT service for interior design analysis using the prompt.md specification
"""
import openai
import json
import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import base64
from PIL import Image
import io

from api.core.config import settings
from api.schemas.chat import DesignAnalysisSchema, ChatMessageSchema, MessageType

logger = logging.getLogger(__name__)


class ChatGPTService:
    """Service for interacting with ChatGPT for interior design analysis"""

    def __init__(self):
        """Initialize the ChatGPT service"""
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.system_prompt = self._load_system_prompt()
        self.conversation_memory = {}  # Store conversation context by session_id

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

CRITICAL: You must respond with a valid JSON object following this exact structure:

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
        image_data: Optional[str] = None
    ) -> Tuple[str, Optional[DesignAnalysisSchema]]:
        """
        Analyze user input and return both a conversational response and structured analysis

        Args:
            user_message: The user's message
            session_id: Session ID for conversation context
            image_data: Base64 encoded image data (optional)

        Returns:
            Tuple of (conversational_response, design_analysis)
        """
        try:
            # Prepare messages for ChatGPT
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Add conversation history if available
            if session_id and session_id in self.conversation_memory:
                messages.extend(self.conversation_memory[session_id][-6:])  # Last 6 messages for context

            # Prepare user message content
            user_content = [{"type": "text", "text": user_message}]

            # Add image if provided
            if image_data:
                # Validate and process image
                processed_image = self._process_image(image_data)
                if processed_image:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{processed_image}",
                            "detail": "high"
                        }
                    })

            messages.append({"role": "user", "content": user_content})

            # Call ChatGPT
            response = await self._call_chatgpt(messages)

            # Parse response
            conversational_response, analysis = self._parse_response(response)

            # Store conversation context
            if session_id:
                if session_id not in self.conversation_memory:
                    self.conversation_memory[session_id] = []

                self.conversation_memory[session_id].extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": conversational_response}
                ])

                # Keep only last 10 messages
                if len(self.conversation_memory[session_id]) > 10:
                    self.conversation_memory[session_id] = self.conversation_memory[session_id][-10:]

            return conversational_response, analysis

        except Exception as e:
            logger.error(f"Error in ChatGPT analysis: {e}")
            fallback_response = "I apologize, but I'm having trouble analyzing your request right now. Could you please try rephrasing your interior design needs?"
            return fallback_response, None

    async def _call_chatgpt(self, messages: List[Dict[str, Any]]) -> str:
        """Call ChatGPT API with the prepared messages"""
        try:
            response = await self.client.chat.completions.acreate(
                model=settings.openai_model,
                messages=messages,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
                response_format={"type": "json_object"}
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"ChatGPT API call failed: {e}")
            # Return a structured fallback response
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
                "user_friendly_response": "I encountered some technical difficulties analyzing your request, but I can still help you find great furniture and decor options. Please feel free to browse our product catalog or try describing your needs again."
            }
            return json.dumps(fallback)

    def _parse_response(self, response: str) -> Tuple[str, Optional[DesignAnalysisSchema]]:
        """Parse ChatGPT response into conversational text and structured analysis"""
        try:
            # Parse JSON response
            response_data = json.loads(response)

            # Extract user-friendly response
            conversational_response = response_data.get(
                "user_friendly_response",
                "I've analyzed your request and found some great recommendations for you!"
            )

            # Create design analysis schema
            analysis = DesignAnalysisSchema(**response_data)

            return conversational_response, analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ChatGPT JSON response: {e}")
            return response, None

        except Exception as e:
            logger.error(f"Error parsing ChatGPT response: {e}")
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
        """Get conversation context for a session"""
        return self.conversation_memory.get(session_id, [])

    def clear_conversation_context(self, session_id: str):
        """Clear conversation context for a session"""
        if session_id in self.conversation_memory:
            del self.conversation_memory[session_id]


# Global service instance
chatgpt_service = ChatGPTService()