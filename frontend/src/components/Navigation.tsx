'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState, useRef, useEffect } from 'react'
import { Bars3Icon, XMarkIcon, UserCircleIcon, FolderIcon, ArrowRightOnRectangleIcon, ArrowLeftOnRectangleIcon } from '@heroicons/react/24/outline'
import { useAuth, isAdmin, isSuperAdmin, canAccessDesignStudio, canAccessCurated } from '@/contexts/AuthContext'

// Base navigation - shown to all users
const baseNavigation = [
  { name: 'Home', href: '/' },
]

// Navigation for upgraded users (Advanced/Curator)
const premiumNavigation = [
  { name: 'Studio', href: '/design' },
]

// Navigation for users with curated access (Advanced/Curator)
const curatedNavigation = [
  { name: 'Curated Looks', href: '/curated' },
]

// Helper to get tier display label
const getTierDisplayLabel = (tier: string | undefined): string => {
  switch (tier) {
    case 'free': return 'Free';
    case 'basic': return 'Basic';
    case 'basic_plus': return 'Basic+';
    case 'advanced': return 'Advanced';
    case 'upgraded': return 'Advanced'; // Legacy tier name
    case 'curator': return 'Curator';
    default: return tier?.replace('_', ' ') || '';
  }
}

export function Navigation() {
  const pathname = usePathname()
  const router = useRouter()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  const { user, isAuthenticated, isLoading, logout } = useAuth()
  const [imageError, setImageError] = useState(false)

  // Close user menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    // Use 'click' instead of 'mousedown' so menu items can handle clicks before menu closes
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  const handleLogout = () => {
    logout()
    setUserMenuOpen(false)
    router.push('/')
  }

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user?.name) return user?.email?.charAt(0).toUpperCase() || '?'
    const names = user.name.split(' ')
    if (names.length >= 2) {
      return names[0].charAt(0) + names[names.length - 1].charAt(0)
    }
    return names[0].charAt(0).toUpperCase()
  }

  return (
    <nav className="bg-white/95 backdrop-blur-sm shadow-sm border-b border-neutral-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center group">
              <div className="flex-shrink-0">
                <svg className="h-7 w-7 text-neutral-700 transition-colors group-hover:text-neutral-800" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z" />
                </svg>
              </div>
              <div className="ml-2">
                <span className="font-display text-xl font-medium text-neutral-800">Omnishop</span>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-4">
            <div className="flex items-baseline space-x-1">
              {/* 1. Home - shown to authenticated users */}
              {isAuthenticated && (
                <>
                  {baseNavigation.map((item) => {
                    const isActive = pathname === item.href
                    return (
                      <Link
                        key={item.name}
                        href={item.href}
                        className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                          isActive
                            ? 'bg-neutral-100 text-neutral-900'
                            : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                        }`}
                      >
                        {item.name}
                      </Link>
                    )
                  })}
                </>
              )}

              {/* 2. Studio - only for upgraded users and admins */}
              {canAccessDesignStudio(user) && premiumNavigation.map((item) => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-neutral-100 text-neutral-900'
                        : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                    }`}
                  >
                    {item.name}
                  </Link>
                )
              })}

              {/* 3. Curated Looks - for advanced/curator users and admins */}
              {canAccessCurated(user) && curatedNavigation.map((item) => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-neutral-100 text-neutral-900'
                        : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                    }`}
                  >
                    {item.name}
                  </Link>
                )
              })}

              {/* 4. Projects - Only for upgraded users and admins */}
              {isAuthenticated && canAccessDesignStudio(user) && (
                <Link
                  href="/projects"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                    pathname === '/projects'
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                  }`}
                >
                  Projects
                </Link>
              )}

              {/* 5. Purchases - shown to authenticated users */}
              {isAuthenticated && (
                <Link
                  href="/purchases"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                    pathname?.startsWith('/purchases')
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                  }`}
                >
                  Purchases
                </Link>
              )}

              {/* Admin Link - Only show for admin/super_admin */}
              {isAuthenticated && isAdmin(user) && (
                <Link
                  href="/admin"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                    pathname === '/admin' || (pathname?.startsWith('/admin') && !pathname?.startsWith('/admin/permissions'))
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                  }`}
                >
                  Admin
                </Link>
              )}
            </div>

            {/* User Menu / Login Button */}
            <div className="ml-4 relative flex items-center gap-3" ref={userMenuRef}>
              {isLoading ? (
                <div className="w-9 h-9 rounded-full bg-neutral-200 animate-pulse" />
              ) : isAuthenticated ? (
                <>
                  {/* Tier Badge - visible in nav bar */}
                  {user?.subscription_tier && (
                    <Link
                      href="/pricing"
                      className={`hidden sm:inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold transition-colors border ${
                        (user.subscription_tier as string) === 'curator'
                          ? 'bg-purple-100 text-purple-700 border-purple-200 hover:bg-purple-200'
                          : (user.subscription_tier as string) === 'advanced' || (user.subscription_tier as string) === 'upgraded'
                          ? 'bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-200'
                          : user.subscription_tier === 'basic_plus'
                          ? 'bg-green-100 text-green-700 border-green-200 hover:bg-green-200'
                          : user.subscription_tier === 'basic'
                          ? 'bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-200'
                          : 'bg-neutral-100 text-neutral-600 border-neutral-200 hover:bg-neutral-200'
                      }`}
                    >
                      {getTierDisplayLabel(user.subscription_tier)}
                    </Link>
                  )}

                  <button
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    className="flex items-center gap-2 p-1 rounded-full hover:bg-neutral-100 transition-all duration-200"
                  >
                    {user?.profile_image_url && !imageError ? (
                      <img
                        src={user.profile_image_url}
                        alt={user.name || 'User'}
                        className="w-9 h-9 rounded-full object-cover border-2 border-neutral-200"
                        onError={() => setImageError(true)}
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-neutral-600 to-neutral-700 flex items-center justify-center text-white font-medium text-sm">
                        {getUserInitials()}
                      </div>
                    )}
                  </button>

                  {/* Dropdown Menu */}
                  {userMenuOpen && (
                    <div className="absolute right-0 top-full mt-2 w-56 rounded-xl bg-white shadow-lg border border-neutral-200/80 py-1 z-[9999]">
                      <div className="px-4 py-3 border-b border-neutral-100">
                        <p className="text-sm font-medium text-neutral-800 truncate">
                          {user?.name || 'User'}
                        </p>
                        <p className="text-xs text-neutral-500 truncate">
                          {user?.email}
                        </p>
                      </div>
                      <div
                        className="flex items-center gap-2 px-4 py-2 text-sm text-neutral-400 cursor-not-allowed"
                      >
                        <UserCircleIcon className="w-4 h-4" />
                        Profile
                      </div>
                      <div className="border-t border-neutral-100 mt-1 pt-1">
                        <button
                          onClick={handleLogout}
                          className="w-full flex items-center gap-2 text-left px-4 py-2 text-sm text-accent-600 hover:bg-accent-50 transition-colors"
                        >
                          <ArrowRightOnRectangleIcon className="w-4 h-4" />
                          Sign Out
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <Link
                  href="/login"
                  className="px-5 py-2 bg-neutral-800 text-white text-sm font-medium rounded-md hover:bg-neutral-900 transition-all duration-200"
                >
                  Sign In
                </Link>
              )}
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center gap-3">
            {/* User avatar on mobile */}
            {!isLoading && isAuthenticated && (
              <Link href="/projects" className="p-1">
                {user?.profile_image_url && !imageError ? (
                  <img
                    src={user.profile_image_url}
                    alt={user.name || 'User'}
                    className="w-8 h-8 rounded-full object-cover border-2 border-neutral-200"
                    onError={() => setImageError(true)}
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neutral-600 to-neutral-700 flex items-center justify-center text-white font-medium text-xs">
                    {getUserInitials()}
                  </div>
                )}
              </Link>
            )}
            <button
              type="button"
              className="bg-white p-2 rounded-md text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-neutral-500 transition-all duration-200"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              <span className="sr-only">Open main menu</span>
              {mobileMenuOpen ? (
                <XMarkIcon className="block h-6 w-6" />
              ) : (
                <Bars3Icon className="block h-6 w-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 border-t border-neutral-200/60">
              {/* 1. Home - shown to authenticated users */}
              {isAuthenticated && (
                <>
                  {baseNavigation.map((item) => {
                    const isActive = pathname === item.href
                    return (
                      <Link
                        key={item.name}
                        href={item.href}
                        className={`block px-3 py-2 rounded-md text-base font-medium transition-all duration-200 ${
                          isActive
                            ? 'bg-neutral-100 text-neutral-900'
                            : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                        }`}
                        onClick={() => setMobileMenuOpen(false)}
                      >
                        {item.name}
                      </Link>
                    )
                  })}
                </>
              )}

              {/* 2. Studio - only for upgraded users and admins */}
              {canAccessDesignStudio(user) && premiumNavigation.map((item) => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`block px-3 py-2 rounded-md text-base font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-neutral-100 text-neutral-900'
                        : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                    }`}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {item.name}
                  </Link>
                )
              })}

              {/* 3. Curated Looks - for advanced/curator users and admins */}
              {canAccessCurated(user) && curatedNavigation.map((item) => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`block px-3 py-2 rounded-md text-base font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-neutral-100 text-neutral-900'
                        : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                    }`}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {item.name}
                  </Link>
                )
              })}

              {/* 4. Projects - Only for upgraded users and admins */}
              {isAuthenticated && canAccessDesignStudio(user) && (
                <Link
                  href="/projects"
                  className={`block px-3 py-2 rounded-md text-base font-medium transition-all duration-200 ${
                    pathname === '/projects'
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                  }`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Projects
                </Link>
              )}

              {/* 5. Purchases - shown to authenticated users */}
              {isAuthenticated && (
                <Link
                  href="/purchases"
                  className={`block px-3 py-2 rounded-md text-base font-medium transition-all duration-200 ${
                    pathname?.startsWith('/purchases')
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                  }`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Purchases
                </Link>
              )}

              {/* Admin - Mobile (only for admin/super_admin) */}
              {isAuthenticated && isAdmin(user) && (
                <Link
                  href="/admin"
                  className={`block px-3 py-2 rounded-md text-base font-medium transition-all duration-200 ${
                    pathname === '/admin' || (pathname?.startsWith('/admin') && !pathname?.startsWith('/admin/permissions'))
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-600 hover:text-neutral-800 hover:bg-neutral-100'
                  }`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Admin
                </Link>
              )}

              {/* Auth Actions - Mobile */}
              <div className="pt-3 border-t border-neutral-200/60 mt-3">
                {isAuthenticated ? (
                  <>
                    <div className="px-3 py-2 text-sm text-neutral-500">
                      {user?.name || user?.email}
                    </div>
                    <button
                      onClick={() => {
                        handleLogout()
                        setMobileMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 rounded-md text-base font-medium text-accent-600 hover:bg-accent-50 transition-colors"
                    >
                      Sign Out
                    </button>
                  </>
                ) : (
                  <Link
                    href="/login"
                    className="block px-3 py-2 rounded-md text-base font-medium text-neutral-800 hover:bg-neutral-100 transition-colors"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Sign In
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}

export default Navigation
