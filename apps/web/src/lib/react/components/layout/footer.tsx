'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { Logo } from '@/lib/react/components/ui/logo'
import { Separator } from '@/lib/react/components/ui/separator'

export function Footer() {
  const pathname = usePathname()
  const isHomePage = pathname === '/'
  const isAdminPage = pathname.startsWith('/admin')

  // Don't show footer on admin pages
  if (isAdminPage) {
    return null
  }

  // Minimal footer for app pages
  if (!isHomePage) {
    return (
      <footer className="border-t bg-background mt-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
            <div className="flex items-center space-x-3">
              <Logo className="h-5 w-auto" />
              <span className="text-xs text-muted-foreground">&copy; 2025 Topos</span>
            </div>
            <div className="flex items-center space-x-4 text-xs text-muted-foreground">
              <Link href="/privacy" className="hover:text-foreground transition-colors">
                Privacy
              </Link>
              <Link href="/terms" className="hover:text-foreground transition-colors">
                Terms
              </Link>
            </div>
          </div>
        </div>
      </footer>
    )
  }

  // Full footer for home page
  return (
    <footer className="relative border-t bg-gradient-to-b from-muted/30 to-muted/50">
      <div className="absolute inset-0 bg-gradient-to-r from-gray-500/2 via-transparent to-gray-600/2" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <div className="flex flex-col md:flex-row gap-8 md:justify-between">
          {/* Brand - Left aligned */}
          <div className="space-y-4 md:max-w-md">
            <Logo className="h-8 w-auto" />
            <p className="text-sm font-semibold text-foreground mb-2">
              AI-Native Data Layer for NFS/SMB
            </p>
            <p className="text-sm text-muted-foreground">
              We're building a semantic and governance data plane for enterprise file systems, so you can unlock your file shares for safe, auditable, more capable AI.
            </p>
          </div>

          {/* Contact - Right aligned */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold">Contact</h3>
            <p className="text-sm text-muted-foreground">
              <a
                href="mailto:founder@usetopos.com"
                className="hover:text-foreground transition-colors"
              >
                founder@usetopos.com
              </a>
            </p>
          </div>
        </div>

        <Separator className="my-8" />

        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-sm text-muted-foreground">&copy; 2025 Topos. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}
