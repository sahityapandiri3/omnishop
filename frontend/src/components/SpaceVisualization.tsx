'use client'

import { useState, useRef, useEffect } from 'react'
import { Product } from '@/types'

interface SpaceVisualizationProps {
  roomImage?: string
  recommendedProducts?: Product[]
  className?: string
}

export function SpaceVisualization({
  roomImage,
  recommendedProducts = [],
  className = ''
}: SpaceVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [productPlacements, setProductPlacements] = useState<Array<{
    product: Product
    x: number
    y: number
    scale: number
  }>>([])

  useEffect(() => {
    if (roomImage) {
      drawVisualization()
    }
  }, [roomImage, productPlacements])

  const drawVisualization = () => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw room image if available
    if (roomImage) {
      const img = new Image()
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        drawProductPlacements(ctx)
      }
      img.src = roomImage
    } else {
      // Draw default room outline
      drawDefaultRoom(ctx)
      drawProductPlacements(ctx)
    }
  }

  const drawDefaultRoom = (ctx: CanvasRenderingContext2D) => {
    const { width, height } = ctx.canvas

    // Draw room outline
    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 2
    ctx.strokeRect(50, 50, width - 100, height - 100)

    // Draw floor grid
    ctx.strokeStyle = '#f3f4f6'
    ctx.lineWidth = 1
    const gridSize = 40

    for (let x = 50; x < width - 50; x += gridSize) {
      ctx.beginPath()
      ctx.moveTo(x, 50)
      ctx.lineTo(x, height - 50)
      ctx.stroke()
    }

    for (let y = 50; y < height - 50; y += gridSize) {
      ctx.beginPath()
      ctx.moveTo(50, y)
      ctx.lineTo(width - 50, y)
      ctx.stroke()
    }

    // Add room label
    ctx.fillStyle = '#6b7280'
    ctx.font = '16px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Your Room', width / 2, 30)
  }

  const drawProductPlacements = (ctx: CanvasRenderingContext2D) => {
    productPlacements.forEach(({ product, x, y, scale }) => {
      const primaryImage = product.images?.find(img => img.is_primary) || product.images?.[0]
      if (primaryImage) {
        const img = new Image()
        img.onload = () => {
          const size = 60 * scale
          ctx.drawImage(img, x - size/2, y - size/2, size, size)

          // Draw product label
          ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
          ctx.fillRect(x - 40, y + size/2, 80, 20)
          ctx.fillStyle = 'white'
          ctx.font = '12px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(product.name.substring(0, 12) + '...', x, y + size/2 + 14)
        }
        img.src = primaryImage.thumbnail_url || primaryImage.original_url
      }
    })
  }

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!selectedProduct) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Add product placement
    setProductPlacements(prev => [
      ...prev,
      {
        product: selectedProduct,
        x,
        y,
        scale: 1
      }
    ])

    setSelectedProduct(null)
  }

  const clearPlacements = () => {
    setProductPlacements([])
  }

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Space Visualization</h3>
        <button
          onClick={clearPlacements}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Clear All
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Canvas */}
        <div className="lg:col-span-2">
          <div className="border border-gray-300 rounded-lg overflow-hidden">
            <canvas
              ref={canvasRef}
              width={600}
              height={400}
              onClick={handleCanvasClick}
              className="w-full h-auto cursor-crosshair bg-gray-50"
            />
          </div>
          <p className="text-sm text-gray-500 mt-2">
            {selectedProduct
              ? `Click on the room to place "${selectedProduct.name}"`
              : 'Select a product from the sidebar to place it in your room'
            }
          </p>
        </div>

        {/* Product Sidebar */}
        <div className="space-y-4">
          <h4 className="font-medium text-gray-900">Recommended Products</h4>

          {recommendedProducts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No products available</p>
              <p className="text-xs mt-1">
                Start a chat to get product recommendations for your space
              </p>
            </div>
          ) : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {recommendedProducts.map((product) => (
                <ProductVisualizationCard
                  key={product.id}
                  product={product}
                  isSelected={selectedProduct?.id === product.id}
                  onSelect={() => setSelectedProduct(product)}
                />
              ))}
            </div>
          )}

          {/* Placed Products */}
          {productPlacements.length > 0 && (
            <div className="mt-6">
              <h4 className="font-medium text-gray-900 mb-3">Placed Items</h4>
              <div className="space-y-2">
                {productPlacements.map((placement, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between text-sm bg-gray-50 rounded-lg p-2"
                  >
                    <span className="truncate">{placement.product.name}</span>
                    <button
                      onClick={() => setProductPlacements(prev => prev.filter((_, i) => i !== index))}
                      className="text-red-500 hover:text-red-700 ml-2"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

interface ProductVisualizationCardProps {
  product: Product
  isSelected: boolean
  onSelect: () => void
}

function ProductVisualizationCard({ product, isSelected, onSelect }: ProductVisualizationCardProps) {
  const primaryImage = product.images?.find(img => img.is_primary) || product.images?.[0]

  return (
    <div
      onClick={onSelect}
      className={`border rounded-lg p-3 cursor-pointer transition-all ${
        isSelected
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-200 hover:border-gray-300 bg-white'
      }`}
    >
      <div className="flex items-center space-x-3">
        {primaryImage ? (
          <img
            src={primaryImage.thumbnail_url || primaryImage.original_url}
            alt={product.name}
            className="w-12 h-12 object-cover rounded"
          />
        ) : (
          <div className="w-12 h-12 bg-gray-200 rounded flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
          <p className="text-sm text-gray-500">${product.price}</p>
          {product.brand && (
            <p className="text-xs text-gray-400">{product.brand}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default SpaceVisualization