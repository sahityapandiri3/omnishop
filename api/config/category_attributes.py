"""
Category attributes configuration for Omni AI Stylist.
Defines which categories are "simple" (show immediately) vs "complex" (need follow-up questions).
Also defines the 2-3 key attributes to gather for complex categories.
"""
from typing import Any, Dict, List

# Simple categories - show products immediately, no follow-up questions needed
SIMPLE_CATEGORIES = [
    "decor_accents",
    "planters",
    "wall_art",
    "wallpapers",
    "vases",
    "candles",
    "photo_frames",
    "mirrors",
    "clocks",
    "sculptures",
    "figurines",
    "ornaments",
    "artefacts",
    "decorative_bowls",
    "decorative_boxes",
    "candle_holders",
    "cushion_covers",
    "bookends",
    "trays",
    "baskets",
    "artificial_plants",
    "benches",
]

# Category attributes for complex categories
# Each category has 2-3 key attributes to gather before recommending
CATEGORY_ATTRIBUTES: Dict[str, Dict[str, Any]] = {
    "sofa": {
        "attributes": ["seating_type", "style", "color"],
        "questions": {
            "seating_type": "What seating configuration are you looking for? (single seater, 2-seater, 3-seater, L-shaped, sectional)",
            "style": "What style do you prefer? (modern, traditional, mid-century, contemporary, minimalist)",
            "color": "Do you have a color preference?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
            "color": "color_palette",
        },
    },
    "dining_table": {
        "attributes": ["seating_capacity", "shape", "material"],
        "questions": {
            "seating_capacity": "How many people do you typically seat? (2, 4, 6, 8+)",
            "shape": "What shape do you prefer? (rectangular, round, oval, square)",
            "material": "Any material preference? (wood, marble, glass, metal)",
        },
        "default_from_room_analysis": {
            "material": "detected_materials",
        },
    },
    "dining_chair": {
        "attributes": ["style", "material", "with_arms"],
        "questions": {
            "style": "What style are you looking for? (modern, traditional, upholstered, wooden)",
            "material": "What material do you prefer? (wood, upholstered, metal, rattan)",
            "with_arms": "Do you prefer chairs with or without arms?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
            "material": "detected_materials",
        },
    },
    "coffee_table": {
        "attributes": ["shape", "style", "material"],
        "questions": {
            "shape": "What shape works best? (rectangular, round, oval, square, nesting)",
            "style": "What style do you prefer? (modern, rustic, industrial, minimalist)",
            "material": "Any material preference? (wood, glass, marble, metal)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
            "material": "detected_materials",
        },
    },
    "side_table": {
        "attributes": ["style", "material"],
        "questions": {
            "style": "What style are you looking for? (modern, traditional, industrial)",
            "material": "Any material preference? (wood, metal, glass, marble)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "console_table": {
        "attributes": ["style", "material", "storage"],
        "questions": {
            "style": "What style do you prefer? (modern, traditional, rustic, industrial)",
            "material": "Any material preference? (wood, metal, marble, glass)",
            "storage": "Do you need storage (drawers/shelves) or prefer open design?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "bed": {
        "attributes": ["size", "style", "headboard_type"],
        "questions": {
            "size": "What size bed? (single, double, queen, king)",
            "style": "What style do you prefer? (modern, traditional, upholstered, platform)",
            "headboard_type": "Do you prefer upholstered headboard, wooden, or minimal/no headboard?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "wardrobe": {
        "attributes": ["size", "door_type", "finish"],
        "questions": {
            "size": "What size do you need? (single door, double door, triple door)",
            "door_type": "What type of doors? (hinged, sliding, open)",
            "finish": "What finish do you prefer? (natural wood, white, walnut, painted)",
        },
        "default_from_room_analysis": {},
    },
    "desk": {
        "attributes": ["size", "style", "storage"],
        "questions": {
            "size": "What size desk do you need? (compact, standard, large/executive)",
            "style": "What style? (modern, traditional, industrial, minimalist)",
            "storage": "Do you need drawers or prefer a simple top?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "office_chair": {
        "attributes": ["style", "ergonomic", "material"],
        "questions": {
            "style": "What style? (executive, ergonomic, minimalist, mesh)",
            "ergonomic": "Do you need ergonomic features (adjustable lumbar, armrests)?",
            "material": "What material? (leather, mesh, fabric)",
        },
        "default_from_room_analysis": {},
    },
    "bookshelf": {
        "attributes": ["size", "style", "configuration"],
        "questions": {
            "size": "What size? (small/accent, medium, large/wall unit)",
            "style": "What style? (modern, industrial, traditional, ladder)",
            "configuration": "Open shelves or with doors/drawers?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "tv_unit": {
        "attributes": ["size", "style", "storage"],
        "questions": {
            "size": 'What size TV are you mounting? (up to 43", 43-55", 55"+)',
            "style": "What style? (modern floating, traditional cabinet, industrial)",
            "storage": "How much storage do you need? (minimal, moderate, lots)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "rugs": {
        "attributes": ["size", "style", "material"],
        "questions": {
            "size": "What size do you need? (small accent, medium area, large room-size)",
            "style": "What style/pattern? (solid, geometric, traditional, abstract)",
            "material": "What material? (wool, cotton, jute, synthetic)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
            "color": "color_palette",
        },
    },
    "lamps": {
        "attributes": ["type", "style", "size"],
        "questions": {
            "type": "What type of lamp? (table lamp, floor lamp, desk lamp)",
            "style": "What style? (modern, traditional, industrial, minimalist)",
            "size": "What size do you need? (small accent, medium, large statement)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "chandelier": {
        "attributes": ["style", "size", "finish"],
        "questions": {
            "style": "What style? (modern, crystal, industrial, minimalist)",
            "size": "What size room is it for? (small, medium, large)",
            "finish": "Any finish preference? (gold, chrome, black, natural)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "curtains": {
        "attributes": ["style", "fabric", "color"],
        "questions": {
            "style": "What style? (sheer, blackout, layered, patterned)",
            "fabric": "What fabric? (linen, cotton, velvet, polyester)",
            "color": "What color family? (neutrals, bold, earthy, pastels)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
            "color": "color_palette",
        },
    },
    "cushions": {
        "attributes": ["style", "color", "size"],
        "questions": {
            "style": "What style/pattern? (solid, textured, patterned, embroidered)",
            "color": "What colors? (to match existing decor or contrast)",
            "size": "What size? (standard 18x18, large 20x20, lumbar)",
        },
        "default_from_room_analysis": {
            "color": "color_palette",
        },
    },
    "throws": {
        "attributes": ["material", "color", "size"],
        "questions": {
            "material": "What material? (cotton, wool, knit, faux fur)",
            "color": "What color family?",
            "size": "What size? (lap throw, standard, oversized)",
        },
        "default_from_room_analysis": {
            "color": "color_palette",
        },
    },
    "outdoor_furniture": {
        "attributes": ["type", "material", "seating_capacity"],
        "questions": {
            "type": "What type? (lounge set, dining set, individual chairs, bench)",
            "material": "What material? (teak, rattan, metal, synthetic wicker)",
            "seating_capacity": "How many people should it seat?",
        },
        "default_from_room_analysis": {},
    },
    "bar_furniture": {
        "attributes": ["type", "style", "seating_capacity"],
        "questions": {
            "type": "What type? (bar cart, bar cabinet, bar counter, bar stools)",
            "style": "What style? (modern, industrial, traditional, art deco)",
            "seating_capacity": "If bar stools, how many do you need?",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
    "storage": {
        "attributes": ["type", "style", "size"],
        "questions": {
            "type": "What type? (cabinet, chest, trunk, sideboard, shoe rack)",
            "style": "What style? (modern, traditional, industrial, rustic)",
            "size": "What size fits your space? (compact, medium, large)",
        },
        "default_from_room_analysis": {
            "style": "detected_style",
        },
    },
}

# Category name normalization mapping
CATEGORY_NAME_MAPPING = {
    # Singular to plural
    "sofa": "sofas",
    "table": "tables",
    "chair": "chairs",
    "lamp": "lamps",
    "rug": "rugs",
    "cushion": "cushions",
    "throw": "throws",
    "curtain": "curtains",
    "mirror": "mirrors",
    "bench": "benches",
    "clock": "clocks",
    "vase": "vases",
    "candle": "candles",
    "planter": "planters",
    "bookshelf": "bookshelves",
    # Alternative names
    "couch": "sofas",
    "couches": "sofas",
    "sofa": "sofas",
    "settee": "sofas",
    "loveseat": "sofas",
    "sectional": "sofas",
    "sectionals": "sofas",
    "sectional_sofa": "sofas",
    "sectional_sofas": "sofas",
    "divan": "sofas",
    "l_shaped_sofa": "sofas",
    "l_shaped_sofas": "sofas",
    "l_shape_sofa": "sofas",
    "l_shape_sofas": "sofas",
    "corner_sofa": "sofas",
    "corner_sofas": "sofas",
    "modular_sofa": "sofas",
    "modular_sofas": "sofas",
    "accent_chair": "accent_chairs",
    "accent_chairs": "accent_chairs",
    "armchair": "accent_chairs",
    "armchairs": "accent_chairs",
    "lounge_chair": "accent_chairs",
    "lounge_chairs": "accent_chairs",
    "recliner": "accent_chairs",
    "recliners": "accent_chairs",
    "end_table": "side_table",
    "accent_table": "side_table",
    "nightstand": "side_table",
    "bedside_table": "side_table",
    "entry_table": "console_table",
    "hall_table": "console_table",
    "foyer_table": "console_table",
    "area_rug": "rugs",
    "carpet": "rugs",
    "runner": "rugs",
    "table_lamp": "lamps",
    "floor_lamp": "lamps",
    "pendant": "chandelier",
    "pendant_light": "chandelier",
    "light_fixture": "chandelier",
    "drapes": "curtains",
    "window_treatments": "curtains",
    "blinds": "curtains",
    "pillow": "cushions",
    "throw_pillow": "cushions",
    "decorative_pillow": "cushions",
    "blanket": "throws",
    "throw_blanket": "throws",
    "decor": "decor_accents",
    "accessories": "decor_accents",
    "decorations": "decor_accents",
    "home_decor": "decor_accents",
    "entertainment_unit": "tv_unit",
    "media_console": "tv_unit",
    "media_unit": "tv_unit",
    "tv_stand": "tv_unit",
    "tv_cabinet": "tv_unit",
    "picture_frame": "photo_frames",
    "frame": "photo_frames",
    "frames": "photo_frames",
    "plant": "planters",
    "plants": "planters",
    "pot": "planters",
    "pots": "planters",
    "flower_pot": "planters",
    "artwork": "wall_art",
    "art": "wall_art",
    "painting": "wall_art",
    "paintings": "wall_art",
    "poster": "wall_art",
    "posters": "wall_art",
    "print": "wall_art",
    "prints": "wall_art",
    "wall_decor": "wall_art",
    # Cushion covers (specific category)
    "cushion_cover": "cushion_covers",
    "pillow_cover": "cushion_covers",
    "pillow_covers": "cushion_covers",
    # Common typos
    "cushion_covres": "cushion_covers",
    "cushion_covre": "cushion_covers",
    "cushions_cover": "cushion_covers",
    "cushions_covers": "cushion_covers",
    # Decor subcategories
    "sculpture": "sculptures",
    "statue": "sculptures",
    "statues": "sculptures",
    "statuette": "sculptures",
    "figurine": "figurines",
    "figure": "figurines",
    "figures": "figurines",
    "ornament": "ornaments",
    "ornaments": "ornaments",
    "artefact": "artefacts",
    "artifact": "artefacts",
    "artifacts": "artefacts",
    "decorative_bowl": "decorative_bowls",
    "decorative_box": "decorative_boxes",
    "candle_holder": "candle_holders",
    "candleholder": "candle_holders",
    "candlestick": "candle_holders",
    "clock": "clocks",
}


def is_simple_category(category: str) -> bool:
    """Check if a category is simple (show products immediately)"""
    normalized = normalize_category_name(category)
    return normalized in SIMPLE_CATEGORIES


def normalize_category_name(category: str) -> str:
    """Normalize category name to standard form"""
    if not category:
        return category

    # Convert to lowercase and replace spaces/hyphens with underscores
    normalized = category.lower().strip().replace(" ", "_").replace("-", "_")

    # Check mapping first
    if normalized in CATEGORY_NAME_MAPPING:
        return CATEGORY_NAME_MAPPING[normalized]

    # Strip material prefixes (e.g., "wooden_accent_chairs" -> "accent_chairs")
    # This handles cases where GPT prepends material to category name
    material_prefixes = [
        "wooden_",
        "wood_",
        "leather_",
        "velvet_",
        "fabric_",
        "metal_",
        "marble_",
        "glass_",
        "rattan_",
        "wicker_",
        "brass_",
        "iron_",
        "steel_",
        "chrome_",
        "cotton_",
        "linen_",
        "silk_",
        "wool_",
        "jute_",
        "cane_",
        "bamboo_",
        "ceramic_",
        "plastic_",
        "acrylic_",
        "upholstered_",
        "teak_",
        "sheesham_",
        "oak_",
        "walnut_",
        "mahogany_",
    ]

    for prefix in material_prefixes:
        if normalized.startswith(prefix):
            stripped = normalized[len(prefix) :]
            # Check if the stripped version is in mapping
            if stripped in CATEGORY_NAME_MAPPING:
                return CATEGORY_NAME_MAPPING[stripped]
            # Return the stripped version (may still need mapping elsewhere)
            return stripped

    return normalized


def get_category_attributes(category: str) -> Dict[str, Any]:
    """Get attributes configuration for a category"""
    normalized = normalize_category_name(category)
    return CATEGORY_ATTRIBUTES.get(normalized, {})


def get_next_question(category: str, filled_attributes: Dict[str, Any]) -> tuple:
    """
    Get the next question to ask for a category based on what's already filled.

    Returns:
        tuple: (attribute_name, question_text) or (None, None) if all filled
    """
    config = get_category_attributes(category)
    if not config:
        return None, None

    attributes = config.get("attributes", [])
    questions = config.get("questions", {})

    for attr in attributes:
        if attr not in filled_attributes or filled_attributes[attr] is None:
            return attr, questions.get(attr)

    return None, None


def auto_fill_from_room_analysis(category: str, room_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-fill category attributes from room analysis (for "stylist chooses" mode).

    Args:
        category: The product category
        room_analysis: Room analysis data with detected_style, color_palette, detected_materials

    Returns:
        Dict of attribute values filled from room analysis
    """
    config = get_category_attributes(category)
    if not config:
        return {}

    defaults = config.get("default_from_room_analysis", {})
    filled = {}

    for attr, source_field in defaults.items():
        if source_field in room_analysis and room_analysis[source_field]:
            value = room_analysis[source_field]
            # If it's a list, take the first item or join with comma
            if isinstance(value, list) and value:
                filled[attr] = value[0] if len(value) == 1 else ", ".join(value[:3])
            else:
                filled[attr] = value

    return filled


def get_all_complex_categories() -> List[str]:
    """Get list of all complex categories (those with attribute configs)"""
    return list(CATEGORY_ATTRIBUTES.keys())


def get_category_attribute_list(category: str) -> List[str]:
    """Get the list of attributes for a category"""
    config = get_category_attributes(category)
    return config.get("attributes", [])
