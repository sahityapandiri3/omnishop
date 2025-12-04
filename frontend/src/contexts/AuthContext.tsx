'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api } from '@/utils/api';

// Types
export interface User {
  id: string;
  email: string;
  name: string | null;
  profile_image_url: string | null;
  auth_provider: string;
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  loginWithGoogle: (googleToken: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token storage key
const TOKEN_KEY = 'auth_token';

// Provider component
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // Get stored token
  const getToken = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  }, []);

  // Set token
  const setToken = useCallback((token: string | null) => {
    if (typeof window === 'undefined') return;
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  // Fetch current user
  const refreshUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setState({ user: null, isLoading: false, isAuthenticated: false });
      return;
    }

    try {
      const response = await api.get('/api/auth/me');
      setState({
        user: response.data,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      // Token invalid or expired
      setToken(null);
      setState({ user: null, isLoading: false, isAuthenticated: false });
    }
  }, [getToken, setToken]);

  // Check auth status on mount
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // Login with email/password
  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await api.post('/api/auth/login', { email, password });
      const { access_token, user } = response.data;
      setToken(access_token);
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error: any) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  }, [setToken]);

  // Register with email/password
  const register = useCallback(async (email: string, password: string, name: string) => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await api.post('/api/auth/register', { email, password, name });
      const { access_token, user } = response.data;
      setToken(access_token);
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error: any) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(error.response?.data?.detail || 'Registration failed');
    }
  }, [setToken]);

  // Login with Google
  const loginWithGoogle = useCallback(async (googleToken: string) => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await api.post('/api/auth/google', { token: googleToken });
      const { access_token, user } = response.data;
      setToken(access_token);
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error: any) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(error.response?.data?.detail || 'Google login failed');
    }
  }, [setToken]);

  // Logout
  const logout = useCallback(() => {
    setToken(null);
    setState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
    });
    // Optionally call logout endpoint (not strictly necessary with JWT)
    api.post('/api/auth/logout').catch(() => {});
  }, [setToken]);

  const value: AuthContextType = {
    ...state,
    login,
    register,
    loginWithGoogle,
    logout,
    refreshUser,
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
