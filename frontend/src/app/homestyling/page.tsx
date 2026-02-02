'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Redirect /homestyling to / (unified landing page)
 *
 * The homestyling landing page has been unified with the main landing page.
 * This redirect ensures any bookmarks or old links continue to work.
 *
 * Note: The /homestyling/preferences, /homestyling/upload, and other
 * sub-routes are still active and used in the user flow.
 */
export default function HomeStylingLandingPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to the main landing page
    router.replace('/');
  }, [router]);

  // Show loading while redirecting
  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-neutral-200 border-t-neutral-800 mx-auto mb-4" />
        <p className="text-sm text-neutral-500">Redirecting...</p>
      </div>
    </div>
  );
}
