# UI V2 Test Cases & Automated Tests

## Overview
Comprehensive test suite for the new three-panel Design Studio UI, covering unit tests, integration tests, and end-to-end tests.

---

## Test Strategy

### Test Levels
1. **Unit Tests** - Individual component functionality
2. **Integration Tests** - Component interaction and API integration
3. **E2E Tests** - Complete user workflows
4. **Visual Regression Tests** - UI consistency
5. **Accessibility Tests** - WCAG compliance

### Test Coverage Goals
- Unit Tests: >80% code coverage
- Integration Tests: All critical paths
- E2E Tests: All user workflows
- Accessibility: WCAG 2.1 AA compliance

---

## Test Cases

## 1. Landing Page Tests

### 1.1 Page Load
**Test ID**: LP-001
**Priority**: High
**Description**: Verify landing page loads correctly

**Test Steps**:
1. Navigate to `http://localhost:3000`
2. Verify page loads without errors
3. Check all sections render
4. Verify no console errors

**Expected Results**:
- ✅ Page loads in <2 seconds
- ✅ Hero section visible
- ✅ Upload area visible
- ✅ Action buttons visible
- ✅ No console errors

**Automated Test**: `tests/unit/LandingPage.test.tsx`

---

### 1.2 Image Upload - Drag & Drop
**Test ID**: LP-002
**Priority**: High
**Description**: Test drag and drop functionality

**Test Steps**:
1. Navigate to landing page
2. Create mock image file
3. Drag image over upload area
4. Verify dragging state shows
5. Drop image
6. Verify preview appears

**Expected Results**:
- ✅ Drag state highlights upload area
- ✅ Image preview displays correctly
- ✅ Success message appears
- ✅ "Upload a different image" link visible

**Automated Test**: `tests/unit/LandingPage.test.tsx`

---

### 1.3 Image Upload - File Picker
**Test ID**: LP-003
**Priority**: High
**Description**: Test file picker upload

**Test Steps**:
1. Navigate to landing page
2. Click "Choose File" button
3. Select valid image file
4. Verify preview appears

**Expected Results**:
- ✅ File input opens
- ✅ Image preview displays
- ✅ Success indicator shows

**Automated Test**: `tests/unit/LandingPage.test.tsx`

---

### 1.4 Image Validation - Invalid Type
**Test ID**: LP-004
**Priority**: High
**Description**: Test file type validation

**Test Steps**:
1. Navigate to landing page
2. Upload non-image file (PDF, TXT, etc.)
3. Verify error message

**Expected Results**:
- ✅ Alert: "Please upload an image file (JPG, PNG, WEBP)"
- ✅ Preview does not show
- ✅ Upload state resets

**Automated Test**: `tests/unit/LandingPage.test.tsx`

---

### 1.5 Image Validation - File Size
**Test ID**: LP-005
**Priority**: High
**Description**: Test file size validation

**Test Steps**:
1. Navigate to landing page
2. Upload image >10MB
3. Verify error message

**Expected Results**:
- ✅ Alert: "File size must be less than 10MB"
- ✅ Upload rejected

**Automated Test**: `tests/unit/LandingPage.test.tsx`

---

### 1.6 Navigation - Upload & Continue
**Test ID**: LP-006
**Priority**: Critical
**Description**: Test navigation with image

**Test Steps**:
1. Upload valid image
2. Click "Upload & Continue"
3. Verify navigation to `/design`
4. Check sessionStorage

**Expected Results**:
- ✅ Navigates to `/design`
- ✅ sessionStorage contains 'roomImage'
- ✅ Image data is base64 string

**Automated Test**: `tests/integration/LandingToDesign.test.tsx`

---

### 1.7 Navigation - Upload Later
**Test ID**: LP-007
**Priority**: High
**Description**: Test skip upload flow

**Test Steps**:
1. Click "Upload Later" (no image uploaded)
2. Verify navigation to `/design`
3. Check sessionStorage

