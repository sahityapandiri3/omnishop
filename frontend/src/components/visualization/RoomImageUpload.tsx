'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { projectsAPI, PreviousRoomImage } from '@/utils/api';

interface RoomImageUploadProps {
  /** Current room image (base64 or data URI) */
  roomImage: string | null;
  /** Callback when image is ready (base64 data) - from file upload or previous room
   *  @param imageData - The image data (base64 or data URI)
   *  @param isAlreadyProcessed - If true, furniture is already removed (from previous rooms)
   */
  onImageReady: (imageData: string, isAlreadyProcessed: boolean) => void;
  /** Whether furniture removal is in progress */
  isProcessing?: boolean;
  /** Whether the room is ready (furniture removed) */
  isRoomReady?: boolean;
  /** Project ID for using previous rooms */
  projectId?: string | null;
  /** Whether this is full-screen overlay mode */
  fullScreen?: boolean;
  /** Number of products ready (for full-screen message) */
  productsCount?: number;
  /** Product thumbnails to show in full-screen mode */
  productThumbnails?: Array<{ id: string; image_url?: string; name: string }>;
}

/**
 * Shared component for room image upload with "Previously Uploaded" support.
 * Used by both /design (CanvasPanel) and /admin/curated/new pages.
 */
export function RoomImageUpload({
  roomImage,
  onImageReady,
  isProcessing = false,
  isRoomReady = false,
  projectId,
  fullScreen = false,
  productsCount = 0,
  productThumbnails = [],
}: RoomImageUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadTab, setUploadTab] = useState<'upload' | 'previous'>('upload');
  const [previousRooms, setPreviousRooms] = useState<PreviousRoomImage[]>([]);
  const [loadingPreviousRooms, setLoadingPreviousRooms] = useState(false);
  const [selectedPreviousRoom, setSelectedPreviousRoom] = useState<string | null>(null);
  const [previousRoomsFetched, setPreviousRoomsFetched] = useState(false);
  // State to show the change UI (upload/previous tabs) when clicking "Change" on existing image
  const [showChangeUI, setShowChangeUI] = useState(false);

  // Fetch previous rooms when tab switches to "previous"
  useEffect(() => {
    if (uploadTab === 'previous' && !previousRoomsFetched) {
      let cancelled = false;
      const fetchPreviousRooms = async () => {
        setLoadingPreviousRooms(true);
        try {
          const response = await projectsAPI.getPreviousRooms(projectId || undefined, 50);
          if (!cancelled) {
            setPreviousRooms(response.rooms);
            setPreviousRoomsFetched(true);
          }
        } catch (error) {
          console.error('Failed to fetch previous rooms:', error);
        } finally {
          if (!cancelled) {
            setLoadingPreviousRooms(false);
          }
        }
      };
      fetchPreviousRooms();
      return () => { cancelled = true; };
    }
  }, [uploadTab, previousRoomsFetched, projectId]);

  // Handle file selection and convert to base64
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    // Read file as base64
    const reader = new FileReader();
    reader.onload = (event) => {
      const imageData = event.target?.result as string;
      // New uploads need furniture removal processing
      onImageReady(imageData, false);
      // Close the change UI after upload
      setShowChangeUI(false);
    };
    reader.readAsDataURL(file);

    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [onImageReady]);

  // Handle selecting a previous room image
  const handleSelectPreviousRoom = useCallback(async (room: PreviousRoomImage) => {
    if (!projectId) {
      alert('Please save your project first to use a previous room image');
      return;
    }

    setSelectedPreviousRoom(room.id);
    try {
      const response = await projectsAPI.usePreviousRoom(projectId, room.id, room.source);
      if (response.success && response.clean_room_image) {
        // Previous rooms already have furniture removed - skip processing
        onImageReady(response.clean_room_image, true);
        setUploadTab('upload');
        // Close the change UI after selection
        setShowChangeUI(false);
      }
    } catch (error) {
      console.error('Failed to use previous room:', error);
      alert('Failed to load previous room. Please try again.');
    } finally {
      setSelectedPreviousRoom(null);
    }
  }, [projectId, onImageReady]);

  const formatImageSrc = (image: string) => {
    if (image.startsWith('data:')) return image;
    if (image.startsWith('/9j/') || image.startsWith('iVBOR')) {
      const isJpeg = image.startsWith('/9j/');
      return `data:image/${isJpeg ? 'jpeg' : 'png'};base64,${image}`;
    }
    return `data:image/jpeg;base64,${image}`;
  };

  // Hidden file input (always in DOM)
  const fileInput = (
    <input
      ref={fileInputRef}
      type="file"
      accept="image/*"
      onChange={handleFileChange}
      className="hidden"
    />
  );

  // If room image already exists, show it with change button
  // Unless showChangeUI is true, in which case show the upload/previous tabs
  if (roomImage && !showChangeUI) {
    return (
      <>
        {fileInput}
        <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg overflow-hidden">
          <img
            src={formatImageSrc(roomImage)}
            alt="Room"
            className="w-full h-full object-cover"
          />
          {/* Processing overlay */}
          {isProcessing && (
            <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-10">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-500 mb-2"></div>
              <span className="text-white font-medium text-sm">Processing Image...</span>
            </div>
          )}
          {/* Change button - opens the upload/previous UI */}
          <button
            onClick={() => setShowChangeUI(true)}
            className="absolute bottom-2 right-2 px-3 py-1.5 bg-white/90 dark:bg-neutral-800/90 backdrop-blur text-xs font-medium text-neutral-900 dark:text-white rounded-lg hover:bg-white dark:hover:bg-neutral-700 transition-colors"
          >
            Change
          </button>
          {/* Room ready badge */}
          {isRoomReady && !isProcessing && (
            <div className="absolute top-2 left-2 bg-green-600 text-white px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Room Ready
            </div>
          )}
        </div>
      </>
    );
  }

  // If showChangeUI is true and we have an existing image, show the change UI with Cancel option
  if (roomImage && showChangeUI) {
    return (
      <>
        {fileInput}
        <div>
          {/* Header with Cancel button */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">Change Room Image</span>
            <button
              onClick={() => setShowChangeUI(false)}
              className="text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
            >
              Cancel
            </button>
          </div>

          {/* Tab Toggle */}
          <div className="flex gap-1 p-1 bg-neutral-100 dark:bg-neutral-700 rounded-lg mb-3">
            <button
              onClick={() => setUploadTab('upload')}
              className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                uploadTab === 'upload'
                  ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
              }`}
            >
              Upload New
            </button>
            <button
              onClick={() => setUploadTab('previous')}
              className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                uploadTab === 'previous'
                  ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
              }`}
            >
              Previously Uploaded
              {previousRooms.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-neutral-200 dark:bg-neutral-500 rounded-full">
                  {previousRooms.length}
                </span>
              )}
            </button>
          </div>

          {/* Upload New Tab */}
          {uploadTab === 'upload' && (
            <div className="aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg flex flex-col items-center justify-center p-4 border-2 border-dashed border-neutral-300 dark:border-neutral-600">
              <svg
                className="w-10 h-10 text-neutral-400 mb-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 bg-neutral-800 hover:bg-neutral-900 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Upload New Room
              </button>
              <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-2">
                JPG, PNG, WEBP • Max 10MB
              </p>
            </div>
          )}

          {/* Previously Uploaded Tab */}
          {uploadTab === 'previous' && (
            <PreviousRoomsGrid
              rooms={previousRooms}
              loading={loadingPreviousRooms}
              selectedId={selectedPreviousRoom}
              onSelect={handleSelectPreviousRoom}
              onSwitchToUpload={() => setUploadTab('upload')}
            />
          )}
        </div>
      </>
    );
  }

  // Full-screen overlay mode
  if (fullScreen) {
    return (
      <div className="absolute inset-0 z-20 bg-gradient-to-br from-neutral-100 to-neutral-200 dark:from-neutral-800 dark:to-neutral-900 flex flex-col items-center justify-center p-6">
        {fileInput}
        <div className="max-w-sm text-center">
          {/* Icon */}
          <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-neutral-600 to-neutral-700 rounded-2xl flex items-center justify-center shadow-lg">
            <svg
              className="w-10 h-10 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-neutral-900 dark:text-white mb-3">
            Upload Your Room
          </h2>

          {/* Description */}
          {productsCount > 0 && (
            <p className="text-neutral-600 dark:text-neutral-400 mb-2">
              You have <span className="font-semibold text-neutral-700 dark:text-neutral-400">{productsCount} curated products</span> ready to visualize!
            </p>
          )}
          <p className="text-sm text-neutral-500 dark:text-neutral-500 mb-4">
            Add a room photo to see how these products will look in your space.
          </p>

          {/* Tab Toggle */}
          <div className="flex gap-1 p-1 bg-neutral-200/80 dark:bg-neutral-700 rounded-lg mb-4 w-full">
            <button
              onClick={() => setUploadTab('upload')}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                uploadTab === 'upload'
                  ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
              }`}
            >
              Upload New
            </button>
            <button
              onClick={() => setUploadTab('previous')}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                uploadTab === 'previous'
                  ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
              }`}
            >
              Previously Uploaded
              {previousRooms.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-neutral-200 dark:bg-neutral-500 rounded-full">
                  {previousRooms.length}
                </span>
              )}
            </button>
          </div>

          {/* Upload New Tab */}
          {uploadTab === 'upload' && (
            <>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full py-4 px-6 bg-gradient-to-r from-neutral-700 to-neutral-800 hover:from-neutral-800 hover:to-neutral-900 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Upload Room Photo
              </button>
              <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-3">
                JPG, PNG, WEBP • Max 10MB
              </p>
            </>
          )}

          {/* Previously Uploaded Tab */}
          {uploadTab === 'previous' && (
            <PreviousRoomsGrid
              rooms={previousRooms}
              loading={loadingPreviousRooms}
              selectedId={selectedPreviousRoom}
              onSelect={handleSelectPreviousRoom}
              onSwitchToUpload={() => setUploadTab('upload')}
              large
            />
          )}

          {/* Products preview */}
          {productThumbnails.length > 0 && (
            <div className="mt-6 pt-6 border-t border-neutral-200 dark:border-neutral-700">
              <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">Products ready to visualize:</p>
              <div className="flex justify-center gap-2 flex-wrap">
                {productThumbnails.slice(0, 4).map((product) => (
                  <div key={product.id} className="w-12 h-12 bg-white dark:bg-neutral-700 rounded-lg shadow overflow-hidden">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-neutral-400">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                        </svg>
                      </div>
                    )}
                  </div>
                ))}
                {productThumbnails.length > 4 && (
                  <div className="w-12 h-12 bg-neutral-100 dark:bg-neutral-700 rounded-lg flex items-center justify-center text-xs font-semibold text-neutral-600 dark:text-neutral-300">
                    +{productThumbnails.length - 4}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Regular upload area (in collapsible section)
  return (
    <>
      {fileInput}
      <div>
        {/* Tab Toggle */}
        <div className="flex gap-1 p-1 bg-neutral-100 dark:bg-neutral-700 rounded-lg mb-3">
          <button
            onClick={() => setUploadTab('upload')}
            className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              uploadTab === 'upload'
                ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
            }`}
          >
            Upload New
          </button>
          <button
            onClick={() => setUploadTab('previous')}
            className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              uploadTab === 'previous'
                ? 'bg-white dark:bg-neutral-600 text-neutral-900 dark:text-white shadow-sm'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
            }`}
          >
            Previously Uploaded
            {previousRooms.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-neutral-200 dark:bg-neutral-500 rounded-full">
                {previousRooms.length}
              </span>
            )}
          </button>
        </div>

        {/* Upload New Tab */}
        {uploadTab === 'upload' && (
          <div className="aspect-video bg-neutral-100 dark:bg-neutral-700 rounded-lg flex flex-col items-center justify-center p-4 border-2 border-dashed border-neutral-300 dark:border-neutral-600">
            <svg
              className="w-12 h-12 text-neutral-400 mb-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-2 bg-neutral-800 hover:bg-neutral-900 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Upload Your Room Image
            </button>
            <p className="text-xs text-neutral-600 dark:text-neutral-300 mt-2 text-center">
              Add your room image to style with these products
            </p>
            <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
              JPG, PNG, WEBP • Max 10MB
            </p>
          </div>
        )}

        {/* Previously Uploaded Tab */}
        {uploadTab === 'previous' && (
          <PreviousRoomsGrid
            rooms={previousRooms}
            loading={loadingPreviousRooms}
            selectedId={selectedPreviousRoom}
            onSelect={handleSelectPreviousRoom}
            onSwitchToUpload={() => setUploadTab('upload')}
          />
        )}
      </div>
    </>
  );
}

