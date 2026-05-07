import { useEffect, useMemo } from 'react'
import { theme } from '../theme'
import type { EquitySnapshot } from '../api'

type Metric = 'assets' | 'return'

function fmtKstHm(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false })
}

function fmtMoney(n: number) {
  if (!isFinite(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(n: number) {
  if (!isFinite(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

function toSeries(items: EquitySnapshot[], metric: Metric) {
  const pts = items
    .filter((x) => typeof x?.ts_utc === 'string' && (metric === 'assets' ? isFinite(x.total_assets_usd) : isFinite(x.total_return_pct)))
    .map((x) => ({
      t: new Date(x.ts_utc).getTime(),
      label: fmtKstHm(x.ts_utc),
      v: metric === 'assets' ? x.total_assets_usd : x.total_return_pct,
      raw: x,
    }))
    .sort((a, b) => a.t - b.t)
  return pts
}

function buildPath(values: number[], w: number, h: number) {
  if (values.length < 2) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = w / (values.length - 1)
  return values
    .map((v, i) => {
      const x = i * step
      const y = h - ((v - min) / span) * (h - 10) - 5
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export default function EquityChartModal({
  open,
  title,
  metric,
  items,
  loading,
  onClose,
}: {
  open: boolean
  title: string
  metric: Metric
  items: EquitySnapshot[]
  loading?: boolean
  onClose: () => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const series = useMemo(() => toSeries(items, metric), [items, metric])
  const values = useMemo(() => series.map((s) => s.v), [series])
  const w = 920
  const h = 240
  const d = useMemo(() => buildPath(values, w, h), [values])
  const last = series[series.length - 1]?.raw

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'grid',
        placeItems: 'center',
        padding: 18,
        background: 'rgba(2, 6, 23, 0.55)',
        backdropFilter: 'blur(10px)',
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          width: 'min(980px, 96vw)',
          maxHeight: 'min(84vh, 860px)',
          borderRadius: theme.radiusLg,
          overflow: 'hidden',
          border: '1px solid rgba(148, 163, 184, 0.18)',
          boxShadow: '0 24px 80px rgba(0,0,0,0.45)',
          background: 'rgba(15, 23, 42, 0.86)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            padding: '12px 14px',
            background: theme.primary,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ fontFamily: theme.fontDisplay, fontSize: 14, fontWeight: 900, color: '#fff', letterSpacing: '-0.02em' }}>
              {title}
            </div>
            <div style={{ marginTop: 4, fontSize: 12, color: 'rgba(226,232,240,0.85)' }}>
              {loading ? '로딩…' : `${series.length}pt · 정규장 1시간 스냅샷`}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                width: 34,
                height: 34,
                borderRadius: 12,
                border: '1px solid rgba(255, 255, 255, 0.18)',
                background: 'rgba(255, 255, 255, 0.14)',
                color: '#fff',
                fontSize: 16,
                fontWeight: 900,
                cursor: 'pointer',
              }}
              aria-label="닫기"
              title="닫기 (Esc)"
            >
              ×
            </button>
          </div>
        </div>

        <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontSize: 12, color: theme.onSurfaceVariant }}>
              기준: 미국 정규장(ET) · KST {`(서머타임: 23:30~05:00)`}
            </div>
            {last && (
              <div style={{ fontSize: 12, color: '#e2e8f0', fontVariantNumeric: 'tabular-nums' }}>
                최신 {metric === 'assets' ? `$${fmtMoney(last.total_assets_usd)}` : fmtPct(last.total_return_pct)}
              </div>
            )}
          </div>

          <div
            style={{
              borderRadius: 16,
              border: '1px solid rgba(148, 163, 184, 0.18)',
              background: 'rgba(2, 6, 23, 0.55)',
              padding: 12,
            }}
          >
            {series.length < 2 ? (
              <div style={{ color: theme.onSurfaceVariant, fontSize: 13 }}>표시할 스냅샷이 아직 없습니다. (장중 1시간마다 쌓입니다)</div>
            ) : (
              <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden>
                <path d={d} fill="none" stroke={theme.accentCyan} strokeWidth={3} strokeLinecap="round" />
              </svg>
            )}
            {series.length >= 2 && (
              <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', color: theme.onSurfaceVariant, fontSize: 11 }}>
                <span>{series[0].label}</span>
                <span>{series[series.length - 1].label}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

