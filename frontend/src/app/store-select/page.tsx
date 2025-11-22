'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getAvailableStores } from '@/utils/api';

export default function StoreSelectPage() {
  const router = useRouter();
  const [stores, setStores] = useState<string[]>([]);
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredStore, setHoveredStore] = useState<string | null>(null);

  useEffect(() => {
    const fetchStores = async () => {
      try {
        setLoading(true);
        const response = await getAvailableStores();
        setStores(response.stores);
      } catch (err) {
        console.error('Error fetching stores:', err);
        setError('Failed to load stores. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchStores();
  }, []);

  const toggleStore = (store: string) => {
    setSelectedStores((prev) =>
      prev.includes(store)
        ? prev.filter((s) => s !== store)
        : [...prev, store]
    );
  };

  const selectAll = () => {
    setSelectedStores([...stores]);
  };

  const deselectAll = () => {
    setSelectedStores([]);
  };

  const handleContinue = () => {
    sessionStorage.setItem('primaryStores', JSON.stringify(selectedStores));
    router.push('/design');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 flex items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-br from-purple-200/30 to-transparent rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-to-tl from-pink-200/30 to-transparent rounded-full blur-3xl animate-pulse delay-1000"></div>
        </div>

        <div className="text-center relative z-10">
          <div className="relative mb-8">
            <div className="animate-spin rounded-full h-20 w-20 border-4 border-purple-200 mx-auto"></div>
            <div className="animate-spin rounded-full h-20 w-20 border-t-4 border-purple-600 mx-auto absolute top-0 left-1/2 -translate-x-1/2"></div>
          </div>
          <p className="text-gray-700 text-xl font-medium">Discovering stores...</p>
          <p className="text-gray-500 text-sm mt-2">Finding the best furniture sources for you</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 flex items-center justify-center p-4">
        <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 max-w-md mx-auto border border-white/20">
          <div className="text-red-600 text-center mb-6">
            <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-lg font-semibold text-gray-800">{error}</p>
          </div>
          <button
            onClick={() => router.push('/')}
            className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white py-3.5 rounded-xl hover:from-purple-700 hover:to-pink-700 transition-all shadow-lg hover:shadow-xl font-medium"
          >
            Go Back Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 relative overflow-hidden">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-200/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-pink-200/20 rounded-full blur-3xl animate-pulse delay-700"></div>
      </div>

      <div className="relative z-10 py-12 px-4">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12 animate-fadeIn">
            <div className="inline-flex items-center gap-2 bg-white/50 backdrop-blur-sm px-4 py-2 rounded-full mb-6 border border-white/20">
              <div className="w-2 h-2 bg-purple-600 rounded-full animate-pulse"></div>
              <span className="text-sm font-medium text-gray-700">Step 2 of 3</span>
            </div>
            <h1 className="text-5xl font-bold bg-gradient-to-r from-purple-600 via-pink-600 to-purple-600 bg-clip-text text-transparent mb-4">
              Choose Your Stores
            </h1>
            <p className="text-gray-600 text-xl max-w-2xl mx-auto">
              Curate your perfect shopping experience by selecting your favorite furniture retailers
            </p>
          </div>

          <div className="bg-white/60 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/20 p-8 mb-8">
            <div className="flex gap-4 mb-8">
              <button
                onClick={selectAll}
                className="group flex-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white py-3.5 px-6 rounded-xl hover:from-purple-600 hover:to-pink-600 transition-all shadow-lg hover:shadow-xl font-medium transform hover:scale-[1.02] active:scale-[0.98]"
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Select All
                </span>
              </button>
              <button
                onClick={deselectAll}
                className="flex-1 bg-white text-gray-700 py-3.5 px-6 rounded-xl hover:bg-gray-50 transition-all shadow-md hover:shadow-lg font-medium border border-gray-200 transform hover:scale-[1.02] active:scale-[0.98]"
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Clear All
                </span>
              </button>
            </div>

            <div className="mb-8 text-center">
              <div className="inline-flex items-center gap-3 bg-gradient-to-r from-purple-50 to-pink-50 px-6 py-3 rounded-full border border-purple-200/50">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${selectedStores.length === 0 ? 'bg-blue-500' : 'bg-purple-500'} animate-pulse`}></div>
                  {selectedStores.length === 0 ? (
                    <span className="text-gray-700 font-medium">
                      Searching <span className="text-purple-600 font-bold">all {stores.length} stores</span>
                    </span>
                  ) : (
                    <span className="text-gray-700 font-medium">
                      <span className="text-purple-600 font-bold">{selectedStores.length}</span> of {stores.length} stores selected
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {stores.map((store, index) => {
                const isSelected = selectedStores.includes(store);
                const isHovered = hoveredStore === store;
                return (
                  <button
                    key={store}
                    onClick={() => toggleStore(store)}
                    onMouseEnter={() => setHoveredStore(store)}
                    onMouseLeave={() => setHoveredStore(null)}
                    className={`group relative p-6 rounded-2xl transition-all duration-300 transform ${
                      isSelected
                        ? 'bg-gradient-to-br from-purple-500 to-pink-500 text-white shadow-xl scale-[1.02] border-2 border-purple-400'
                        : 'bg-white/80 backdrop-blur-sm text-gray-700 shadow-md hover:shadow-xl hover:scale-[1.02] border-2 border-white/50 hover:border-purple-300'
                    }`}
                    style={{
                      animationDelay: `${index * 50}ms`,
                    }}
                  >
                    {!isSelected && isHovered && (
                      <div className="absolute inset-0 bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl opacity-50 transition-opacity"></div>
                    )}

                    <div className="relative flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1">
                        <div
                          className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold text-lg transition-all ${
                            isSelected
                              ? 'bg-white/20 text-white'
                              : 'bg-gradient-to-br from-purple-100 to-pink-100 text-purple-600 group-hover:scale-110'
                          }`}
                        >
                          {store.charAt(0).toUpperCase()}
                        </div>

                        <div className="text-left flex-1">
                          <span className={`font-semibold block text-base capitalize ${isSelected ? 'text-white' : 'text-gray-800'}`}>
                            {store.replace(/([A-Z])/g, ' $1').trim()}
                          </span>
                          <span className={`text-xs ${isSelected ? 'text-white/80' : 'text-gray-500'}`}>
                            Premium retailer
                          </span>
                        </div>
                      </div>

                      <div
                        className={`flex-shrink-0 transition-all duration-300 ${
                          isSelected ? 'scale-100 opacity-100' : 'scale-75 opacity-0'
                        }`}
                      >
                        <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
                          <svg className="w-5 h-5 text-purple-600" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        </div>
                      </div>
                    </div>

                    {!isSelected && isHovered && (
                      <div className="absolute inset-0 rounded-2xl overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer"></div>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 mb-8">
            <button
              onClick={() => router.push('/')}
              className="group sm:flex-1 bg-white/80 backdrop-blur-sm text-gray-700 py-4 px-8 rounded-xl hover:bg-white transition-all shadow-md hover:shadow-lg font-semibold text-lg border border-gray-200 transform hover:scale-[1.02] active:scale-[0.98]"
            >
              <span className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5 transform group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back to Upload
              </span>
            </button>
            <button
              onClick={handleContinue}
              className="group sm:flex-[2] bg-gradient-to-r from-purple-600 via-pink-600 to-purple-600 bg-size-200 bg-pos-0 hover:bg-pos-100 text-white py-4 px-8 rounded-xl transition-all duration-500 font-semibold text-lg shadow-xl hover:shadow-2xl transform hover:scale-[1.02] active:scale-[0.98]"
            >
              <span className="flex items-center justify-center gap-2">
                Continue to Design Studio
                <svg className="w-5 h-5 transform group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </span>
            </button>
          </div>

          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 backdrop-blur-sm border border-blue-200/50 rounded-2xl p-6 shadow-lg">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-400 to-indigo-500 rounded-xl flex items-center justify-center">
                  <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-800 mb-2">Pro Tip</h3>
                <p className="text-gray-700 leading-relaxed">
                  Customize your experience anytime! Change your store selection from the design page,
                  or leave everything unselected to browse our complete catalog of <span className="font-semibold text-purple-600">{stores.length}+ premium retailers</span>.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