/**
 * Grid display for previously uploaded rooms
 */
function PreviousRoomsGrid({
  rooms,
  loading,
  selectedId,
  onSelect,
  onSwitchToUpload,
  large = false,
}: {
  rooms: PreviousRoomImage[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (room: PreviousRoomImage) => void;
  onSwitchToUpload: () => void;
  large?: boolean;
}) {
  if (loading) {
    return (
      <div className={`flex items-center justify-center ${large ? 'py-8' : 'py-8 min-h-[150px]'}`}>
        <div className={`animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-600 ${large ? 'h-8 w-8' : 'h-6 w-6'}`}></div>
      </div>
    );
  }

  if (rooms.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center text-center ${large ? 'py-8' : 'py-8 min-h-[150px]'}`}>
        <svg className={`text-neutral-300 dark:text-neutral-600 mb-3 ${large ? 'w-12 h-12' : 'w-10 h-10'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <p className={`text-neutral-500 dark:text-neutral-400 ${large ? 'text-sm mb-1' : 'text-sm'}`}>No previous rooms yet</p>
        {large && (
          <p className="text-xs text-neutral-400 dark:text-neutral-500 mb-3">
            Upload your first room to get started
          </p>
        )}
        <button
          onClick={onSwitchToUpload}
          className={large
            ? "px-4 py-2 bg-neutral-700 hover:bg-neutral-800 text-white text-sm font-medium rounded-lg transition-colors"
            : "mt-2 text-xs text-neutral-600 dark:text-neutral-300 hover:underline"
          }
        >
          {large ? 'Upload New Room' : 'Upload your first room'}
        </button>
      </div>
    );
  }

  return (
    <div className={`grid grid-cols-2 ${large ? 'gap-3 max-h-[300px] overflow-y-auto w-full min-h-[180px]' : 'gap-2 min-h-[150px]'}`}>
      {rooms.map((room) => (
        <button
          key={room.id}
          onClick={() => onSelect(room)}
          disabled={selectedId === room.id}
          className={`relative aspect-[4/3] ${large ? 'rounded-xl' : 'rounded-lg'} overflow-hidden border-2 transition-all ${
            selectedId === room.id
              ? 'border-purple-500 ring-2 ring-purple-200'
              : `border-transparent ${large ? 'hover:border-neutral-400 dark:hover:border-neutral-500' : 'hover:border-neutral-300 dark:hover:border-neutral-600'}`
          }`}
        >
          <img
            src={`data:image/jpeg;base64,${room.thumbnail}`}
            alt={room.name || 'Previous room'}
            className="w-full h-full object-cover"
          />
          {/* Loading overlay */}
          {selectedId === room.id && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
              <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
            </div>
          )}
          {/* Hover info */}
          <div className={`absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 ${large ? '' : 'opacity-0 hover:opacity-100 transition-opacity'}`}>
            <p className={`text-white truncate ${large ? 'text-xs' : 'text-[10px]'}`}>{room.name || 'Room'}</p>
            <p className={`text-white/70 ${large ? 'text-[10px]' : 'text-[9px]'}`}>
              {new Date(room.created_at).toLocaleDateString()}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
}

export default RoomImageUpload;
