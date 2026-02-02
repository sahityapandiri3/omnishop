'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';

function ProfilePageContent() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [imageError, setImageError] = useState(false);

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user?.name) return user?.email?.charAt(0).toUpperCase() || '?';
    const names = user.name.split(' ');
    if (names.length >= 2) {
      return names[0].charAt(0) + names[names.length - 1].charAt(0);
    }
    return names[0].charAt(0).toUpperCase();
  };

  // Format tier name
  const formatTierName = (tier: string) => {
    return tier.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="min-h-screen bg-neutral-50 py-12">
      <div className="max-w-2xl mx-auto px-4">
        {/* Back button */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-neutral-500 hover:text-neutral-700 mb-8 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>

        {/* Profile Card */}
        <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-neutral-800 to-neutral-700 px-6 py-8">
            <div className="flex items-center gap-4">
              {user?.profile_image_url && !imageError ? (
                <img
                  src={user.profile_image_url}
                  alt={user.name || 'User'}
                  className="w-20 h-20 rounded-full object-cover border-4 border-white shadow-lg"
                  onError={() => setImageError(true)}
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-white flex items-center justify-center text-neutral-700 font-semibold text-2xl border-4 border-white shadow-lg">
                  {getUserInitials()}
                </div>
              )}
              <div>
                <h1 className="text-2xl font-semibold text-white">
                  {user?.name || 'User'}
                </h1>
                <p className="text-neutral-300">{user?.email}</p>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="p-6 space-y-6">
            {/* Subscription Tier */}
            <div>
              <h2 className="text-sm font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Subscription Plan
              </h2>
              <div className="flex items-center justify-between p-4 bg-neutral-50 rounded-lg border border-neutral-200">
                <div>
                  <p className="font-medium text-neutral-800">
                    {user?.subscription_tier ? formatTierName(user.subscription_tier) : 'Free'} Plan
                  </p>
                  <p className="text-sm text-neutral-500 mt-0.5">
                    {user?.subscription_tier === 'free' && 'Basic access to curated looks'}
                    {user?.subscription_tier === 'basic' && '3 curated looks for your space'}
                    {user?.subscription_tier === 'basic_plus' && '6 curated looks with advanced matching'}
                    {user?.subscription_tier === 'advanced' && 'Full Omni Studio access'}
                    {user?.subscription_tier === 'curator' && 'Full access + publish to gallery'}
                    {!user?.subscription_tier && 'Upgrade to access more features'}
                  </p>
                </div>
                <Link
                  href="/pricing"
                  className="px-4 py-2 bg-neutral-800 text-white text-sm font-medium rounded-lg hover:bg-neutral-900 transition-colors"
                >
                  {user?.subscription_tier === 'curator' ? 'Manage' : 'Upgrade'}
                </Link>
              </div>
            </div>

            {/* Account Info */}
            <div>
              <h2 className="text-sm font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Account Information
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between py-3 border-b border-neutral-100">
                  <span className="text-neutral-600">Email</span>
                  <span className="text-neutral-800 font-medium">{user?.email}</span>
                </div>
                <div className="flex items-center justify-between py-3 border-b border-neutral-100">
                  <span className="text-neutral-600">Name</span>
                  <span className="text-neutral-800 font-medium">{user?.name || 'Not set'}</span>
                </div>
                <div className="flex items-center justify-between py-3 border-b border-neutral-100">
                  <span className="text-neutral-600">Role</span>
                  <span className="text-neutral-800 font-medium capitalize">{user?.role || 'User'}</span>
                </div>
              </div>
            </div>

            {/* Quick Links */}
            <div>
              <h2 className="text-sm font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Quick Links
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <Link
                  href="/purchases"
                  className="flex items-center gap-2 p-3 bg-neutral-50 rounded-lg border border-neutral-200 hover:border-neutral-300 transition-colors"
                >
                  <svg className="w-5 h-5 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
                  </svg>
                  <span className="text-sm font-medium text-neutral-700">My Purchases</span>
                </Link>
                <Link
                  href="/projects"
                  className="flex items-center gap-2 p-3 bg-neutral-50 rounded-lg border border-neutral-200 hover:border-neutral-300 transition-colors"
                >
                  <svg className="w-5 h-5 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  <span className="text-sm font-medium text-neutral-700">My Projects</span>
                </Link>
              </div>
            </div>

            {/* Sign Out */}
            <div className="pt-4 border-t border-neutral-200">
              <button
                onClick={handleLogout}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-accent-50 text-accent-600 rounded-lg hover:bg-accent-100 transition-colors font-medium"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <ProtectedRoute requiredRole="user">
      <ProfilePageContent />
    </ProtectedRoute>
  );
}
