import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import Tooltip from '../../components/Tooltip'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import {
  fetchAdminPublicConfig,
  fetchSchedulerStatus,
  fetchSellCandidates,
} from '../../api'

function StatusPill({ running }: { running: boolean }) {
  return (
    <div
      className="trader-status-pill"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '9px 16px',
        borderRadius: 9999,
        fontSize: 14,
        fontWeight: 700,
        background: running
          ? 'linear-gradient(135deg, rgba(5,150,105,0.2), rgba(5,150,105,0.06))'
          : 'linear-gradient(135deg, rgba(225,29,72,0.18), rgba(225,29,72,0.06))',
        color: running ? theme.positive : theme.negative,
        border: running ? '1px solid rgba(5,150,105,0.4)' : '1px solid rgba(225,29,72,0.35)',
        boxShadow: running ? '0 0 20px rgba(5,150,105,0.2)' : '0 0 16px rgba(225,29,72,0.15)',
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: running ? theme.positive : theme.negative, boxShadow: `0 0 10px ${running ? theme.positive : theme.negative}` }} />
      {running ? '실행 중' : '중지됨'}
    </div>
  )
}

export default function AutoTrading() {
  const { data: status, loading: sLoading } = useApi(fetchSchedulerStatus)
  const { data: sellCandidates, loading: scLoading } = useApi(fetchSellCandidates)
  const { data: cfg } = useApi(fetchAdminPublicConfig)

  const buyRunning = status?.buy_running ?? false
  const sellRunning = status?.sell_running ?? false

  const buyTime = cfg?.schedule?.auto_buy_time_kst ?? '23:35'
  const sellEveryMin = cfg?.schedule?.auto_sell_interval_min ?? 1
  const econTime = cfg?.schedule?.economic_update_time_kst ?? '06:10'
  const tp = cfg?.sell?.take_profit_pct ?? 5
  const sl = cfg?.sell?.stop_loss_pct ?? -5
  const rsiOb = cfg?.sell?.rsi_overbought ?? 70

  const rules = [
    { name: '자동 매수', detail: `매일 ${buyTime} KST`, running: buyRunning },
    { name: '자동 매도', detail: `${sellEveryMin}분 간격 · 장중에만 실행`, running: sellRunning },
    { name: '경제 데이터 수집', detail: `매일 ${econTime} KST`, running: true },
  ]

  interface SellCandidate {
    ticker?: string
    stock_name?: string
    reason?: string
    current_price?: number
    purchase_price?: number
    pnl_pct?: number
    [key: string]: unknown
  }

  const candidates: SellCandidate[] = (sellCandidates?.results as SellCandidate[] | undefined) ?? []

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%', position: 'relative' }}>
      <PageHeader title="자동매매 현황" subtitle="스케줄러 상태" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: theme.gutter, marginBottom: theme.gutter }}>
        {/* Buy scheduler */}
        <Card title={<Tooltip tip={`매일 ${buyTime} KST 기술·감성·AI 통합 종목 자동 매수`}>매수 스케줄러</Tooltip>}>
          <StatusPill running={buyRunning} />
        </Card>

        {/* Sell scheduler */}
        <Card title={<Tooltip tip={`${sellEveryMin}분 간격으로 매도 조건 체크 · 익절 +${tp}% / 손절 ${sl}% / 기술 신호`}>매도 스케줄러</Tooltip>}>
          <StatusPill running={sellRunning} />
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: theme.gutter }}>
        {/* Schedule rules */}
        <Card title="스케줄 규칙">
          {sLoading && <div style={{ color: theme.onSurfaceVariant, padding: 12 }}>로딩 중…</div>}
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {rules.map((r) => (
              <li
                key={r.name}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '14px 10px',
                  borderBottom: `1px solid ${theme.surfaceContainer}`,
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14, color: theme.onSurface }}>{r.name}</div>
                  <div style={{ fontSize: 12, color: theme.onSurfaceVariant, marginTop: 2 }}>{r.detail}</div>
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: r.running ? theme.positive : theme.negative }}>
                  {r.running ? 'ON' : 'OFF'}
                </span>
              </li>
            ))}
          </ul>
        </Card>

        {/* Sell candidates */}
        <Card title="현재 매도 대상" subtitle={`익절 +${tp}% / 손절 ${sl}% · RSI>${rsiOb}·MACD 매도신호`}>
          {scLoading && <div style={{ color: theme.onSurfaceVariant, padding: 12 }}>로딩 중…</div>}
          {!scLoading && candidates.length === 0 && (
            <div style={{ color: theme.onSurfaceVariant, padding: '12px 0' }}>매도 대상 종목 없음</div>
          )}
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {candidates.map((c, i) => (
              <li
                key={i}
                style={{
                  padding: '14px 10px',
                  borderBottom: `1px solid ${theme.surfaceContainer}`,
                  display: 'grid',
                  gridTemplateColumns: '80px 1fr auto',
                  gap: 8,
                  alignItems: 'start',
                }}
              >
                <span style={{ fontWeight: 700, fontSize: 14 }}>{c.ticker ?? '—'}</span>
                <div>
                  <div style={{ fontSize: 13, color: theme.onSurface }}>{c.stock_name ?? ''}</div>
                  <div style={{ fontSize: 11, color: theme.onSurfaceVariant, marginTop: 2 }}>{c.reason ?? ''}</div>
                </div>
                {c.pnl_pct != null && (
                  <Tooltip tip="매수가 대비 현재가 등락률">
                    <span style={{ fontWeight: 700, fontSize: 13, color: (c.pnl_pct as number) >= 0 ? theme.positive : theme.negative }}>
                      {(c.pnl_pct as number) >= 0 ? '+' : ''}{(c.pnl_pct as number).toFixed(2)}%
                    </span>
                  </Tooltip>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
