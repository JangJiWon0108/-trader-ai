import type { CSSProperties } from 'react'
import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import SortableTh from '../../components/SortableTh'
import Tooltip from '../../components/Tooltip'
import { useTableSort } from '../../hooks/useTableSort'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import { fetchAllBalances, type KisHolding } from '../../api'

const th: CSSProperties = {
  padding: '12px 14px',
  fontSize: 12,
  fontWeight: 600,
  color: theme.onSurfaceVariant,
  textAlign: 'left',
  borderBottom: `1px solid ${theme.outline}`,
}
const td: CSSProperties = {
  padding: '14px',
  fontSize: 14,
  fontVariantNumeric: 'tabular-nums',
  color: theme.onSurface,
  borderBottom: `1px solid ${theme.surfaceContainer}`,
}

function fmt(n: number | string | null | undefined, digits = 2) {
  const v = typeof n === 'string' ? parseFloat(n) : n
  if (v == null || isNaN(v as number)) return '—'
  return (v as number).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function toNum(s: string | undefined) {
  return parseFloat(s ?? '0') || 0
}

type RowData = {
  symbol: string
  name: string
  qty: number
  avgCost: number
  price: number
  evalAmt: number
  costAmt: number
  pnlAmt: number
  pnlPct: number
  weight: number
}

const rowAccessors: Record<string, (r: RowData) => string | number> = {
  symbol: (r) => r.symbol,
  name: (r) => r.name,
  qty: (r) => r.qty,
  avgCost: (r) => r.avgCost,
  price: (r) => r.price,
  evalAmt: (r) => r.evalAmt,
  pnlPct: (r) => r.pnlPct,
  weight: (r) => r.weight,
}

function buildRows(holdings: KisHolding[]): RowData[] {
  const totalEval = holdings.reduce((s, h) => {
    const qty = toNum(h.ovrs_cblc_qty)
    const price = toNum(h.now_pric2)
    return s + qty * price
  }, 0)

  return holdings.map((h) => {
    const qty = toNum(h.ovrs_cblc_qty)
    const avgCost = toNum(h.pchs_avg_pric)
    const price = toNum(h.now_pric2)
    const evalAmt = qty * price
    const costAmt = qty * avgCost
    const pnlAmt = evalAmt - costAmt
    const pnlPct = costAmt > 0 ? (pnlAmt / costAmt) * 100 : 0
    const weight = totalEval > 0 ? (evalAmt / totalEval) * 100 : 0
    return { symbol: h.ovrs_pdno, name: h.ovrs_item_name, qty, avgCost, price, evalAmt, costAmt, pnlAmt, pnlPct, weight }
  })
}

const CARD_TIPS: Record<string, string> = {
  '평가 금액': '현재가 × 수량 합산 (USD)',
  '매입 금액': '평단가 × 수량 합산 (USD)',
  '평가 손익': '평가금액 - 매입금액 / 손익률 포함',
  '보유 종목': '나스닥·NYSE·AMEX 전 거래소 합산',
}

function SummaryCard({ title, value, color }: { title: string; value: string; color?: string }) {
  const tip = CARD_TIPS[title]
  return (
    <Card title={tip ? <Tooltip tip={tip}>{title}</Tooltip> : title}>
      <div style={{ fontSize: 22, fontWeight: 800, fontVariantNumeric: 'tabular-nums', fontFamily: theme.fontDisplay, letterSpacing: '-0.03em', color: color ?? theme.onSurface }}>
        {value}
      </div>
    </Card>
  )
}

export default function Portfolio() {
  const { data, loading, error, refetch } = useApi(fetchAllBalances)
  const holdings: KisHolding[] = data?.output1 ?? []
  const rows = buildRows(holdings)

  const totalEval = rows.reduce((s, r) => s + r.evalAmt, 0)
  const totalCost = rows.reduce((s, r) => s + r.costAmt, 0)
  const totalPnl = totalEval - totalCost
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0

  const { sortedRows, sortKey, sortDir, requestSort } = useTableSort(rows, rowAccessors)

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%' }}>
      <PageHeader title="포트폴리오" subtitle="해외주식 보유 현황 · 나스닥/NYSE/AMEX" />

      {error && (
        <div style={{ marginBottom: theme.gutter, padding: '12px 16px', borderRadius: theme.radiusMd, background: 'rgba(225,29,72,0.1)', color: theme.negative, fontSize: 14 }}>
          데이터 로딩 실패: {error} ·{' '}
          <span style={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={refetch}>재시도</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: theme.gutter, marginBottom: theme.gutter }}>
        <SummaryCard title="평가 금액" value={loading ? '…' : `$${fmt(totalEval)}`} />
        <SummaryCard title="매입 금액" value={loading ? '…' : `$${fmt(totalCost)}`} />
        <SummaryCard
          title="평가 손익"
          value={loading ? '…' : `${totalPnl >= 0 ? '+' : ''}$${fmt(Math.abs(totalPnl))} (${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(2)}%)`}
          color={totalPnl >= 0 ? theme.positive : theme.negative}
        />
        <SummaryCard title="보유 종목" value={loading ? '…' : `${rows.length}개`} />
      </div>

      <Card title="보유 종목 목록" subtitle="비중은 평가 금액 기준 · 헤더 클릭으로 정렬">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {[
                  { id: 'symbol', label: '티커', align: 'left' as const },
                  { id: 'name', label: '종목명', align: 'left' as const },
                  { id: 'qty', label: '수량', align: 'right' as const, tip: '보유 주식 수 (주)' },
                  { id: 'avgCost', label: '평단가', align: 'right' as const, tip: '매입 평균 단가 (USD)' },
                  { id: 'price', label: '현재가', align: 'right' as const, tip: '현재 실시간 체결가 (USD)' },
                  { id: 'evalAmt', label: '평가액', align: 'right' as const, tip: '현재가 × 수량 (USD)' },
                  { id: 'pnlPct', label: '손익률', align: 'right' as const, tip: '(현재가 - 평단가) / 평단가 × 100' },
                  { id: 'weight', label: '비중', align: 'right' as const, tip: '총 포트폴리오 대비 해당 종목 비율' },
                ].map(({ id, label, align, tip }) => (
                  <SortableTh key={id} colId={id} label={label} align={align} sortKey={sortKey} sortDir={sortDir} onSort={requestSort}
                    style={{ ...th, textAlign: align }} tip={tip} />
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ ...td, textAlign: 'center', color: theme.onSurfaceVariant }}>잔고 조회 중…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={8} style={{ ...td, textAlign: 'center', color: theme.onSurfaceVariant }}>보유 종목 없음</td></tr>
              )}
              {sortedRows.map((r) => (
                <tr key={r.symbol}>
                  <td style={{ ...td, fontWeight: 600 }}>{r.symbol}</td>
                  <td style={td}>{r.name}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{r.qty.toFixed(0)}</td>
                  <td style={{ ...td, textAlign: 'right' }}>${fmt(r.avgCost)}</td>
                  <td style={{ ...td, textAlign: 'right' }}>${fmt(r.price)}</td>
                  <td style={{ ...td, textAlign: 'right' }}>${fmt(r.evalAmt)}</td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 700, color: r.pnlPct >= 0 ? theme.positive : theme.negative }}>
                    {r.pnlPct >= 0 ? '+' : ''}{r.pnlPct.toFixed(2)}%
                  </td>
                  <td style={{ ...td, textAlign: 'right' }}>{r.weight.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
