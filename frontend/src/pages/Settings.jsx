import { Copy, KeyRound, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useRegenerateKey, useSaveSettings, useSettings } from '../hooks/useSettings'

export default function Settings() {
  const { data } = useSettings()
  const save = useSaveSettings()
  const regenerate = useRegenerateKey()
  const [form, setForm] = useState(null)

  useEffect(() => {
    if (data) setForm(data)
  }, [data])

  if (!form) return null

  const maskedKey = `${form.api_key.slice(0, 8)}••••••••••••`

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Company profile, notifications and integrations</p>
      </div>

      <div className="grid grid-cols-2 gap-4 max-xl:grid-cols-1">
        <Card title="Company Profile">
          <Label>Company Name</Label>
          <Input value={form.company_name} onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))} />
          <Label>Industry</Label>
          <select value={form.industry} onChange={(e) => setForm((p) => ({ ...p, industry: e.target.value }))} className="h-11 w-full rounded-lg border px-3" style={{ background: 'var(--bg-sidebar)', borderColor: 'var(--border-color)' }}>
            {['E-commerce', 'Retail', 'Warehousing', 'D2C'].map((option) => <option key={option}>{option}</option>)}
          </select>
          <div className="mt-4 rounded-xl p-4" style={{ background: 'var(--bg-main)' }}>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm">Plan</span>
              <span className="rounded-full bg-violet-600/20 px-2 py-1 text-xs font-semibold text-violet-400">PRO</span>
            </div>
            <div className="mb-2 text-sm" style={{ color: 'var(--text-secondary)' }}>Items this month usage</div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-700/20"><div className="h-full w-[64%] rounded-full bg-violet-600" /></div>
          </div>
        </Card>

        <Card title="Notification Preferences">
          <ToggleRow label="Email on auto-approve" checked={form.email_on_auto_approve} onChange={() => setForm((p) => ({ ...p, email_on_auto_approve: !p.email_on_auto_approve }))} />
          <ToggleRow label="Email on high-value item" checked={form.email_on_high_value} onChange={() => setForm((p) => ({ ...p, email_on_high_value: !p.email_on_high_value }))} />
          <ToggleRow label="Daily summary report" checked={form.daily_summary} onChange={() => setForm((p) => ({ ...p, daily_summary: !p.daily_summary }))} />
          <ToggleRow label="Weekly analytics report" checked={form.weekly_analytics} onChange={() => setForm((p) => ({ ...p, weekly_analytics: !p.weekly_analytics }))} />
        </Card>
      </div>

      <Card title="API Configuration">
        <div className="mb-2 flex items-center gap-2"><KeyRound size={18} /><span className="font-medium">API Key</span></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="rounded-lg border px-4 py-3 font-mono" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>{maskedKey}</div>
          <button type="button" onClick={() => { navigator.clipboard.writeText(form.api_key); toast.success('API Key copied!') }} className="flex h-11 items-center gap-2 rounded-lg border px-4" style={{ borderColor: 'var(--border-color)' }}>
            <Copy size={16} /> Copy
          </button>
          <button type="button" onClick={async () => { if (window.confirm('This will invalidate your existing integrations.')) { const result = await regenerate.mutateAsync(); setForm((p) => ({ ...p, api_key: result.api_key })) } }} className="h-11 rounded-lg px-4 font-medium text-white" style={{ background: 'var(--accent-primary)' }}>
            Regenerate Key
          </button>
        </div>

        <Label>Webhook URL</Label>
        <Input value={form.webhook_url || ''} onChange={(e) => setForm((p) => ({ ...p, webhook_url: e.target.value }))} placeholder="https://example.com/reprofit-webhook" />
        {form.webhook_url ? (
          <button type="button" onClick={() => toast.success('Webhook test sent!')} className="mt-3 flex h-11 items-center gap-2 rounded-lg border px-4" style={{ borderColor: 'var(--border-color)' }}>
            <Send size={16} /> Test Webhook
          </button>
        ) : null}
      </Card>

      <button type="button" onClick={() => save.mutate(form)} className="h-11 w-full rounded-lg font-medium text-white" style={{ background: 'var(--accent-primary)' }}>
        Save Changes
      </button>
    </div>
  )
}

function Card({ title, children }) {
  return <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}><h2 className="mb-4 text-lg font-semibold">{title}</h2>{children}</div>
}

function Label({ children }) {
  return <label className="mb-2 mt-4 block text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{children}</label>
}

function Input(props) {
  return <input {...props} className="h-11 w-full rounded-lg border px-3 outline-none" style={{ background: 'var(--bg-sidebar)', borderColor: 'var(--border-color)' }} />
}

function ToggleRow({ label, checked, onChange }) {
  return (
    <div className="mb-3 flex items-center justify-between rounded-xl border p-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
      <span>{label}</span>
      <button type="button" onClick={onChange} className="flex h-8 w-14 items-center rounded-full p-1" style={{ background: checked ? 'var(--success)' : 'var(--bg-elevated)' }}>
        <span className="h-6 w-6 rounded-full bg-white transition-all" style={{ transform: `translateX(${checked ? 24 : 0}px)` }} />
      </button>
    </div>
  )
}

