'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getCuratedLooks, CuratedLook } from '@/utils/api';

// Helper to format image source - handles base64 and URLs
const formatImageSrc = (src: string | null | undefined): string => {
  if (!src) return '';
  // If it's already a URL or data URI, return as-is
  if (src.startsWith('http') || src.startsWith('data:')) return src;
  // If it's base64 data (starts with /9j/ for JPEG or similar), add data URI prefix
  if (src.startsWith('/9j/') || src.startsWith('iVBOR')) {
    const isJpeg = src.startsWith('/9j/');
    return `data:image/${isJpeg ? 'jpeg' : 'png'};base64,${src}`;
  }
  return src;
};

export default function HomePage() {
  const [looks, setLooks] = useState<CuratedLook[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLooks = async () => {
      try {
        // Request full-quality images for landing page (not thumbnails)
        const response = await getCuratedLooks(undefined, true);
        setLooks(response.looks.slice(0, 5)); // Get first 5 looks
      } catch (error) {
        console.error('Failed to fetch curated looks:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchLooks();
  }, []);

  // Get hero image from first look or use placeholder
  const heroImage = formatImageSrc(looks[0]?.visualization_image || looks[0]?.room_image);

  return (
    <div className="min-h-screen bg-white">
      {/* Hero Section - Full Bleed */}
      <section className="relative h-screen w-full overflow-hidden">
        {/* Background Image */}
        <div className="absolute inset-0 bg-neutral-900">
          {heroImage ? (
            <img
              src={heroImage}
              alt="Beautifully styled room"
              className="absolute inset-0 w-full h-full object-cover opacity-80"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-neutral-800 to-neutral-900" />
          )}
          {/* Overlay */}
          <div className="absolute inset-0 bg-black/40" />
        </div>

        {/* Hero Content */}
        <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 text-center">
          <h1 className="text-5xl md:text-7xl font-light text-white tracking-tight mb-6 max-w-4xl">
            Design Your Space with Real Products
          </h1>
          <p className="text-lg md:text-xl text-white/80 font-light mb-12 max-w-2xl">
            AI-powered interior styling with furniture and decor from top stores
          </p>
          <Link
            href="/login"
            className="px-10 py-4 bg-white text-neutral-900 text-sm uppercase tracking-[0.2em] font-medium hover:bg-neutral-100 transition-colors"
          >
            Start Styling
          </Link>
        </div>

        {/* Scroll Indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/60">
          <span className="text-xs uppercase tracking-widest">Scroll</span>
          <div className="w-px h-8 bg-white/40 animate-pulse" />
        </div>
      </section>

      {/* Curated Looks Section */}
      <section className="py-24 md:py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-light text-neutral-900 text-center mb-16">
            Curated Looks
          </h2>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className={`${i === 0 ? 'md:col-span-2 md:row-span-2' : ''} aspect-[4/3] bg-neutral-100 animate-pulse rounded-lg`} />
              ))}
            </div>
          ) : looks.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Large Featured Look - Modern Luxe Living Room (index 4) */}
              {looks[4] && (looks[4].visualization_image || looks[4].room_image) && (
                <div className="md:col-span-2 md:row-span-2 relative aspect-[4/3] md:aspect-auto md:min-h-[500px] overflow-hidden group rounded-lg">
                  <img
                    src={formatImageSrc(looks[4].visualization_image || looks[4].room_image)}
                    alt={looks[4].style_theme}
                    className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                  <div className="absolute bottom-0 left-0 right-0 p-6 translate-y-4 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-500">
                    <p className="text-white text-xl font-light">{looks[4].style_theme}</p>
                  </div>
                </div>
              )}

              {/* Smaller Looks - Scandinavian and Contemporary */}
              {looks.slice(1, 3).map((look) => (
                (look.visualization_image || look.room_image) && (
                  <div key={look.look_id} className="relative aspect-[4/3] overflow-hidden group rounded-lg">
                    <img
                      src={formatImageSrc(look.visualization_image || look.room_image)}
                      alt={look.style_theme}
                      className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <div className="absolute bottom-0 left-0 right-0 p-4 translate-y-4 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-500">
                      <p className="text-white text-lg font-light">{look.style_theme}</p>
                    </div>
                  </div>
                )
              ))}
            </div>
          ) : (
            <p className="text-center text-neutral-500">Curated looks coming soon</p>
          )}
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 md:py-32 bg-[#FAFAF9]">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-16 md:gap-12">
            <div className="text-center">
              <h3 className="text-2xl font-light text-neutral-900 mb-4">
                Curated by Professional Stylists
              </h3>
              <p className="text-neutral-500 font-light leading-relaxed">
                Room styles featuring products you can actually buy
              </p>
            </div>

            <div className="text-center">
              <h3 className="text-2xl font-light text-neutral-900 mb-4">
                AI-Powered Styling
              </h3>
              <p className="text-neutral-500 font-light leading-relaxed">
                Personalized recommendations that understand your taste
              </p>
            </div>

            <div className="text-center">
              <h3 className="text-2xl font-light text-neutral-900 mb-4">
                Visualize Before You Buy
              </h3>
              <p className="text-neutral-500 font-light leading-relaxed">
                See furniture in your actual space
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Visual Break with CTA */}
      <section className="relative h-[70vh] overflow-hidden">
        {/* Background - use a different look or gradient */}
        <div className="absolute inset-0 bg-neutral-900">
          {looks[3]?.visualization_image || looks[3]?.room_image ? (
            <img
              src={formatImageSrc(looks[3].visualization_image || looks[3].room_image)}
              alt="Transform your space"
              className="absolute inset-0 w-full h-full object-cover opacity-70"
            />
          ) : looks[1]?.visualization_image || looks[1]?.room_image ? (
            <img
              src={formatImageSrc(looks[1].visualization_image || looks[1].room_image)}
              alt="Transform your space"
              className="absolute inset-0 w-full h-full object-cover opacity-70"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-neutral-700 to-neutral-900" />
          )}
          <div className="absolute inset-0 bg-black/50" />
        </div>

        {/* Content */}
        <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 text-center">
          <h2 className="text-4xl md:text-5xl font-light text-white tracking-tight mb-8">
            Transform Your Space
          </h2>
          <Link
            href="/login"
            className="px-10 py-4 border border-white text-white text-sm uppercase tracking-[0.2em] font-medium hover:bg-white hover:text-neutral-900 transition-all"
          >
            Start Styling
          </Link>
        </div>
      </section>

      {/* Partner Stores */}
      <section className="py-16 md:py-20 border-t border-neutral-100">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-center text-neutral-400 text-sm uppercase tracking-widest mb-8">
            Products from
          </p>
          <div className="flex flex-wrap justify-center items-center gap-8 md:gap-16">
            <span className="text-xl md:text-2xl font-light text-neutral-300 hover:text-neutral-600 transition-colors">Mason Home</span>
            <span className="text-xl md:text-2xl font-light text-neutral-300 hover:text-neutral-600 transition-colors">Fleck</span>
            <span className="text-xl md:text-2xl font-light text-neutral-300 hover:text-neutral-600 transition-colors">Palasa</span>
            <span className="text-xl md:text-2xl font-light text-neutral-300 hover:text-neutral-600 transition-colors">House of Things</span>
            <span className="text-xl md:text-2xl font-light text-neutral-300 hover:text-neutral-600 transition-colors">Modern Quests</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-neutral-900 text-neutral-400 py-12">
        <div className="max-w-5xl mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="text-center md:text-left">
              <h3 className="text-xl font-light text-white tracking-wide">Omnishop</h3>
            </div>
            <div className="flex gap-10 text-sm tracking-wide">
              <Link href="/curated" className="hover:text-white transition-colors">Curated Looks</Link>
              <Link href="/design" className="hover:text-white transition-colors">Design Studio</Link>
              <Link href="/products" className="hover:text-white transition-colors">Products</Link>
            </div>
          </div>
          <div className="border-t border-neutral-800 mt-8 pt-8 text-center">
            <p className="text-sm text-neutral-500">
              © 2024 Omnishop
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
