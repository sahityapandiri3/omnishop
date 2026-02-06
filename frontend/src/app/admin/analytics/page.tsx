'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { analyticsAPI } from '@/utils/api';

/**
 * Analytics Admin Dashboard
 *
 * Tech tip: This is a first-party analytics dashboard. All data comes from our
 * own PostgreSQL database via the /api/analytics/admin/* endpoints. No third-party
 * like Google Analytics is involved — we own the data and can query it any way we want.
 */

// Type definitions for API responses
interface EventsPerDay {
  date: string;
  count: number;
}

interface Overview {
  total_users: number;
  active_users: number;
  new_signups: number;
  total_events: number;
  events_per_day: EventsPerDay[];
}

interface FunnelStep {
  step: string;
  count: number;
  percentage: number;
}

interface PageMetric {
  path: string;
  views: number;
  unique_users: number;
}

interface FeatureUsage {
  feature: string;
  event_count: number;
  unique_users: number;
}

interface DropoffStep {
  step: string;
  count: number;
  retained_pct: number;
}

interface DropoffFunnel {
  name: string;
  steps: DropoffStep[];
}

interface ActiveUser {
  user_id: string;
  email: string;
  name: string | null;
  event_count: number;
}

interface SearchEvent {
  id: number;
  user_id: string | null;
  user_email: string | null;
  query: string | null;
  results_count: number | null;
  filters_applied: Record<string, unknown> | null;
  page_url: string | null;
  created_at: string;
}

interface VisualizationEvent {
  id: number;
  event_type: string;
  user_id: string | null;
  user_email: string | null;
  project_id: string | null;
  session_id: string | null;  // For homestyling events
  product_count: number | null;
  views_count: number | null;  // For homestyling events (1, 3, or 6 views)
  products: Array<{ id: string; name: string; category?: string }> | null;
  wall_color: { id: string; name: string; code: string; hex: string } | null;
  wall_texture: { id: string; name: string } | null;
  floor_tile: { id: string; name: string } | null;
  method: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  duration_ms: number | null;
  success: boolean | null;
  page_url: string | null;
  created_at: string;
}

type DaysOption = 7 | 14 | 30 | 90;
type TabOption = 'overview' | 'searches' | 'visualizations';

