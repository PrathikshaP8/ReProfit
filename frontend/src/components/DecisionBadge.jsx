const styles = {
  Resell: { background: 'rgba(16,185,129,0.15)', color: '#10b981' },
  Refurbish: { background: 'rgba(245,158,11,0.15)', color: '#f59e0b' },
  Recycle: { background: 'rgba(239,68,68,0.15)', color: '#ef4444' },
  approved: { background: 'rgba(16,185,129,0.15)', color: '#10b981' },
  rejected: { background: 'rgba(239,68,68,0.15)', color: '#ef4444' },
  pending: { background: 'rgba(59,130,246,0.15)', color: '#3b82f6' },
}

export default function DecisionBadge({ value }) {
  const style = styles[value] || { background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
      style={style}
    >
      {value || '--'}
    </span>
  )
}

