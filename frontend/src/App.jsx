import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import ProcessReturns from './pages/ProcessReturns.jsx'
import Analytics from './pages/Analytics.jsx'
import DecisionEngine from './pages/DecisionEngine.jsx'
import DataManagement from './pages/DataManagement.jsx'
import Settings from './pages/Settings.jsx'
import { useTheme } from './hooks/useTheme.js'

export default function App() {
  useTheme()

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/process-returns" element={<ProcessReturns />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/decision-engine" element={<DecisionEngine />} />
        <Route path="/data-management" element={<DataManagement />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
