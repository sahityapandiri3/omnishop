'use client';

import { ReactNode, useRef } from 'react';
import { Panel, Group, GroupImperativeHandle } from 'react-resizable-panels';
import { PanelResizeHandle } from '@/components/ui/PanelResizeHandle';

// Default panel sizes (percentages)
const DEFAULT_SIZES = {
  chat: 25,
  products: 35,
  canvas: 40,
};

// Minimum sizes to ensure usability (percentages)
const MIN_SIZES = {
  chat: 15,
  products: 20,
  canvas: 25,
};

// localStorage key for persistence
const STORAGE_KEY = 'omnishop-design-panels';

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
  const panelGroupRef = useRef<GroupImperativeHandle>(null);

  return (
    <Group
      groupRef={panelGroupRef}
      orientation="horizontal"
      id={STORAGE_KEY}
      className={`h-full ${className}`}
    >
      <Panel
        id="chat-panel"
        defaultSize={DEFAULT_SIZES.chat}
        minSize={MIN_SIZES.chat}
        className="bg-white dark:bg-neutral-800 overflow-hidden"
      >
        <div className="h-full">
          {chatPanel}
        </div>
      </Panel>

      <PanelResizeHandle id="chat-products-handle" />

      <Panel
        id="products-panel"
        defaultSize={DEFAULT_SIZES.products}
        minSize={MIN_SIZES.products}
        className="bg-white dark:bg-neutral-800 overflow-hidden"
      >
        <div className="h-full">
          {productsPanel}
        </div>
      </Panel>

      <PanelResizeHandle id="products-canvas-handle" />

      <Panel
        id="canvas-panel"
        defaultSize={DEFAULT_SIZES.canvas}
        minSize={MIN_SIZES.canvas}
        className="bg-white dark:bg-neutral-800 overflow-hidden"
      >
        {canvasPanel}
      </Panel>
    </Group>
  );
}

export default ResizablePanelLayout;
