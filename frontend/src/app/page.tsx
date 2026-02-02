'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { getCuratedLooks, CuratedLook } from '@/utils/api';
import { useAuth, isAdmin } from '@/contexts/AuthContext';

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
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [looks, setLooks] = useState<CuratedLook[]>([]);
  const [loading, setLoading] = useState(true);
  const carouselRef = useRef<HTMLDivElement>(null);
  const isScrolling = useRef(false);

  // Get carousel items (triplicated for infinite scroll effect)
  const getCarouselLooks = () => {
    const displayLooks = looks.slice(0, 6).filter(look => look && (look.visualization_image || look.room_image));
    // Triple the items: [clone of end items] [original items] [clone of start items]
    return [...displayLooks, ...displayLooks, ...displayLooks];
  };

  // Initialize carousel position to the middle set
  useEffect(() => {
    if (!carouselRef.current || looks.length === 0) return;
    const container = carouselRef.current;
    const displayLooks = looks.slice(0, 6).filter(look => look && (look.visualization_image || look.room_image));
    const singleSetWidth = container.scrollWidth / 3;
    // Start at the middle set (instant, no animation)
    container.scrollLeft = singleSetWidth;
  }, [looks]);

  // Handle infinite scroll - snap back when reaching clone sections
  useEffect(() => {
    if (!carouselRef.current || looks.length === 0) return;
    const container = carouselRef.current;
    let scrollTimeout: NodeJS.Timeout;

    const handleScrollEnd = () => {
      if (isScrolling.current) return;

      const singleSetWidth = container.scrollWidth / 3;

      // If scrolled to the third set (clones at the end), snap back to middle
      if (container.scrollLeft >= singleSetWidth * 2 - 50) {
        isScrolling.current = true;
        container.style.scrollBehavior = 'auto';
        container.scrollLeft = container.scrollLeft - singleSetWidth;
        container.style.scrollBehavior = 'smooth';
        isScrolling.current = false;
      }
      // If scrolled to the first set (clones at the start), snap forward to middle
      else if (container.scrollLeft < singleSetWidth * 0.1) {
        isScrolling.current = true;
        container.style.scrollBehavior = 'auto';
        container.scrollLeft = container.scrollLeft + singleSetWidth;
        container.style.scrollBehavior = 'smooth';
        isScrolling.current = false;
      }
    };

    const handleScroll = () => {
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(handleScrollEnd, 100);
    };

    container.addEventListener('scroll', handleScroll);
    return () => {
      container.removeEventListener('scroll', handleScroll);
      clearTimeout(scrollTimeout);
    };
  }, [looks]);

  // Carousel scroll functions
  const scrollCarousel = (direction: 'left' | 'right') => {
    if (!carouselRef.current) return;
    const container = carouselRef.current;
    const scrollAmount = 400; // Scroll by roughly one card width

    if (direction === 'right') {
      container.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    } else {
      container.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
    }
  };

  // Auto-scroll carousel every 4 seconds
  useEffect(() => {
    if (looks.length === 0) return;

    const interval = setInterval(() => {
      scrollCarousel('right');
    }, 4000);

    return () => clearInterval(interval);
  }, [looks]);

  // Landing page is always accessible - no auto-redirect
  // Users can navigate to their dashboard via "Home Styling" or "Curated" links

  useEffect(() => {
    const fetchLooks = async () => {
      try {
        // Request medium-quality images for landing page (1200px, 80% quality - faster loading)
        // Fetch 50 looks (API max) to ensure we find the hardcoded home page looks (IDs 4, 5, 7, 8, 10)
        const response = await getCuratedLooks(undefined, 'medium', undefined, undefined, 50, 0);
        setLooks(response.looks);
      } catch (error) {
        console.error('Failed to fetch curated looks:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchLooks();
  }, []);

  // Show loading only while fetching looks (auth check no longer blocks the page)
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-neutral-200 border-t-neutral-800" />
      </div>
    );
  }

  // Use first look with a visualization image for the hero section
  const heroLook = looks.find(look => look.visualization_image || look.room_image);

  // Get hero image
  const heroImage = formatImageSrc(heroLook?.visualization_image || heroLook?.room_image);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Hero Section - Full Bleed */}
      <section className="relative h-screen w-full overflow-hidden">
        {/* Background Image */}
        <div className="absolute inset-0 bg-neutral-800">
          {heroImage ? (
            <img
              src={heroImage}
              alt="Beautifully styled room"
              className="absolute inset-0 w-full h-full object-cover opacity-90"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-neutral-700 to-neutral-900" />
          )}
          {/* Softer Overlay - gradient for depth */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/30 to-black/50" />
        </div>

        {/* Hero Content */}
        <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 text-center">
          <h1 className="font-display text-5xl md:text-6xl lg:text-7xl font-light text-white tracking-tight mb-6 max-w-4xl leading-tight">
            Style Your Space with Real Products
          </h1>
          <p className="text-lg md:text-xl text-white/85 font-light mb-10 max-w-2xl leading-relaxed">
            AI-powered interior styling with furniture and decor from top brands
          </p>
          <Link
            href="/pricing"
            className="px-10 py-4 bg-white text-neutral-800 text-xs uppercase tracking-[0.2em] font-medium hover:bg-neutral-100 transition-all duration-300 rounded-sm shadow-lg hover:shadow-xl"
          >
            Start Styling
          </Link>
        </div>

        {/* Scroll Indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/70">
          <span className="text-xs uppercase tracking-[0.2em]">Scroll</span>
          <div className="w-px h-8 bg-white/50 animate-pulse" />
        </div>
      </section>

      {/* Curated Looks Section - Horizontal Carousel */}
      <section className="py-12 md:py-16 bg-neutral-50">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-light text-neutral-800 text-center mb-10 px-6">
            Curated Looks
          </h2>

          {loading ? (
            <div className="flex gap-4 px-6 overflow-hidden">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex-shrink-0 w-[300px] md:w-[400px] aspect-[4/3] bg-neutral-200 animate-pulse rounded-lg" />
              ))}
            </div>
          ) : looks.length > 0 ? (
            <div className="relative group/carousel">
              {/* Left Arrow */}
              <button
                onClick={() => scrollCarousel('left')}
                className="absolute left-2 md:left-4 top-1/2 -translate-y-1/2 z-10 w-10 h-10 md:w-12 md:h-12 bg-white/90 hover:bg-white rounded-full shadow-lg flex items-center justify-center opacity-0 group-hover/carousel:opacity-100 transition-opacity duration-300 backdrop-blur-sm"
                aria-label="Scroll left"
              >
                <svg className="w-5 h-5 md:w-6 md:h-6 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              {/* Carousel Container */}
              <div
                ref={carouselRef}
                className="flex gap-4 px-6 overflow-x-auto scrollbar-hide scroll-smooth"
                style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
              >
                {getCarouselLooks().map((look, index) => (
                  <div
                    key={`${look.look_id}-${index}`}
                    className="flex-shrink-0 w-[280px] md:w-[380px] relative aspect-[4/3] overflow-hidden group rounded-xl cursor-pointer"
                  >
                    <img
                      src={formatImageSrc(look.visualization_image || look.room_image)}
                      alt={look.style_theme}
                      className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent opacity-70 group-hover:opacity-90 transition-opacity duration-500" />
                    <div className="absolute bottom-0 left-0 right-0 p-5">
                      <p className="font-display text-white text-lg font-light tracking-wide">{look.style_theme}</p>
                      {(look as any).room_type && (
                        <p className="text-white/70 text-sm mt-1 capitalize">{(look as any).room_type.replace('_', ' ')}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Right Arrow */}
              <button
                onClick={() => scrollCarousel('right')}
                className="absolute right-2 md:right-4 top-1/2 -translate-y-1/2 z-10 w-10 h-10 md:w-12 md:h-12 bg-white/90 hover:bg-white rounded-full shadow-lg flex items-center justify-center opacity-0 group-hover/carousel:opacity-100 transition-opacity duration-300 backdrop-blur-sm"
                aria-label="Scroll right"
              >
                <svg className="w-5 h-5 md:w-6 md:h-6 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* Scroll Indicator Dots - Mobile */}
              <div className="flex justify-center gap-2 mt-6 md:hidden">
                {looks.slice(0, 6).map((_, index) => (
                  <div key={index} className="w-2 h-2 rounded-full bg-neutral-300" />
                ))}
              </div>
            </div>
          ) : (
            <p className="text-center text-neutral-500 px-6">Curated looks coming soon</p>
          )}
        </div>
      </section>

      {/* Features Section - Compact with warm cream background */}
      <section className="py-10 md:py-12 bg-secondary-50 border-y border-neutral-200/60">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-8">
            <div className="text-center">
              <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-neutral-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
              </div>
              <h3 className="font-display text-2xl md:text-3xl font-light text-neutral-800 mb-2">
                Curated by Professional Stylists
              </h3>
              <p className="text-neutral-500 text-sm leading-relaxed">
                Room styles featuring products you can actually buy
              </p>
            </div>

            <div className="text-center">
              <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-neutral-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="font-display text-2xl md:text-3xl font-light text-neutral-800 mb-2">
                AI-Powered Styling
              </h3>
              <p className="text-neutral-500 text-sm leading-relaxed">
                Personalized recommendations that understand your taste
              </p>
            </div>

            <div className="text-center">
              <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-neutral-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-neutral-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </div>
              <h3 className="font-display text-2xl md:text-3xl font-light text-neutral-800 mb-2">
                Visualize Before You Buy
              </h3>
              <p className="text-neutral-500 text-sm leading-relaxed">
                See furniture in your actual space
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Visual Break with CTA */}
      <section className="relative h-[60vh] overflow-hidden">
        {/* Background - Use a different look from the carousel if available */}
        <div className="absolute inset-0 bg-neutral-800">
          {looks[2]?.visualization_image || looks[2]?.room_image ? (
            <img
              src={formatImageSrc(looks[2].visualization_image || looks[2].room_image)}
              alt="Transform your space"
              className="absolute inset-0 w-full h-full object-cover opacity-85"
            />
          ) : heroLook?.visualization_image || heroLook?.room_image ? (
            <img
              src={formatImageSrc(heroLook.visualization_image || heroLook.room_image)}
              alt="Transform your space"
              className="absolute inset-0 w-full h-full object-cover opacity-85"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-neutral-700 to-neutral-900" />
          )}
          {/* Softer overlay */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/40 to-black/50" />
        </div>

        {/* Content */}
        <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 text-center">
          <h2 className="font-display text-4xl md:text-5xl font-light text-white tracking-tight mb-6">
            Transform Your Space
          </h2>
          <Link
            href="/pricing"
            className="px-10 py-4 border border-white/80 text-white text-xs uppercase tracking-[0.2em] font-medium hover:bg-white hover:text-neutral-800 transition-all duration-300 rounded-sm"
          >
            Start Styling
          </Link>
        </div>
      </section>

      {/* Partner Stores */}
      <section className="py-12 md:py-14 bg-secondary-50/50 border-t border-neutral-200/60">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-center text-neutral-500 text-xs uppercase tracking-[0.25em] mb-8">
            Featuring Products From
          </p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 md:gap-10 items-center justify-items-center">
            <div className="text-center">
              <span className="font-display text-3xl md:text-4xl font-light text-neutral-800 hover:text-neutral-700 transition-colors duration-300 cursor-pointer">Mason Home</span>
            </div>
            <div className="text-center">
              <span className="font-display text-3xl md:text-4xl font-light text-neutral-800 hover:text-neutral-700 transition-colors duration-300 cursor-pointer">Fleck</span>
            </div>
            <div className="text-center">
              <span className="font-display text-3xl md:text-4xl font-light text-neutral-800 hover:text-neutral-700 transition-colors duration-300 cursor-pointer">Palasa</span>
            </div>
            <div className="text-center">
              <span className="font-display text-3xl md:text-4xl font-light text-neutral-800 hover:text-neutral-700 transition-colors duration-300 cursor-pointer">House of Things</span>
            </div>
            <div className="text-center col-span-2 md:col-span-1">
              <span className="font-display text-3xl md:text-4xl font-light text-neutral-800 hover:text-neutral-700 transition-colors duration-300 cursor-pointer">Modern Quests</span>
            </div>
          </div>
          <p className="text-center text-neutral-500 text-lg font-medium mt-6">
            and many more
          </p>
        </div>
      </section>

      {/* Footer - Simple */}
      <footer className="bg-neutral-800 py-6">
        <div className="max-w-5xl mx-auto px-6 text-center">
          <p className="text-xs text-neutral-400">
            © 2025 Omnishop. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
