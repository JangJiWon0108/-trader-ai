import type { CSSProperties } from 'react'
import { useState } from 'react'
import Badge from '../../components/Badge'
import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import SortableTh from '../../components/SortableTh'
import Tooltip from '../../components/Tooltip'
import { useTableSort } from '../../hooks/useTableSort'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import { fetchCombinedRecommendations, fetchPredictions, type CombinedRecommendation, type StockPrediction } from '../../api'

const th: CSSProperties = {
  padding: '12px 10px',
  fontSize: 12,
  fontWeight: 600,
  color: theme.onSurfaceVariant,
  textAlign: 'left',
  borderBottom: `1px solid ${theme.outline}`,
}
const td: CSSProperties = {
  padding: '12px 10px',
  fontSize: 13,
  borderBottom: `1px solid ${theme.surfaceContainer}`,
  color: theme.onSurface,
  verticalAlign: 'top',
}

function fmt(n: number | null | undefined, digits = 2) {
  if (n == null) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function signalVariant(rec: string): 'buy' | 'sell' | 'hold' | 'neutral' {
  const r = rec.toUpperCase()
  if (r === 'BUY' || r === '매수') return 'buy'
  if (r === 'SELL' || r === '매도') return 'sell'
  if (r === 'HOLD' || r === '보유') return 'hold'
  return 'neutral'
}

function SentimentDot({ score }: { score: number | undefined }) {
  if (score == null) return <span style={{ color: theme.onSurfaceVariant }}>—</span>
  const color = score >= 0.15 ? theme.positive : score <= -0.15 ? theme.negative : theme.onSurfaceVariant
  return <span style={{ fontWeight: 700, color }}>{score >= 0 ? '+' : ''}{score.toFixed(3)}</span>
}

// Combined rec row type for sort
type CombRow = CombinedRecommendation & { _type: 'combined' }
const combAccessors: Record<string, (r: CombRow) => string | number> = {
  ticker: (r) => r.ticker,
  stock_name: (r) => r.stock_name,
  recommendation: (r) => r.recommendation,
  rise_probability: (r) => r.rise_probability,
  last_price: (r) => r.last_price,
  predicted_price: (r) => r.predicted_price,
  sentiment_score: (r) => r.sentiment_score ?? r.average_sentiment_score ?? -999,
  accuracy: (r) => r.accuracy ?? 0,
}

// AI prediction row type for sort
type PredRow = StockPrediction & { _type: 'pred' }
const predAccessors: Record<string, (r: PredRow) => string | number> = {
  stock: (r) => r.stock,
  recommendation: (r) => r.recommendation ?? '',
  rise_probability: (r) => r.rise_probability ?? 0,
  last_price: (r) => r.last_price ?? 0,
  predicted_price: (r) => r.predicted_price ?? 0,
}

type Tab = 'combined' | 'ai'

export default function Recommendations() {
  const [tab, setTab] = useState<Tab>('combined')

  const combined = useApi(fetchCombinedRecommendations)
  const aiPreds = useApi(fetchPredictions)

  const combRows: CombRow[] = (combined.data?.results ?? []).map((r) => ({ ...r, _type: 'combined' as const }))
  const predRows: PredRow[] = (aiPreds.data ?? []).map((r) => ({ ...r, _type: 'pred' as const }))

  const {
    sortedRows: sortedComb,
    sortKey: ck,
    sortDir: cd,
    requestSort: cr,
  } = useTableSort(combRows, combAccessors)

  const {
    sortedRows: sortedPred,
    sortKey: pk,
    sortDir: pd,
    requestSort: pr,
  } = useTableSort(predRows, predAccessors)

  const tabStyle = (active: boolean): CSSProperties => ({
    padding: '8px 18px',
    borderRadius: theme.radiusMd,
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
    border: 'none',
    background: active ? theme.primary : 'transparent',
    color: active ? '#fff' : theme.onSurfaceVariant,
    transition: 'all 0.15s',
  })

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%' }}>
      <PageHeader title="AI 추천 종목" subtitle="기술적 지표 + 감성분석 + AI 모델 통합 결과" />

      <div style={{ display: 'flex', gap: 8, marginBottom: theme.gutter }}>
        <button style={tabStyle(tab === 'combined')} onClick={() => setTab('combined')}>통합 추천 (기술+감성)</button>
        <button style={tabStyle(tab === 'ai')} onClick={() => setTab('ai')}>AI 모델 예측</button>
      </div>

      {tab === 'combined' && (
        <Card title="통합 추천 종목" subtitle="골든크로스·MACD·RSI + 감성점수 ≥ 0.15 필터링">
          {combined.loading && <div style={{ padding: 20, color: theme.onSurfaceVariant }}>데이터 로딩 중…</div>}
          {combined.error && <div style={{ padding: 20, color: theme.negative }}>오류: {combined.error}</div>}
          {!combined.loading && combRows.length === 0 && <div style={{ padding: 20, color: theme.onSurfaceVariant }}>조건을 만족하는 종목이 없습니다</div>}
          {combRows.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
                <thead>
                  <tr>
                    {[
                      { id: 'ticker', label: '티커' },
                      { id: 'stock_name', label: '종목명' },
                      { id: 'recommendation', label: '신호', tip: 'AI·기술·감성 통합 매수/매도/보유 판단' },
                      { id: 'rise_probability', label: '상승확률', right: true, tip: 'AI 모델 예측 상승 확률 (%)' },
                      { id: 'last_price', label: '현재가', right: true, tip: '가장 최근 실제 체결가 (USD)' },
                      { id: 'predicted_price', label: '예측가', right: true, tip: 'LSTM 모델이 예측한 미래 가격 (USD)' },
                      { id: 'sentiment_score', label: '감성점수', right: true, tip: '뉴스 감성 점수 (-1~1) · 0.15↑ 긍정 / -0.15↓ 부정' },
                      { id: 'accuracy', label: '정확도', right: true, tip: '모델 백테스트 예측 정확도 (%)' },
                    ].map(({ id, label, right, tip }) => (
                      <SortableTh key={id} colId={id} label={label} align={right ? 'right' : 'left'}
                        sortKey={ck} sortDir={cd} onSort={cr}
                        style={{ ...th, textAlign: right ? 'right' : 'left' }} tip={tip} />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedComb.map((r) => (
                    <tr key={r.ticker}>
                      <td style={{ ...td, fontWeight: 700 }}>{r.ticker}</td>
                      <td style={td}>{r.stock_name}</td>
                      <td style={td}><Badge variant={signalVariant(r.recommendation)} /></td>
                      <td style={{ ...td, textAlign: 'right', fontWeight: 700, color: r.rise_probability >= 50 ? theme.positive : theme.negative }}>
                        {fmt(r.rise_probability, 1)}%
                      </td>
                      <td style={{ ...td, textAlign: 'right' }}>${fmt(r.last_price)}</td>
                      <td style={{ ...td, textAlign: 'right' }}>${fmt(r.predicted_price)}</td>
                      <td style={{ ...td, textAlign: 'right' }}><SentimentDot score={r.sentiment_score ?? r.average_sentiment_score} /></td>
                      <td style={{ ...td, textAlign: 'right' }}>{r.accuracy != null ? `${fmt(r.accuracy, 1)}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === 'ai' && (
        <Card title="AI 모델 예측" subtitle="LSTM 모델 기반 · 정확도 80% 이상 + 상승확률 3% 이상">
          {aiPreds.loading && <div style={{ padding: 20, color: theme.onSurfaceVariant }}>데이터 로딩 중…</div>}
          {aiPreds.error && <div style={{ padding: 20, color: theme.negative }}>오류: {aiPreds.error}</div>}
          {!aiPreds.loading && predRows.length === 0 && <div style={{ padding: 20, color: theme.onSurfaceVariant }}>데이터 없음</div>}
          {predRows.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
                <thead>
                  <tr>
                    {[
                      { id: 'stock', label: '종목명' },
                      { id: 'recommendation', label: '신호', tip: 'LSTM 모델의 매수/매도/보유 판단' },
                      { id: 'rise_probability', label: '상승확률', right: true, tip: 'AI 모델 예측 상승 확률 (%)' },
                      { id: 'last_price', label: '현재가', right: true, tip: '가장 최근 실제 체결가 (USD)' },
                      { id: 'predicted_price', label: '예측가', right: true, tip: 'LSTM 모델이 예측한 미래 가격 (USD)' },
                    ].map(({ id, label, right, tip }) => (
                      <SortableTh key={id} colId={id} label={label} align={right ? 'right' : 'left'}
                        sortKey={pk} sortDir={pd} onSort={pr}
                        style={{ ...th, textAlign: right ? 'right' : 'left' }} tip={tip} />
                    ))}
                    <th style={th}><Tooltip tip="AI가 생성한 해당 종목 투자 근거 요약" below>분석 요약</Tooltip></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPred.map((p) => (
                    <tr key={p.stock}>
                      <td style={{ ...td, fontWeight: 600 }}>{p.stock}</td>
                      <td style={td}><Badge variant={signalVariant(p.recommendation ?? '')} /></td>
                      <td style={{ ...td, textAlign: 'right', fontWeight: 700, color: (p.rise_probability ?? 0) >= 50 ? theme.positive : theme.negative }}>
                        {fmt(p.rise_probability, 1)}%
                      </td>
                      <td style={{ ...td, textAlign: 'right' }}>${fmt(p.last_price)}</td>
                      <td style={{ ...td, textAlign: 'right' }}>${fmt(p.predicted_price)}</td>
                      <td style={{ ...td, fontSize: 12, color: theme.onSurfaceVariant, maxWidth: 300 }}>
                        {p.analysis ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
