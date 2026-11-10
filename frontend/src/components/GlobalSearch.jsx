import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useReturns } from '../hooks/useReturns'
import DecisionBadge from './DecisionBadge'

export default function GlobalSearch({ open, onClose, onOpen }) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const { data = [] } = useReturns('all')

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        if (!open) onOpen()
      }
      if (event.key === 'Escape' && open) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return data.slice(0, 8)
    return data.filter((item) => item.product_name.toLowerCase().includes(q)).slice(0, 8)
  }, [data, query])

  useEffect(() => {
    if (open) setQuery('')
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 px-4 pt-24 backdrop-blur-sm">
      <div
        className="w-full max-w-[560px] rounded-2xl border p-4"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
      >
        <div className="mb-4 flex items-center gap-3 rounded-xl border px-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-elevated)' }}>
          <Search size={18} style={{ color: 'var(--text-secondary)' }} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search returns by product name..."
            className="h-14 w-full border-none bg-transparent outline-none"
          />
        </div>
        <div className="space-y-2">
          {results.length ? (
            results.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onClose()
                  navigate(`/process-returns?selected=${item.id}`)
                }}
                className="flex w-full items-center justify-between rounded-xl border p-4 text-left"
                style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}
              >
                <div>
                  <div className="font-medium">{item.product_name}</div>
                  <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {item.return_id} • {item.category}
                  </div>
                </div>
                <DecisionBadge value={item.recommended_decision || item.status} />
              </button>
            ))
          ) : (
            <div className="py-10 text-center">
              <Search className="mx-auto mb-3" size={26} style={{ color: 'var(--text-muted)' }} />
              <div className="font-medium">No results found</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

