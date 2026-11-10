import { Outlet, useLocation } from 'react-router-dom'
import { useState } from 'react'
import GlobalSearch from './GlobalSearch'
import Header from './Header'
import Sidebar from './Sidebar'

export default function Layout() {
  const [searchOpen, setSearchOpen] = useState(false)
  const isProcessReturns = useLocation().pathname === '/process-returns'

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-main)', color: 'var(--text-primary)' }}>
      <Sidebar />
      <Header onOpenSearch={() => setSearchOpen(true)} />
      <GlobalSearch open={searchOpen} onOpen={() => setSearchOpen(true)} onClose={() => setSearchOpen(false)} />
      <main className={`ml-[240px] px-6 ${isProcessReturns ? 'h-screen overflow-hidden pb-6 max-lg:h-auto max-lg:min-h-screen max-lg:overflow-y-auto' : 'pb-24'} pt-[84px] max-md:ml-[88px] max-sm:ml-0 max-sm:px-4`}>
        <div className={`page-enter ${isProcessReturns ? 'h-full min-h-0 max-lg:h-auto' : ''}`}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}

