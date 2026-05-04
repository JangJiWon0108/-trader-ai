import type { CSSProperties } from 'react'
import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import Sparkline from '../../components/Sparkline'
import Tooltip from '../../components/Tooltip'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import {
  fetchAllBalances,
  fetchPredictions,
  fetchSchedulerStatus,
  type KisHolding,
  type StockPrediction,
} from '../../api'

const cell: CSSProperties = {
  padding: '12px 14px',
  fontSize: 14,
  fontVariantNumeric: 'tabular-nums',
  borderBottom: `1px solid ${theme.surfaceContainer}`,
}

function fmt(n: number | string | null | undefined, digits = 2) {
  const v = typeof n === 'string' ? parseFloat(n) : n
  if (v == null || isNaN(v as number)) return '—'
  return (v as number).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function fmtPct(n: number | string | null | undefined) {
  const v = typeof n === 'string' ? parseFloat(n) : n
  if (v == null || isNaN(v as number)) return '—'
  const num = v as number
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
}

function LoadingRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} style={{ ...cell, color: theme.onSurfaceVariant }}>…</td>
      ))}
    </tr>
  )
}

function getSignalColor(rec: string | null) {
  if (!rec) return theme.onSurfaceVariant
  const r = rec.toUpperCase()
  if (r === 'BUY' || r === '매수') return theme.positive
  if (r === 'SELL' || r === '매도') return theme.negative
  return theme.onSurfaceVariant
}

