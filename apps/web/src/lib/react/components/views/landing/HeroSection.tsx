import { ArrowRight } from 'lucide-react'
import Link from 'next/link'

import { Button } from '@/lib/react/components/ui/button'

export function HeroSection() {
  return (
    <section className="relative overflow-hidden py-24 bg-white">
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-6xl">
            Unlock your file shares for safe, auditable, more capable AI
          </h1>

          <p className="mt-6 text-lg leading-8 text-gray-600 max-w-3xl mx-auto">
            Topos is an AI-ready governance and semantic layer for unstructured data.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-x-6">
            <Button
              size="lg"
              className="w-full sm:w-auto h-12 px-8 bg-gradient-to-r from-primary to-gray-800 hover:from-primary/90 hover:to-gray-800/90 shadow-lg hover:shadow-xl transition-all duration-300"
              asChild
            >
              <Link href="https://calendly.com/jay-usetopos/30min">
                Book a discovery call
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>

          <p className="mt-6 text-sm max-w-2xl text-gray-500 mx-auto">
            We're currently in early development, doing 20-minute discovery calls with teams operating large file estates and building internal AI.
          </p>
          <p className="mt-2 text-sm max-w-2xl text-gray-500 mx-auto font-semibold">No rollout required.</p>
        </div>
      </div>
    </section>
  )
}
