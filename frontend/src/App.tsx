import type { CSSProperties } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/dashboard'
import Portfolio from './pages/portfolio'
import Recommendations from './pages/ai-recommendations'
import AutoTrading from './pages/auto-trading'
import Orders from './pages/orders'
import Economic from './pages/economic'
import { theme } from './theme'

const shell: CSSProperties = {
  display: 'flex',
  minHeight: '100vh',
  backgroundColor: theme.bgBase,
  backgroundImage: `
    radial-gradient(ellipse 90% 55% at 0% -10%, ${theme.bgAccentA}, transparent 55%),
    radial-gradient(ellipse 70% 45% at 100% 0%, ${theme.bgAccentB}, transparent 50%),
    radial-gradient(ellipse 50% 35% at 80% 100%, ${theme.bgAccentC}, transparent 45%)
  `,
}

export default function App() {
  return (
    <BrowserRouter>
      <div style={shell}>
        <Sidebar />
        <main className="trader-scroll" style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/auto-trading" element={<AutoTrading />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/economic" element={<Economic />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
