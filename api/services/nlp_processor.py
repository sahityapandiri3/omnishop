"""
Natural Language Processing service for design style extraction and preference analysis
"""
import re
import logging
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
import json
from collections import Counter, defaultdict
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class StyleExtraction:
    """Results from style extraction"""
    primary_style: str
    secondary_styles: List[str]
    confidence_score: float
    style_keywords: List[str]
    reasoning: str


@dataclass
class PreferenceAnalysis:
    """Results from preference analysis"""
    colors: List[str]
    materials: List[str]
    patterns: List[str]
    textures: List[str]
    budget_indicators: str
    functional_requirements: List[str]
    confidence_score: float


@dataclass
class IntentClassification:
    """Results from intent classification"""
    primary_intent: str
    confidence_score: float
    entities: Dict[str, List[str]]
    action_required: str


class DesignNLPProcessor:
    """Advanced NLP processor for interior design conversations"""

    def __init__(self):
        self.style_keywords = self._load_style_keywords()
        self.color_keywords = self._load_color_keywords()
        self.material_keywords = self._load_material_keywords()
        self.intent_patterns = self._load_intent_patterns()
        self.budget_indicators = self._load_budget_indicators()

        logger.info("Design NLP Processor initialized")

    def _load_style_keywords(self) -> Dict[str, List[str]]:
        """Load design style keywords and synonyms"""
        return {
            "modern": [
                "modern", "contemporary", "sleek", "minimalist", "clean lines",
                "simple", "uncluttered", "streamlined", "geometric", "monochromatic"
            ],
            "traditional": [
                "traditional", "classic", "timeless", "elegant", "formal",
                "ornate", "detailed", "refined", "sophisticated", "conventional"
            ],
            "rustic": [
                "rustic", "farmhouse", "country", "barn", "reclaimed", "weathered",
                "natural", "raw", "distressed", "vintage", "aged"
            ],
            "industrial": [
                "industrial", "urban", "loft", "exposed", "raw", "concrete",
                "steel", "iron", "warehouse", "factory", "utilitarian"
            ],
            "scandinavian": [
                "scandinavian", "nordic", "hygge", "cozy", "light", "airy",
                "functional", "minimal", "natural light", "white", "blonde wood"
            ],
            "bohemian": [
                "bohemian", "boho", "eclectic", "artistic", "layered", "textured",
                "colorful", "mixed patterns", "global", "artistic", "free-spirited"
            ],
            "mid-century": [
                "mid-century", "retro", "vintage", "atomic", "geometric",
                "teak", "walnut", "clean lines", "functional", "iconic"
            ],
            "mediterranean": [
                "mediterranean", "coastal", "tuscan", "warm", "earthy",
                "terracotta", "stucco", "arched", "wrought iron", "tile"
            ],
            "art_deco": [
                "art deco", "glamorous", "luxury", "geometric patterns", "metallic",
                "bold", "dramatic", "ornamental", "symmetrical", "lavish"
            ],
            "transitional": [
                "transitional", "blend", "balanced", "neutral", "comfortable",
                "accessible", "timeless", "versatile", "relaxed", "updated"
            ]
        }

    def _load_color_keywords(self) -> Dict[str, List[str]]:
        """Load color keywords and descriptions"""
        return {
            "neutral": [
                "white", "off-white", "cream", "beige", "tan", "taupe", "gray",
                "grey", "charcoal", "black", "ivory", "bone", "linen", "sand"
            ],
            "warm": [
                "red", "orange", "yellow", "coral", "peach", "salmon", "gold",
                "amber", "burnt orange", "terracotta", "rust", "burgundy"
            ],
            "cool": [
                "blue", "green", "purple", "violet", "teal", "turquoise", "mint",
                "sage", "navy", "royal blue", "emerald", "forest green"
            ],
            "earth_tones": [
                "brown", "tan", "olive", "moss", "clay", "sienna", "umber",
                "chocolate", "coffee", "camel", "khaki", "bronze"
            ],
            "jewel_tones": [
                "emerald", "sapphire", "ruby", "amethyst", "topaz", "garnet",
                "jade", "opal", "turquoise", "citrine"
            ],
            "pastels": [
                "pastel", "soft", "light", "pale", "blush", "lavender", "mint",
                "powder blue", "rose", "champagne", "pearl"
            ]
        }

    def _load_material_keywords(self) -> Dict[str, List[str]]:
        """Load material keywords"""
        return {
            "wood": [
                "wood", "wooden", "timber", "oak", "maple", "walnut", "cherry",
                "pine", "mahogany", "teak", "bamboo", "reclaimed wood", "hardwood"
            ],
            "metal": [
                "metal", "steel", "iron", "brass", "copper", "bronze", "aluminum",
                "chrome", "nickel", "gold", "silver", "wrought iron", "stainless steel"
            ],
            "fabric": [
                "fabric", "textile", "cotton", "linen", "silk", "wool", "velvet",
                "leather", "suede", "canvas", "burlap", "cashmere", "tweed"
            ],
            "stone": [
                "stone", "marble", "granite", "limestone", "travertine", "slate",
                "quartz", "concrete", "brick", "ceramic", "porcelain", "tile"
            ],
            "glass": [
                "glass", "crystal", "acrylic", "lucite", "transparent", "translucent",
                "frosted", "tempered", "mirrored", "stained glass"
            ],
            "natural": [
                "natural", "organic", "rattan", "wicker", "jute", "sisal", "hemp",
                "cork", "bamboo", "seagrass", "rush", "cane"
            ]
        }

    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """Load intent classification patterns"""
        return {
            "browse_products": [
                "show me", "find", "looking for", "need", "want", "browse",
                "search", "recommend", "suggest", "options", "choices"
            ],
            "design_consultation": [
                "help with", "advice", "how to", "design", "decorate", "style",
                "layout", "arrange", "ideas", "inspiration", "guidance"
            ],
            "room_analysis": [
                "analyze", "room", "space", "layout", "what do you think",
                "feedback", "assessment", "evaluate", "opinion"
            ],
            "visualization": [
                "visualize", "see how", "would look", "place", "arrange",
                "preview", "render", "show placement", "try out"
            ],
            "budget_planning": [
                "budget", "cost", "price", "afford", "expensive", "cheap",
                "investment", "spend", "money", "financing"
            ],
            "style_guidance": [
                "style", "aesthetic", "theme", "look", "vibe", "mood",
                "feeling", "atmosphere", "character", "personality"
            ]
        }

    def _load_budget_indicators(self) -> Dict[str, List[str]]:
        """Load budget indicator keywords"""
        return {
            "budget": [
                "budget", "affordable", "cheap", "inexpensive", "economical",
                "cost-effective", "value", "deal", "bargain", "low-cost"
            ],
            "mid_range": [
                "mid-range", "moderate", "reasonable", "fair price", "average",
                "standard", "typical", "normal", "middle", "balanced"
            ],
            "luxury": [
                "luxury", "high-end", "premium", "expensive", "designer",
                "exclusive", "upscale", "sophisticated", "investment", "splurge"
            ]
        }

    async def extract_design_styles(self, text: str) -> StyleExtraction:
        """Extract design styles from text"""
        text_lower = text.lower()
        style_scores = {}
        found_keywords = []

        # Score each style based on keyword matches
        for style, keywords in self.style_keywords.items():
            score = 0
            style_keywords_found = []

            for keyword in keywords:
                if keyword in text_lower:
                    # Weight longer phrases higher
                    weight = len(keyword.split()) * 2
                    score += weight
                    style_keywords_found.append(keyword)

            if score > 0:
                style_scores[style] = score
                found_keywords.extend(style_keywords_found)

        if not style_scores:
            return StyleExtraction(
                primary_style="modern",  # Default fallback
                secondary_styles=[],
                confidence_score=0.1,
                style_keywords=[],
                reasoning="No specific style keywords found, defaulting to modern"
            )

        # Sort styles by score
        sorted_styles = sorted(style_scores.items(), key=lambda x: x[1], reverse=True)

        primary_style = sorted_styles[0][0]
        secondary_styles = [style for style, _ in sorted_styles[1:3]]  # Top 2 secondary

        # Calculate confidence score
        total_score = sum(style_scores.values())
        confidence_score = min(sorted_styles[0][1] / max(total_score, 1), 1.0)

        reasoning = f"Identified '{primary_style}' as primary style based on keywords: {', '.join(found_keywords[:5])}"

        return StyleExtraction(
            primary_style=primary_style,
            secondary_styles=secondary_styles,
            confidence_score=confidence_score,
            style_keywords=list(set(found_keywords)),
            reasoning=reasoning
        )

    async def analyze_preferences(self, text: str) -> PreferenceAnalysis:
        """Analyze user preferences from text"""
        text_lower = text.lower()

        # Extract colors
        colors = []
        for color_category, color_words in self.color_keywords.items():
            for color in color_words:
                if color in text_lower:
                    colors.append(color)

        # Extract materials
        materials = []
        for material_category, material_words in self.material_keywords.items():
            for material in material_words:
                if material in text_lower:
                    materials.append(material)

        # Extract patterns and textures
        patterns = self._extract_patterns(text_lower)
        textures = self._extract_textures(text_lower)

        # Analyze budget indicators
        budget = self._analyze_budget(text_lower)

        # Extract functional requirements
        functional_requirements = self._extract_functional_requirements(text_lower)

        # Calculate confidence score
        total_found = len(colors) + len(materials) + len(patterns) + len(textures)
        confidence_score = min(total_found * 0.1, 1.0)

        return PreferenceAnalysis(
            colors=list(set(colors)),
            materials=list(set(materials)),
            patterns=patterns,
            textures=textures,
            budget_indicators=budget,
            functional_requirements=functional_requirements,
            confidence_score=confidence_score
        )

    async def classify_intent(self, text: str) -> IntentClassification:
        """Classify user intent from text"""
        text_lower = text.lower()
        intent_scores = {}

        # Score each intent based on pattern matches
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    score += 1

            if score > 0:
                intent_scores[intent] = score

        if not intent_scores:
            primary_intent = "general_inquiry"
            confidence_score = 0.5
        else:
            primary_intent = max(intent_scores.keys(), key=lambda x: intent_scores[x])
            max_score = intent_scores[primary_intent]
            total_score = sum(intent_scores.values())
            confidence_score = max_score / max(total_score, 1)

        # Extract entities
        entities = self._extract_entities(text_lower)

        # Determine action required
        action_required = self._determine_action(primary_intent, entities)

        return IntentClassification(
            primary_intent=primary_intent,
            confidence_score=confidence_score,
            entities=entities,
            action_required=action_required
        )

    def _extract_patterns(self, text: str) -> List[str]:
        """Extract pattern keywords from text"""
        pattern_keywords = [
            "stripes", "striped", "dots", "polka dot", "geometric", "floral",
            "paisley", "checkered", "plaid", "solid", "abstract", "chevron",
            "herringbone", "damask", "toile", "ikat", "tribal", "moroccan"
        ]

        found_patterns = []
        for pattern in pattern_keywords:
            if pattern in text:
                found_patterns.append(pattern)

        return found_patterns

    def _extract_textures(self, text: str) -> List[str]:
        """Extract texture keywords from text"""
        texture_keywords = [
            "smooth", "rough", "soft", "hard", "glossy", "matte", "textured",
            "bumpy", "ribbed", "woven", "knitted", "brushed", "polished",
            "distressed", "weathered", "sleek", "coarse", "fine", "grainy"
        ]

        found_textures = []
        for texture in texture_keywords:
            if texture in text:
                found_textures.append(texture)

        return found_textures

    def _analyze_budget(self, text: str) -> str:
        """Analyze budget indicators from text"""
        budget_scores = {}

        for budget_level, indicators in self.budget_indicators.items():
            score = 0
            for indicator in indicators:
                if indicator in text:
                    score += 1

            if score > 0:
                budget_scores[budget_level] = score

        if not budget_scores:
            return "unknown"

        return max(budget_scores.keys(), key=lambda x: budget_scores[x])

    def _extract_functional_requirements(self, text: str) -> List[str]:
        """Extract functional requirements from text"""
        functional_keywords = {
            "storage": ["storage", "organize", "closet", "shelving", "cabinets"],
            "seating": ["seating", "sit", "chair", "sofa", "bench", "stool"],
            "workspace": ["work", "office", "desk", "study", "computer"],
            "entertainment": ["tv", "entertainment", "media", "gaming", "music"],
            "dining": ["dining", "eat", "kitchen", "table", "meals"],
            "sleeping": ["sleep", "bed", "bedroom", "rest", "nap"],
            "lighting": ["light", "bright", "dark", "lamp", "illumination"],
            "privacy": ["private", "quiet", "separate", "intimate", "secluded"]
        }

        requirements = []
        for requirement, keywords in functional_keywords.items():
            if any(keyword in text for keyword in keywords):
                requirements.append(requirement)

        return requirements

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text"""
        entities = {
            "rooms": [],
            "furniture": [],
            "colors": [],
            "materials": [],
            "brands": [],
            "dimensions": []
        }

        # Room types
        room_patterns = [
            "living room", "bedroom", "kitchen", "bathroom", "dining room",
            "office", "study", "basement", "attic", "garage", "patio",
            "balcony", "terrace", "foyer", "hallway", "closet"
        ]

        for room in room_patterns:
            if room in text:
                entities["rooms"].append(room)

        # Furniture types
        furniture_patterns = [
            "sofa", "chair", "table", "bed", "dresser", "bookshelf",
            "cabinet", "desk", "lamp", "mirror", "rug", "curtains"
        ]

        for furniture in furniture_patterns:
            if furniture in text:
                entities["furniture"].append(furniture)

        # Extract dimensions
        dimension_pattern = r'\b\d+\s*(ft|feet|foot|in|inch|inches|cm|meter|meters|m)\b'
        dimensions = re.findall(dimension_pattern, text, re.IGNORECASE)
        entities["dimensions"] = [f"{match[0]} {match[1]}" for match in dimensions]

        return entities

    def _determine_action(self, intent: str, entities: Dict[str, List[str]]) -> str:
        """Determine required action based on intent and entities"""
        action_map = {
            "browse_products": "show_product_recommendations",
            "design_consultation": "provide_design_advice",
            "room_analysis": "analyze_space_layout",
            "visualization": "create_room_visualization",
            "budget_planning": "suggest_budget_options",
            "style_guidance": "explain_style_principles"
        }

        base_action = action_map.get(intent, "general_assistance")

        # Modify action based on entities
        if entities.get("rooms"):
            base_action += f"_for_{entities['rooms'][0].replace(' ', '_')}"

        return base_action

    async def process_conversation_history(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Process entire conversation history for insights"""
        all_text = " ".join([msg.get("content", "") for msg in messages if msg.get("role") == "user"])

        # Run all analyses in parallel
        style_extraction, preference_analysis, intent_classification = await asyncio.gather(
            self.extract_design_styles(all_text),
            self.analyze_preferences(all_text),
            self.classify_intent(all_text)
        )

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
            },
            "conversation_metrics": {
                "total_messages": len(messages),
                "user_messages": len([m for m in messages if m.get("role") == "user"]),
                "text_length": len(all_text),
                "engagement_level": "high" if len(messages) > 10 else "medium" if len(messages) > 5 else "low"
            }
        }


# Global NLP processor instance
design_nlp_processor = DesignNLPProcessor()