**Expected Results**:
- ✅ Navigates to `/design`
- ✅ sessionStorage does NOT contain 'roomImage'

**Automated Test**: `tests/integration/LandingToDesign.test.tsx`

---

## 2. Three-Panel Layout Tests

### 2.1 Layout Rendering - Desktop
**Test ID**: TPL-001
**Priority**: Critical
**Description**: Verify three-panel layout on desktop

**Test Steps**:
1. Navigate to `/design`
2. Set viewport to 1920x1080
3. Verify all panels visible

**Expected Results**:
- ✅ Panel 1 (Chat) visible - 25% width
- ✅ Panel 2 (Products) visible - 50% width
- ✅ Panel 3 (Canvas) visible - 25% width
- ✅ No horizontal scroll

**Automated Test**: `tests/unit/DesignPage.test.tsx`

---

### 2.2 Layout Rendering - Mobile
**Test ID**: TPL-002
**Priority**: High
**Description**: Verify tab layout on mobile

**Test Steps**:
1. Navigate to `/design`
2. Set viewport to 375x667 (mobile)
3. Verify tab navigation

**Expected Results**:
- ✅ Tab bar visible (Chat | Products | Canvas)
- ✅ Only one panel visible at a time
- ✅ Active tab highlighted

**Automated Test**: `tests/unit/DesignPage.test.tsx`

---

### 2.3 Mobile Tab Switching
**Test ID**: TPL-003
**Priority**: High
**Description**: Test mobile tab navigation

**Test Steps**:
1. Set mobile viewport
2. Click "Products" tab
3. Verify Products panel shows
4. Click "Canvas" tab
5. Verify Canvas panel shows

**Expected Results**:
- ✅ Correct panel displays for each tab
- ✅ Previous panel hidden
- ✅ Tab indicator updates

**Automated Test**: `tests/unit/DesignPage.test.tsx`

---

### 2.4 Room Image Loading from sessionStorage
**Test ID**: TPL-004
**Priority**: Critical
**Description**: Verify room image loads from sessionStorage

**Test Steps**:
1. Set mock base64 image in sessionStorage
2. Navigate to `/design`
3. Check Panel 3 (Canvas)

**Expected Results**:
- ✅ Room image displays in Canvas panel
- ✅ sessionStorage cleared after load
- ✅ Image state set correctly

**Automated Test**: `tests/integration/RoomImageFlow.test.tsx`

---

## 3. ChatPanel Tests

### 3.1 Initial Render
**Test ID**: CP-001
**Priority**: High
**Description**: Verify ChatPanel renders correctly

**Test Steps**:
1. Navigate to `/design`
2. View Panel 1 (Chat)

**Expected Results**:
- ✅ Welcome message displays
- ✅ Input field visible
- ✅ Send button visible
- ✅ Suggested prompts visible

**Automated Test**: `tests/unit/ChatPanel.test.tsx`

---

### 3.2 Session Initialization
**Test ID**: CP-002
**Priority**: Critical
**Description**: Test chat session creation

**Test Steps**:
1. Load ChatPanel
2. Wait for session initialization
3. Verify API call made

**Expected Results**:
- ✅ `startChatSession()` called
- ✅ Session ID stored in state
- ✅ No errors in console

**Automated Test**: `tests/integration/ChatPanel.test.tsx`

---

### 3.3 Send Message - Success
**Test ID**: CP-003
**Priority**: Critical
**Description**: Test sending chat message

**Test Steps**:
1. Type "I need a modern sofa"
2. Click Send button
3. Wait for response

**Expected Results**:
- ✅ User message appears in chat
- ✅ Loading indicator shows
- ✅ AI response appears
- ✅ Input field clears

**Automated Test**: `tests/integration/ChatPanel.test.tsx`

---

### 3.4 Product Recommendations
**Test ID**: CP-004
**Priority**: Critical
**Description**: Test product recommendation flow

**Test Steps**:
1. Send message requesting products
2. Wait for AI response
3. Verify product fetch triggered
4. Check Panel 2 updates

