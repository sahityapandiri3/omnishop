'use client';

import { useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, UserRole, SubscriptionTier, isAdmin } from '@/contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: UserRole;  // Optional: 'user' (default), 'admin', or 'super_admin'
  requiredTier?: SubscriptionTier;  // Optional: single tier requirement (legacy)
  requiredTiers?: SubscriptionTier[];  // Optional: array of allowed tiers (new)
  allowAdmin?: boolean;  // Optional: allow admin access regardless of tier (default: true)
  bypassTierWithSessionKeys?: string[];  // Optional: bypass tier check if any of these sessionStorage keys exist
  redirectTo?: string;  // Optional: custom redirect URL for unauthorized users
}

/**
 * Wrapper component that protects routes requiring authentication.
 * Redirects unauthenticated users to the login page.
 * Optionally restricts access based on user role and/or subscription tier.
 */
export function ProtectedRoute({
  children,
  requiredRole = 'user',
  requiredTier,
  requiredTiers,
  allowAdmin = true,
  bypassTierWithSessionKeys,
  redirectTo
}: ProtectedRouteProps) {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();

  // Check if user has required role
  const hasRequiredRole = useMemo(() => {
    if (!user) return false;

    // Role hierarchy: super_admin > admin > user
    if (requiredRole === 'user') {
      // Any authenticated user has 'user' role access
      return true;
    }
    if (requiredRole === 'admin') {
      // Admin or super_admin can access admin routes
      return user.role === 'admin' || user.role === 'super_admin';
    }
    if (requiredRole === 'super_admin') {
      // Only super_admin can access super_admin routes
      return user.role === 'super_admin';
    }
    return false;
  }, [user, requiredRole]);

  // Check if user has required subscription tier
  const hasRequiredTier = useMemo(() => {
    if (!user) return false;

    // Admins always have access to everything (if allowAdmin is true)
    if (allowAdmin && isAdmin(user)) return true;

    // If no tier requirement specified, allow access
    if (!requiredTier && (!requiredTiers || requiredTiers.length === 0)) return true;

    // Check for bypass via sessionStorage keys (e.g., coming from "Style This Further" flow)
    if (bypassTierWithSessionKeys && bypassTierWithSessionKeys.length > 0) {
      const hasBypassKey = bypassTierWithSessionKeys.some(key => {
        try {
          return sessionStorage.getItem(key) !== null;
        } catch {
          return false;
        }
      });
      if (hasBypassKey) return true;
    }

    // New: Check against array of required tiers
    if (requiredTiers && requiredTiers.length > 0) {
      return requiredTiers.includes(user.subscription_tier);
    }

    // Legacy: Check single tier requirement
    if (requiredTier) {
      // For legacy compatibility: advanced/curator tiers have access to everything
      if (['advanced', 'curator'].includes(user.subscription_tier)) return true;
      return user.subscription_tier === requiredTier;
    }

    return true;
  }, [user, requiredTier, requiredTiers, allowAdmin, bypassTierWithSessionKeys]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // Store the current path to redirect back after login
      const currentPath = window.location.pathname + window.location.search;
      sessionStorage.setItem('redirectAfterLogin', currentPath);
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Show loading spinner while checking auth state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render children if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  // Check role - block unauthorized users
  if (!hasRequiredRole) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md mx-auto px-6">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Access Restricted</h2>
          <p className="text-gray-600 mb-6">
            You don&apos;t have permission to access this page. {requiredRole === 'admin' ? 'Admin' : 'Super admin'} privileges are required.
          </p>
          <button
            onClick={() => router.push('/homestyling/preferences')}
            className="px-4 py-2 bg-neutral-900 text-white rounded-lg text-sm font-medium hover:bg-neutral-800 transition-colors"
          >
            Go to Homestyling
          </button>
        </div>
      </div>
    );
  }

  // Check tier - redirect users to pricing/upgrade page
  if (!hasRequiredTier) {
    const upgradeUrl = redirectTo || '/pricing';
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md mx-auto px-6">
          <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Upgrade Required</h2>
          <p className="text-gray-600 mb-6">
            This feature requires an upgraded subscription. Upgrade to access the full design studio and curated looks library.
          </p>
          <div className="flex flex-col gap-3">
            <button
              onClick={() => router.push(upgradeUrl)}
              className="px-4 py-2 bg-neutral-800 text-white rounded-lg text-sm font-medium hover:bg-neutral-900 transition-colors"
            >
              View Plans
            </button>
            <button
              onClick={() => router.push('/')}
              className="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              Back to Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export default ProtectedRoute;
