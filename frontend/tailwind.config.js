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
        // Teal palette (cool tones from left side of palette)
        primary: {
          50: '#f0f7f7',
          100: '#d4e8e8',
          200: '#a8d4d4',
          300: '#7eb8b0',
          400: '#5a9a94',
          500: '#4a8a84',
          600: '#3d7a74',
          700: '#2d5f5a',
          800: '#1f4a46',
          900: '#1a3634',
        },
        // Warm palette (orange/gold from right side)
        secondary: {
          50: '#fdf8f0',
          100: '#f8edd8',
          200: '#f0d8b0',
          300: '#e8c088',
          400: '#d8a048',
          500: '#c88a38',
          600: '#b87830',
          700: '#a06528',
          800: '#885420',
          900: '#704418',
        },
        // Accent colors (rust/maroon)
        accent: {
          50: '#fdf4f2',
          100: '#f8e4df',
          200: '#f0c4b8',
          300: '#d89888',
          400: '#c87058',
          500: '#b85838',
          600: '#a04030',
          700: '#8a3028',
          800: '#7a2828',
          900: '#5f1f1f',
        },
        // Neutral palette (navy to cream)
        neutral: {
          50: '#f8f6f2',
          100: '#f0ece4',
          200: '#e8dcc4',
          300: '#d4cbb0',
          400: '#a09080',
          500: '#706860',
          600: '#525050',
          700: '#3d3a38',
          800: '#2d3038',
          900: '#1a2634',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
        serif: ['ui-serif', 'Georgia'],
        mono: ['ui-monospace', 'SFMono-Regular'],
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
