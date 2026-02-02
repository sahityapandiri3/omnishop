'use client';

export type SearchSubMode = 'furniture' | 'walls';

interface SubModeToggleProps {
  subMode: SearchSubMode;
  onSubModeChange: (subMode: SearchSubMode) => void;
}

/**
 * Shared SubModeToggle Component - Furniture and Decor vs Walls
 * Used by both /design page and /admin/curated/new page
 */
export function SubModeToggle({
  subMode,
  onSubModeChange,
}: SubModeToggleProps) {
  return (
    <div className="inline-flex items-center p-0.5 bg-neutral-100 dark:bg-neutral-800 rounded-lg">
      <button
        onClick={() => onSubModeChange('furniture')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center ${
          subMode === 'furniture'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        Furniture & Decor
      </button>
      <button
        onClick={() => onSubModeChange('walls')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all text-center ${
          subMode === 'walls'
            ? 'bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 shadow-sm'
            : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
        }`}
      >
        Walls
      </button>
    </div>
  );
}

export default SubModeToggle;
