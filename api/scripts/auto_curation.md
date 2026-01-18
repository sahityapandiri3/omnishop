# Automated Curated Looks Generator

## Overview
Automatically generate **12 curated looks** for the Omnishop interior design app.

**Matrix**: 3 styles × 4 budget tiers × 1 look each = 12 looks

| Style | Pocket Friendly | Mid-Tier | Premium | Luxury |
|-------|-----------------|----------|---------|--------|
| Modern | 1 look | 1 look | 1 look | 1 look |
| Modern Luxury | 1 look | 1 look | 1 look | 1 look |
| Indian Contemporary | 1 look | 1 look | 1 look | 1 look |

---

## Scripts

### 1. `process_base_images.py` - Prepare Base Images
Runs furniture removal on room images to create clean backgrounds.

```bash
# Process all images in Base_Images folder
python3 api/scripts/process_base_images.py
```

**Output:**
- Cleaned images saved to: `Base_Images/cleaned/*_clean.jpg`
- Room analysis saved to: `Base_Images/cleaned/room_analysis.json`

### 2. `auto_curation.py` - Generate Curated Looks
Creates curated looks with product selection and AI visualizations.

```bash
# Dry run (preview without saving)
python3 api/scripts/auto_curation.py --dry-run

# Generate all 12 looks
python3 api/scripts/auto_curation.py

# Generate specific style only
python3 api/scripts/auto_curation.py --style modern

# Generate specific tier only
python3 api/scripts/auto_curation.py --tier premium

# Skip visualization (faster testing)
python3 api/scripts/auto_curation.py --skip-visualization
```

---

## Configuration

### Styles
| Style | Labels | Keywords | Colors | Materials |
|-------|--------|----------|--------|-----------|
| Modern | `["modern"]` | modern, contemporary, minimalist | gray, white, black, beige | metal, glass, leather |
| Modern Luxury | `["modern_luxury"]` | luxury, premium, elegant | gold, cream, white, navy | velvet, brass, marble |
| Indian Contemporary | `["indian_contemporary"]` | indian, ethnic, traditional | brown, gold, red, orange | wood, brass, fabric, jute |

### Budget Tiers
| Tier | Price Range | Target Total |
|------|-------------|--------------|
| pocket_friendly | < ₹2,00,000 | ~₹1,50,000 |
| mid_tier | ₹2,00,000 - ₹8,00,000 | ~₹5,00,000 |
| premium | ₹8,00,000 - ₹15,00,000 | ~₹11,00,000 |
| luxury | ≥ ₹15,00,000 | ~₹20,00,000 |

### Room Type
- Living Room only

---

## Products Per Look

### Required (10 items)
1. Sofa
2. Accent chair (1-2 depending on space)
3. Center table (coffee_table)
4. Side table
5. Wall art
6. Carpet (rugs)
7. Floor lamp
8. Ceiling lamp
9. Throw
10. Planter

### Optional (include 2-3)
- Table decor
- Side lamp (table_lamp)
- Book shelf
- Cushions

### Budget Allocation
| Product | Allocation |
|---------|------------|
| Sofa | ~30% |
| Accent chair(s) | ~12% |
| Rugs | ~12% |
| Coffee table | ~10% |
| Ceiling lamp | ~8% |
| Others | ~28% |

---

## Workflow

### Step 1: Prepare Base Images (One-time)
```bash
python3 api/scripts/process_base_images.py
```
- Processes images from `Base_Images/` folder
- Removes furniture using Google AI
- Saves cleaned images to `Base_Images/cleaned/`
- Caches room analysis data for faster visualization

### Step 2: Generate Looks
```bash
# Test with dry run first
python3 api/scripts/auto_curation.py --dry-run --skip-visualization

# Generate with visualizations
python3 api/scripts/auto_curation.py
```

### Step 3: Review & Publish
1. Check generated looks in admin curation page
2. Verify visualizations look correct
3. Set `is_published=True` for approved looks

---

## Key Files

