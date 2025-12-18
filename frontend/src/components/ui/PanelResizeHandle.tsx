'use client';

import { Separator } from 'react-resizable-panels';

interface PanelResizeHandleProps {
  id?: string;
}

/**
 * Styled vertical resize handle for panel layout.
 * Single line that highlights purple on hover.
 */
export function PanelResizeHandle({ id }: PanelResizeHandleProps) {
  return (
    <Separator
      id={id}
      style={{
        width: '1px',
        backgroundColor: '#e5e5e5',
        border: 'none',
        outline: 'none',
        boxShadow: 'none',
        cursor: 'col-resize',
        transition: 'background-color 150ms',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = '#a855f7';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = '#e5e5e5';
      }}
    />
  );
}

export default PanelResizeHandle;
