'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { adminCuratedAPI, AdminCuratedLook } from '@/utils/api';

// Available style labels for multi-select
const STYLE_LABEL_OPTIONS = [
  { value: 'modern', label: 'Modern' },
  { value: 'modern_luxury', label: 'Modern Luxury' },
  { value: 'indian_contemporary', label: 'Indian Contemporary' },
  { value: 'minimalist', label: 'Minimalist' },
  { value: 'japandi', label: 'Japandi' },
  { value: 'scandinavian', label: 'Scandinavian' },
  { value: 'mid_century_modern', label: 'Mid-Century Modern' },
  { value: 'bohemian', label: 'Bohemian' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'contemporary', label: 'Contemporary' },
  { value: 'eclectic', label: 'Eclectic' },
];

export default function CuratedLookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const lookId = Number(params?.id);

  const [look, setLook] = useState<AdminCuratedLook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingLabels, setEditingLabels] = useState(false);
  const [styleLabels, setStyleLabels] = useState<string[]>([]);
  const [savingLabels, setSavingLabels] = useState(false);

  // Scroll to top when the page loads
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    if (lookId) {
      fetchLook();
    }
  }, [lookId]);

  const fetchLook = async () => {
    try {
      setLoading(true);
      const data = await adminCuratedAPI.get(lookId);
      setLook(data);
      setStyleLabels(data.style_labels || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching look:', err);
      setError('Failed to load curated look');
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!look) return;
    try {
      await adminCuratedAPI.publish(look.id);
      fetchLook();
    } catch (err) {
      console.error('Error publishing look:', err);
    }
  };

  const handleUnpublish = async () => {
    if (!look) return;
    try {
      await adminCuratedAPI.unpublish(look.id);
      fetchLook();
    } catch (err) {
      console.error('Error unpublishing look:', err);
    }
  };

  const handleDelete = async () => {
    if (!look) return;
    if (!confirm('Are you sure you want to delete this curated look?')) return;

    try {
      await adminCuratedAPI.delete(look.id);
      router.push('/admin/curated');
    } catch (err) {
      console.error('Error deleting look:', err);
    }
  };

  const handleStartEditLabels = () => {
    setStyleLabels(look?.style_labels || []);
    setEditingLabels(true);
  };

  const handleCancelEditLabels = () => {
    setStyleLabels(look?.style_labels || []);
    setEditingLabels(false);
  };

  const toggleStyleLabel = (value: string) => {
    setStyleLabels(prev =>
      prev.includes(value)
        ? prev.filter(l => l !== value)
        : [...prev, value]
    );
  };

  const handleSaveLabels = async () => {
    if (!look) return;
    try {
      setSavingLabels(true);
      await adminCuratedAPI.update(look.id, { style_labels: styleLabels });
      setLook({ ...look, style_labels: styleLabels });
      setEditingLabels(false);
    } catch (err) {
      console.error('Error saving style labels:', err);
    } finally {
      setSavingLabels(false);
    }
  };

  const formatPrice = (price: number | null) => {
    if (price === null) return 'Price N/A';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
      </div>
    );
  }

  if (error || !look) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error || 'Look not found'}</p>
          <Link href="/admin/curated" className="text-purple-600 hover:text-purple-700 font-medium">
            Back to Curated Looks
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link href="/admin/curated" className="text-gray-500 hover:text-gray-700">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{look.title}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  look.is_published
                    ? 'bg-green-100 text-green-700'
                    : 'bg-yellow-100 text-yellow-700'
                }`}>
                  {look.is_published ? 'Published' : 'Draft'}
                </span>
                <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-medium capitalize">
                  {look.room_type.replace('_', ' ')}
                </span>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Link
              href={`/admin/curated/new?edit=${look.id}`}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium rounded-lg transition-colors"
            >
              Edit Look
            </Link>
            {look.is_published ? (
              <button
                onClick={handleUnpublish}
                className="px-4 py-2 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 font-medium rounded-lg transition-colors"
              >
                Unpublish
              </button>
            ) : (
              <button
                onClick={handlePublish}
                className="px-4 py-2 bg-green-100 hover:bg-green-200 text-green-700 font-medium rounded-lg transition-colors"
              >
                Publish
              </button>
            )}
            <button
              onClick={handleDelete}
              className="px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 font-medium rounded-lg transition-colors"
            >
              Delete
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Visualization Image - Large */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="aspect-[4/3] relative bg-gray-100">
                {look.visualization_image ? (
                  <Image
                    src={look.visualization_image.startsWith('data:') ? look.visualization_image : `data:image/png;base64,${look.visualization_image}`}
                    alt={look.title}
                    fill
                    className="object-contain"
                    unoptimized
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                    <svg className="w-20 h-20 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="text-sm">No visualization image</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Look Details */}
          <div className="space-y-6">
            {/* Description Card */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Look Details</h2>

              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">Style Theme</label>
                  <p className="text-gray-900">{look.style_theme}</p>
                </div>

                {/* Style Labels Section */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-gray-500">Style Labels</label>
                    {!editingLabels ? (
                      <button
                        onClick={handleStartEditLabels}
                        className="text-xs text-purple-600 hover:text-purple-700 font-medium"
                      >
                        Edit
                      </button>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          onClick={handleCancelEditLabels}
                          className="text-xs text-gray-500 hover:text-gray-700"
                          disabled={savingLabels}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleSaveLabels}
                          className="text-xs text-purple-600 hover:text-purple-700 font-medium"
                          disabled={savingLabels}
                        >
                          {savingLabels ? 'Saving...' : 'Save'}
                        </button>
                      </div>
                    )}
                  </div>

                  {editingLabels ? (
                    <div className="flex flex-wrap gap-2">
                      {STYLE_LABEL_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => toggleStyleLabel(option.value)}
                          className={`px-2 py-1 rounded-full text-xs font-medium transition-colors ${
                            styleLabels.includes(option.value)
                              ? 'bg-purple-600 text-white'
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {look.style_labels && look.style_labels.length > 0 ? (
                        look.style_labels.map((label) => {
                          const option = STYLE_LABEL_OPTIONS.find(o => o.value === label);
                          return (
                            <span
                              key={label}
                              className="px-2 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-medium"
                            >
                              {option?.label || label}
                            </span>
                          );
                        })
                      ) : (
                        <span className="text-gray-400 text-sm italic">No style labels</span>
                      )}
                    </div>
                  )}
                </div>

                {look.style_description && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Description</label>
                    <p className="text-gray-700">{look.style_description}</p>
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium text-gray-500">Total Price</label>
                  <p className="text-2xl font-bold text-purple-600">{formatPrice(look.total_price)}</p>
                </div>

                <div className="pt-4 border-t border-gray-100">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Created</span>
                    <span className="text-gray-700">{formatDate(look.created_at)}</span>
                  </div>
                  <div className="flex justify-between text-sm mt-2">
                    <span className="text-gray-500">Last Updated</span>
                    <span className="text-gray-700">{formatDate(look.updated_at)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Style This Look Button */}
            <Link
              href={`/admin/curated/new?style_from=${look.id}`}
              className="block w-full px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg text-center transition-colors"
            >
              <span className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Further Style This Look
              </span>
            </Link>
          </div>
        </div>

        {/* Products Section */}
        <div className="mt-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Products in This Look ({look.products.length})
            </h2>

            {look.products.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No products in this look</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {look.products.map((product) => (
                  <div
                    key={product.id}
                    className="border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
                  >
                    <div className="aspect-square relative bg-gray-100">
                      {product.image_url ? (
                        <Image
                          src={product.image_url}
                          alt={product.name}
                          fill
                          className="object-cover"
                          unoptimized
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <svg className="w-12 h-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                      {product.product_type && (
                        <div className="absolute top-2 left-2">
                          <span className="px-2 py-1 bg-black/60 text-white rounded-full text-xs capitalize">
                            {product.product_type.replace('_', ' ')}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="p-3">
                      <h3 className="font-medium text-gray-900 text-sm line-clamp-2 mb-1">
                        {product.name}
                      </h3>
                      <p className="text-xs text-gray-500 mb-2 capitalize">
                        {product.source_website}
                      </p>
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-gray-900">
                          {formatPrice(product.price)}
                        </span>
                        {product.source_url && (
                          <a
                            href={product.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-purple-600 hover:text-purple-700"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
