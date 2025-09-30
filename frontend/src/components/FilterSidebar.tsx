'use client'

import { useState } from 'react'
import { ProductFilters, Category } from '@/types'
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline'

interface FilterSidebarProps {
  filters: ProductFilters
  categories: Category[]
  onFiltersChange: (filters: ProductFilters) => void
  className?: string
}

export function FilterSidebar({
  filters,
  categories,
  onFiltersChange,
  className = ""
}: FilterSidebarProps) {
  const [expandedSections, setExpandedSections] = useState({
    price: true,
    category: true,
    brand: true,
    source: true,
    availability: true
  })

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const updateFilters = (updates: Partial<ProductFilters>) => {
    onFiltersChange({ ...filters, ...updates })
  }

  const clearFilters = () => {
    onFiltersChange({})
  }

  const hasActiveFilters = Object.values(filters).some(value =>
    value !== null && value !== undefined &&
    (Array.isArray(value) ? value.length > 0 : true)
  )

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 p-6 ${className}`}>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="space-y-6">
        {/* Price Range */}
        <FilterSection
          title="Price Range"
          isExpanded={expandedSections.price}
          onToggle={() => toggleSection('price')}
        >
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min</label>
                <input
                  type="number"
                  min="0"
                  value={filters.min_price || ''}
                  onChange={(e) => updateFilters({ min_price: e.target.value ? parseFloat(e.target.value) : undefined })}
                  placeholder="$0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max</label>
                <input
                  type="number"
                  min="0"
                  value={filters.max_price || ''}
                  onChange={(e) => updateFilters({ max_price: e.target.value ? parseFloat(e.target.value) : undefined })}
                  placeholder="$999+"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>
        </FilterSection>

        {/* Categories */}
        <FilterSection
          title="Categories"
          isExpanded={expandedSections.category}
          onToggle={() => toggleSection('category')}
        >
          <div className="space-y-2">
            {categories.map((category) => (
              <label key={category.id} className="flex items-center">
                <input
                  type="radio"
                  name="category"
                  value={category.id}
                  checked={filters.category_id === category.id}
                  onChange={(e) => updateFilters({
                    category_id: e.target.checked ? category.id : undefined
                  })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                />
                <span className="ml-2 text-sm text-gray-700">{category.name}</span>
                {category.product_count && (
                  <span className="ml-auto text-xs text-gray-400">({category.product_count})</span>
                )}
              </label>
            ))}
          </div>
        </FilterSection>

        {/* Source Websites */}
        <FilterSection
          title="Source Websites"
          isExpanded={expandedSections.source}
          onToggle={() => toggleSection('source')}
        >
          <div className="space-y-2">
            {['westelm.com', 'orangetree.com', 'pelicanessentials.com'].map((source) => (
              <label key={source} className="flex items-center">
                <input
                  type="checkbox"
                  checked={filters.source_website?.includes(source) || false}
                  onChange={(e) => {
                    const current = filters.source_website || []
                    const updated = e.target.checked
                      ? [...current, source]
                      : current.filter(s => s !== source)
                    updateFilters({ source_website: updated.length > 0 ? updated : undefined })
                  }}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700 capitalize">
                  {source.replace('.com', '')}
                </span>
              </label>
            ))}
          </div>
        </FilterSection>

        {/* Availability */}
        <FilterSection
          title="Availability"
          isExpanded={expandedSections.availability}
          onToggle={() => toggleSection('availability')}
        >
          <div className="space-y-2">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filters.is_available === true}
                onChange={(e) => updateFilters({
                  is_available: e.target.checked ? true : undefined
                })}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">In Stock Only</span>
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filters.is_on_sale === true}
                onChange={(e) => updateFilters({
                  is_on_sale: e.target.checked ? true : undefined
                })}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">On Sale</span>
            </label>
          </div>
        </FilterSection>
      </div>
    </div>
  )
}

interface FilterSectionProps {
  title: string
  isExpanded: boolean
  onToggle: () => void
  children: React.ReactNode
}

function FilterSection({ title, isExpanded, onToggle, children }: FilterSectionProps) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="flex items-center justify-between w-full text-left"
      >
        <h4 className="text-sm font-medium text-gray-900">{title}</h4>
        {isExpanded ? (
          <ChevronUpIcon className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDownIcon className="h-4 w-4 text-gray-500" />
        )}
      </button>
      {isExpanded && <div className="mt-3">{children}</div>}
    </div>
  )
}

export default FilterSidebar