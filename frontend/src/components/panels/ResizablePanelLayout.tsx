'use client';

import { ReactNode, Component, ErrorInfo, useState, useRef, useCallback, useEffect } from 'react';

// Default panel sizes (percentages)
const DEFAULT_SIZES = {
  chat: 25,
  products: 35,
  canvas: 40,
};

// Minimum sizes in pixels
const MIN_SIZES = {
  chat: 200,
  products: 250,
  canvas: 300,
};

// Error Boundary to catch panel crashes
class PanelErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode; name: string },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: ReactNode; fallback?: ReactNode; name: string }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[${this.props.name}] Panel error:`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="h-full flex items-center justify-center bg-red-50 p-4">
            <div className="text-center">
              <p className="text-red-600 font-medium">Panel Error</p>
              <button
                onClick={() => this.setState({ hasError: false })}
                className="mt-2 px-3 py-1 bg-red-600 text-white rounded text-sm"
              >
                Retry
              </button>
            </div>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

// Resize handle component
function ResizeHandle({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      className="w-1 bg-neutral-200 hover:bg-primary-400 cursor-col-resize transition-colors flex-shrink-0"
      onMouseDown={onMouseDown}
      style={{ touchAction: 'none' }}
    />
  );
}

interface ResizablePanelLayoutProps {
  chatPanel: ReactNode;
  productsPanel: ReactNode;
  canvasPanel: ReactNode;
  className?: string;
}

export function ResizablePanelLayout({
  chatPanel,
  productsPanel,
  canvasPanel,
  className = '',
}: ResizablePanelLayoutProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [sizes, setSizes] = useState([DEFAULT_SIZES.chat, DEFAULT_SIZES.products, DEFAULT_SIZES.canvas]);
  const draggingRef = useRef<{ index: number; startX: number; startSizes: number[] } | null>(null);

  const handleMouseDown = useCallback((index: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = {
      index,
      startX: e.clientX,
      startSizes: [...sizes],
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [sizes]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current || !containerRef.current) return;

      const { index, startX, startSizes } = draggingRef.current;
      const containerWidth = containerRef.current.offsetWidth;
      const deltaX = e.clientX - startX;
      const deltaPercent = (deltaX / containerWidth) * 100;

      const newSizes = [...startSizes];

      // Adjust the panel being resized and the next panel
      newSizes[index] = Math.max(10, startSizes[index] + deltaPercent);
      newSizes[index + 1] = Math.max(10, startSizes[index + 1] - deltaPercent);

      // Ensure total is still 100%
      const total = newSizes.reduce((a, b) => a + b, 0);
      if (Math.abs(total - 100) < 1) {
        setSizes(newSizes);
      }
    };

    const handleMouseUp = () => {
      if (draggingRef.current) {
        draggingRef.current = null;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  return (
    <div ref={containerRef} className={`h-full flex ${className}`}>
      {/* Chat Panel */}
      <div
        className="h-full overflow-hidden bg-white dark:bg-neutral-800"
        style={{ width: `${sizes[0]}%`, minWidth: MIN_SIZES.chat }}
      >
        <PanelErrorBoundary name="Chat">
          <div className="h-full">{chatPanel}</div>
        </PanelErrorBoundary>
      </div>

      <ResizeHandle onMouseDown={handleMouseDown(0)} />

      {/* Products Panel */}
      <div
        className="h-full overflow-hidden bg-white dark:bg-neutral-800"
        style={{ width: `${sizes[1]}%`, minWidth: MIN_SIZES.products }}
      >
        <PanelErrorBoundary name="Products">
          <div className="h-full">{productsPanel}</div>
        </PanelErrorBoundary>
      </div>

      <ResizeHandle onMouseDown={handleMouseDown(1)} />

      {/* Canvas Panel */}
      <div
        className="h-full overflow-hidden bg-white dark:bg-neutral-800 flex-1"
        style={{ minWidth: MIN_SIZES.canvas }}
      >
        <PanelErrorBoundary name="Canvas">
          {canvasPanel}
        </PanelErrorBoundary>
      </div>
    </div>
  );
}

export default ResizablePanelLayout;
