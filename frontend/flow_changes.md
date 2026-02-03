# Flow Changes - User Type Selection & Tier-Based Navigation

This document details all flow changes implemented for user type selection and tier-based navigation.

---

## Summary

- Added user type selection (Home Owner vs Professional Stylist) on pricing page
- All tiers now go through payment first, then to appropriate next step
- Tier-based CTAs on purchase page
- Navigation updates with renamed labels and tier-based visibility
- Full publish form for Curator users on design page

---

## Phase 1: Pricing Page - User Type Selection

### User Type Toggle

Added a prominent toggle at the top of the pricing page:
- **"I'm a Home Owner/Renter"** → Shows Free, Basic, Basic+, Advanced tiers
- **"I'm a Professional Stylist"** → Shows Curator tier only

### Tier Display Logic

**Home Owner/Renter View:**
| Tier | Price | Features |
|------|-------|----------|
| Free | Rs 0 | 1 curated look with sample room |
| Basic | Rs 399 | 3 curated looks |
| Basic+ | Rs 699 | 6 curated looks (highlighted as Most Popular) |
| Advanced | Rs 11,999/mo | 6 looks + Omni Studio access |

**Professional Stylist View:**
| Tier | Price | Features |
|------|-------|----------|
| Curator | Rs 14,999/mo | Full studio + Publish to platform |

### Highlight Parameter Support

When URL contains `?highlight=advanced`:
- Auto-scrolls to Advanced tier card
- Adds visual highlight (ring, glow effect)
- Shows tooltip: "Upgrade to style further"

---

## Phase 2: Unified Payment Flow

### New Flow (ALL tiers including Free)

```
/pricing → /payment?tier=X → /homestyling/preferences → /homestyling/upload → /homestyling/results/{id} → /purchases/{id}
```

### Curator Exception

```
/pricing → /payment?tier=curator → /curated
```

### Changes Made

1. **Pricing page**: All tiers route to `/payment?tier=X`
2. **Payment page**:
   - After payment success, routes to `/homestyling/preferences` (not upload)
   - Curator routes to `/curated`
3. **Preferences page**:
   - Removed internal payment routing
   - Goes directly to upload (or status for Free tier)

---

## Phase 3: Purchase Page CTAs

### Tier-Based CTAs

**For Free, Basic, Basic+ users:**
| CTA | Action |
|-----|--------|
| "Style This Further" | → `/pricing?highlight=advanced` (prompts upgrade) |
| "Get More Looks" | → `/pricing` |

**For Advanced/Curator users:**
| CTA | Action |
|-----|--------|
| "Style This Further" | → `/design` directly with room image, visualization, and products loaded |
| "See More Looks" | → `/curated` |

### Context Loading for Design

When "Style This Further" navigates to /design for Advanced users:
- Stores in sessionStorage before navigation:
  - `curatedRoomImage` - the base room image
  - `curatedVisualizationImage` - the AI-generated visualization
  - `preselectedProducts` - JSON stringified products array
  - `designAccessGranted` - tier bypass flag
- Design page loads these on mount and initializes canvas

---

## Phase 4: Navigation Updates

### Label Changes

| Current | New |
|---------|-----|
| "Design" | "Studio" |
| "Curated" | "Curated Looks" |
| "Home Styling" | **REMOVED** (flow merged with pricing → payment) |

### Tier-Based Navigation Items

**Free, Basic, Basic+ users see:**
- Home
- Purchases

**Advanced users see:**
- Home
- Studio
- Curated Looks
- Projects
- Purchases

**Curator users see:**
- Home
- Studio
- Curated Looks
- Projects
- Purchases

### User Type Badge

Added badge on user avatar showing:
- User's subscription tier (e.g., "Advanced Plan", "Curator Plan")
- Clicking badge → `/pricing`

---

## Phase 5: Curator Publish on Design Page

### Full Publish Form for Curator

When `user.subscription_tier === 'curator'`, the design page shows a full publish form:

**Fields:**
- Title (required)
- Description (optional)
- Room Type (dropdown: living_room, bedroom)
- Style Labels (multi-select)
- Budget Tier (auto-calculated, read-only)
- Publish button

### API Integration

Publishes to curated gallery via `adminCuratedAPI.create()` with:
- `title`, `description`, `room_type`
- `style_labels` - selected style tags
- `budget_tier` - calculated from total product prices
- `visualization_image`, `room_image` - base64 images
- `product_ids`, `product_quantities` - canvas products

---

## Files Modified

| File | Changes |
|------|---------|
| `/frontend/src/app/pricing/page.tsx` | User type toggle, tier filtering, highlight support |
| `/frontend/src/app/payment/page.tsx` | Route to preferences (not upload), Curator → /curated |
| `/frontend/src/app/homestyling/preferences/page.tsx` | Remove payment routing, go direct to upload |
| `/frontend/src/app/purchases/[id]/page.tsx` | Tier-based CTAs |
| `/frontend/src/components/Navigation.tsx` | Label changes, remove Home Styling, tier-based visibility, user badge |
| `/frontend/src/app/design/page.tsx` | Full curator publish form |

---

## User Flow Diagrams

### Home Owner Flow (Free/Basic/Basic+)
```
Landing → Pricing (Home Owner tab) → Select Tier → Payment → Preferences → Upload → Results → Purchases
                                                                                            ↓
                                                                        "Style This Further" → Pricing (highlight Advanced)
                                                                        "Get More Looks" → Pricing
```

### Home Owner Flow (Advanced)
```
Landing → Pricing (Home Owner tab) → Select Advanced → Payment → Preferences → Upload → Results → Purchases
                                                                                                     ↓
                                                                                "Style This Further" → Design (with context)
                                                                                "See More Looks" → Curated
```

### Professional Stylist Flow (Curator)
```
Landing → Pricing (Professional tab) → Select Curator → Payment → Curated Gallery
                                                                       ↓
                                                        Full access to Studio with Publish capability
```

---

## Testing Checklist

### User Type Selection
- [ ] Go to `/pricing`
- [ ] Toggle "Home Owner/Renter" → See Free, Basic, Basic+, Advanced
- [ ] Toggle "Professional Stylist" → See only Curator

### Payment Flows
- [ ] Free tier: Pricing → Payment (Rs 0) → Preferences → Status → Purchases
- [ ] Basic/Basic+: Pricing → Payment → Preferences → Upload → Results → Purchases
- [ ] Advanced: Pricing → Payment → Preferences → Upload → Results → Purchases
- [ ] Curator: Pricing → Payment → /curated

### Purchase Page CTAs
- [ ] As Free/Basic/Basic+ user:
  - "Get More Looks" → goes to /pricing
  - "Style This Further" → goes to /pricing with Advanced highlighted
- [ ] As Advanced user:
  - "See More Looks" → goes to /curated
  - "Style This Further" → goes to /design with images loaded

### Navigation
- [ ] "Design" shows as "Studio"
- [ ] "Curated" shows as "Curated Looks"
- [ ] "Home Styling" is removed
- [ ] Free/Basic/Basic+ users see limited nav (Home, Purchases)
- [ ] Advanced/Curator users see full nav (Home, Studio, Curated Looks, Projects, Purchases)

### Curator Publish
- [ ] As Curator on /design
- [ ] See full publish form with Title, Description, Room Type, Style Labels
- [ ] Publish creates look in curated gallery
