'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/ProtectedRoute';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface OperationSummary {
  operation: string;
  calls: number;
  tokens: number;
}

interface ModelSummary {
  model: string;
  calls: number;
  tokens: number;
}

interface DetailedLog {
  timestamp: string;
  user: string;
  provider: string;
  model: string;
  operation: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  session_id: string | null;
}

interface UsageData {
  status: string;
  period_hours: number;
  usage: {
    total_api_calls: number;
    total_tokens: number;
    by_operation: OperationSummary[];
    by_provider: { provider: string; calls: number; tokens: number }[];
    by_model: ModelSummary[];
    detailed_log: DetailedLog[];
  };
}

function ApiUsageContent() {
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hours, setHours] = useState(24);

  const fetchUsage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/visualization/api-usage?hours=${hours}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <Link href="/admin" className="text-gray-400 hover:text-gray-600 transition-colors">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">API Usage</h1>
            </div>
            <p className="text-gray-500 text-sm ml-8">Gemini and OpenAI API call tracking</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value={1}>Last 1 hour</option>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={72}>Last 3 days</option>
              <option value={168}>Last 7 days</option>
            </select>
            <button
              onClick={fetchUsage}
              className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm hover:bg-gray-800 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading && (
          <div className="text-center py-12 text-gray-500">Loading...</div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
            Error: {error}
          </div>
        )}

        {data && !loading && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="text-sm text-gray-500 mb-1">Total API Calls</div>
                <div className="text-3xl font-bold text-gray-900">{data.usage.total_api_calls}</div>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="text-sm text-gray-500 mb-1">Total Tokens</div>
                <div className="text-3xl font-bold text-gray-900">{data.usage.total_tokens.toLocaleString()}</div>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="text-sm text-gray-500 mb-1">Period</div>
                <div className="text-3xl font-bold text-gray-900">{data.period_hours}h</div>
              </div>
            </div>

            {/* Summary Tables */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* By Operation */}
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h2 className="font-semibold text-gray-900">By Operation</h2>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <th className="px-6 py-3">Operation</th>
                      <th className="px-6 py-3 text-right">Calls</th>
                      <th className="px-6 py-3 text-right">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.usage.by_operation.map((op) => (
                      <tr key={op.operation} className="hover:bg-gray-50">
                        <td className="px-6 py-3 text-sm text-gray-900 font-mono">{op.operation}</td>
                        <td className="px-6 py-3 text-sm text-gray-700 text-right">{op.calls}</td>
                        <td className="px-6 py-3 text-sm text-gray-700 text-right">{op.tokens.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* By Model */}
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h2 className="font-semibold text-gray-900">By Model</h2>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <th className="px-6 py-3">Model</th>
                      <th className="px-6 py-3 text-right">Calls</th>
                      <th className="px-6 py-3 text-right">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.usage.by_model.map((m) => (
                      <tr key={m.model} className="hover:bg-gray-50">
                        <td className="px-6 py-3 text-sm text-gray-900 font-mono">{m.model}</td>
                        <td className="px-6 py-3 text-sm text-gray-700 text-right">{m.calls}</td>
                        <td className="px-6 py-3 text-sm text-gray-700 text-right">{m.tokens.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Detailed Log */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">
                  Detailed Log ({data.usage.detailed_log.length} calls)
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <th className="px-4 py-3">Time</th>
                      <th className="px-4 py-3">User</th>
                      <th className="px-4 py-3">Model</th>
                      <th className="px-4 py-3">Operation</th>
                      <th className="px-4 py-3 text-right">Prompt</th>
                      <th className="px-4 py-3 text-right">Completion</th>
                      <th className="px-4 py-3 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.usage.detailed_log.map((log, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                          <span className="text-gray-400">{formatDate(log.timestamp)}</span>{' '}
                          {formatTime(log.timestamp)}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-600 max-w-[120px] truncate">
                          {log.user}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-700 font-mono whitespace-nowrap">
                          {log.model}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-900 font-mono whitespace-nowrap">
                          {log.operation}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-600 text-right tabular-nums">
                          {log.prompt_tokens.toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-600 text-right tabular-nums">
                          {log.completion_tokens.toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-900 font-medium text-right tabular-nums">
                          {log.total_tokens.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ApiUsagePage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <ApiUsageContent />
    </ProtectedRoute>
  );
}
