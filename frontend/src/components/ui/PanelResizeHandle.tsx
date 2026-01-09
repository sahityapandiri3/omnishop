'use client';

import { Separator } from 'react-resizable-panels';

interface PanelResizeHandleProps {
  id?: string;
}

/**
 * Styled vertical resize handle for panel layout.
 * Wide hit area (8px) for easy grabbing, with visible line in center.
 */
export function PanelResizeHandle({ id }: PanelResizeHandleProps) {
  return (
    <Separator
      id={id}
      className="hover:bg-purple-100 active:bg-purple-200 transition-colors"
      style={{
        width: '8px',
        background: 'linear-gradient(to right, transparent 3px, #d1d5db 3px, #d1d5db 5px, transparent 5px)',
        cursor: 'col-resize',
      }}
    />
  );
}

export default PanelResizeHandle;
