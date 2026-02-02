/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Primary: Soft teal/sage (luxury interior feel)
        primary: {
          50: '#f7fafa',
          100: '#e8f4f3',
          200: '#d1e9e7',
          300: '#a8d5d1',
          400: '#7ebdb7',
          500: '#5a9f99',   // Main brand color
          600: '#4a8580',
          700: '#3d6b67',
          800: '#345755',
          900: '#2d4946',
        },
        // Secondary: Warm cream/gold (accent warmth)
        secondary: {
          50: '#fdfcfa',
          100: '#f9f6f0',
          200: '#f2ebe0',
          300: '#e8dcc8',
          400: '#d4c4a8',
          500: '#c4b08a',
          600: '#a89470',
          700: '#8a785c',
          800: '#6e604a',
          900: '#584c3c',
        },
        // Neutral: Warm grays (cream-tinted, not cold)
        neutral: {
          50: '#fafaf9',    // Page background
          100: '#f5f4f2',   // Card backgrounds
          200: '#e8e6e3',   // Borders, dividers
          300: '#d4d1cc',   // Muted text
          400: '#a8a49e',   // Placeholder text
          500: '#78746d',   // Secondary text
          600: '#5c5955',   // Body text
          700: '#44423f',   // Headings
          800: '#2d2b29',   // Dark text
          900: '#1a1918',   // Near black
        },
        // Accent: Soft terracotta/rust (warm pop)
        accent: {
          50: '#fdf7f5',
          100: '#f9ebe6',
          200: '#f2d4cc',
          300: '#e5b5a8',
          400: '#d4917f',
          500: '#c27560',
          600: '#a85c48',
          700: '#8a4a3a',
          800: '#6e3c30',
          900: '#5a3228',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        display: ['var(--font-playfair)', 'Georgia', 'serif'],  // For headings
        body: ['var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'fadeIn': 'fadeIn 0.6s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
      backgroundSize: {
        '200': '200% 200%',
      },
      backgroundPosition: {
        '0': '0% 50%',
        '100': '100% 50%',
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
        'medium': '0 4px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        'strong': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
    require('@tailwindcss/line-clamp'),
  ],
}
