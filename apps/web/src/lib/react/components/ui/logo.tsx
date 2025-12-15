import { cn } from '@/lib/client/utils/cn'

interface LogoProps {
  className?: string
}

export function Logo({ className }: LogoProps) {
  return <span className={cn('font-bold', className)}>Topos</span>
}
