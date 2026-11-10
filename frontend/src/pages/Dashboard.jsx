import { BarChart3, Package, ShieldCheck, TrendingDown, TrendingUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  Area,
  AreaChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import DecisionBadge from '../components/DecisionBadge'
import ErrorCard from '../components/ErrorCard'
import KPICard from '../components/KPICard'
import Skeleton from '../components/Skeleton'
import { useDashboardSummary, useDashboardTrend, useDecisionSplit, useRecentDecisions } from '../hooks/useDashboard'
import { formatCurrencyINR } from '../utils/formatCurrency'
import { formatDateTime } from '../utils/formatDate'

const tooltipStyle = {
  background: '#1a1f35',
  border: '1px solid #1e2240',
  borderRadius: 8,
  padding: 12,
}

export default function Dashboard() {
  const [period, setPeriod] = useState('weekly')
  const [now, setNow] = useState(() => new Date())
  const summary = useDashboardSummary()
  const trend = useDashboardTrend(period)
  const split = useDecisionSplit()
  const recent = useRecentDecisions()

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(id)
  }, [])

  if (summary.isLoading || trend.isLoading || split.isLoading || recent.isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-4 gap-4 max-xl:grid-cols-2 max-sm:grid-cols-1">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-36" />)}
        </div>
        <div className="grid grid-cols-5 gap-4 max-xl:grid-cols-1">
          <Skeleton className="col-span-3 h-[340px]" />
          <Skeleton className="col-span-2 h-[340px]" />
        </div>
        <Skeleton className="h-[320px]" />
      </div>
    )
  }

  if (summary.error || trend.error || split.error || recent.error) {
    return <ErrorCard message="Unable to load dashboard data." onRetry={() => window.location.reload()} />
  }

  const splitData = [
    { name: 'Resell', value: split.data.resell_percent, color: '#10b981' },
    { name: 'Refurbish', value: split.data.refurbish_percent, color: '#f59e0b' },
    { name: 'Recycle', value: split.data.recycle_percent, color: '#ef4444' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between max-sm:flex-col max-sm:items-start">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Live operational snapshot • {now.toLocaleString()}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4 max-xl:grid-cols-2 max-sm:grid-cols-1">
        <KPICard title="Average Profit" value={summary.data.average_profit} icon={TrendingUp} color="#10b981" formatter={formatCurrencyINR} />
        <KPICard title="Average Loss" value={summary.data.average_loss} icon={TrendingDown} color="#ef4444" formatter={formatCurrencyINR} />
        <KPICard title="Items Processed Today" value={summary.data.items_today} icon={Package} color="#3b82f6" change={summary.data.items_change_vs_yesterday} />
        <KPICard title="Decision Accuracy" value={summary.data.decision_accuracy} suffix="%" icon={ShieldCheck} color="#10b981" />
        <KPICard title="Loss Reduction" value={summary.data.loss_reduction_percent} suffix="%" icon={BarChart3} color="#f59e0b" />
      </div>

      <div className="grid grid-cols-5 gap-4 max-xl:grid-cols-1">
        <div className="col-span-3 rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Profit Recovery Trend</h2>
            <div className="flex gap-2">
              {['weekly', 'monthly'].map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setPeriod(key)}
                  className="rounded-lg px-3 py-2 text-sm font-medium"
                  style={{
                    color: period === key ? 'white' : 'var(--text-secondary)',
                    background: period === key ? 'var(--accent-primary)' : 'var(--bg-elevated)',
                  }}
                >
                  {key[0].toUpperCase() + key.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trend.data}>
              <defs>
                <linearGradient id="profitFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#7c3aed" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="profit_recovered" stroke="#7c3aed" fill="url(#profitFill)" activeDot={{ r: 6, fill: '#7c3aed', stroke: '#fff', strokeWidth: 2 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="col-span-2 rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
          <h2 className="mb-5 text-lg font-semibold">Decision Split</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={splitData} dataKey="value" innerRadius={70} outerRadius={98} paddingAngle={3}>
                {splitData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Decisions</h2>
        </div>
        <div className="overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr style={{ color: 'var(--text-secondary)' }}>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Profit</th>
                <th className="px-4 py-3">Time</th>
              </tr>
            </thead>
            <tbody>
              {recent.data.map((item, index) => (
                <tr key={item.id} style={{ background: index % 2 ? 'var(--bg-elevated)' : 'var(--bg-card)' }}>
                  <td className="px-4 py-3 font-medium">{item.product_name}</td>
                  <td className="px-4 py-3">{item.category}</td>
                  <td className="px-4 py-3"><DecisionBadge value={item.recommended_decision} /></td>
                  <td className="px-4 py-3">{item.confidence_score ? `${Math.round(item.confidence_score)}%` : '--'}</td>
                  <td className={`px-4 py-3 ${(item.profit_estimate || 0) < 0 ? 'text-red-400' : 'text-emerald-500'}`}>{formatCurrencyINR(item.profit_estimate)}</td>
                  <td className="px-4 py-3">{formatDateTime(item.processed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
