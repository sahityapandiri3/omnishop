"""
Product style definitions for semantic search and style classification.

These styles are used by:
1. Gemini Vision API for classifying product styles
2. Embedding generation for semantic search
3. Style-based filtering in product recommendations
"""

# 11 predefined design styles for product classification
PREDEFINED_STYLES = [
    "indian_contemporary",   # Modern Indian, subtle craft, warm
    "modern",                # Clean, functional, neutral everyday modern
    "minimalist",            # Ultra clean, less ornamentation
    "japandi",               # Japanese-Scandinavian warm minimalism
    "scandinavian",          # Light woods, hygge, airy
    "mid_century_modern",    # 50s-60s, tapered legs, organic curves
    "modern_luxury",         # Premium finishes, hotel-like feel
    "contemporary",          # Trend-driven, mixed materials
    "boho",                  # Relaxed, textured, natural
    "eclectic",              # Intentional mix, personality-driven
    "industrial"             # Raw, metal, urban
]

# Style descriptions for AI classification prompts
STYLE_DESCRIPTIONS = {
    "indian_contemporary": "Modern Indian design with subtle craft elements, warm tones, traditional motifs reimagined",
    "modern": "Clean and functional design, neutral colors, everyday modern aesthetic without being stark",
    "minimalist": "Ultra clean design, minimal ornamentation, simple geometric forms, 'less is more' philosophy",
    "japandi": "Japanese-Scandinavian fusion with warm minimalism, natural materials, zen-like simplicity",
    "scandinavian": "Light woods, hygge comfort, airy and bright spaces, cozy textiles, functional beauty",
    "mid_century_modern": "1950s-60s inspired design with tapered legs, organic curves, bold accent colors",
    "modern_luxury": "Premium materials and finishes, hotel-like sophisticated feel, statement pieces",
    "contemporary": "Current trend-driven design, mixed materials, fresh and current aesthetic",
    "boho": "Relaxed bohemian style with layered textures, natural materials, eclectic patterns",
    "eclectic": "Intentional mix of different styles, personality-driven, curated collected look",
    "industrial": "Raw materials like metal and exposed wood, urban warehouse aesthetic, utilitarian beauty"
}

# Style similarity matrix for recommendations
# Values 0-1 indicate how similar/compatible two styles are
STYLE_SIMILARITY_MATRIX = {
    "indian_contemporary": {
        "modern": 0.7, "contemporary": 0.75, "eclectic": 0.6, "boho": 0.5,
        "modern_luxury": 0.6, "minimalist": 0.3, "japandi": 0.4
    },
    "modern": {
        "minimalist": 0.8, "contemporary": 0.85, "scandinavian": 0.7, "japandi": 0.65,
        "mid_century_modern": 0.6, "modern_luxury": 0.7, "industrial": 0.5
    },
    "minimalist": {
        "modern": 0.8, "japandi": 0.85, "scandinavian": 0.75, "contemporary": 0.6,
        "modern_luxury": 0.5, "industrial": 0.4
    },
    "japandi": {
        "minimalist": 0.85, "scandinavian": 0.9, "modern": 0.65, "contemporary": 0.5,
        "boho": 0.4
    },
    "scandinavian": {
        "japandi": 0.9, "minimalist": 0.75, "modern": 0.7, "contemporary": 0.6,
        "boho": 0.5, "mid_century_modern": 0.55
    },
    "mid_century_modern": {
        "modern": 0.6, "contemporary": 0.65, "scandinavian": 0.55, "eclectic": 0.5,
        "industrial": 0.4, "boho": 0.35
    },
    "modern_luxury": {
        "contemporary": 0.75, "modern": 0.7, "indian_contemporary": 0.6,
        "minimalist": 0.5, "art_deco": 0.6
    },
    "contemporary": {
        "modern": 0.85, "modern_luxury": 0.75, "indian_contemporary": 0.75,
        "mid_century_modern": 0.65, "scandinavian": 0.6, "eclectic": 0.6
    },
    "boho": {
        "eclectic": 0.8, "indian_contemporary": 0.5, "scandinavian": 0.5,
        "japandi": 0.4, "mid_century_modern": 0.35
    },
    "eclectic": {
        "boho": 0.8, "indian_contemporary": 0.6, "mid_century_modern": 0.5,
        "contemporary": 0.6, "industrial": 0.45
    },
    "industrial": {
        "modern": 0.5, "contemporary": 0.55, "minimalist": 0.4, "eclectic": 0.45,
        "mid_century_modern": 0.4
    }
}


def get_style_similarity(style1: str, style2: str) -> float:
    """
    Get similarity score between two styles.
    Returns 1.0 if same style, 0.0 if no known similarity.
    """
    if style1 == style2:
        return 1.0

    # Check forward lookup
    if style1 in STYLE_SIMILARITY_MATRIX:
        if style2 in STYLE_SIMILARITY_MATRIX[style1]:
            return STYLE_SIMILARITY_MATRIX[style1][style2]

    # Check reverse lookup (matrix is symmetric)
    if style2 in STYLE_SIMILARITY_MATRIX:
        if style1 in STYLE_SIMILARITY_MATRIX[style2]:
            return STYLE_SIMILARITY_MATRIX[style2][style1]

    # Default: low similarity for unknown combinations
    return 0.2


def is_valid_style(style: str) -> bool:
    """Check if a style is in the predefined list."""
    return style in PREDEFINED_STYLES


def normalize_style(style: str) -> str:
    """
    Normalize style name to match predefined styles.
    Handles common variations and aliases.
    """
    style_lower = style.lower().strip().replace(" ", "_").replace("-", "_")

    # Direct match
    if style_lower in PREDEFINED_STYLES:
        return style_lower

    # Common aliases
    aliases = {
        "indian": "indian_contemporary",
        "indian_modern": "indian_contemporary",
        "traditional_indian": "indian_contemporary",
        "minimal": "minimalist",
        "scandi": "scandinavian",
        "nordic": "scandinavian",
        "hygge": "scandinavian",
        "mcm": "mid_century_modern",
        "midcentury": "mid_century_modern",
        "mid_century": "mid_century_modern",
        "retro": "mid_century_modern",
        "luxury": "modern_luxury",
        "glam": "modern_luxury",
        "bohemian": "boho",
        "boho_chic": "boho",
        "urban": "industrial",
        "loft": "industrial",
        "warehouse": "industrial",
        "japanese": "japandi",
        "zen": "japandi",
    }

    return aliases.get(style_lower, style_lower)
