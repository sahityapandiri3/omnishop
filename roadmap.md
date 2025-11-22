# Omnishop Product Roadmap

## V1.5 (Current) - Store Selection & Furniture Removal
**Status**: In Development
- ✅ Multi-store selection page
- ✅ Backend store filtering
- ✅ Automatic furniture removal with Gemini 2.5 Flash
- ✅ Async processing with retry logic

## V2.0 - Future Enhancements

### Custom Store URLs
**Description**: Allow users to provide their own store URLs for product scraping

**User Story**: As a user, I want to shop from my favorite stores that aren't currently in Omnishop's catalog, so I can find products that match my style preferences and budget.

**Technical Requirements**:
- URL validation and normalization
- Dynamic scraper creation for new stores
- Store metadata extraction (logo, name, categories)
- Product extraction with fallback patterns
- Store persistence and caching
- User-submitted store review/approval workflow

**Priority**: Medium

### Selective Furniture Removal
**Description**: Let users select specific furniture items to remove instead of removing all furniture automatically

**User Story**: As a user, I want to keep some of my existing furniture (like a bookshelf or rug) while removing other pieces (like a sofa), so I can visualize how new furniture integrates with my favorite items.

**Technical Requirements**:
- Interactive furniture detection and labeling
- Click-to-select UI on uploaded room image
- Bounding box visualization for detected furniture
- Multi-selection support
- Partial furniture removal using Gemini 2.5 Flash with selective prompts
- "Keep All" / "Remove All" quick actions

**Priority**: High

## V2.1+ - Long-term Ideas

### AR/VR Visualization
- Augmented reality room preview
- VR room walkthrough
- Mobile AR app integration

### Social Features
- Share design boards
- Collaborate with friends/family
- Designer community

### Advanced Personalization
- Style profile learning
- Purchase history integration
- Budget tracking and recommendations
- Seasonal trend suggestions

### Smart Home Integration
- Integration with smart home platforms
- Automated shopping lists
- Price tracking and alerts

### Multi-room Support
- Whole-home design projects
- Room-to-room style consistency
- Floor plan visualization

## Completed Milestones

### V1.0 - Initial Launch
- ✅ Product scraping from multiple stores
- ✅ AI-powered product recommendations
- ✅ Room visualization with Gemini 2.5 Flash
- ✅ Chat-based design assistant
- ✅ Multi-store product diversity

### V1.1 - Furniture Detection & Replacement
- ✅ Furniture detection in uploaded images
- ✅ Add vs Replace workflow
- ✅ Similar furniture recommendations for replacement

### V1.2 - Enhanced Recommendations
- ✅ Attribute-based filtering (color, material, texture)
- ✅ AI stylist integration
- ✅ Source diversity optimization
