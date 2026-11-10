import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { useCountUp } from '../hooks/useCountUp'

export default function KPICard({ title, value, suffix = '', icon: Icon, change, color = 'var(--accent-primary)', formatter }) {
  const animated = useCountUp(value ?? 0)
  const display = formatter ? formatter(animated) : `${Math.round(animated)}${suffix}`
  const positive = (change ?? 0) >= 0

  return (
    <div
      className="rounded-xl border p-5 transition-all hover:-translate-y-0.5"
      style={{
        background: 'var(--bg-card)',
        borderColor: 'var(--border-color)',
        borderTop: `2px solid ${color}`,
        boxShadow: `0 10px 20px var(--shadow-color)`,
      }}
    >
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          {title}
        </span>
        {Icon ? (
          <div className="rounded-lg p-2" style={{ background: 'var(--accent-light)', color }}>
            <Icon size={18} />
          </div>
        ) : null}
      </div>
      <div className="mb-3 text-3xl font-semibold tracking-tight">{display}</div>
      {change !== undefined ? (
        <div className="flex items-center gap-2 text-sm" style={{ color: positive ? 'var(--success)' : 'var(--danger)' }}>
          {positive ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
          <span>{Math.abs(change)}%</span>
        </div>
      ) : null}
    </div>
  )
}

