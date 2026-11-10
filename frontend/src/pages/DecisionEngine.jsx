import { AlertTriangle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useAutoProcess, useReturns } from '../hooks/useReturns'
import { useSaveSettings, useSettings } from '../hooks/useSettings'
import { formatCurrencyINR } from '../utils/formatCurrency'

export default function DecisionEngine() {
  const { data: settings } = useSettings()
  const save = useSaveSettings()
  const autoProcess = useAutoProcess()
  const { data: pending = [] } = useReturns('pending')
  const [showWarning, setShowWarning] = useState(true)
  const [formEdits, setFormEdits] = useState(null)
  const form = formEdits || settings
  const updateForm = (updater) => setFormEdits((current) => {
    const base = current || settings
    return typeof updater === 'function' ? updater(base) : updater
  })

  const preview = useMemo(() => {
    if (!form) return { count: 0, total: 0, breakdown: {} }
    const eligible = pending.filter(
      (item) =>
        (item.confidence_score || 0) >= form.min_confidence &&
        (item.profit_estimate || 0) >= form.min_profit_floor &&
        (item.demand_score || 0) >= form.min_demand_score,
    )
    const breakdown = eligible.reduce((acc, item) => {
      acc[item.category] = (acc[item.category] || 0) + (item.profit_estimate || 0)
      return acc
    }, {})
    return {
      count: eligible.length,
      total: eligible.reduce((sum, item) => sum + (item.profit_estimate || 0), 0),
      breakdown,
    }
  }, [pending, form])

  if (!form) return null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Decision Engine Configuration</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Configure approval thresholds and estimated recovery assumptions</p>
      </div>

      <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold">Auto-approve mode</div>
            <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Items meeting all thresholds will be approved automatically.
            </div>
          </div>
          <button
            type="button"
            onClick={async () => {
              const next = !form.auto_approve
              updateForm((p) => ({ ...p, auto_approve: next }))
              if (next) await autoProcess.mutateAsync()
            }}
            className="flex h-9 w-16 items-center rounded-full p-1"
            style={{ background: form.auto_approve ? 'var(--success)' : 'var(--bg-elevated)' }}
          >
            <span className="h-7 w-7 rounded-full bg-white transition-all" style={{ transform: `translateX(${form.auto_approve ? 28 : 0}px)` }} />
          </button>
        </div>
        <div className="mt-3 inline-flex rounded-full px-3 py-1 text-xs font-semibold" style={{ background: form.auto_approve ? 'rgba(16,185,129,0.15)' : 'var(--bg-elevated)', color: form.auto_approve ? '#10b981' : 'var(--text-secondary)' }}>
          {form.auto_approve ? 'ACTIVE' : 'INACTIVE'}
        </div>
        {form.auto_approve && showWarning ? (
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
            <AlertTriangle size={18} className="mt-0.5 text-amber-400" />
            <div className="flex-1 text-sm">Auto-approve mode is active. Items meeting all thresholds will be approved without manual review.</div>
            <button type="button" onClick={() => setShowWarning(false)}>X</button>
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-3 gap-4 max-xl:grid-cols-1">
        <SliderCard label="Confidence" color="#7c3aed" value={form.min_confidence} min={0} max={100} onChange={(value) => updateForm((p) => ({ ...p, min_confidence: value }))} suffix="%" />
        <SliderCard label="Profit Floor" color="#10b981" value={form.min_profit_floor} min={0} max={10000} onChange={(value) => updateForm((p) => ({ ...p, min_profit_floor: value }))} formatter={formatCurrencyINR} />
        <SliderCard label="Demand Score" color="#3b82f6" value={form.min_demand_score} min={0} max={100} onChange={(value) => updateForm((p) => ({ ...p, min_demand_score: value }))} suffix="%" />
      </div>

      <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
        <h2 className="mb-2 text-lg font-semibold">Estimated recovery assumptions</h2>
        <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Starting values retain the project&apos;s existing planning assumptions; they are estimates, not measured recovery rates. Refurbishment cost is modeled as a percentage of market reference price. Other costs default to ₹0 because no per-item costs are configured.
        </p>
        <div className="grid grid-cols-2 gap-4 max-xl:grid-cols-1">
          <SliderCard label="Resell recovery rate" color="#10b981" value={form.resell_recovery_rate * 100} min={0} max={100} onChange={(value) => updateForm((p) => ({ ...p, resell_recovery_rate: value / 100 }))} suffix="%" />
          <SliderCard label="Refurbish recovery rate" color="#3b82f6" value={form.refurbish_recovery_rate * 100} min={0} max={100} onChange={(value) => updateForm((p) => ({ ...p, refurbish_recovery_rate: value / 100 }))} suffix="%" />
          <SliderCard label="Refurbish cost rate" color="#f59e0b" value={form.refurbish_cost_rate * 100} min={0} max={100} onChange={(value) => updateForm((p) => ({ ...p, refurbish_cost_rate: value / 100 }))} suffix="%" />
          <SliderCard label="Recycle recovery rate" color="#8b5cf6" value={form.recycle_recovery_rate * 100} min={0} max={100} onChange={(value) => updateForm((p) => ({ ...p, recycle_recovery_rate: value / 100 }))} suffix="%" />
        </div>
        <label className="mt-4 block text-sm font-medium" htmlFor="other-costs">Other costs per item (INR)</label>
        <input id="other-costs" type="number" min="0" step="0.01" value={form.other_costs_per_item} onChange={(event) => updateForm((p) => ({ ...p, other_costs_per_item: Number(event.target.value) }))} className="mt-2 h-11 w-full rounded-lg border px-3" style={{ background: 'var(--bg-main)', borderColor: 'var(--border-color)' }} />
      </div>

      <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: '#7c3aed' }}>
        <h2 className="mb-2 text-lg font-semibold">Live Preview</h2>
        <div className="text-3xl font-semibold">{preview.count} of {pending.length} pending items would be auto-approved</div>
        <div className="mt-2 text-lg text-emerald-500">Estimated additional profit: {formatCurrencyINR(preview.total)}</div>
        <div className="mt-4 grid grid-cols-3 gap-3 max-sm:grid-cols-1">
          {Object.entries(preview.breakdown).map(([category, value]) => (
            <div key={category} className="rounded-xl border p-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
              <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{category}</div>
              <div className="mt-1 font-semibold">{formatCurrencyINR(value)}</div>
            </div>
          ))}
        </div>
      </div>

      <button type="button" onClick={() => save.mutate(form)} className="h-11 w-full rounded-lg font-medium text-white" style={{ background: 'var(--accent-primary)' }}>
        Save Settings
      </button>
    </div>
  )
}

function SliderCard({ label, color, value, onChange, min, max, suffix = '', formatter }) {
  return (
    <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)', borderLeft: `3px solid ${color}` }}>
      <div className="mb-3 flex items-center justify-between">
        <div className="font-semibold">{label}</div>
        <div className="rounded-full px-2 py-1 text-sm" style={{ background: 'var(--bg-elevated)' }}>
          {formatter ? formatter(value) : `${Math.round(value)}${suffix}`}
        </div>
      </div>
      <input type="range" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-violet-600" />
    </div>
  )
}
