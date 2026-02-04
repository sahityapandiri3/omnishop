'use client';

import { useState, useEffect, useCallback } from 'react';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { api } from '@/utils/api';
import { useAuth } from '@/contexts/AuthContext';

interface UserListItem {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface UserListResponse {
  users: UserListItem[];
  total: number;
  page: number;
  size: number;
}

interface WhitelistSettings {
  enabled: boolean;
  emails: string[];
}

function PermissionsPageContent() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [togglingUserId, setTogglingUserId] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Whitelist state
  const [whitelistEnabled, setWhitelistEnabled] = useState(false);
  const [whitelistEmails, setWhitelistEmails] = useState<string[]>([]);
  const [newEmail, setNewEmail] = useState('');
  const [whitelistLoading, setWhitelistLoading] = useState(true);
  const [whitelistSaving, setWhitelistSaving] = useState(false);
  const [whitelistDirty, setWhitelistDirty] = useState(false);

  const pageSize = 20;

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = {
        page,
        size: pageSize,
      };
      if (search.trim()) {
        params.search = search.trim();
      }
      if (roleFilter) {
        params.role = roleFilter;
      }

      const response = await api.get<UserListResponse>('/api/admin/permissions/users', { params });
      setUsers(response.data.users);
      setTotal(response.data.total);
    } catch (err: any) {
      console.error('Error fetching users:', err);
      setError(err.response?.data?.detail || 'Failed to fetch users');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, roleFilter]);

  const fetchWhitelistSettings = useCallback(async () => {
    setWhitelistLoading(true);
    try {
      const response = await api.get<WhitelistSettings>('/api/admin/permissions/settings/whitelist');
      setWhitelistEnabled(response.data.enabled);
      setWhitelistEmails(response.data.emails);
      setWhitelistDirty(false);
    } catch (err: any) {
      console.error('Error fetching whitelist settings:', err);
    } finally {
      setWhitelistLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    fetchWhitelistSettings();
  }, [fetchWhitelistSettings]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      fetchUsers();
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (userId === currentUser?.id) {
      setError("You cannot change your own role");
      return;
    }

    setUpdatingUserId(userId);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await api.put(`/api/admin/permissions/users/${userId}/role`, {
        role: newRole,
      });

      // Update local state
      setUsers(prev => prev.map(u =>
        u.id === userId ? { ...u, role: newRole } : u
      ));

      setSuccessMessage(`Role updated successfully for ${response.data.email}`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error updating role:', err);
      setError(err.response?.data?.detail || 'Failed to update role');
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleToggleActive = async (userId: string, newValue: boolean) => {
    if (userId === currentUser?.id) {
      setError("You cannot change your own status");
      return;
    }

    setTogglingUserId(userId);
    setError(null);
    setSuccessMessage(null);

    // Optimistic update
    setUsers(prev => prev.map(u =>
      u.id === userId ? { ...u, is_active: newValue } : u
    ));

    try {
      const response = await api.put(`/api/admin/permissions/users/${userId}/active`, {
        is_active: newValue,
      });

      const action = newValue ? 'unblocked' : 'blocked';
      setSuccessMessage(`User ${response.data.email} ${action} successfully`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error toggling user active status:', err);
      // Revert optimistic update
      setUsers(prev => prev.map(u =>
        u.id === userId ? { ...u, is_active: !newValue } : u
      ));
      setError(err.response?.data?.detail || 'Failed to update user status');
    } finally {
      setTogglingUserId(null);
    }
  };

  const handleAddEmail = () => {
    const email = newEmail.trim().toLowerCase();
    if (!email) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid email address');
      return;
    }
    if (whitelistEmails.includes(email)) {
      setError('Email is already in the whitelist');
      return;
    }
    setWhitelistEmails(prev => [...prev, email]);
    setNewEmail('');
    setWhitelistDirty(true);
    setError(null);
  };

  const handleRemoveEmail = (email: string) => {
    setWhitelistEmails(prev => prev.filter(e => e !== email));
    setWhitelistDirty(true);
  };

  const handleWhitelistToggle = (enabled: boolean) => {
    setWhitelistEnabled(enabled);
    setWhitelistDirty(true);
  };

  const handleSaveWhitelist = async () => {
    setWhitelistSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await api.put('/api/admin/permissions/settings/whitelist', {
        enabled: whitelistEnabled,
        emails: whitelistEmails,
      });

      setWhitelistDirty(false);
      setSuccessMessage('Whitelist settings saved successfully');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error saving whitelist:', err);
      setError(err.response?.data?.detail || 'Failed to save whitelist settings');
    } finally {
      setWhitelistSaving(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'super_admin':
        return 'bg-purple-100 text-purple-800';
      case 'admin':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">User Permissions</h1>
          <p className="mt-2 text-gray-600">
            Manage user roles and permissions. Only super admins can access this page.
          </p>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-red-700">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {successMessage && (
          <div className="mb-6 p-4 bg-neutral-100 border border-neutral-300 rounded-lg flex items-center gap-3">
            <svg className="w-5 h-5 text-neutral-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-neutral-700">{successMessage}</span>
          </div>
        )}

        {/* Access Control - Whitelist Settings */}
        <div className="mb-6 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Access Control</h2>
          <p className="text-sm text-gray-500 mb-4">
            Restrict registration and login to a specific list of email addresses.
          </p>

          {whitelistLoading ? (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600"></div>
              Loading settings...
            </div>
          ) : (
            <>
              {/* Whitelist Toggle */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-sm font-medium text-gray-700">Whitelist-only access</span>
                  <p className="text-xs text-gray-400 mt-0.5">
                    When enabled, only whitelisted emails can register or log in.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={whitelistEnabled}
                  onClick={() => handleWhitelistToggle(!whitelistEnabled)}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 ${
                    whitelistEnabled ? 'bg-purple-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      whitelistEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Email list (shown when enabled) */}
              {whitelistEnabled && (
                <div className="border-t border-gray-100 pt-4">
                  {/* Add email input */}
                  <div className="flex gap-2 mb-3">
                    <input
                      type="email"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddEmail();
                        }
                      }}
                      placeholder="Add email to whitelist..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    />
                    <button
                      onClick={handleAddEmail}
                      className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
                    >
                      Add
                    </button>
                  </div>

                  {/* Email list */}
                  {whitelistEmails.length === 0 ? (
                    <p className="text-sm text-gray-400 italic">
                      No emails in whitelist. Add emails above to allow access.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {whitelistEmails.map((email) => (
                        <span
                          key={email}
                          className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
                        >
                          {email}
                          <button
                            onClick={() => handleRemoveEmail(email)}
                            className="ml-1 text-gray-400 hover:text-red-500"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Save button */}
              {whitelistDirty && (
                <div className="mt-4 flex items-center gap-3 border-t border-gray-100 pt-4">
                  <button
                    onClick={handleSaveWhitelist}
                    disabled={whitelistSaving}
                    className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {whitelistSaving ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    onClick={fetchWhitelistSettings}
                    disabled={whitelistSaving}
                    className="px-4 py-2 text-gray-600 text-sm font-medium rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Cancel
                  </button>
                  <span className="text-xs text-amber-600">Unsaved changes</span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Filters */}
        <div className="mb-6 bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <label htmlFor="search" className="sr-only">Search by email</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  id="search"
                  placeholder="Search by email..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Role Filter */}
            <div className="sm:w-48">
              <label htmlFor="roleFilter" className="sr-only">Filter by role</label>
              <select
                id="roleFilter"
                value={roleFilter}
                onChange={(e) => {
                  setRoleFilter(e.target.value);
                  setPage(1);
                }}
                className="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              >
                <option value="">All roles</option>
                <option value="user">User</option>
                <option value="admin">Admin</option>
                <option value="super_admin">Super Admin</option>
              </select>
            </div>
          </div>

          <div className="mt-4 text-sm text-gray-500">
            {total} user{total !== 1 ? 's' : ''} found
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto"></div>
              <p className="mt-4 text-gray-500">Loading users...</p>
            </div>
          ) : users.length === 0 ? (
            <div className="p-12 text-center">
              <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
              <p className="text-gray-500">No users found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Current Role
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Joined
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Change Role
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((user) => {
                    const isSelf = user.id === currentUser?.id;
                    const isSuperAdmin = user.role === 'super_admin';
                    const canToggle = !isSelf && !isSuperAdmin;

                    return (
                      <tr key={user.id} className={isSelf ? 'bg-purple-50' : ''}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div className="flex-shrink-0 h-10 w-10 bg-gray-200 rounded-full flex items-center justify-center">
                              <span className="text-gray-600 font-medium">
                                {(user.name || user.email)[0].toUpperCase()}
                              </span>
                            </div>
                            <div className="ml-4">
                              <div className="text-sm font-medium text-gray-900">
                                {user.name || 'No name'}
                                {isSelf && (
                                  <span className="ml-2 text-xs text-purple-600">(you)</span>
                                )}
                              </div>
                              <div className="text-sm text-gray-500">{user.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(user.role)}`}>
                            {user.role === 'super_admin' ? 'Super Admin' : user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {canToggle ? (
                              <>
                                <button
                                  type="button"
                                  role="switch"
                                  aria-checked={user.is_active}
                                  onClick={() => handleToggleActive(user.id, !user.is_active)}
                                  disabled={togglingUserId === user.id}
                                  className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                                    user.is_active ? 'bg-green-500' : 'bg-red-400'
                                  }`}
                                >
                                  <span
                                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                      user.is_active ? 'translate-x-4' : 'translate-x-0'
                                    }`}
                                  />
                                </button>
                                {togglingUserId === user.id ? (
                                  <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-purple-600"></div>
                                ) : (
                                  <span className={`text-xs ${user.is_active ? 'text-green-700' : 'text-red-700'}`}>
                                    {user.is_active ? 'Active' : 'Blocked'}
                                  </span>
                                )}
                              </>
                            ) : (
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${user.is_active ? 'bg-neutral-200 text-neutral-700' : 'bg-red-100 text-red-800'}`}>
                                {user.is_active ? 'Active' : 'Blocked'}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDate(user.created_at)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {isSelf ? (
                            <span className="text-sm text-gray-400 italic">Cannot change own role</span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <select
                                value={user.role}
                                onChange={(e) => handleRoleChange(user.id, e.target.value)}
                                disabled={updatingUserId === user.id}
                                className="block w-32 px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
                              >
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                                <option value="super_admin">Super Admin</option>
                              </select>
                              {updatingUserId === user.id && (
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600"></div>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
              <div className="flex-1 flex justify-between sm:hidden">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-gray-700">
                    Showing <span className="font-medium">{(page - 1) * pageSize + 1}</span> to{' '}
                    <span className="font-medium">{Math.min(page * pageSize, total)}</span> of{' '}
                    <span className="font-medium">{total}</span> results
                  </p>
                </div>
                <div>
                  <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span className="sr-only">Previous</span>
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (page <= 3) {
                        pageNum = i + 1;
                      } else if (page >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = page - 2 + i;
                      }
                      return (
                        <button
                          key={pageNum}
                          onClick={() => setPage(pageNum)}
                          className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                            page === pageNum
                              ? 'z-10 bg-purple-50 border-purple-500 text-purple-600'
                              : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                    <button
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span className="sr-only">Next</span>
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  </nav>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Role Legend */}
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-sm font-medium text-gray-900 mb-4">Role Permissions</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-start gap-3">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor('user')}`}>
                User
              </span>
              <p className="text-sm text-gray-600">
                Can access Curated Looks, Design Studio, and their own projects.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor('admin')}`}>
                Admin
              </span>
              <p className="text-sm text-gray-600">
                User privileges plus access to Admin page and can edit all curations.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor('super_admin')}`}>
                Super Admin
              </span>
              <p className="text-sm text-gray-600">
                Admin privileges plus access to this Permissions page to manage user roles.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PermissionsPage() {
  return (
    <ProtectedRoute requiredRole="super_admin">
      <PermissionsPageContent />
    </ProtectedRoute>
  );
}