**Expected Results**:
- ✅ AI returns `product_matching_criteria`
- ✅ `getProducts()` called with criteria
- ✅ Products emitted to Panel 2
- ✅ Products display in Panel 2

**Automated Test**: `tests/integration/ChatToProducts.test.tsx`

---

### 3.5 Send Message with Room Image
**Test ID**: CP-005
**Priority**: High
**Description**: Test message with image context

**Test Steps**:
1. Load page with room image
2. Send chat message
3. Verify API call includes image

**Expected Results**:
- ✅ `sendChatMessage()` includes `image_data`
- ✅ Room image context used by AI

**Automated Test**: `tests/integration/ChatPanel.test.tsx`

---

### 3.6 Error Handling - API Failure
**Test ID**: CP-006
**Priority**: High
**Description**: Test chat API error handling

**Test Steps**:
1. Mock API failure
2. Send message
3. Verify error handling

**Expected Results**:
- ✅ Error message displayed
- ✅ User-friendly text shown
- ✅ UI remains functional

**Automated Test**: `tests/integration/ChatPanel.test.tsx`

---

### 3.7 Suggested Prompts
**Test ID**: CP-007
**Priority**: Medium
**Description**: Test suggested prompt clicks

**Test Steps**:
1. View initial chat state
2. Click suggested prompt
3. Verify input populated

**Expected Results**:
- ✅ Input field populated with prompt text
- ✅ User can edit before sending

**Automated Test**: `tests/unit/ChatPanel.test.tsx`

---

## 4. ProductDiscoveryPanel Tests

### 4.1 Empty State
**Test ID**: PDP-001
**Priority**: High
**Description**: Verify empty state display

**Test Steps**:
1. Load Panel 2 with no products
2. Verify empty state

**Expected Results**:
- ✅ Empty state message visible
- ✅ Icon displayed
- ✅ Helpful text shown

**Automated Test**: `tests/unit/ProductDiscoveryPanel.test.tsx`

---

### 4.2 Product Display
**Test ID**: PDP-002
**Priority**: Critical
**Description**: Test product grid rendering

**Test Steps**:
1. Pass mock products array
2. Verify all products render

**Expected Results**:
- ✅ Product cards display
- ✅ Images load
- ✅ Prices show
- ✅ Product type badges visible
- ✅ Website links present

**Automated Test**: `tests/unit/ProductDiscoveryPanel.test.tsx`

---

### 4.3 Product Selection - Single
**Test ID**: PDP-003
**Priority**: Critical
**Description**: Test selecting a product

**Test Steps**:
1. Click "Select" on a product
2. Verify selection state

**Expected Results**:
- ✅ Product card highlighted
- ✅ "Selected" button shows
- ✅ "Add to Canvas" button enabled
- ✅ Only one product selected

**Automated Test**: `tests/unit/ProductDiscoveryPanel.test.tsx`

---

### 4.4 Product Selection - Type Constraint
**Test ID**: PDP-004
**Priority**: Critical
**Description**: Test one-per-type constraint

**Test Steps**:
1. Select Product A (type: sofa)
2. Click "Add to Canvas"
3. Select Product B (type: sofa)
4. Try to add to canvas

**Expected Results**:
- ✅ Warning message shows
- ✅ "Add to Canvas" disabled
- ✅ Tooltip explains constraint

**Automated Test**: `tests/integration/ProductDiscoveryPanel.test.tsx`

---

### 4.5 Add to Canvas
**Test ID**: PDP-005
**Priority**: Critical
**Description**: Test adding product to canvas

**Test Steps**:
1. Select product
2. Click "Add to Canvas"
3. Verify emission to parent

**Expected Results**:
- ✅ `onAddToCanvas` callback fired
- ✅ Product data passed correctly
- ✅ Button changes to "Added ✓"
- ✅ Product badge shows "In Canvas"

