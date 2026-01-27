import {
  Bot,
  Brain,
  Cloud,
  Crosshair,
  Database,
  FileText,
  MessageSquare,
  Network,
  Server,
  Shield,
} from 'lucide-react'

export function ArchitectureSection() {
  return (
    <section className="relative py-24 architecture-bg overflow-hidden">
      {/* Grid background overlay */}
      <div className="absolute inset-0 architecture-grid pointer-events-none" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            How Topos fits between storage and AI
          </h2>
          <p className="mt-4 text-lg text-slate-400 max-w-4xl mx-auto">
            Topos aims to turn your high-value NFS/SMB shares into a semantic,
            policy-aware data plane.
          </p>
        </div>

        {/* Architecture Diagram - Three columns with flow lines */}
        <div className="relative">
          <div className="flex flex-col lg:flex-row items-stretch justify-center gap-0 relative">
            {/* Enterprise File Estates */}
            <div className="flex-1 flex flex-col items-center lg:items-end justify-center gap-8 relative z-20 py-10">
              <h3 className="text-xl font-bold text-white absolute top-0 right-0 w-full text-center lg:text-right lg:pr-4">
                Enterprise File Estates
              </h3>

              <div className="flex flex-col items-center lg:items-end gap-2 w-full lg:pr-8 relative">
                <span className="text-slate-400 text-sm font-medium mb-2">On-prem + hybrid infra</span>
                <div className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className="glass-card-dark p-4 rounded-xl w-28 h-20 flex items-center justify-center mb-2 bg-[#0f172a]">
                      <Server className="h-8 w-8 text-blue-400" />
                    </div>
                    <span className="text-xs text-slate-300 text-center max-w-[100px]">File Servers & NAS</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="glass-card-dark p-4 rounded-xl w-28 h-20 flex items-center justify-center mb-2 bg-[#0f172a]">
                      <Network className="h-8 w-8 text-purple-400" />
                    </div>
                    <span className="text-xs text-slate-300 text-center max-w-[100px]">Hybrid Gateways</span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col items-center lg:items-end gap-2 w-full lg:pr-8 relative">
                <span className="text-slate-400 text-sm font-medium mb-2">Cloud file platforms</span>
                <div className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className="glass-card-dark p-3 rounded-xl w-20 h-16 flex items-center justify-center mb-2 bg-[#0f172a]">
                      <Cloud className="h-6 w-6 text-blue-400" />
                    </div>
                    <span className="text-xs text-slate-300 text-center">Cloud Files</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="glass-card-dark p-3 rounded-xl w-20 h-16 flex items-center justify-center mb-2 bg-[#0f172a]">
                      <Database className="h-6 w-6 text-purple-400" />
                    </div>
                    <span className="text-xs text-slate-300 text-center">Object Storage</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="glass-card-dark p-3 rounded-xl w-20 h-16 flex items-center justify-center mb-2 bg-[#0f172a]">
                      <Cloud className="h-6 w-6 text-pink-400" />
                    </div>
                    <span className="text-xs text-slate-300 text-center">SaaS Drives</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Left Connector */}
            <div className="hidden lg:block w-[120px] relative -top-20 z-0">
              <svg className="absolute inset-0 w-full h-full overflow-visible" style={{ transform: 'scale(1.3)' }}>
                <defs>
                  <linearGradient id="flowGradientLeft" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.8" />
                  </linearGradient>
                </defs>
                <path
                  d="M-80 180 C 20 180, 60 300, 160 300"
                  fill="none"
                  stroke="url(#flowGradientLeft)"
                  strokeWidth="2.5"
                  className="flow-path"
                  opacity="0.7"
                />
                <path
                  d="M-80 420 C 20 420, 60 300, 160 300"
                  fill="none"
                  stroke="url(#flowGradientLeft)"
                  strokeWidth="2.5"
                  className="flow-path"
                  opacity="0.7"
                  style={{ animationDelay: '0.5s' }}
                />
              </svg>
            </div>

            {/* Topos Data Plane */}
            <div className="flex-[1.5] w-full max-w-2xl px-4 py-8 relative flex flex-col items-center justify-center z-20">
              <h3 className="text-xl font-bold text-white mb-6 text-center absolute top-0">
                Topos Data Plane
              </h3>

              <div className="glass-panel rounded-[2rem] p-8 lg:p-10 w-full">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="glass-card-dark p-5 rounded-2xl flex flex-col items-center text-center">
                    <div className="w-12 h-12 rounded-lg bg-purple-500/20 flex items-center justify-center mb-3 border border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.3)]">
                      <FileText className="h-6 w-6 text-purple-300" />
                    </div>
                    <p className="text-sm font-semibold text-white">Semantic & Risk Model</p>
                  </div>
                  <div className="glass-card-dark p-5 rounded-2xl flex flex-col items-center text-center">
                    <div className="w-12 h-12 rounded-lg bg-blue-500/20 flex items-center justify-center mb-3 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
                      <Shield className="h-6 w-6 text-blue-300" />
                    </div>
                    <p className="text-sm font-semibold text-white">ACL Enforcement & Redaction</p>
                  </div>
                  <div className="glass-card-dark p-5 rounded-2xl flex flex-col items-center text-center">
                    <div className="w-12 h-12 rounded-lg bg-pink-500/20 flex items-center justify-center mb-3 border border-pink-500/30 shadow-[0_0_15px_rgba(236,72,153,0.3)]">
                      <Brain className="h-6 w-6 text-pink-300" />
                    </div>
                    <p className="text-sm font-semibold text-white">Type-Aware Chunking</p>
                  </div>
                  <div className="glass-card-dark p-5 rounded-2xl flex flex-col items-center text-center">
                    <div className="w-12 h-12 rounded-lg bg-emerald-500/20 flex items-center justify-center mb-3 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                      <Crosshair className="h-6 w-6 text-emerald-300" />
                    </div>
                    <p className="text-sm font-semibold text-white">Observability</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Connector */}
            <div className="hidden lg:block w-[120px] relative -top-20 z-0">
              <svg className="absolute inset-0 w-full h-full overflow-visible" style={{ transform: 'scale(1.3)' }}>
                <defs>
                  <linearGradient id="flowGradientRight" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#34d399" stopOpacity="0.6" />
                  </linearGradient>
                </defs>
                <path
                  d="M-60 300 C 40 300, 80 180, 180 180"
                  fill="none"
                  stroke="url(#flowGradientRight)"
                  strokeWidth="2.5"
                  className="flow-path"
                  opacity="0.7"
                />
                <path
                  d="M-60 300 C 40 300, 80 420, 180 420"
                  fill="none"
                  stroke="url(#flowGradientRight)"
                  strokeWidth="2.5"
                  className="flow-path"
                  opacity="0.7"
                  style={{ animationDelay: '0.5s' }}
                />
              </svg>
            </div>

            {/* AI Agents & Copilots */}
            <div className="flex-1 flex flex-col items-center lg:items-start justify-center gap-8 relative z-20 py-10 lg:pl-4">
              <h3 className="text-xl font-bold text-white absolute top-0 left-0 w-full text-center lg:text-left lg:pl-4">
                Agents & Copilots
              </h3>

              <div className="flex items-center gap-4 w-full">
                <div className="glass-card-dark w-14 h-14 rounded-2xl flex items-center justify-center border-l-4 border-l-purple-400 shadow-[0_0_20px_rgba(168,85,247,0.2)] bg-[#0f172a]">
                  <Bot className="h-7 w-7 text-emerald-400" />
                </div>
                <span className="font-bold text-white text-lg">Agentic Workflows</span>
              </div>

              <div className="flex items-center gap-4 w-full">
                <div className="glass-card-dark w-14 h-14 rounded-2xl flex items-center justify-center border-l-4 border-l-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.2)] bg-[#0f172a]">
                  <MessageSquare className="h-7 w-7 text-purple-400" />
                </div>
                <div>
                  <span className="font-bold text-white text-lg">AI Hubs</span>
                  <p className="text-sm text-slate-400">(e.g., ChatGPT Enterprise)</p>
                </div>
              </div>

              <p className="text-slate-400 text-sm leading-relaxed max-w-[280px]">
                Agents call Topos through ACL-aware, purpose-built tools, like{' '}
                <span className="text-slate-300">Search</span>,{' '}
                <span className="text-slate-300">Read</span>,{' '}
                <span className="text-slate-300">Summarize</span>, and{' '}
                <span className="text-slate-300">Propose Remediation</span>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