export default function Dashboard() {
  const balance = useApi(fetchAllBalances)
  const predictions = useApi(fetchPredictions)
  const scheduler = useApi(fetchSchedulerStatus)

  // ── summary cards from balance ──────────────────────────────────
  const holdings: KisHolding[] = balance.data?.output1 ?? []

  const totalCost = holdings.reduce((s, h) => s + parseFloat(h.frcr_buy_amt_smtl1 || '0'), 0)
  const totalEval = holdings.reduce((s, h) => {
    const qty = parseFloat(h.ovrs_cblc_qty || '0')
    const price = parseFloat(h.now_pric2 || '0')
    return s + qty * price
  }, 0)
  const totalPnl = totalEval - totalCost
  const totalPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0

  const preds: StockPrediction[] = predictions.data ?? []

  const summaryCards = [
    {
      id: 'eval',
      title: '총 평가 금액',
      tip: '보유 종목 현재가 × 수량의 합계 (USD)',
      value: balance.loading ? '로딩 중…' : `$${fmt(totalEval)}`,
      changePct: totalPct,
      spark: [0.4, 0.42, 0.45, 0.48, 0.5, 0.52, 0.55],
    },
    {
      id: 'pnl',
      title: '평가 손익',
      tip: '현재 평가금액 - 매입금액. 아래 % 는 수익률',
      value: balance.loading ? '로딩 중…' : `${totalPnl >= 0 ? '+' : ''}$${fmt(Math.abs(totalPnl))}`,
      changePct: totalPct,
      spark: [0.5, 0.52, 0.55, 0.53, 0.57, 0.6, 0.62],
    },
    {
      id: 'holdings',
      title: '보유 종목 수',
      tip: '나스닥·NYSE·AMEX 전 거래소 보유 종목 합산',
      value: balance.loading ? '로딩 중…' : `${holdings.length}개`,
      changePct: 0,
      spark: [0.6, 0.6, 0.6, 0.6, 0.61, 0.61, 0.62],
    },
  ]

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%' }}>
      <PageHeader
        title="대시보드"
        subtitle={`US 시장 기준 · 스케줄러: 매수 ${scheduler.data?.buy_running ? '실행 중' : '중지'} / 매도 ${scheduler.data?.sell_running ? '실행 중' : '중지'}`}
      />

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: theme.gutter, marginBottom: theme.gutter }}>
        {summaryCards.map((c) => (
          <Card key={c.id} title={<Tooltip tip={c.tip}>{c.title}</Tooltip>}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <div>
                <div style={{ fontSize: 24, fontWeight: 800, fontVariantNumeric: 'tabular-nums', color: theme.onSurface, fontFamily: theme.fontDisplay, letterSpacing: '-0.03em' }}>
                  {c.value}
                </div>
                {c.changePct !== 0 && (
                  <div style={{ marginTop: 8, fontSize: 13, fontWeight: 700, color: c.changePct >= 0 ? theme.positive : theme.negative }}>
                    {fmtPct(c.changePct)}
                  </div>
                )}
              </div>
              <Sparkline points={c.spark} positive={c.changePct === 0 ? undefined : c.changePct > 0} />
            </div>
          </Card>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: theme.gutter }}>
        {/* Holdings table */}
        <Card title="보유 종목" subtitle="해외주식 잔고 · 나스닥/NYSE/AMEX">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ color: theme.onSurfaceVariant, fontSize: 12 }}>
                  {([
                    ['티커', '', 'left'],
                    ['종목명', '', 'left'],
                    ['수량', '보유 주식 수 (주)', 'right'],
                    ['평단', '매입 평균 단가 (USD)', 'right'],
                    ['현재가', '현재 실시간 체결가 (USD)', 'right'],
                    ['손익', '(현재가 - 평단) / 평단 × 100', 'right'],
                  ] as [string, string, string][]).map(([h, tip, align]) => (
                    <th key={h} style={{ ...cell, fontWeight: 700, textAlign: align as 'left' | 'right' }}>
                      {tip ? <Tooltip tip={tip} below>{h}</Tooltip> : h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {balance.loading && <LoadingRow cols={6} />}
                {balance.error && (
                  <tr>
                    <td colSpan={6} style={{ ...cell, color: theme.negative }}>잔고 조회 실패: {balance.error}</td>
                  </tr>
                )}
                {!balance.loading && holdings.length === 0 && !balance.error && (
                  <tr>
                    <td colSpan={6} style={{ ...cell, color: theme.onSurfaceVariant }}>보유 종목 없음</td>
                  </tr>
                )}
                {holdings.map((h) => {
                  const pnlPct = parseFloat(h.evlu_pfls_rt || '0')
                  const pnlAmt = parseFloat(h.frcr_evlu_pfls_amt || '0')
                  return (
                    <tr key={h.ovrs_pdno} style={{ color: theme.onSurface }}>
                      <td style={{ ...cell, fontWeight: 700 }}>{h.ovrs_pdno}</td>
                      <td style={{ ...cell, fontSize: 13, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.ovrs_item_name}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{parseFloat(h.ovrs_cblc_qty || '0').toFixed(0)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>${fmt(h.pchs_avg_pric)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>${fmt(h.now_pric2)}</td>
                      <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: pnlAmt >= 0 ? theme.positive : theme.negative }}>
                        {fmtPct(pnlPct)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* AI Predictions feed */}
        <Card title="AI 예측 종목" subtitle="상승 확률 상위 · 실제 모델 결과">
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {predictions.loading && (
              <li style={{ padding: '14px 0', color: theme.onSurfaceVariant }}>로딩 중…</li>
            )}
            {predictions.error && (
              <li style={{ padding: '14px 0', color: theme.negative }}>오류: {predictions.error}</li>
            )}
            {preds
              .filter((p) => p.rise_probability != null)
              .sort((a, b) => (b.rise_probability ?? 0) - (a.rise_probability ?? 0))
              .slice(0, 8)
              .map((p) => {
                const rec = p.recommendation ?? ''
                return (
                  <li
                    key={p.stock}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr auto',
                      gap: 8,
                      padding: '12px 10px',
                      borderBottom: `1px solid ${theme.surfaceContainer}`,
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 700, fontSize: 14, color: theme.onSurface }}>{p.stock}</span>
                      <span style={{ marginLeft: 8, fontSize: 12, color: theme.onSurfaceVariant }}>
                        현재 ${fmt(p.last_price)} → 예측 ${fmt(p.predicted_price)}
                      </span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: getSignalColor(rec) }}>
                        <Tooltip tip="LSTM 모델의 매수·매도·보유 판단">{rec}</Tooltip>
                      </div>
                      <div style={{ fontSize: 12, color: theme.onSurfaceVariant }}>
                        <Tooltip tip="AI 모델이 예측한 내일 주가 상승 확률">상승확률 {fmt(p.rise_probability, 1)}%</Tooltip>
                      </div>
                    </div>
                  </li>
                )
              })}
          </ul>
        </Card>
      </div>
    </div>
  )
}
