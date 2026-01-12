'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { adminCuratedAPI, AdminCuratedLookSummary } from '@/utils/api';
import { ProtectedRoute } from '@/components/ProtectedRoute';

function AdminCuratedLooksContent() {
  const [looks, setLooks] = useState<AdminCuratedLookSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'published' | 'draft'>('all');

  useEffect(() => {
    fetchLooks();
  }, [filter]);

  const fetchLooks = async () => {
    try {
      setLoading(true);
      const params: { is_published?: boolean } = {};
      if (filter === 'published') params.is_published = true;
      if (filter === 'draft') params.is_published = false;

      const response = await adminCuratedAPI.list(params);
      setLooks(response.items);
      setError(null);
    } catch (err) {
      console.error('Error fetching looks:', err);
      setError('Failed to load curated looks');
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async (lookId: number) => {
    try {
      await adminCuratedAPI.publish(lookId);
      fetchLooks();
    } catch (err) {
      console.error('Error publishing look:', err);
    }
  };

  const handleUnpublish = async (lookId: number) => {
    try {
      await adminCuratedAPI.unpublish(lookId);
      fetchLooks();
    } catch (err) {
      console.error('Error unpublishing look:', err);
    }
  };

  const handleDelete = async (lookId: number) => {
    if (!confirm('Are you sure you want to delete this curated look?')) return;

    try {
      await adminCuratedAPI.delete(lookId);
      fetchLooks();
    } catch (err) {
      console.error('Error deleting look:', err);
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Link href="/admin" className="text-gray-500 hover:text-gray-700">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">Curated Looks</h1>
            </div>
            <p className="text-gray-600">Create and manage pre-designed room looks</p>
          </div>
          <Link
            href="/admin/curated/new"
            className="inline-flex items-center px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Create New Look
          </Link>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-gray-700">Filter:</span>
            <div className="flex gap-2">
              {(['all', 'published', 'draft'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    filter === f
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-600">{error}</p>
            <button
              onClick={fetchLooks}
              className="mt-4 text-purple-600 hover:text-purple-700 font-medium"
            >
              Try Again
            </button>
          </div>
        ) : looks.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No curated looks yet</h3>
            <p className="text-gray-600 mb-4">Get started by creating your first curated look</p>
            <Link
              href="/admin/curated/new"
              className="inline-flex items-center px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
            >
              Create First Look
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {looks.map((look) => (
              <div
                key={look.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
              >
                {/* Clickable Image */}
                <Link href={`/admin/curated/${look.id}`} className="block">
                  <div className="aspect-[16/10] relative bg-gray-100 cursor-pointer group">
                    {look.visualization_image ? (
                      <Image
                        src={look.visualization_image.startsWith('data:') ? look.visualization_image : `data:image/png;base64,${look.visualization_image}`}
                        alt={look.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-300"
                        unoptimized
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                        <svg className="w-16 h-16 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        <span className="text-sm">No visualization</span>
                      </div>
                    )}

                    {/* Hover Overlay */}
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                      <span className="opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 px-4 py-2 rounded-lg font-medium text-gray-900">
                        View Details
                      </span>
                    </div>

                    {/* Status Badge */}
                    <div className="absolute top-3 left-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        look.is_published
                          ? 'bg-green-100 text-green-700'
                          : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {look.is_published ? 'Published' : 'Draft'}
                      </span>
                    </div>

                    {/* Room Type Badge */}
                    <div className="absolute top-3 right-3">
                      <span className="px-2 py-1 bg-black/60 text-white rounded-full text-xs font-medium capitalize">
                        {look.room_type.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                </Link>

                {/* Content */}
                <div className="p-4">
                  <Link href={`/admin/curated/${look.id}`} className="block hover:text-purple-600 transition-colors">
                    <h3 className="font-semibold text-gray-900 text-base mb-0.5 line-clamp-1">{look.title}</h3>
                  </Link>
                  {look.style_theme && (
                    <p className="text-xs text-gray-500 mb-2">{look.style_theme}</p>
                  )}

                  <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                    <span>{look.product_count} products</span>
                    <span className="text-base font-semibold text-gray-900">{formatPrice(look.total_price)}</span>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1.5">
                    <Link
                      href={`/admin/curated/${look.id}`}
                      className="flex-1 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium rounded-lg text-center transition-colors"
                    >
                      View
                    </Link>
                    {look.is_published ? (
                      <button
                        onClick={() => handleUnpublish(look.id)}
                        className="px-3 py-2 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 text-xs font-medium rounded-lg transition-colors"
                      >
                        Unpublish
                      </button>
                    ) : (
                      <button
                        onClick={() => handlePublish(look.id)}
                        className="px-3 py-2 bg-green-100 hover:bg-green-200 text-green-700 text-xs font-medium rounded-lg transition-colors"
                      >
                        Publish
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(look.id)}
                      className="px-2 py-2 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-medium rounded-lg transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminCuratedLooksPage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <AdminCuratedLooksContent />
    </ProtectedRoute>
  );
}
