'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode, useRef } from 'react';
import { api } from '@/utils/api';

// Types
export type UserRole = 'user' | 'admin' | 'super_admin';
export type SubscriptionTier = 'free' | 'build_your_own' | 'upgraded';

export interface User {
  id: string;
  email: string;
  name: string | null;
  profile_image_url: string | null;
  auth_provider: string;
  is_active: boolean;
  role: UserRole;
  subscription_tier: SubscriptionTier;
  created_at: string;
}

// Role helper functions
export function isAdmin(user: User | null): boolean {
  return user?.role === 'admin' || user?.role === 'super_admin';
}

export function isSuperAdmin(user: User | null): boolean {
  return user?.role === 'super_admin';
}

// Subscription helper functions
export function hasBuildYourOwn(user: User | null): boolean {
  // Admins always have full access
  if (isAdmin(user)) return true;
  // Check for "upgraded" tier (covers both Build Your Own and Style This Further upgrades)
  return user?.subscription_tier === 'upgraded';
}

export function canAccessDesignTools(user: User | null): boolean {
  return hasBuildYourOwn(user);
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  // Indicates if session was invalidated by another tab (e.g., logout in another tab)
  sessionInvalidatedExternally: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, name: string) => Promise<User>;
  loginWithGoogle: (googleToken: string) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  // Clear the external invalidation flag (after user acknowledges)
  clearExternalInvalidation: () => void;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token storage keys
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Provider component
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
    sessionInvalidatedExternally: false,
  });

  // Track the current user ID to detect user changes across tabs
  const currentUserIdRef = useRef<string | null>(null);

  // Get stored token
  const getToken = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  }, []);

  // Set access token
  const setToken = useCallback((token: string | null) => {
    if (typeof window === 'undefined') return;
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  // Set refresh token
  const setRefreshToken = useCallback((token: string | null) => {
    if (typeof window === 'undefined') return;
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  }, []);

  // Clear external invalidation flag
  const clearExternalInvalidation = useCallback(() => {
    setState(prev => ({ ...prev, sessionInvalidatedExternally: false }));
  }, []);

  // Fetch current user
  const refreshUser = useCallback(async (isExternalChange = false) => {
    const token = getToken();
    if (!token) {
      // If we had a user before and now there's no token, mark as externally invalidated
      const wasAuthenticated = currentUserIdRef.current !== null;
      currentUserIdRef.current = null;
      setState({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        sessionInvalidatedExternally: wasAuthenticated && isExternalChange,
      });
      return;
    }

    try {
      const response = await api.get('/api/auth/me');
      const newUser = response.data;

      // Check if user changed (different user logged in from another tab)
      const userChanged = currentUserIdRef.current !== null &&
                          currentUserIdRef.current !== newUser.id;
      currentUserIdRef.current = newUser.id;

      setState({
        user: newUser,
        isLoading: false,
        isAuthenticated: true,
        // If a different user logged in externally, flag it
        sessionInvalidatedExternally: userChanged && isExternalChange,
      });
    } catch (error) {
      // Token invalid or expired
      const wasAuthenticated = currentUserIdRef.current !== null;
      currentUserIdRef.current = null;
      setToken(null);
      setState({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        sessionInvalidatedExternally: wasAuthenticated && isExternalChange,
      });
    }
  }, [getToken, setToken]);

  // Check auth status on mount
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // Listen for storage events (token changes from other tabs)
  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      // Only react to auth_token changes
      if (event.key !== TOKEN_KEY) return;

      console.log('[AuthContext] Token changed in another tab:', {
        oldValue: event.oldValue ? 'present' : 'none',
        newValue: event.newValue ? 'present' : 'none',
      });

      // Token was cleared in another tab (logout)
      if (!event.newValue && event.oldValue) {
        console.log('[AuthContext] Session invalidated by another tab (logout)');
        refreshUser(true); // true = external change
      }
      // Token was set/changed in another tab (login or user switch)
      else if (event.newValue && event.newValue !== event.oldValue) {
        console.log('[AuthContext] Token changed in another tab, refreshing user');
        refreshUser(true); // true = external change
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [refreshUser]);

  // Login with email/password
  const login = useCallback(async (email: string, password: string): Promise<User> => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await api.post('/api/auth/login', { email, password });
      const { access_token, refresh_token, user } = response.data;
      setToken(access_token);
      setRefreshToken(refresh_token);
      currentUserIdRef.current = user.id;
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
        sessionInvalidatedExternally: false,
      });
      return user;
    } catch (error: any) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  }, [setToken, setRefreshToken]);

  // Register with email/password
  const register = useCallback(async (email: string, password: string, name: string): Promise<User> => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await api.post('/api/auth/register', { email, password, name });
      const { access_token, refresh_token, user } = response.data;
      setToken(access_token);
      setRefreshToken(refresh_token);
      currentUserIdRef.current = user.id;
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
        sessionInvalidatedExternally: false,
      });
      return user;
    } catch (error: any) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(error.response?.data?.detail || 'Registration failed');
    }
  }, [setToken, setRefreshToken]);

  // Login with Google
  const loginWithGoogle = useCallback(async (googleToken: string): Promise<User> => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await api.post('/api/auth/google', { token: googleToken });
      const { access_token, refresh_token, user } = response.data;
      setToken(access_token);
      setRefreshToken(refresh_token);
      currentUserIdRef.current = user.id;
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
        sessionInvalidatedExternally: false,
      });
      return user;
    } catch (error: any) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(error.response?.data?.detail || 'Google login failed');
    }
  }, [setToken, setRefreshToken]);

  // Logout
  const logout = useCallback(() => {
    setToken(null);
    setRefreshToken(null);
    currentUserIdRef.current = null;
    setState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
      sessionInvalidatedExternally: false,
    });
    // Optionally call logout endpoint (not strictly necessary with JWT)
    api.post('/api/auth/logout').catch(() => {});
  }, [setToken, setRefreshToken]);

  const value: AuthContextType = {
    ...state,
    login,
    register,
    loginWithGoogle,
    logout,
    refreshUser,
    clearExternalInvalidation,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook to use auth context
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// HOC for protected routes
export function withAuth<P extends object>(
  WrappedComponent: React.ComponentType<P>
) {
  return function WithAuthComponent(props: P) {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
        </div>
      );
    }

    if (!isAuthenticated) {
      // Redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      return null;
    }

    return <WrappedComponent {...props} />;
  };
}
