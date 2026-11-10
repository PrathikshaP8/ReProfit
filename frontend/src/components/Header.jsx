import { Bell, ChevronDown, Search, Settings, UserCircle2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useDashboardSummary, useRecentDecisions } from '../hooks/useDashboard'
import { formatCurrencyINR } from '../utils/formatCurrency'
import { timeFromNow } from '../utils/formatDate'
import DecisionBadge from './DecisionBadge'
import ThemeToggle from './ThemeToggle'

const titles = {
  '/dashboard': ['Dashboard', 'Overview / Dashboard'],
  '/process-returns': ['Process Returns', 'Operations / Process Returns'],
  '/analytics': ['Analytics', 'Insights / Analytics'],
  '/decision-engine': ['Decision Engine', 'Automation / Decision Engine'],
  '/data-management': ['Data Management', 'Operations / Data Management'],
  '/settings': ['Settings', 'Configuration / Settings'],
}

function useOutsideClick(ref, onClose) {
  useEffect(() => {
    const handle = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onClose()
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [ref, onClose])
}

export default function Header({ onOpenSearch }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const bellRef = useRef(null)
  const profileRef = useRef(null)
  const { data: summary } = useDashboardSummary()
  const { data: decisions = [] } = useRecentDecisions()
  const [title, breadcrumb] = titles[location.pathname] || ['ReProfit', 'Dashboard']

  useOutsideClick(bellRef, () => setNotificationOpen(false))
  useOutsideClick(profileRef, () => setProfileOpen(false))

  return (
    <header
      className="fixed left-[240px] right-0 top-0 z-30 flex h-[60px] items-center justify-between gap-4 border-b px-6 max-md:left-[88px] max-sm:left-0"
      style={{ background: 'color-mix(in srgb, var(--bg-main) 88%, transparent)', borderColor: 'var(--border-color)', backdropFilter: 'blur(10px)' }}
    >
      <div>
        <div className="text-lg font-semibold">{title}</div>
        <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {breadcrumb}
        </div>
      </div>

      <button
        type="button"
        onClick={onOpenSearch}
        className="hidden h-11 min-w-[320px] items-center gap-2 rounded-xl border px-4 md:flex"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
      >
        <Search size={16} style={{ color: 'var(--text-secondary)' }} />
        <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Search returns...
        </span>
        <span className="ml-auto rounded-md px-2 py-1 text-xs" style={{ background: 'var(--bg-elevated)' }}>
          Ctrl+K
        </span>
      </button>

      <div className="flex items-center gap-3">
        <ThemeToggle />

        <div className="relative" ref={bellRef}>
          <button
            type="button"
            onClick={() => setNotificationOpen((v) => !v)}
            className="relative flex h-11 w-11 items-center justify-center rounded-lg border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
          >
            <Bell size={18} />
            <span className="absolute right-2 top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] text-white">
              {summary?.items_today ?? 0}
            </span>
          </button>
          {notificationOpen ? (
            <div
              className="absolute right-0 top-[60px] w-[360px] rounded-xl border p-3"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)', boxShadow: '0 10px 24px var(--shadow-color)' }}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="font-semibold">Recent Decisions</div>
                <button type="button" className="text-sm" style={{ color: 'var(--accent-primary)' }}>
                  Mark all read
                </button>
              </div>
              <div className="space-y-2">
                {decisions.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border-l-4 p-3"
                    style={{
                      background: 'var(--bg-main)',
                      borderLeftColor: item.status === 'approved' ? '#10b981' : '#ef4444',
                    }}
                  >
                    <div className="mb-1 flex items-start justify-between gap-3">
                      <div className="font-medium">{item.product_name}</div>
                      <DecisionBadge value={item.recommended_decision} />
                    </div>
                    <div className="flex items-center justify-between text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <span>{timeFromNow(item.processed_at)}</span>
                      <span style={{ color: 'var(--success)' }}>{formatCurrencyINR(item.profit_estimate)}</span>
                    </div>
                  </div>
                ))}
              </div>
              <Link to="/dashboard" className="mt-3 block text-sm" style={{ color: 'var(--accent-primary)' }}>
                View all in Dashboard
              </Link>
            </div>
          ) : null}
        </div>

        <div className="relative" ref={profileRef}>
          <button
            type="button"
            onClick={() => setProfileOpen((v) => !v)}
            className="flex items-center gap-2 rounded-xl border px-2 py-1.5"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-600 text-sm font-semibold text-white">
              RD
            </div>
            <ChevronDown size={16} />
          </button>
          {profileOpen ? (
            <div
              className="absolute right-0 top-[60px] w-[280px] rounded-xl border p-4"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)', boxShadow: '0 10px 24px var(--shadow-color)' }}
            >
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-violet-600 text-lg font-semibold text-white">
                  RD
                </div>
                <div>
                  <div className="font-semibold">ReProfit Demo</div>
                  <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    ReProfit Demo Pvt Ltd
                  </div>
                </div>
                <span className="ml-auto rounded-full bg-violet-600/20 px-2 py-1 text-xs font-semibold text-violet-400">PRO</span>
              </div>
              <button type="button" onClick={() => navigate('/settings')} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-black/5">
                <Settings size={16} />
                Settings
              </button>
              <button type="button" onClick={() => navigate('/decision-engine')} className="mt-1 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-black/5">
                <UserCircle2 size={16} />
                Decision Engine
              </button>
              <div className="mt-4 border-t pt-3 text-xs" style={{ borderColor: 'var(--border-color)', color: 'var(--text-secondary)' }}>
                ReProfit v1.0.0
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}

