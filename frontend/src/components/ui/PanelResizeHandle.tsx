'use client';

import { Separator } from 'react-resizable-panels';

interface PanelResizeHandleProps {
  id?: string;
}

/**
 * Styled vertical resize handle for panel layout.
 * - Shows a subtle line by default
 * - Expands and highlights on hover
 * - Shows grip dots for visual affordance
 */
export function PanelResizeHandle({ id }: PanelResizeHandleProps) {
  return (
    <Separator
      id={id}
      className="
        group relative w-1 bg-transparent transition-all duration-150
        after:absolute after:inset-y-0 after:left-1/2 after:-translate-x-1/2
        after:w-px after:bg-neutral-200 dark:after:bg-neutral-700
        hover:w-2 hover:bg-neutral-100 dark:hover:bg-neutral-700/50
        hover:after:w-0.5 hover:after:bg-purple-500
        active:bg-purple-100 dark:active:bg-purple-900/30
        active:after:bg-purple-600
        cursor-col-resize
        focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500
      "
    >
      {/* Grip dots on hover */}
      <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex flex-col items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="w-1 h-1 rounded-full bg-neutral-400 dark:bg-neutral-500" />
        <div className="w-1 h-1 rounded-full bg-neutral-400 dark:bg-neutral-500" />
        <div className="w-1 h-1 rounded-full bg-neutral-400 dark:bg-neutral-500" />
      </div>
    </Separator>
  );
}

export default PanelResizeHandle;