**Automated Test**: `tests/integration/ProductDiscoveryPanel.test.tsx`

---

### 4.6 Sorting
**Test ID**: PDP-006
**Priority**: Medium
**Description**: Test product sorting

**Test Steps**:
1. Load products
2. Change sort to "Price: Low to High"
3. Verify order

**Expected Results**:
- ✅ Products reorder correctly
- ✅ Lowest price first
- ✅ All products still visible

**Automated Test**: `tests/unit/ProductDiscoveryPanel.test.tsx`

---

### 4.7 In Canvas Indicator
**Test ID**: PDP-007
**Priority**: High
**Description**: Test "In Canvas" badge

**Test Steps**:
1. Add product to canvas
2. Verify badge appears
3. Check product card state

**Expected Results**:
- ✅ "In Canvas" badge visible
- ✅ Green background on card
- ✅ "Added ✓" text shows

**Automated Test**: `tests/integration/ProductDiscoveryPanel.test.tsx`

---

## 5. CanvasPanel Tests

### 5.1 Initial Render - No Data
**Test ID**: CNV-001
**Priority**: High
**Description**: Verify empty canvas state

**Test Steps**:
1. Load Panel 3 with no data
2. Verify empty states

**Expected Results**:
- ✅ "No products added yet" message
- ✅ Room image placeholder
- ✅ "Upload Room Image" button visible
- ✅ "Visualize" button disabled

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.2 Room Image Display
**Test ID**: CNV-002
**Priority**: Critical
**Description**: Test room image rendering

**Test Steps**:
1. Pass room image prop
2. Verify display

**Expected Results**:
- ✅ Room image thumbnail shows
- ✅ "Change Image" button visible
- ✅ Aspect ratio preserved

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.3 Room Image Upload
**Test ID**: CNV-003
**Priority**: High
**Description**: Test uploading room image in canvas

**Test Steps**:
1. Click "Upload Room Image"
2. Select file
3. Verify upload

**Expected Results**:
- ✅ File picker opens
- ✅ Image validates
- ✅ Callback fired with image data
- ✅ Preview updates

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.4 Products in Canvas - Grid View
**Test ID**: CNV-004
**Priority**: High
**Description**: Test product grid display

**Test Steps**:
1. Add products to canvas
2. Select grid view
3. Verify layout

**Expected Results**:
- ✅ Products in 2-column grid
- ✅ Thumbnails visible
- ✅ Prices shown
- ✅ Remove buttons on hover

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.5 Products in Canvas - List View
**Test ID**: CNV-005
**Priority**: High
**Description**: Test product list display

**Test Steps**:
1. Add products to canvas
2. Select list view
3. Verify layout

**Expected Results**:
- ✅ Products in vertical list
- ✅ Detailed information visible
- ✅ Remove buttons present
- ✅ Source website shown

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.6 Remove Product
**Test ID**: CNV-006
**Priority**: High
**Description**: Test removing product from canvas

**Test Steps**:
1. Add products to canvas
2. Click remove button
3. Verify removal

**Expected Results**:
- ✅ Product removed from list
- ✅ Total count updates
- ✅ Total price updates
- ✅ Callback fired

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.7 Clear All Products
**Test ID**: CNV-007
**Priority**: Medium
**Description**: Test clear all functionality

**Test Steps**:
1. Add multiple products
2. Click "Clear All"
3. Verify all removed

**Expected Results**:
- ✅ All products removed
- ✅ Count shows 0
- ✅ Empty state displays
- ✅ Callback fired

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.8 Visualize Button - Disabled State
**Test ID**: CNV-008
**Priority**: High
**Description**: Test visualize button validation

**Test Steps**:
1. Test various states:
   - No room image, no products
   - Room image, no products
   - No room image, has products
2. Verify button disabled

**Expected Results**:
- ✅ Button disabled when incomplete
- ✅ Tooltip explains requirement
- ✅ Helper text shows

**Automated Test**: `tests/unit/CanvasPanel.test.tsx`

