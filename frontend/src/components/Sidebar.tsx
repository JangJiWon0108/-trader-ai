import { NavLink } from 'react-router-dom'
import { theme } from '../theme'
import './Sidebar.css'

const menus = [
  { path: '/', label: '대시보드', icon: '⊞' },
  { path: '/portfolio', label: '포트폴리오 / 잔고', icon: '◈' },
  { path: '/recommendations', label: 'AI 추천 종목', icon: '✦' },
  { path: '/auto-trading', label: '자동매매 현황', icon: '⟳' },
  { path: '/orders', label: '주문 내역', icon: '≡' },
  { path: '/economic', label: '경제 지표', icon: '◉' },
]

export default function Sidebar() {
  return (
    <aside
      style={{
        width: theme.sidebarWidth,
        minHeight: '100vh',
        background: `linear-gradient(165deg, #0f172a 0%, #020617 48%, #0c1224 100%)`,
        borderRight: `1px solid ${theme.sidebarBorder}`,
        padding: '28px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        flexShrink: 0,
        boxShadow: '8px 0 40px rgba(0, 0, 0, 0.35)',
      }}
    >
      <div
        style={{
          padding: '0 22px 28px',
          fontFamily: theme.fontDisplay,
          fontSize: 22,
          fontWeight: 800,
          letterSpacing: '-0.03em',
          background: `linear-gradient(120deg, #e0e7ff 0%, #38bdf8 45%, #c4b5fd 100%)`,
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}
      >
        Trader AI
      </div>
      <nav className="sidebar-nav">
        {menus.map(({ path, label, icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) => `sidebar-nav-link${isActive ? ' is-active' : ''}`}
          >
            <span className="sidebar-nav-link__icon" aria-hidden>
              {icon}
            </span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div style={{ flex: 1 }} />
      <div
        className="sidebar-foot"
        style={{
          margin: '0 18px 12px',
          padding: 14,
          borderRadius: theme.radiusMd,
          background: 'rgba(15, 23, 42, 0.65)',
          border: '1px solid rgba(148, 163, 184, 0.15)',
          fontFamily: theme.fontSans,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#818cf8', marginBottom: 6 }}>
          NEXT
        </div>
        <div style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.45 }}>실계좌 연동 · 알림은 곧 추가됩니다.</div>
      </div>
    </aside>
  )
}
