'use client'

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Product, ProductFilters, Category, ProductSearchResponse } from '@/types'
import { getProducts, getCategories } from '@/utils/api'
import ProductGrid from '@/components/ProductGrid'
import SearchBar from '@/components/SearchBar'
import FilterSidebar from '@/components/FilterSidebar'
import { AdjustmentsHorizontalIcon } from '@heroicons/react/24/outline'
import { ProtectedRoute } from '@/components/ProtectedRoute'

function ProductsPageContent() {
  const [filters, setFilters] = useState<ProductFilters>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [showMobileFilters, setShowMobileFilters] = useState(false)
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDirection, setSortDirection] = useState('desc')

  // Fetch products
  const {
    data: productsResponse,
    isLoading: productsLoading,
    error: productsError
  } = useQuery<ProductSearchResponse>({
    queryKey: ['products', page, searchQuery, filters, sortBy, sortDirection],
    queryFn: () => getProducts({
      page,
      size: 20,
      search: searchQuery || undefined,
      sort_by: sortBy,
      sort_direction: sortDirection,
      ...filters
    })
  })

  // Fetch categories for filters
  const {
    data: categories = [],
    isLoading: categoriesLoading
  } = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: getCategories
  })

  const handleSearch = (query: string) => {
    setSearchQuery(query)
    setPage(1) // Reset to first page on new search
  }

  const handleFiltersChange = (newFilters: ProductFilters) => {
    setFilters(newFilters)
    setPage(1) // Reset to first page on filter change
  }

  const handleSortChange = (newSortBy: string, newSortDirection: string) => {
    setSortBy(newSortBy)
    setSortDirection(newSortDirection)
    setPage(1) // Reset to first page on sort change
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col space-y-4">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold text-gray-900">Products</h1>
              <button
                onClick={() => setShowMobileFilters(!showMobileFilters)}
                className="lg:hidden flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                <AdjustmentsHorizontalIcon className="h-5 w-5" />
                <span>Filters</span>
              </button>
            </div>
            <SearchBar
              onSearch={handleSearch}
              defaultValue={searchQuery}
              className="max-w-2xl"
            />
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Mobile Filters */}
          {showMobileFilters && (
            <div className="lg:hidden">
              <FilterSidebar
                filters={filters}
                categories={categories}
                onFiltersChange={handleFiltersChange}
              />
            </div>
          )}

          {/* Desktop Filters */}
          <div className="hidden lg:block w-80 flex-shrink-0">
            <FilterSidebar
              filters={filters}
              categories={categories}
              onFiltersChange={handleFiltersChange}
            />
          </div>

          {/* Main Content */}
          <div className="flex-1">
            {/* Results Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center space-x-4">
                <p className="text-sm text-gray-600">
                  {productsResponse ? (
                    `Showing ${((productsResponse.page - 1) * productsResponse.size) + 1}-${Math.min(productsResponse.page * productsResponse.size, productsResponse.total)} of ${productsResponse.total} results`
                  ) : (
                    'Loading...'
                  )}
                </p>
              </div>

              {/* Sort Options */}
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700">Sort by:</label>
                <select
                  value={`${sortBy}-${sortDirection}`}
                  onChange={(e) => {
                    const [newSortBy, newSortDirection] = e.target.value.split('-')
                    handleSortChange(newSortBy, newSortDirection)
                  }}
                  className="text-sm border border-gray-300 rounded-md px-3 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="created_at-desc">Newest</option>
                  <option value="created_at-asc">Oldest</option>
                  <option value="price-asc">Price: Low to High</option>
                  <option value="price-desc">Price: High to Low</option>
                  <option value="name-asc">Name: A to Z</option>
                  <option value="name-desc">Name: Z to A</option>
                </select>
              </div>
            </div>

            {/* Products Grid */}
            <ProductGrid
              products={productsResponse?.items || []}
              loading={productsLoading}
            />

            {/* Pagination */}
            {productsResponse && productsResponse.pages > 1 && (
              <div className="mt-12 flex justify-center">
                <Pagination
                  currentPage={productsResponse.page}
                  totalPages={productsResponse.pages}
                  onPageChange={handlePageChange}
                  hasNext={productsResponse.has_next}
                  hasPrev={productsResponse.has_prev}
                />
              </div>
            )}

            {/* Error State */}
            {productsError && (
              <div className="text-center py-12">
                <p className="text-red-600">Error loading products. Please try again.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  hasNext: boolean
  hasPrev: boolean
}

function Pagination({ currentPage, totalPages, onPageChange, hasNext, hasPrev }: PaginationProps) {
  const pages = []
  const maxVisiblePages = 7

  // Calculate which pages to show
  let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2))
  let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1)

  if (endPage - startPage + 1 < maxVisiblePages) {
    startPage = Math.max(1, endPage - maxVisiblePages + 1)
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i)
  }

  return (
    <nav className="flex items-center space-x-1">
      {/* Previous button */}
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={!hasPrev}
        className="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 rounded-l-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Previous
      </button>

      {/* Page numbers */}
      {startPage > 1 && (
        <>
          <button
            onClick={() => onPageChange(1)}
            className="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 hover:bg-gray-50"
          >
            1
          </button>
          {startPage > 2 && (
            <span className="px-3 py-2 text-sm font-medium text-gray-500">...</span>
          )}
        </>
      )}

      {pages.map((page) => (
        <button
          key={page}
          onClick={() => onPageChange(page)}
          className={`px-3 py-2 text-sm font-medium border border-gray-300 hover:bg-gray-50 ${
            page === currentPage
              ? 'bg-blue-50 text-blue-600 border-blue-500'
              : 'text-gray-500 bg-white'
          }`}
        >
          {page}
        </button>
      ))}

      {endPage < totalPages && (
        <>
          {endPage < totalPages - 1 && (
            <span className="px-3 py-2 text-sm font-medium text-gray-500">...</span>
          )}
          <button
            onClick={() => onPageChange(totalPages)}
            className="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 hover:bg-gray-50"
          >
            {totalPages}
          </button>
        </>
      )}

      {/* Next button */}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={!hasNext}
        className="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 rounded-r-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Next
      </button>
    </nav>
  )
}

export default function ProductsPage() {
  return (
    <ProtectedRoute requiredTier="build_your_own">
      <ProductsPageContent />
    </ProtectedRoute>
  );
}
