import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';
import Navigation from '@/components/Navigation';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Omnishop - AI Interior Design Visualization',
  description: 'Transform your space with AI-powered interior design. Browse thousands of furniture and decor items, chat with our AI designer, and visualize your dream room.',
  keywords: 'interior design, furniture, home decor, AI design assistant, room visualization',
  authors: [{ name: 'Omnishop Team' }],
  creator: 'Omnishop',
  publisher: 'Omnishop',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://omni-shop.in',
    title: 'Omnishop - AI Interior Design Visualization',
    description: 'Transform your space with AI-powered interior design. Browse thousands of furniture and decor items.',
    siteName: 'Omnishop',
    images: [
      {
        url: '/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'Omnishop - AI Interior Design',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Omnishop - AI Interior Design Visualization',
    description: 'Transform your space with AI-powered interior design.',
    images: ['/og-image.jpg'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  verification: {
    google: 'your-google-verification-code',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Preconnect to external domains for performance */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />

        {/* Favicon and app icons */}
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.json" />

        {/* Theme color for mobile browsers */}
        <meta name="theme-color" content="#0ea5e9" />
        <meta name="color-scheme" content="light dark" />

        {/* Viewport for responsive design */}
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />

        {/* Performance hints */}
        <link rel="dns-prefetch" href="//app.omni-shop.in" />
        <link rel="preconnect" href="https://app.omni-shop.in" />
      </head>
      <body className={`${inter.className} bg-neutral-50 text-neutral-900 antialiased`}>
        <Providers>
          <Navigation />
          {children}
        </Providers>
      </body>
    </html>
  );
}
