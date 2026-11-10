import { Database, Download, ExternalLink, FileSpreadsheet, Search, UploadCloud, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { useCreateReturn, useImportEbayItem, useMarketSearch } from '../hooks/useReturns'

const sampleCsv = `product_name,category,purchase_cost,market_price
Mi Power Bank 3i,Electronics,1200,1999
Adidas Running Tee,Apparel,900,1699
Noise Smartwatch Strap,Accessories,250,599`

export default function DataManagement() {
  const createReturn = useCreateReturn()
  const marketSearch = useMarketSearch()
  const importEbayItem = useImportEbayItem()
  const [fileName, setFileName] = useState('')
  const [rows, setRows] = useState([])
  const [history, setHistory] = useState([])
  const [ebayQuery, setEbayQuery] = useState('')
  const [ebayResults, setEbayResults] = useState([])
  const [purchaseCosts, setPurchaseCosts] = useState({})

  const preview = useMemo(() => rows.slice(0, 10), [rows])

  const parseCsv = async (file) => {
    const text = await file.text()
    const [header, ...lines] = text.trim().split(/\r?\n/)
    const columns = header.split(',')
    const parsed = lines.map((line) => {
      const values = line.split(',')
      return columns.reduce((acc, col, index) => {
        acc[col.trim()] = values[index]?.trim()
        return acc
      }, {})
    })
    setRows(parsed)
    setFileName(file.name)
  }

  const processAll = async () => {
    const invalidRow = rows.find((row) =>
      !row.product_name?.trim()
      || !row.category?.trim()
      || row.purchase_cost == null
      || String(row.purchase_cost).trim() === ''
      || !Number.isFinite(Number(row.purchase_cost))
      || Number(row.purchase_cost) < 0
      || row.market_price == null
      || String(row.market_price).trim() === ''
      || !Number.isFinite(Number(row.market_price))
      || Number(row.market_price) <= 0,
    )
    if (invalidRow) {
      toast.error('Each CSV row needs a product, category, valid purchase cost, and positive INR market price.')
      return
    }
    try {
      for (const row of rows) {
        await createReturn.mutateAsync({
          product_name: row.product_name.trim(),
          category: row.category.trim(),
          purchase_cost: Number(row.purchase_cost),
          market_price: Number(row.market_price),
        })
      }
    } catch (error) {
      toast.error(error.message || 'Unable to import the CSV rows.')
      return
    }
    setHistory((items) => [
      {
        filename: fileName,
        date: new Date().toLocaleString(),
        items: rows.length,
        processed: rows.length,
        status: 'Complete',
      },
      ...items,
    ].slice(0, 10))
    toast.success(`Processed ${rows.length} items`)
    setRows([])
    setFileName('')
  }

  const downloadTemplate = () => {
    const blob = new Blob([sampleCsv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'reprofit-sample-template.csv'
    a.click()
  }

  const searchMarket = async (event) => {
    event.preventDefault()
    if (!ebayQuery.trim()) return
    setEbayResults(await marketSearch.mutateAsync(ebayQuery.trim()))
  }

  const importListing = async (item) => {
    if (!item.price_available || !item.price || item.currency !== 'INR') {
      toast.error('Import requires a valid market price converted to INR.')
      return
    }
    const rawPurchaseCost = purchaseCosts[item.item_id]
    const purchaseCost = Number(rawPurchaseCost)
    if (rawPurchaseCost == null || String(rawPurchaseCost).trim() === '' || !Number.isFinite(purchaseCost) || purchaseCost < 0) {
      toast.error('Enter a valid non-negative purchase cost before importing')
      return
    }
    await importEbayItem.mutateAsync({
      ebay_item_id: item.item_id,
      product_name: item.title,
      category: 'Electronics',
      purchase_cost: purchaseCost,
      market_price: item.price,
      market_price_source: 'SerpAPI',
      market_price_url: item.url || null,
    })
    setEbayResults((items) => items.filter((result) => result.item_id !== item.item_id))
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Data Management</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Bulk upload and manage return data</p>
      </div>

      <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-6 py-14 text-center" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-card)' }}>
        <UploadCloud size={34} className="mb-3" />
        <div className="text-lg font-semibold">Drag & drop CSV file here</div>
        <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>or click to browse</div>
        <input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && parseCsv(e.target.files[0])} />
      </label>

      {rows.length ? (
        <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="font-semibold">{fileName}</div>
              <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{rows.length} items ready</div>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={processAll} className="h-11 rounded-lg px-4 font-medium text-white" style={{ background: 'var(--accent-primary)' }}>
                Process All {rows.length} Items
              </button>
              <button type="button" onClick={() => { setRows([]); setFileName('') }} className="flex h-11 items-center gap-2 rounded-lg border px-4" style={{ borderColor: 'var(--border-color)' }}>
                <X size={16} /> Cancel
              </button>
            </div>
          </div>
          <div className="overflow-auto">
            <table className="min-w-full text-left text-sm">
              <thead><tr>{Object.keys(preview[0]).map((key) => <th key={key} className="px-3 py-2 font-semibold">{key}</th>)}</tr></thead>
              <tbody>{preview.map((row, index) => <tr key={index}>{Object.values(row).map((value, idx) => <td key={idx} className="px-3 py-2">{value}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>
      ) : null}

      <section className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
        <div className="mb-4 flex items-center gap-2"><Search size={18} /><h2 className="text-lg font-semibold">Find live market prices</h2></div>
        <p className="mb-3 text-sm" style={{ color: 'var(--text-secondary)' }}>Verify the listing matches the exact model and specifications before importing. Market listings are references, not guaranteed resale prices for returned-condition items.</p>
        <form onSubmit={searchMarket} className="flex gap-2 max-sm:flex-col">
          <input value={ebayQuery} onChange={(e) => setEbayQuery(e.target.value)} placeholder="Search mobile, laptop, or electronics" className="h-11 flex-1 rounded-lg border px-3 outline-none" style={{ background: 'var(--bg-main)', borderColor: 'var(--border-color)' }} />
          <button type="submit" disabled={marketSearch.isPending} className="flex h-11 items-center justify-center gap-2 rounded-lg px-4 font-medium text-white" style={{ background: 'var(--accent-primary)' }}><Search size={16} /> {marketSearch.isPending ? 'Searching...' : 'Search market'}</button>
        </form>
        {ebayResults.length ? <div className="mt-4 space-y-3">
          {ebayResults.map((item) => <div key={item.item_id} className="flex gap-3 rounded-lg border p-3 max-sm:flex-col" style={{ borderColor: 'var(--border-color)' }}>
            {item.image_url ? <img src={item.image_url} alt="" className="h-16 w-16 rounded object-cover" /> : null}
            <div className="min-w-0 flex-1">
              <div className="font-medium">{item.title}</div>
              <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{item.price_available ? `₹ ${item.price}` : `Price unavailable${item.original_currency ? ` (${item.original_currency} cannot be converted safely)` : ' (currency not identified)'}`}{item.original_currency === 'USD' ? ` (converted from $${item.original_price})` : ''}{item.source ? ` · ${item.source}` : ''}{item.condition ? ` · ${item.condition}` : ''}</div>
              <div className="mt-2 flex items-center gap-2 max-sm:flex-col max-sm:items-stretch">
                <input type="number" min="0" step="0.01" placeholder="Purchase cost" value={purchaseCosts[item.item_id] || ''} onChange={(e) => setPurchaseCosts((costs) => ({ ...costs, [item.item_id]: e.target.value }))} className="h-9 rounded border px-2 text-sm" style={{ background: 'var(--bg-main)', borderColor: 'var(--border-color)' }} />
                <button type="button" onClick={() => importListing(item)} disabled={importEbayItem.isPending || !item.price_available} className="h-9 rounded px-3 text-sm font-medium text-white" style={{ background: 'var(--accent-primary)' }}>Import to queue</button>
                {item.url ? <a href={item.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm" style={{ color: 'var(--accent-primary)' }}>View listing <ExternalLink size={14} /></a> : null}
              </div>
            </div>
          </div>)}
        </div> : null}
      </section>

      <div className="grid grid-cols-2 gap-4 max-xl:grid-cols-1">
        <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
          <div className="mb-2 flex items-center gap-2"><FileSpreadsheet size={18} /><h2 className="text-lg font-semibold">Sample CSV Template</h2></div>
          <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>Required columns: `product_name`, `category`, `purchase_cost`, `market_price`</p>
          <button type="button" onClick={downloadTemplate} className="flex h-11 items-center gap-2 rounded-lg px-4 font-medium text-white" style={{ background: 'var(--accent-primary)' }}>
            <Download size={16} /> Download Template
          </button>
        </div>

        <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
          <div className="mb-4 flex items-center gap-2"><Database size={18} /><h2 className="text-lg font-semibold">Upload History</h2></div>
          <table className="min-w-full text-left text-sm">
            <thead><tr><th className="py-2">Filename</th><th>Date</th><th>Items</th><th>Processed</th><th>Status</th></tr></thead>
            <tbody>
              {history.length ? history.map((item, index) => (
                <tr key={index}>
                  <td className="py-2">{item.filename}</td>
                  <td>{item.date}</td>
                  <td>{item.items}</td>
                  <td>{item.processed}</td>
                  <td><span className="rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-500">{item.status}</span></td>
                </tr>
              )) : <tr><td colSpan="5" className="py-6 text-center" style={{ color: 'var(--text-secondary)' }}>No uploads yet</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
