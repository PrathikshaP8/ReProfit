import { AlertTriangle, RefreshCcw } from 'lucide-react'

export default function ErrorCard({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div
      className="rounded-xl border p-5"
      style={{ background: 'var(--bg-card)', borderColor: 'rgba(239,68,68,0.4)' }}
    >
      <div className="mb-3 flex items-center gap-3">
        <AlertTriangle className="text-red-500" size={20} />
        <h3 className="text-base font-semibold">{title}</h3>
      </div>
      <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
        {message || 'Please try again.'}
      </p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex h-11 items-center gap-2 rounded-lg border px-4 text-sm font-medium"
          style={{ borderColor: 'var(--border-color)' }}
        >
          <RefreshCcw size={16} />
          Retry
        </button>
      ) : null}
    </div>
  )
}

