'use client';

import { STYLE_OPTIONS } from '@/config/styles';

interface StylePreferenceStepProps {
  primaryStyle: string | null;
  secondaryStyle: string | null;
  onSelect: (primary: string | null, secondary: string | null) => void;
}

export function StylePreferenceStep({
  primaryStyle,
  secondaryStyle,
  onSelect,
}: StylePreferenceStepProps) {
  const handleStyleClick = (styleId: string) => {
    if (primaryStyle === styleId) {
      // Deselect primary, promote secondary to primary
      onSelect(secondaryStyle, null);
    } else if (secondaryStyle === styleId) {
      // Deselect secondary
      onSelect(primaryStyle, null);
    } else if (!primaryStyle) {
      // No primary selected, set as primary
      onSelect(styleId, secondaryStyle);
    } else if (!secondaryStyle) {
      // Primary exists, set as secondary
      onSelect(primaryStyle, styleId);
    } else {
      // Both exist, replace secondary
      onSelect(primaryStyle, styleId);
    }
  };

  const getSelectionState = (styleId: string): 'primary' | 'secondary' | null => {
    if (primaryStyle === styleId) return 'primary';
    if (secondaryStyle === styleId) return 'secondary';
    return null;
  };

  return (
    <div className="flex flex-col items-center">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-2xl md:text-3xl font-light text-neutral-900 mb-3">
          What's your style?
        </h2>
        <p className="text-neutral-500 font-light">
          Select your primary and secondary style preferences
        </p>
      </div>

      {/* Selection Summary */}
      <div className="flex items-center gap-4 mb-8 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-neutral-800 text-white flex items-center justify-center text-xs font-medium">
            1
          </span>
          <span className={primaryStyle ? 'text-neutral-900' : 'text-neutral-400'}>
            {primaryStyle
              ? STYLE_OPTIONS.find((s) => s.id === primaryStyle)?.displayName
              : 'Primary'}
          </span>
        </div>
        <div className="w-px h-4 bg-neutral-300" />
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-neutral-400 text-white flex items-center justify-center text-xs font-medium">
            2
          </span>
          <span className={secondaryStyle ? 'text-neutral-900' : 'text-neutral-400'}>
            {secondaryStyle
              ? STYLE_OPTIONS.find((s) => s.id === secondaryStyle)?.displayName
              : 'Secondary (optional)'}
          </span>
        </div>
      </div>

      {/* Style Grid - Increased size by 20% */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-5 w-full max-w-6xl">
        {STYLE_OPTIONS.map((style) => {
          const selectionState = getSelectionState(style.id);

          return (
            <button
              key={style.id}
              onClick={() => handleStyleClick(style.id)}
              className={`group relative overflow-hidden rounded-lg transition-all duration-300 ${
                selectionState
                  ? 'ring-2 ring-offset-2 shadow-lg scale-[1.02]'
                  : 'hover:shadow-md hover:scale-[1.01]'
              } ${
                selectionState === 'primary'
                  ? 'ring-neutral-800'
                  : selectionState === 'secondary'
                  ? 'ring-neutral-400'
                  : ''
              }`}
            >
              {/* Image - 20% larger */}
              <div className="aspect-[1.2/1] relative overflow-hidden">
                <img
                  src={style.imagePath}
                  alt={style.displayName}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
                {/* Overlay */}
                <div
                  className={`absolute inset-0 transition-opacity duration-300 ${
                    selectionState === 'primary'
                      ? 'bg-neutral-800/20'
                      : selectionState === 'secondary'
                      ? 'bg-neutral-600/20'
                      : 'bg-black/0 group-hover:bg-black/20'
                  }`}
                />

                {/* Selection Badge */}
                {selectionState && (
                  <div
                    className={`absolute top-2 right-2 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-lg ${
                      selectionState === 'primary' ? 'bg-neutral-800' : 'bg-neutral-500'
                    }`}
                  >
                    {selectionState === 'primary' ? '1' : '2'}
                  </div>
                )}
              </div>

              {/* Label */}
              <div className="p-2.5 bg-white">
                <h3 className="text-sm font-medium text-neutral-900 truncate">
                  {style.displayName}
                </h3>
                <p className="text-xs text-neutral-500 font-light truncate">
                  {style.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Helper Text */}
      <p className="mt-6 text-xs text-neutral-400 text-center">
        Tap once for primary, tap another for secondary. Tap again to deselect.
      </p>
    </div>
  );
}