| File | Purpose |
|------|---------|
| `api/scripts/auto_curation.py` | Main auto-curation script |
| `api/scripts/process_base_images.py` | Furniture removal for base images |
| `Base_Images/cleaned/` | Cleaned room images (furniture removed) |
| `Base_Images/cleaned/room_analysis.json` | Cached room analysis data |
| `api/database/models.py:505-568` | CuratedLook, CuratedLookProduct models |
| `api/services/google_ai_service.py` | Google AI visualization service |

---

## Error Handling

- Retry visualization API calls up to 3 times with exponential backoff
- Log failed looks and continue with remaining
- Validate products exist before creating look
- Track used product IDs to ensure uniqueness across looks

---

## Scaling

To generate more looks per style/budget:
```bash
# Generate 6 looks per combination (72 total)
python3 api/scripts/auto_curation.py --count 6
```

---

## All Related Scripts

### 1. `auto_curation.py` - Main Auto-Curation Script
Generates curated looks automatically with product selection and AI visualizations.

```bash
# Dry run (preview without saving)
python3 api/scripts/auto_curation.py --dry-run

# Generate all 12 looks
python3 api/scripts/auto_curation.py

# Generate specific style only
python3 api/scripts/auto_curation.py --style modern

# Generate specific tier only
python3 api/scripts/auto_curation.py --tier premium

# Skip visualization (faster testing)
python3 api/scripts/auto_curation.py --skip-visualization
```

---

### 2. `process_base_images.py` - Prepare Base Images
Runs furniture removal on room images to create clean backgrounds for visualization.

```bash
# Process all images in Base_Images folder
python3 api/scripts/process_base_images.py
```

**Input:** `Base_Images/*.jpg`
**Output:**
- Cleaned images: `Base_Images/cleaned/*_clean.jpg`
- Room analysis: `Base_Images/cleaned/room_analysis.json`

---

### 3. `regenerate_look.py` - Regenerate Single Look (Full)
Regenerates the visualization for an existing curated look using all its products.

```bash
# Regenerate look by ID (default: 31)
python3 api/scripts/regenerate_look.py 31

# Specify a different look ID
python3 api/scripts/regenerate_look.py 45
```

**What it does:**
- Fetches the curated look from the database
- Retrieves all products with their images and dimensions
- Regenerates visualization from the original clean room image
- Saves new visualization to database and `/tmp/regenerated_look_{id}.jpg`

**Use case:** When a look's visualization needs updating after product changes or to improve quality.

---

### 4. `regenerate_look_lite.py` - Regenerate Single Look (Lite)
Regenerates visualization with fewer products (max 4) to avoid API failures on complex looks.

```bash
# Regenerate look with limited products (default: 50)
python3 api/scripts/regenerate_look_lite.py 50

# Specify a different look ID
python3 api/scripts/regenerate_look_lite.py 42
```

**Priority order for product selection:**
1. Sofa
2. Accent chair
3. Coffee table
4. Rugs
5. Floor lamp
6. Ceiling lamp
7. Side table
8. Wall art

**What it does:**
- Uses only top 4 priority products instead of all products
- Reduces API load and improves success rate
- Same output as `regenerate_look.py`

**Use case:** When full regeneration fails due to too many products or API limitations.

---

### 5. `populate_curated_looks.py` - Seed Sample Curated Looks
Creates sample curated looks with hardcoded product data. One-time setup script.

```bash
# Requires DATABASE_URL environment variable
DATABASE_URL="your_production_url" python3 api/scripts/populate_curated_looks.py
```

**What it does:**
- Creates 3 sample curated looks (Modern Minimalist, Contemporary, Classic Elegant)
- Links predefined product IDs to each look
- Calculates total prices from product data
- Sets looks as published with display order

**Use case:** Initial seeding of the curated_looks table for development/testing.

---

## Script Comparison

| Script | Purpose | Products | Visualization |
|--------|---------|----------|---------------|
| `auto_curation.py` | Generate new looks | Auto-selected | Yes |
| `process_base_images.py` | Prepare room images | N/A | No |
| `regenerate_look.py` | Update existing look | All products | Yes |
| `regenerate_look_lite.py` | Update with fewer products | Top 4 priority | Yes |
| `populate_curated_looks.py` | Seed sample data | Hardcoded | No |
