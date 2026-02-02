/**
 * Visualization Components
 *
 * Shared components for visualization functionality.
 * These are used by both CanvasPanel (design page) and Admin Curation page.
 */

// Controls
export {
  VisualizationControls,
  ImproveQualityButton,
  VisualizeButton,
  OutdatedWarning,
  TextBasedEditControls,
} from './VisualizationControls';

// Canvas
export {
  VisualizationPreview,
  VisualizationResult,
  RoomImageSection,
} from './VisualizationCanvas';

// Product display
export { ProductCanvas } from './ProductCanvas';

// Room Image Upload (with Previously Uploaded support)
export { RoomImageUpload } from './RoomImageUpload';
