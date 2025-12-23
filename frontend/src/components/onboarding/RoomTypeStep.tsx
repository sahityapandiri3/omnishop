'use client';

import { ROOM_TYPE_OPTIONS } from '@/config/styles';

interface RoomTypeStepProps {
  selectedRoom: string | null;
  onSelect: (roomType: string) => void;
}

export function RoomTypeStep({ selectedRoom, onSelect }: RoomTypeStepProps) {
  return (
    <div className="flex flex-col items-center">
      {/* Header */}
      <div className="text-center mb-10">
        <h2 className="text-2xl md:text-3xl font-light text-neutral-900 mb-3">
          Which room are you designing?
        </h2>
        <p className="text-neutral-500 font-light">
          Select the space you want to transform
        </p>
      </div>

      {/* Room Options */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-xl">
        {ROOM_TYPE_OPTIONS.map((room) => {
          const isSelected = selectedRoom === room.id;

          return (
            <button
              key={room.id}
              onClick={() => onSelect(room.id)}
              className={`group relative overflow-hidden rounded-xl transition-all duration-300 ${
                isSelected
                  ? 'ring-2 ring-primary-600 ring-offset-2 shadow-lg scale-[1.02]'
                  : 'hover:shadow-md hover:scale-[1.01]'
              }`}
            >
              {/* Image */}
              <div className="aspect-[4/3] relative overflow-hidden">
                <img
                  src={room.imagePath}
                  alt={room.displayName}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
                {/* Overlay */}
                <div
                  className={`absolute inset-0 transition-opacity duration-300 ${
                    isSelected
                      ? 'bg-primary-600/20'
                      : 'bg-black/0 group-hover:bg-black/10'
                  }`}
                />
              </div>

              {/* Label */}
              <div
                className={`absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/70 to-transparent ${
                  isSelected ? 'from-primary-900/80' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="text-left">
                    <h3 className="text-lg font-medium text-white">
                      {room.displayName}
                    </h3>
                    <p className="text-sm text-white/80 font-light">
                      {room.description}
                    </p>
                  </div>

                  {/* Selection indicator */}
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                      isSelected
                        ? 'border-white bg-white'
                        : 'border-white/50'
                    }`}
                  >
                    {isSelected && (
                      <svg className="w-4 h-4 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Coming Soon Note */}
      <p className="mt-8 text-sm text-neutral-400 text-center">
        More room types coming soon
      </p>
    </div>
  );
}