function AnalyticsContent() {
  const [days, setDays] = useState<DaysOption>(7);
  const [activeTab, setActiveTab] = useState<TabOption>('overview');
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [overview, setOverview] = useState<Overview | null>(null);
  const [funnel, setFunnel] = useState<FunnelStep[]>([]);
  const [pages, setPages] = useState<PageMetric[]>([]);
  const [features, setFeatures] = useState<FeatureUsage[]>([]);
  const [dropoff, setDropoff] = useState<DropoffFunnel[]>([]);
  const [activeUsers, setActiveUsers] = useState<ActiveUser[]>([]);
  const [searches, setSearches] = useState<SearchEvent[]>([]);
  const [visualizations, setVisualizations] = useState<VisualizationEvent[]>([]);

  const fetchOverviewData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [overviewRes, funnelRes, pagesRes, featuresRes, dropoffRes, usersRes] = await Promise.all([
        analyticsAPI.getOverview(days),
        analyticsAPI.getFunnel(days),
        analyticsAPI.getPages(days),
        analyticsAPI.getFeatures(days),
        analyticsAPI.getDropoff(days),
        analyticsAPI.getActiveUsers(days),
      ]);

      setOverview(overviewRes.data);
      setFunnel(funnelRes.data.steps || []);
      setPages(pagesRes.data.pages || []);
      setFeatures(featuresRes.data.features || []);
      setDropoff(dropoffRes.data.funnels || []);
      setActiveUsers(usersRes.data.users || []);
    } catch (e: unknown) {
      console.error('Analytics fetch error:', e);
      setError(e instanceof Error ? e.message : 'Failed to fetch analytics');
    } finally {
      setLoading(false);
    }
  }, [days]);

  const fetchSearches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyticsAPI.getSearches(days, selectedUserId || undefined, 100);
      setSearches(res.data.events || []);
    } catch (e: unknown) {
      console.error('Searches fetch error:', e);
      setError(e instanceof Error ? e.message : 'Failed to fetch searches');
    } finally {
      setLoading(false);
    }
  }, [days, selectedUserId]);

  const fetchVisualizations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyticsAPI.getVisualizations(days, selectedUserId || undefined, 100);
      setVisualizations(res.data.events || []);
    } catch (e: unknown) {
      console.error('Visualizations fetch error:', e);
      setError(e instanceof Error ? e.message : 'Failed to fetch visualizations');
    } finally {
      setLoading(false);
    }
  }, [days, selectedUserId]);

  useEffect(() => {
    if (activeTab === 'overview') {
      fetchOverviewData();
    } else if (activeTab === 'searches') {
      fetchSearches();
    } else if (activeTab === 'visualizations') {
      fetchVisualizations();
    }
  }, [activeTab, days, selectedUserId, fetchOverviewData, fetchSearches, fetchVisualizations]);

  // Find max for bar chart scaling
  const maxEvents = overview?.events_per_day.reduce((max, d) => Math.max(max, d.count), 1) || 1;

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  };

  // Format date in IST (Indian Standard Time, UTC+5:30)
  const formatDate = (iso: string) => {
    const d = new Date(iso);
    // IST is UTC+5:30 - add 'Z' suffix if not present to treat as UTC
    const utcDate = iso.endsWith('Z') ? d : new Date(iso + 'Z');
    const istOptions: Intl.DateTimeFormatOptions = {
      timeZone: 'Asia/Kolkata',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    };
    return utcDate.toLocaleString('en-IN', istOptions);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <Link href="/admin" className="text-gray-400 hover:text-gray-600 transition-colors">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">User Analytics</h1>
            </div>
            <p className="text-gray-500 text-sm ml-8">Track user behavior, searches, and visualizations</p>
          </div>
          <div className="flex items-center gap-2">
            {([7, 14, 30, 90] as DaysOption[]).map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  days === d
                    ? 'bg-amber-600 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {/* Tabs & User Filter */}
        <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
          <div className="flex items-center gap-1 bg-white rounded-lg p-1 border border-gray-200">
            {(['overview', 'searches', 'visualizations'] as TabOption[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors capitalize ${
                  activeTab === tab
                    ? 'bg-amber-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* User Filter - shown on searches and visualizations tabs */}
          {(activeTab === 'searches' || activeTab === 'visualizations') && (
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Filter by user:</label>
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white min-w-[200px]"
              >
                <option value="">All Users</option>
                {activeUsers.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.email} ({u.event_count} events)
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Loading & Error */}
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-200 border-t-gray-800" />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm mb-6">
            {error}
          </div>
        )}

        {/* Overview Tab */}
        {!loading && !error && activeTab === 'overview' && overview && (
          <>
            {/* Overview Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm text-gray-500 mb-1">Total Users</p>
                <p className="text-3xl font-bold text-gray-900">{overview.total_users.toLocaleString()}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm text-gray-500 mb-1">Active Users ({days}d)</p>
                <p className="text-3xl font-bold text-amber-600">{overview.active_users.toLocaleString()}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm text-gray-500 mb-1">New Signups ({days}d)</p>
                <p className="text-3xl font-bold text-green-600">{overview.new_signups.toLocaleString()}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm text-gray-500 mb-1">Total Events ({days}d)</p>
                <p className="text-3xl font-bold text-blue-600">{overview.total_events.toLocaleString()}</p>
              </div>
            </div>

            {/* User Funnel */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">User Funnel</h2>
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {funnel.map((step, i) => (
                  <div key={step.step} className="flex items-center">
                    <div
                      className="flex flex-col items-center justify-center rounded-lg py-3 min-w-[120px]"
                      style={{
                        backgroundColor: `rgba(217, 119, 6, ${0.15 + step.percentage / 200})`,
                        width: `${Math.max(100, step.percentage)}px`,
                      }}
                    >
                      <span className="text-xs font-medium text-gray-600">{step.step}</span>
                      <span className="text-xl font-bold text-gray-900">{step.count}</span>
                      <span className="text-xs text-gray-500">{step.percentage.toFixed(1)}%</span>
                    </div>
                    {i < funnel.length - 1 && (
                      <svg className="w-6 h-6 text-gray-300 mx-1 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Drop-off Analysis */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Drop-off Analysis</h2>
              <div className="grid md:grid-cols-2 gap-6">
                {dropoff.map((f) => (
                  <div key={f.name}>
                    <h3 className="text-sm font-medium text-gray-700 mb-3">{f.name} Funnel</h3>
                    <div className="space-y-2">
                      {f.steps.map((step, i) => (
                        <div key={step.step} className="flex items-center gap-3">
                          <div className="w-28 text-xs text-gray-600 truncate" title={step.step}>{step.step}</div>
                          <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
                            <div
                              className={`h-full ${i === 0 ? 'bg-amber-500' : 'bg-amber-400'}`}
                              style={{ width: `${Math.min(100, step.retained_pct)}%` }}
                            />
                          </div>
                          <div className="w-12 text-right text-xs text-gray-600">{step.count}</div>
                          <div className="w-14 text-right text-xs font-medium text-gray-700">
                            {step.retained_pct.toFixed(1)}%
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Top Pages and Feature Usage */}
            <div className="grid md:grid-cols-2 gap-6 mb-8">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Top Pages</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 font-medium text-gray-600">Path</th>
                        <th className="text-right py-2 font-medium text-gray-600">Views</th>
                        <th className="text-right py-2 font-medium text-gray-600">Users</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pages.slice(0, 10).map((page) => (
                        <tr key={page.path} className="border-b border-gray-100">
                          <td className="py-2 text-gray-900 truncate max-w-[200px]" title={page.path}>{page.path}</td>
                          <td className="py-2 text-right text-gray-600">{page.views.toLocaleString()}</td>
                          <td className="py-2 text-right text-gray-600">{page.unique_users.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Feature Usage</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 font-medium text-gray-600">Feature</th>
                        <th className="text-right py-2 font-medium text-gray-600">Events</th>
                        <th className="text-right py-2 font-medium text-gray-600">Users</th>
                      </tr>
                    </thead>
                    <tbody>
                      {features.map((f) => (
                        <tr key={f.feature} className="border-b border-gray-100">
                          <td className="py-2 text-gray-900 capitalize">{f.feature}</td>
                          <td className="py-2 text-right text-gray-600">{f.event_count.toLocaleString()}</td>
                          <td className="py-2 text-right text-gray-600">{f.unique_users.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Events Timeline */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Events Timeline</h2>
              <div className="flex items-end gap-1 h-40 overflow-x-auto pb-2">
                {overview.events_per_day.map((day) => (
                  <div key={day.date} className="flex flex-col items-center min-w-[28px]">
                    <div
                      className="w-5 bg-amber-500 rounded-t"
                      style={{ height: `${(day.count / maxEvents) * 120}px` }}
                      title={`${day.date}: ${day.count} events`}
                    />
                    <span className="text-[10px] text-gray-400 mt-1 whitespace-nowrap">
                      {new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Searches Tab */}
        {!loading && !error && activeTab === 'searches' && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Search & Filter Events
              <span className="ml-2 text-sm font-normal text-gray-500">({searches.length} events)</span>
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 font-medium text-gray-600">Time (IST)</th>
                    <th className="text-left py-2 font-medium text-gray-600">User</th>
                    <th className="text-left py-2 font-medium text-gray-600">Query</th>
                    <th className="text-right py-2 font-medium text-gray-600">Results</th>
                    <th className="text-left py-2 font-medium text-gray-600">Filters Applied</th>
                  </tr>
                </thead>
                <tbody>
                  {searches.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-gray-500">No search events found</td>
                    </tr>
                  ) : (
                    searches.map((e) => (
                      <tr key={e.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-2 text-gray-600 whitespace-nowrap">{formatDate(e.created_at)}</td>
                        <td className="py-2 text-gray-900 truncate max-w-[150px]" title={e.user_email || ''}>
                          {e.user_email || <span className="text-gray-400">Anonymous</span>}
                        </td>
                        <td className="py-2 text-gray-900">
                          {e.query ? (
                            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{e.query}</span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="py-2 text-right text-gray-600">
                          {e.results_count !== null ? e.results_count.toLocaleString() : '—'}
                        </td>
                        <td className="py-2 text-gray-600 max-w-[200px]">
                          {e.filters_applied && Object.keys(e.filters_applied).length > 0 ? (
                            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded break-all">
                              {JSON.stringify(e.filters_applied)}
                            </code>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Visualizations Tab */}
        {!loading && !error && activeTab === 'visualizations' && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Visualization Events
              <span className="ml-2 text-sm font-normal text-gray-500">({visualizations.length} events)</span>
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Time (IST)</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">User</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Method</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Products</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Walls</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Flooring</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Tokens In</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Tokens Out</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Total</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-600">Duration</th>
                    <th className="text-center py-2 px-2 font-medium text-gray-600">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visualizations.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="py-8 text-center text-gray-500">No visualization events found</td>
                    </tr>
                  ) : (
                    visualizations.map((e) => {
                      // Determine event source type
                      const isHomestyling = e.event_type === 'homestyling.generate_complete';
                      const isCuration = e.event_type.startsWith('curated.');
                      const isDesign = e.event_type.startsWith('design.');

                      // Use method from API
                      const method = e.method || null;
                      const methodDisplay = method ? method.replace(/_/g, ' ') : '—';

                      // Color coding based on event source
                      const getMethodStyle = (isHS: boolean, isCur: boolean) => {
                        if (isHS) return 'bg-pink-100 text-pink-700';  // Homestyling = pink
                        if (isCur) return 'bg-green-100 text-green-700';  // Curation = green
                        return 'bg-blue-100 text-blue-700';  // Design = blue
                      };

                      return (
                        <tr key={e.id} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="py-2 px-2 text-gray-600 whitespace-nowrap text-xs">{formatDate(e.created_at)}</td>
                          <td className="py-2 px-2 text-gray-900 truncate max-w-[120px]" title={e.user_email || ''}>
                            {e.user_email ? e.user_email.split('@')[0] : <span className="text-gray-400">Anon</span>}
                          </td>
                          <td className="py-2 px-2">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getMethodStyle(isHomestyling, isCuration)}`}>
                              {methodDisplay}
                            </span>
                          </td>
                          <td className="py-2 px-2 text-gray-900">
                            {e.products && e.products.length > 0 ? (
                              <div
                                className="cursor-help"
                                title={e.products.map(p => p.name).join('\n')}
                              >
                                <span className={`font-medium ${isHomestyling ? 'text-pink-600' : isCuration ? 'text-green-600' : 'text-blue-600'}`}>
                                  {e.products.length}
                                </span>
                                <span className="text-gray-500 text-xs ml-1 block truncate max-w-[150px]">
                                  {e.products.map(p => p.name.split(' ')[0]).join(', ')}
                                </span>
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-gray-600">
                            <div className="flex flex-col gap-0.5">
                              {e.wall_color && (
                                <span
                                  className="inline-flex items-center gap-1 text-xs cursor-help"
                                  title={`${e.wall_color.name} (${e.wall_color.code}) - ${e.wall_color.hex}`}
                                >
                                  <span
                                    className="w-3 h-3 rounded-full border border-gray-300 flex-shrink-0"
                                    style={{ backgroundColor: e.wall_color.hex }}
                                  />
                                  <span className="truncate max-w-[80px]">{e.wall_color.name}</span>
                                </span>
                              )}
                              {e.wall_texture && (
                                <span
                                  className="text-xs text-purple-600 cursor-help inline-flex items-center gap-1"
                                  title={e.wall_texture.name}
                                >
                                  <span>🧱</span>
                                  <span className="truncate max-w-[80px]">{e.wall_texture.name}</span>
                                </span>
                              )}
                              {!e.wall_color && !e.wall_texture && (
                                <span className="text-gray-400">—</span>
                              )}
                            </div>
                          </td>
                          <td className="py-2 px-2 text-gray-600">
                            {e.floor_tile ? (
                              <span
                                className="text-xs text-teal-600 cursor-help inline-flex items-center gap-1"
                                title={e.floor_tile.name}
                              >
                                <span>🪨</span>
                                <span className="truncate max-w-[80px]">{e.floor_tile.name}</span>
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-right text-gray-600 whitespace-nowrap text-xs">
                            {e.input_tokens !== null ? (
                              <span title={`${e.input_tokens?.toLocaleString() || 0} input tokens`}>
                                {((e.input_tokens || 0) / 1000).toFixed(1)}k
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-right text-gray-600 whitespace-nowrap text-xs">
                            {e.output_tokens !== null ? (
                              <span title={`${e.output_tokens?.toLocaleString() || 0} output tokens`}>
                                {((e.output_tokens || 0) / 1000).toFixed(1)}k
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-right text-gray-600 whitespace-nowrap text-xs font-medium">
                            {e.input_tokens !== null || e.output_tokens !== null ? (
                              <span title={`${((e.input_tokens || 0) + (e.output_tokens || 0)).toLocaleString()} total tokens`}>
                                {(((e.input_tokens || 0) + (e.output_tokens || 0)) / 1000).toFixed(1)}k
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-right text-gray-600 whitespace-nowrap">
                            {e.duration_ms !== null ? `${(e.duration_ms / 1000).toFixed(1)}s` : '—'}
                          </td>
                          <td className="py-2 px-2 text-center">
                            {e.success === true && (
                              <span className="inline-flex items-center justify-center w-5 h-5 bg-green-100 rounded-full" title="Success">
                                <svg className="w-3 h-3 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                </svg>
                              </span>
                            )}
                            {e.success === false && (
                              <span className="inline-flex items-center justify-center w-5 h-5 bg-red-100 rounded-full" title="Failed">
                                <svg className="w-3 h-3 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                </svg>
                              </span>
                            )}
                            {e.success === null && <span className="text-gray-400">—</span>}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {/* Legend */}
            <div className="mt-4 pt-4 border-t border-gray-200 flex items-center gap-6 text-xs text-gray-600">
              <span className="font-medium">Legend:</span>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-pink-100 border border-pink-200"></span>
                <span>Homestyling</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-blue-100 border border-blue-200"></span>
                <span>Design Studio</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-green-100 border border-green-200"></span>
                <span>Curation</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <AnalyticsContent />
    </ProtectedRoute>
  );
}
