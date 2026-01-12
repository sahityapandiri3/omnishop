'use client';

import { Separator } from 'react-resizable-panels';

interface PanelResizeHandleProps {
  id?: string;
}

/**
 * Styled vertical resize handle for panel layout.
 * Uses data-separator attribute for hover/active styles as recommended by library.
 */
export function PanelResizeHandle({ id }: PanelResizeHandleProps) {
  return (
    <Separator
      id={id}
      style={{
        width: '8px',
        background: '#d1d5db',
        cursor: 'col-resize',
      }}
    />
  );
}

export default PanelResizeHandle;