---

### 5.9 Visualize Button - Enabled State
**Test ID**: CNV-009
**Priority**: Critical
**Description**: Test visualize when ready

**Test Steps**:
1. Add room image
2. Add products
3. Verify button enabled

**Expected Results**:
- ✅ Button enabled
- ✅ Gradient styling visible
- ✅ Click triggers visualization

**Automated Test**: `tests/integration/CanvasPanel.test.tsx`

---

### 5.10 Visualization API Call
**Test ID**: CNV-010
**Priority**: Critical
**Description**: Test visualization API integration

**Test Steps**:
1. Click "Visualize Room"
2. Wait for API response
3. Verify result

**Expected Results**:
- ✅ `visualizeRoom()` API called
- ✅ Loading state shows
- ✅ Session ID included
- ✅ Products and image sent
- ✅ Result displays on success

**Automated Test**: `tests/integration/Visualization.test.tsx`

---

### 5.11 Visualization Loading State
**Test ID**: CNV-011
**Priority**: High
**Description**: Test loading UI

**Test Steps**:
1. Mock slow API response
2. Click visualize
3. Verify loading state

**Expected Results**:
- ✅ Button shows spinner
- ✅ "Visualizing..." text
- ✅ Button disabled
- ✅ Cannot trigger again

**Automated Test**: `tests/integration/Visualization.test.tsx`

---

### 5.12 Visualization Result Display
**Test ID**: CNV-012
**Priority**: Critical
**Description**: Test result rendering

**Test Steps**:
1. Complete visualization
2. Verify result display

**Expected Results**:
- ✅ Result section appears
- ✅ Visualization image shows
- ✅ "Close Preview" button visible
- ✅ Aspect ratio preserved

**Automated Test**: `tests/integration/Visualization.test.tsx`

---

### 5.13 Visualization Error Handling
**Test ID**: CNV-013
**Priority**: High
**Description**: Test visualization failure

**Test Steps**:
1. Mock API error
2. Click visualize
3. Verify error handling

**Expected Results**:
- ✅ Alert with error message
- ✅ Loading state clears
- ✅ Can retry
- ✅ UI remains functional

**Automated Test**: `tests/integration/Visualization.test.tsx`

---

## 6. End-to-End Workflow Tests

### 6.1 Complete Happy Path
**Test ID**: E2E-001
**Priority**: Critical
**Description**: Test complete user workflow

**Test Steps**:
1. Navigate to landing page
2. Upload room image
3. Click "Upload & Continue"
4. In chat: "I need a modern sofa"
5. Wait for products
6. Select product
7. Click "Add to Canvas"
8. Click "Visualize Room"
9. Wait for result

**Expected Results**:
- ✅ Each step completes successfully
- ✅ Data flows between components
- ✅ Visualization generated
- ✅ No errors in console

**Automated Test**: `tests/e2e/CompleteWorkflow.spec.ts`

---

### 6.2 Skip Upload Flow
**Test ID**: E2E-002
**Priority**: High
**Description**: Test workflow without initial upload

**Test Steps**:
1. Click "Upload Later"
2. Navigate to design
3. Upload image in Panel 3
4. Continue with products
5. Visualize

**Expected Results**:
- ✅ Upload works in Panel 3
- ✅ Rest of flow normal
- ✅ Visualization works

**Automated Test**: `tests/e2e/SkipUploadFlow.spec.ts`

---

### 6.3 Multiple Products Flow
**Test ID**: E2E-003
**Priority**: High
**Description**: Test adding multiple different product types

**Test Steps**:
1. Chat: "I need furniture for my living room"
2. Add sofa to canvas
3. Chat: "Show me coffee tables"
4. Add table to canvas
5. Visualize with both

**Expected Results**:
- ✅ Both products in canvas
- ✅ Total price updated
- ✅ Visualization includes both

**Automated Test**: `tests/e2e/MultipleProducts.spec.ts`

---

