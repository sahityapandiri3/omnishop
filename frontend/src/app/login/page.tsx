'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useAuth, hasBuildYourOwn } from '@/contexts/AuthContext';

type AuthMode = 'login' | 'register';

// Check if Google OAuth is configured
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, register, loginWithGoogle, isAuthenticated, isLoading, user } = useAuth();

  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Get explicit redirect URL from query params or sessionStorage (returns null if none)
  const getExplicitRedirectUrl = () => {
    // First check query params
    const queryRedirect = searchParams?.get('redirect');
    if (queryRedirect) return queryRedirect;

    // Then check sessionStorage (set by ProtectedRoute)
    if (typeof window !== 'undefined') {
      const storedRedirect = sessionStorage.getItem('redirectAfterLogin');
      if (storedRedirect) {
        sessionStorage.removeItem('redirectAfterLogin');
        return storedRedirect;
      }
    }

    // No explicit redirect - will be determined by user tier after login
    return null;
  };

  const explicitRedirectUrl = getExplicitRedirectUrl();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      // Use explicit redirect if available, otherwise determine by user tier
      const targetUrl = explicitRedirectUrl || (hasBuildYourOwn(user) ? '/curated' : '/homestyling');
      router.push(targetUrl);
    }
  }, [isAuthenticated, isLoading, router, explicitRedirectUrl, user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      let loggedInUser;
      if (mode === 'login') {
        loggedInUser = await login(email, password);
      } else {
        loggedInUser = await register(email, password, name);
      }
      // Use explicit redirect if available, otherwise determine by user tier
      const targetUrl = explicitRedirectUrl || (hasBuildYourOwn(loggedInUser) ? '/curated' : '/homestyling');
      router.push(targetUrl);
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    if (!credentialResponse.credential) {
      setError('Google login failed: No credential received');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const loggedInUser = await loginWithGoogle(credentialResponse.credential);
      // Use explicit redirect if available, otherwise determine by user tier
      const targetUrl = explicitRedirectUrl || (hasBuildYourOwn(loggedInUser) ? '/curated' : '/homestyling');
      router.push(targetUrl);
    } catch (err: any) {
      setError(err.message || 'Google login failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleError = () => {
    setError('Google login failed. Please try again.');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <svg className="h-10 w-10 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z" />
            </svg>
            <div>
              <span className="text-xl font-bold text-neutral-900">Omnishop</span>
              <span className="ml-1 text-sm text-neutral-500">AI Design</span>
            </div>
          </Link>
          <h2 className="heading-2 text-neutral-900">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="mt-2 body-medium">
            {mode === 'login'
              ? 'Sign in to continue to your projects'
              : 'Start designing your dream space'}
          </p>
        </div>

        {/* Form Card */}
        <div className="card p-6">
          {/* Mode Toggle */}
          <div className="flex bg-neutral-100 rounded-lg p-1 mb-6">
            <button
              type="button"
              onClick={() => setMode('login')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                mode === 'login'
                  ? 'bg-white text-neutral-900 shadow-sm'
                  : 'text-neutral-600 hover:text-neutral-900'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                mode === 'register'
                  ? 'bg-white text-neutral-900 shadow-sm'
                  : 'text-neutral-600 hover:text-neutral-900'
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Session expired message */}
          {searchParams?.get('reason') === 'session_expired' && (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg text-sm mb-4">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Your session has expired. Please sign in again to continue.</span>
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div className="space-y-4">
              {mode === 'register' && (
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-neutral-700 mb-1">
                    Full Name
                  </label>
                  <input
                    id="name"
                    type="text"
                    required={mode === 'register'}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="input h-11"
                    placeholder="John Doe"
                  />
                </div>
              )}

              <div>
                <label htmlFor="email" className="block text-sm font-medium text-neutral-700 mb-1">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input h-11"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-neutral-700 mb-1">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input h-11"
                  placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter your password'}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="btn btn-primary w-full h-11"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  {mode === 'login' ? 'Signing in...' : 'Creating account...'}
                </span>
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-neutral-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-neutral-500">
                  Or continue with
                </span>
              </div>
            </div>

            {/* Google Login */}
            {GOOGLE_CLIENT_ID ? (
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  theme="outline"
                  size="large"
                  width="100%"
                  text="continue_with"
                />
              </div>
            ) : (
              <div className="text-center text-sm text-neutral-500 bg-neutral-50 py-3 px-4 rounded-lg border border-neutral-200">
                Google Sign In not configured. Please use email/password.
              </div>
            )}
          </form>
        </div>

        {/* Footer links */}
        <p className="text-center text-xs text-neutral-500">
          By continuing, you agree to our{' '}
          <Link href="/terms" className="text-primary-600 hover:text-primary-700">
            Terms of Service
          </Link>{' '}
          and{' '}
          <Link href="/privacy" className="text-primary-600 hover:text-primary-700">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
