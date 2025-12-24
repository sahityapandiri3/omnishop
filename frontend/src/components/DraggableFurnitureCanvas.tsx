'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Stage, Layer, Image as KonvaImage, Rect, Text, Group } from 'react-konva';
import type Konva from 'konva';
import useImage from 'use-image';

export interface FurniturePosition {
  productId: string;
  x: number; // percentage 0-1
  y: number; // percentage 0-1
  label: string;
  width?: number;
  height?: number;
}

interface Product {
  id: string;
  name: string;
  price: number;
  image_url?: string;
  images?: Array<{
    original_url?: string;
    medium_url?: string;
    large_url?: string;
    is_primary?: boolean;
  }>;
}

interface DraggableFurnitureCanvasProps {
  visualizationImage: string; // base64 or URL (fallback)
  baseRoomLayer?: string | null; // base64 image of empty room
  furnitureLayers?: any[]; // array of furniture layer objects from API
  furniturePositions: FurniturePosition[];
  onPositionsChange: (positions: FurniturePosition[]) => void;
  products: Product[];
  containerWidth?: number;
  containerHeight?: number;
}

interface DraggableFurnitureItemProps {
  position: FurniturePosition;
  productImageUrl: string;
  canvasWidth: number;
  canvasHeight: number;
  onDragEnd: (newPosition: { x: number; y: number }) => void;
  isSelected: boolean;
  onSelect: () => void;
}

const DraggableFurnitureItem: React.FC<DraggableFurnitureItemProps> = ({
  position,
  productImageUrl,
  canvasWidth,
  canvasHeight,
  onDragEnd,
  isSelected,
  onSelect,
}) => {
  const [image] = useImage(productImageUrl);
  const boxWidth = (position.width || 0.15) * canvasWidth;
  const boxHeight = (position.height || 0.15) * canvasHeight;
  const x = position.x * canvasWidth;
  const y = position.y * canvasHeight;

  return (
    <Group
      x={x}
      y={y}
      draggable
      onDragEnd={(e: Konva.KonvaEventObject<DragEvent>) => {
        const newX = Math.max(0, Math.min(e.target.x(), canvasWidth - boxWidth));
        const newY = Math.max(0, Math.min(e.target.y(), canvasHeight - boxHeight));

        onDragEnd({
          x: newX / canvasWidth,
          y: newY / canvasHeight,
        });
      }}
      onClick={onSelect}
      onTap={onSelect}
    >
      {/* Product Image */}
      {image && (
        <KonvaImage
          image={image}
          width={boxWidth}
          height={boxHeight}
          shadowColor="black"
          shadowBlur={isSelected ? 10 : 5}
          shadowOpacity={0.3}
          opacity={isSelected ? 1 : 0.9}
        />
      )}
    </Group>
  );
};

const BackgroundImage: React.FC<{ src: string; width: number; height: number }> = ({ src, width, height }) => {
  const [image] = useImage(src);

  return <KonvaImage image={image} width={width} height={height} />;
};

export const DraggableFurnitureCanvas: React.FC<DraggableFurnitureCanvasProps> = ({
  visualizationImage,
  baseRoomLayer,
  furnitureLayers,
  furniturePositions,
  onPositionsChange,
  products,
  containerWidth = 800,
  containerHeight = 600,
}) => {
  const [positions, setPositions] = useState<FurniturePosition[]>(furniturePositions);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const stageRef = useRef<any>(null);

  useEffect(() => {
    setPositions(furniturePositions);
  }, [furniturePositions]);

  // Get image URL from product (handles both old and new format)
  const getProductImageUrl = (product: Product): string => {
    // Try images array first (transformed format)
    if (product.images && product.images.length > 0) {
      const primaryImage = product.images.find(img => img.is_primary) || product.images[0];
      return primaryImage.large_url || primaryImage.medium_url || primaryImage.original_url || '/placeholder-product.jpg';
    }
    // Fall back to image_url
    return product.image_url || '/placeholder-product.jpg';
  };

  // Get product image for a position
  // Always uses product catalog image (no layer extraction)
  // Handles instance IDs like "12345-1" by extracting the base product ID
  const getImageForPosition = (position: FurniturePosition): string => {
    // Extract base product ID from instance ID (e.g., "12345-1" -> "12345")
    // Instance IDs are created for products with quantity > 1
    const baseProductId = position.productId.includes('-')
      ? position.productId.split('-')[0]
      : position.productId;

    const product = products.find(p => String(p.id) === baseProductId);
    return product ? getProductImageUrl(product) : '/placeholder-product.jpg';
  };

  // Determine which background image to use
  const backgroundImage = baseRoomLayer || visualizationImage;

  const handlePositionChange = (productId: string, newPos: { x: number; y: number }) => {
    const updatedPositions = positions.map((pos) =>
      pos.productId === productId
        ? { ...pos, x: newPos.x, y: newPos.y }
        : pos
    );

    setPositions(updatedPositions);
    onPositionsChange(updatedPositions);
  };

  const handleStageClick = (e: Konva.KonvaEventObject<MouseEvent>) => {
    if (e.target === e.target.getStage()) {
      setSelectedId(null);
    }
  };

  return (
    <div className="relative w-full h-full border-2 border-purple-300 rounded-lg overflow-hidden">
      <Stage
        width={containerWidth}
        height={containerHeight}
        ref={stageRef}
        onClick={handleStageClick}
        onTap={handleStageClick}
      >
        <Layer>
          <BackgroundImage
            src={backgroundImage}
            width={containerWidth}
            height={containerHeight}
          />
        </Layer>

        <Layer>
          {positions.map((position) => (
            <DraggableFurnitureItem
              key={position.productId}
              position={position}
              productImageUrl={getImageForPosition(position)}
              canvasWidth={containerWidth}
              canvasHeight={containerHeight}
              onDragEnd={(newPos) => handlePositionChange(position.productId, newPos)}
              isSelected={selectedId === position.productId}
              onSelect={() => setSelectedId(position.productId)}
            />
          ))}
        </Layer>
      </Stage>

      <div className="absolute bottom-2 left-2 bg-white/90 backdrop-blur-sm px-3 py-2 rounded-md shadow-md text-sm text-gray-700">
        <p className="font-semibold">Edit Mode</p>
        <p className="text-xs">Drag furniture to reposition</p>
      </div>

      {selectedId && (
        <div className="absolute top-2 right-2 bg-purple-50 border border-purple-200 px-3 py-2 rounded-md shadow-md text-sm">
          <p className="text-purple-900 font-semibold">
            {positions.find(p => p.productId === selectedId)?.label}
          </p>
          <p className="text-xs text-purple-600">Selected</p>
        </div>
      )}
    </div>
  );
};
