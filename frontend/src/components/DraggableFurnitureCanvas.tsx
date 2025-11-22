'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Stage, Layer, Image as KonvaImage, Rect, Text, Group } from 'react-konva';
import useImage from 'use-image';

export interface FurniturePosition {
  productId: string;
  x: number; // percentage 0-1
  y: number; // percentage 0-1
  label: string;
  width?: number;
  height?: number;
}

interface DraggableFurnitureCanvasProps {
  visualizationImage: string; // base64 or URL
  furniturePositions: FurniturePosition[];
  onPositionsChange: (positions: FurniturePosition[]) => void;
  containerWidth?: number;
  containerHeight?: number;
}

interface DraggableFurnitureItemProps {
  position: FurniturePosition;
  canvasWidth: number;
  canvasHeight: number;
  onDragEnd: (newPosition: { x: number; y: number }) => void;
  isSelected: boolean;
  onSelect: () => void;
}

const DraggableFurnitureItem: React.FC<DraggableFurnitureItemProps> = ({
  position,
  canvasWidth,
  canvasHeight,
  onDragEnd,
  isSelected,
  onSelect,
}) => {
  const boxWidth = (position.width || 0.1) * canvasWidth;
  const boxHeight = (position.height || 0.1) * canvasHeight;
  const x = position.x * canvasWidth;
  const y = position.y * canvasHeight;

  return (
    <Group
      x={x}
      y={y}
      draggable
      onDragEnd={(e) => {
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
      <Rect
        width={boxWidth}
        height={boxHeight}
        fill="rgba(139, 92, 246, 0.2)"
        stroke={isSelected ? "#8b5cf6" : "#a78bfa"}
        strokeWidth={isSelected ? 3 : 2}
        dash={[5, 5]}
        cornerRadius={4}
      />

      <Text
        text={position.label}
        fontSize={14}
        fontFamily="Arial"
        fill={isSelected ? "#8b5cf6" : "#6b7280"}
        fontStyle="bold"
        padding={4}
        x={5}
        y={5}
      />

      {isSelected && (
        <>
          <Rect
            x={boxWidth - 12}
            y={boxHeight - 12}
            width={10}
            height={10}
            fill="#8b5cf6"
            cornerRadius={2}
          />
          <Rect
            x={0}
            y={boxHeight - 12}
            width={10}
            height={10}
            fill="#8b5cf6"
            cornerRadius={2}
          />
          <Rect
            x={boxWidth - 12}
            y={0}
            width={10}
            height={10}
            fill="#8b5cf6"
            cornerRadius={2}
          />
        </>
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
  furniturePositions,
  onPositionsChange,
  containerWidth = 800,
  containerHeight = 600,
}) => {
  const [positions, setPositions] = useState<FurniturePosition[]>(furniturePositions);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const stageRef = useRef<any>(null);

  useEffect(() => {
    setPositions(furniturePositions);
  }, [furniturePositions]);

  const handlePositionChange = (productId: string, newPos: { x: number; y: number }) => {
    const updatedPositions = positions.map((pos) =>
      pos.productId === productId
        ? { ...pos, x: newPos.x, y: newPos.y }
        : pos
    );

    setPositions(updatedPositions);
    onPositionsChange(updatedPositions);
  };

  const handleStageClick = (e: any) => {
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
            src={visualizationImage}
            width={containerWidth}
            height={containerHeight}
          />
        </Layer>

        <Layer>
          {positions.map((position) => (
            <DraggableFurnitureItem
              key={position.productId}
              position={position}
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
