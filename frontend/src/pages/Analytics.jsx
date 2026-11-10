import { Download, PackageSearch } from 'lucide-react'
import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import ErrorCard from '../components/ErrorCard'
import Skeleton from '../components/Skeleton'
import { useCategoryBreakdown, useConditionDistribution, useDailyProfit } from '../hooks/useAnalytics'
import { formatCurrencyINR } from '../utils/formatCurrency'

const tooltipStyle = { background: '#1a1f35', border: '1px solid #1e2240', borderRadius: 8, padding: 12 }
const categoryColors = { Electronics: '#7c3aed', Apparel: '#10b981', Accessories: '#f59e0b', Other: '#3b82f6' }
const conditionColors = { Damaged: '#ef4444', Bad: '#f97316', Fair: '#f59e0b', Good: '#10b981' }

export default function Analytics() {
  const [range, setRange] = useState(30)
  const daily = useDailyProfit(range)
  const categories = useCategoryBreakdown(range)
  const conditions = useConditionDistribution(range)

  const totals = useMemo(() => {
    if (!daily.data || !categories.data) return null
    const totalRecovered = Number(daily.data.reduce((sum, item) => sum + item.profit_recovered, 0).toFixed(2))
    const bestDay = daily.data
      .filter((item) => item.item_count > 0)
      .reduce((best, item) => (!best || item.profit_recovered > best.profit_recovered ? item : best), null)
    const totalItems = daily.data.reduce((sum, item) => sum + item.item_count, 0)
    const topCategory = getCategoryExtreme(categories.data, 'max')
    return { totalRecovered, bestDay, totalItems, topCategory }
  }, [daily.data, categories.data])

  const exportCsv = async () => {
    if (!daily.data || !categories.data) return
    const lines = ['Date,Profit Recovered,Resell,Refurbish,Recycle']
    daily.data.forEach((row) => lines.push(`${row.date},${row.profit_recovered},${row.resell_count},${row.refurbish_count},${row.recycle_count}`))
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `reprofit-analytics-${range}days-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    toast.success('CSV exported successfully')
  }

  if (daily.isLoading || categories.isLoading || conditions.isLoading) {
    return <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-[320px]" /><Skeleton className="h-[320px]" /></div>
  }
  if (daily.error || categories.error || conditions.error) {
    return <ErrorCard message="Unable to load analytics." onRetry={() => window.location.reload()} />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between max-sm:flex-col max-sm:items-start">
        <div>
          <h1 className="text-2xl font-semibold">Analytics</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Performance trends and category recovery insights</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90].map((item) => (
            <button key={item} type="button" onClick={() => setRange(item)} className="rounded-lg px-3 py-2 text-sm font-medium" style={{ background: range === item ? 'var(--accent-primary)' : 'var(--bg-card)', color: range === item ? '#fff' : 'var(--text-secondary)' }}>
              {item}d
            </button>
          ))}
          <button type="button" onClick={exportCsv} className="flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium text-white" style={{ background: 'var(--accent-primary)' }}>
            <Download size={16} /> Export CSV
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 max-xl:grid-cols-2 max-sm:grid-cols-1">
        <StatCard label="Total Recovered" value={formatCurrencyINR(totals.totalRecovered)} />
        <StatCard label="Best Single Day" value={totals.bestDay ? formatCurrencyINR(totals.bestDay.profit_recovered) : '--'} sub={totals.bestDay?.date} />
        <StatCard label="Avg per Item" value={totals.totalItems ? formatCurrencyINR(totals.totalRecovered / totals.totalItems) : '--'} />
        <StatCard label="Top Category" value={totals.topCategory?.category || '--'} sub={formatCurrencyINR(totals.topCategory?.total_profit)} />
      </div>

      <div className="grid grid-cols-2 gap-4 max-xl:grid-cols-1">
        <ChartCard title="Daily Profit Recovered">
          {daily.data.some((item) => item.item_count > 0) ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={daily.data}>
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="profit_recovered" fill="#7c3aed" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </ChartCard>

        <ChartCard title="Returns by Category">
          {categories.data.length ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={categories.data}>
                <XAxis dataKey="category" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="total_profit">
                  {categories.data.map((entry) => <Cell key={entry.category} fill={categoryColors[entry.category] || '#3b82f6'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </ChartCard>

        <ChartCard title="Condition Distribution">
          {conditions.data.some((item) => item.count > 0) ? (
            conditions.data.filter((item) => item.count > 0).length === 1 && conditions.data.find((item) => item.count > 0)?.condition === 'Good' ? (
              <div className="flex h-[280px] items-center justify-center px-6 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
                All {conditions.data.find((item) => item.count > 0).count} products with a recorded condition are currently classified as Good.
              </div>
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height={236}>
                  <PieChart>
                    <Pie data={conditions.data} dataKey="count" nameKey="condition" outerRadius={96}>
                      {conditions.data.map((entry) => <Cell key={entry.condition} fill={conditionColors[entry.condition] || '#3b82f6'} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex h-11 flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs">
                  {conditions.data.map((entry) => (
                    <div key={entry.condition} className="flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: conditionColors[entry.condition] || '#3b82f6' }} />
                      {entry.condition} ({entry.count})
                    </div>
                  ))}
                </div>
              </div>
            )
          ) : (
            <EmptyChart />
          )}
        </ChartCard>

        <ChartCard title="Decision Trend Over Time">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={daily.data}>
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Line type="monotone" dataKey="resell_count" stroke="#10b981" />
              <Line type="monotone" dataKey="refurbish_count" stroke="#f59e0b" />
              <Line type="monotone" dataKey="recycle_count" stroke="#ef4444" />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}

function ChartCard({ title, children }) {
  return <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}><h2 className="mb-4 text-lg font-semibold">{title}</h2>{children}</div>
}

function StatCard({ label, value, sub }) {
  return <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}><div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</div><div className="mt-2 text-2xl font-semibold">{value}</div>{sub ? <div className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>{sub}</div> : null}</div>
}

function getCategoryExtreme(categories, direction) {
  if (!categories.length) return null
  const compare = direction === 'max' ? Math.max : Math.min
  const value = compare(...categories.map((item) => item.total_profit))
  const tied = categories
    .filter((item) => item.total_profit === value)
    .sort((a, b) => a.category.localeCompare(b.category))
  return {
    category: tied.length > 1 ? `Tie: ${tied.map((item) => item.category).join(', ')}` : tied[0].category,
    total_profit: value,
  }
}

function EmptyChart() {
  return <div className="flex h-[280px] flex-col items-center justify-center text-center"><PackageSearch size={34} style={{ color: 'var(--text-muted)' }} /><div className="mt-3 font-medium">No data for this period</div></div>
}