### 6.4 Product Replacement Flow
**Test ID**: E2E-004
**Priority**: High
**Description**: Test replacing product of same type

**Test Steps**:
1. Add Sofa A to canvas
2. Find Sofa B
3. Remove Sofa A
4. Add Sofa B
5. Visualize

**Expected Results**:
- ✅ Can remove and add same type
- ✅ Only one sofa in canvas
- ✅ Visualization uses new product

**Automated Test**: `tests/e2e/ProductReplacement.spec.ts`

---

### 6.5 Mobile Complete Flow
**Test ID**: E2E-005
**Priority**: High
**Description**: Test entire flow on mobile

**Test Steps**:
1. Set mobile viewport
2. Complete full workflow
3. Use tab navigation

**Expected Results**:
- ✅ All features work on mobile
- ✅ Tab switching smooth
- ✅ Upload works
- ✅ Visualization works

**Automated Test**: `tests/e2e/MobileWorkflow.spec.ts`

---

## 7. Responsive Design Tests

### 7.1 Desktop Breakpoint (1920px)
**Test ID**: RD-001
**Priority**: High
**Description**: Test large desktop layout

**Expected Results**:
- ✅ Three panels side-by-side
- ✅ No horizontal scroll
- ✅ Proper spacing

**Automated Test**: `tests/visual/Responsive.test.tsx`

---

### 7.2 Laptop Breakpoint (1280px)
**Test ID**: RD-002
**Priority**: High
**Description**: Test standard laptop

**Expected Results**:
- ✅ Three panels visible
- ✅ Product grid adjusts
- ✅ Readable text

**Automated Test**: `tests/visual/Responsive.test.tsx`

---

### 7.3 Tablet Breakpoint (768px)
**Test ID**: RD-003
**Priority**: High
**Description**: Test tablet layout

**Expected Results**:
- ✅ Tabs visible
- ✅ Single panel display
- ✅ Touch-friendly

**Automated Test**: `tests/visual/Responsive.test.tsx`

---

### 7.4 Mobile Breakpoint (375px)
**Test ID**: RD-004
**Priority**: High
**Description**: Test mobile phone

**Expected Results**:
- ✅ Stacked layout
- ✅ Tabs work
- ✅ Text readable
- ✅ Touch targets >44px

**Automated Test**: `tests/visual/Responsive.test.tsx`

---

## 8. Accessibility Tests

### 8.1 Keyboard Navigation
**Test ID**: A11Y-001
**Priority**: Critical
**Description**: Test keyboard-only navigation

**Test Steps**:
1. Navigate with Tab key
2. Activate with Enter/Space
3. Complete workflow

**Expected Results**:
- ✅ All interactive elements accessible
- ✅ Focus indicators visible
- ✅ Logical tab order
- ✅ Can complete all actions

**Automated Test**: `tests/a11y/KeyboardNav.test.tsx`

---

### 8.2 Screen Reader Compatibility
**Test ID**: A11Y-002
**Priority**: Critical
**Description**: Test with screen reader

**Expected Results**:
- ✅ All text announced
- ✅ ARIA labels present
- ✅ Role attributes correct
- ✅ State changes announced

**Automated Test**: `tests/a11y/ScreenReader.test.tsx`

---

### 8.3 Color Contrast
**Test ID**: A11Y-003
**Priority**: High
**Description**: Verify WCAG color contrast

**Expected Results**:
- ✅ All text meets 4.5:1 ratio
- ✅ UI elements meet 3:1 ratio
- ✅ Error states visible

**Automated Test**: `tests/a11y/ColorContrast.test.tsx`

---

### 8.4 Form Labels
**Test ID**: A11Y-004
**Priority**: High
**Description**: Verify form accessibility

**Expected Results**:
- ✅ All inputs have labels
- ✅ Error messages associated
- ✅ Required fields indicated

**Automated Test**: `tests/a11y/Forms.test.tsx`

---

## 9. Performance Tests

