import { ArrowRight } from 'lucide-react'
import Link from 'next/link'

import { Button } from '@/lib/react/components/ui/button'

export function CTASection() {
  return (
    <section id="cta" className="relative py-24 architecture-bg overflow-hidden">
      <div className="absolute inset-0 architecture-grid pointer-events-none" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Help us shape Topos
          </h2>
          <p className="mt-4 text-gray-300">
            We&apos;re interviewing a small number of infra, platform, and security teams with sizable SMB/NFS/NAS estates who are exploring internal AI hubs.
          </p>
          <p className="mt-4 text-gray-300">
            If you want your agents to become more capable on real file data, while keeping access safe and auditable, we&apos;d value 20 minutes.
          </p>
          <p className="mt-4 text-gray-300 font-semibold">
            No rollout or installation required.
          </p>

          <div className="mt-10 flex items-center justify-center">
            <Button
              size="lg"
              className="h-12 px-8 bg-white text-gray-900 hover:bg-gray-100 shadow-lg hover:shadow-xl transition-all duration-300"
              asChild
            >
              <Link href="mailto:founder@usetopos.com">
                Book a discovery call
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>

          <p className="mt-6 text-sm text-gray-400">
            Or email{' '}
            <a href="mailto:founder@usetopos.com" className="text-white hover:underline">
              founder@usetopos.com
            </a>
          </p>
        </div>
      </div>
    </section>
  )
}
