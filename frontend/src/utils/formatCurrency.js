export function formatCurrencyINR(value) {
  if (value === null || value === undefined) return '--'
  const n = Number(value)
  if (Number.isNaN(n)) return '--'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(n)
}