### 9.1 Initial Load Time
**Test ID**: PERF-001
**Priority**: High
**Description**: Measure page load performance

**Expected Results**:
- ✅ Landing page <2s
- ✅ Design page <3s
- ✅ No blocking resources

**Automated Test**: `tests/performance/LoadTime.test.ts`

---

### 9.2 API Response Time
**Test ID**: PERF-002
**Priority**: High
**Description**: Measure API call times

**Expected Results**:
- ✅ Chat message <5s
- ✅ Product fetch <2s
- ✅ Visualization <45s

**Automated Test**: `tests/performance/APITiming.test.ts`

---

### 9.3 Image Optimization
**Test ID**: PERF-003
**Priority**: Medium
**Description**: Verify image loading

**Expected Results**:
- ✅ Images lazy load
- ✅ Next.js optimization active
- ✅ Proper caching headers

**Automated Test**: `tests/performance/ImageOptimization.test.ts`

---

## 10. Error Handling Tests

### 10.1 Network Failure
**Test ID**: ERR-001
**Priority**: Critical
**Description**: Test offline behavior

**Test Steps**:
1. Simulate network failure
2. Try chat message
3. Verify error handling

**Expected Results**:
- ✅ User-friendly error message
- ✅ Retry option available
- ✅ UI remains stable

**Automated Test**: `tests/integration/NetworkErrors.test.tsx`

---

### 10.2 API Errors
**Test ID**: ERR-002
**Priority**: Critical
**Description**: Test API error responses

**Test Steps**:
1. Mock 500 error
2. Mock 404 error
3. Mock timeout

**Expected Results**:
- ✅ Specific error messages
- ✅ Graceful degradation
- ✅ No crashes

**Automated Test**: `tests/integration/APIErrors.test.tsx`

---

### 10.3 Invalid Data
**Test ID**: ERR-003
**Priority**: High
**Description**: Test data validation

**Test Steps**:
1. Send malformed data
2. Verify validation

**Expected Results**:
- ✅ Data validated
- ✅ Errors caught
- ✅ User notified

**Automated Test**: `tests/integration/DataValidation.test.tsx`

---

## Test Execution

### Running Tests

```bash
# Run all tests
npm test

# Run unit tests only
npm test:unit

# Run integration tests
npm test:integration

# Run E2E tests
npm test:e2e

# Run with coverage
npm test:coverage

# Run specific test file
npm test LandingPage.test.tsx

# Run in watch mode
npm test:watch
```

---

## Test Coverage Requirements

| Test Type | Minimum Coverage | Current Coverage |
|-----------|-----------------|------------------|
| Unit Tests | 80% | TBD |
| Integration Tests | 70% | TBD |
| E2E Tests | 100% critical paths | TBD |
| Accessibility | WCAG 2.1 AA | TBD |

---

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: UI V2 Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: cd frontend && npm install
      - name: Run unit tests
        run: cd frontend && npm test:unit
      - name: Run integration tests
        run: cd frontend && npm test:integration
      - name: Run E2E tests
        run: cd frontend && npm test:e2e
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Test Data

### Mock Data Files
- `tests/fixtures/products.json` - Sample products
- `tests/fixtures/chatResponses.json` - Mock AI responses
- `tests/fixtures/roomImages.json` - Base64 test images
- `tests/fixtures/visualizations.json` - Mock visualization results

---

## Known Issues & Limitations

1. **Flaky Tests**: E2E tests may be flaky due to network timing
2. **Browser Compatibility**: Tests run primarily in Chrome
3. **Mock Limitations**: Some AI responses are simplified
4. **Performance**: E2E tests slow on CI

---

## Test Maintenance

### Regular Tasks
- [ ] Update test data monthly
- [ ] Review and update expected results
- [ ] Add tests for new features
- [ ] Fix flaky tests
- [ ] Update snapshots
- [ ] Review coverage reports

---

## Contact

For test-related questions:
- Check test documentation
- Review test files in `/tests` directory
- Consult team testing guidelines
