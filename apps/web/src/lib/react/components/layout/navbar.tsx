'use client'

import { usePathname } from 'next/navigation'

import { cn } from '@/lib/client/utils/cn'
import { Link } from '@/lib/react/components/ui/link'
import { Logo } from '@/lib/react/components/ui/logo'
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from '@/lib/react/components/ui/navigation-menu'

type NavItem = {
  href: string
  label: string
  badge?: string
  children?: {
    title: string
    href: string
    description?: string
  }[]
}

export function Navbar() {
  const pathname = usePathname()

  const isActive = (path: string) => {
    if (path === '/') {
      return pathname === '/'
    }

    if (path === '/reviewers') {
      return pathname.startsWith('/reviewers')
    }
    // For other paths, use startsWith
    return pathname.startsWith(path)
  }

  const marketingNavItems: NavItem[] = []

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="relative flex h-16 items-center justify-between">
          {/* Logo - Fixed width for consistent spacing */}
          <div className="flex w-[140px]">
            <Link className="flex items-center" href="/">
              <Logo className="text-3xl" />
            </Link>
          </div>

          {/* Desktop Auth/Avatar and Navigation */}
          <div className="hidden md:flex md:flex-1 md:items-center md:justify-end md:gap-4">
            <>
              <NavigationMenu className="ms-auto">
                <NavigationMenuList>
                  {marketingNavItems.map((item) => {
                    if (item.children) {
                      return (
                        <NavigationMenuItem key={item.href}>
                          <NavigationMenuTrigger
                            className={cn(
                              'text-sm font-medium transition-colors hover:text-foreground/80',
                              isActive(item.href) ? 'text-foreground' : 'text-foreground/60'
                            )}
                          >
                            {item.label}
                          </NavigationMenuTrigger>
                          <NavigationMenuContent>
                            <ul className="grid gap-3 p-6 md:w-[400px] lg:w-[500px] lg:grid-cols-[.75fr_1fr]">
                              {item.children.map((child) => (
                                <li key={child.href}>
                                  <NavigationMenuLink asChild>
                                    <Link
                                      href={child.href}
                                      className="block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
                                    >
                                      <div className="text-sm font-medium leading-none">
                                        {child.title}
                                      </div>
                                      {child.description && (
                                        <p className="line-clamp-2 text-sm leading-snug text-muted-foreground">
                                          {child.description}
                                        </p>
                                      )}
                                    </Link>
                                  </NavigationMenuLink>
                                </li>
                              ))}
                            </ul>
                          </NavigationMenuContent>
                        </NavigationMenuItem>
                      )
                    }
                    return (
                      <NavigationMenuItem key={item.href}>
                        <Link
                          href={item.href}
                          className={cn(
                            'text-sm font-medium transition-colors hover:text-foreground/80 px-3',
                            isActive(item.href) ? 'text-foreground' : 'text-foreground/60'
                          )}
                        >
                          {item.label}
                        </Link>
                      </NavigationMenuItem>
                    )
                  })}
                </NavigationMenuList>
              </NavigationMenu>
            </>
          </div>
        </div>
      </div>
    </header>
  )
}
