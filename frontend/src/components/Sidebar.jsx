import { BarChart3, Cpu, Database, LayoutDashboard, PackageCheck, Settings2 } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, description: 'Overview of profit recovery' },
  { to: '/process-returns', label: 'Process Returns', icon: PackageCheck, description: 'Review and process return queue' },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, description: 'Performance and recovery insights' },
  { to: '/decision-engine', label: 'Decision Engine', icon: Cpu, description: 'AI auto-approval thresholds' },
  { to: '/data-management', label: 'Data Management', icon: Database, description: 'Bulk upload and CSV tools' },
  { to: '/settings', label: 'Settings', icon: Settings2, description: 'Company, notifications and API config' },
]

export default function Sidebar() {
  return (
    <aside
      className="fixed left-0 top-0 z-40 flex h-screen w-[240px] flex-col border-r px-4 py-5 max-md:w-[88px] max-sm:hidden"
      style={{ background: 'var(--bg-sidebar)', borderColor: 'rgba(255,255,255,0.04)' }}
    >
      <div className="mb-8 flex items-center gap-3 px-2">
        <div
          className="flex h-11 w-11 items-center justify-center rounded-xl text-lg font-bold text-white"
          style={{
            background: 'linear-gradient(135deg, #7c3aed, #8b5cf6)',
            animation: 'logoPulse 2s ease-in-out infinite',
          }}
        >
          R
        </div>
        <div className="max-md:hidden">
          <div className="text-lg font-semibold text-white">ReProfit</div>
          <div className="text-xs text-slate-400">AI Profit Recovery</div>
        </div>
      </div>

      <nav className="space-y-1">
        {links.map(({ to, label, icon: Icon, description }) => (
          <NavLink key={to} to={to} title={description}>
            {({ isActive }) => (
              <div
                className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-all"
                style={{
                  color: isActive ? '#7c3aed' : '#cbd5e1',
                  background: isActive ? 'rgba(124,58,237,0.15)' : 'transparent',
                  borderLeft: isActive ? '3px solid #7c3aed' : '3px solid transparent',
                  boxShadow: isActive ? 'inset 0 0 20px rgba(124,58,237,0.08)' : 'none',
                }}
              >
                <Icon size={18} />
                <span className="max-md:hidden">{label}</span>
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto rounded-xl border px-3 py-4" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <span
            className="h-2.5 w-2.5 rounded-full bg-emerald-400"
            style={{ animation: 'blink 1.5s ease-in-out infinite' }}
          />
          <span className="max-md:hidden">All Systems Operational</span>
        </div>
      </div>
    </aside>
  )
}

