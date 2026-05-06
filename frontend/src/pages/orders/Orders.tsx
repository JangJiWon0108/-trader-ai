import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import SortableTh from '../../components/SortableTh'
import { useTableSort } from '../../hooks/useTableSort'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import { fetchOrderHistory, type OrderHistoryItem } from '../../api'
import { tdBase, thColHead, tableScrollBox, monoFont } from '../../components/gridTableStyles'

function formatKst(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

type HistoryRow = OrderHistoryItem & {
  _reason: string
  _accuracy: number | null
  _riseProb: number | null
}

function buildHistoryRows(items: OrderHistoryItem[]): HistoryRow[] {
  return (items ?? []).map((it) => {
    const payload: any = it.payload ?? null
    const meta = payload?.meta ?? null
    const sellReasons = payload?.sell_reasons
    const reason = payload?.reason
    const reasonText =
      Array.isArray(sellReasons) && sellReasons.length ? sellReasons.join('; ')
        : typeof reason === 'string' && reason.trim() ? reason.trim()
          : '—'
    const accuracy = meta?.accuracy != null ? Number(meta.accuracy) : null
    const riseProb = meta?.rise_probability != null ? Number(meta.rise_probability) : null
    return {
      ...it,
      _reason: reasonText,
      _accuracy: accuracy != null && !Number.isNaN(accuracy) ? accuracy : null,
      _riseProb: riseProb != null && !Number.isNaN(riseProb) ? riseProb : null,
    }
  })
}

const hAccessors: Record<string, (r: HistoryRow) => string | number> = {
  kst_at: (r) => r.kst_at ?? '',
  side: (r) => r.side ?? '',
  ticker: (r) => r.ticker ?? '',
  stock_name: (r) => r.stock_name ?? '',
  quantity: (r) => r.quantity ?? 0,
  limit_price: (r) => r.limit_price ?? 0,
  _accuracy: (r) => r._accuracy ?? 0,
  _riseProb: (r) => r._riseProb ?? 0,
  _reason: (r) => r._reason ?? '',
  success: (r) => (r.success ? 1 : 0),
}

export default function Orders() {
  const history = useApi(fetchOrderHistory)

  const hRows = buildHistoryRows(history.data?.items ?? [])

  const { sortedRows: sortedHist, sortKey: hk, sortDir: hd, requestSort: hr } = useTableSort(
    hRows,
    hAccessors,
    { key: 'kst_at', dir: 'desc' },
  )

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%' }}>
      <PageHeader title="주문 내역" subtitle="매수·매도 히스토리" />

      <div style={{ display: 'flex', gap: 8, marginBottom: theme.gutter, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: theme.onSurfaceVariant }}>
          {history.loading ? '로딩 중…' : `${hRows.length}건`}
        </span>
      </div>

      <Card title="매수·매도 히스토리">
        <div style={tableScrollBox}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 1100 }}>
            <thead>
              <tr>
                {[
                  { id: 'kst_at', label: '일시(KST)', tip: '주문 실행 시각(한국시간)' },
                  { id: 'side', label: '구분', tip: '매수/매도' },
                  { id: 'ticker', label: '티커' },
                  { id: 'stock_name', label: '종목명' },
                  { id: 'quantity', label: '수량', right: true },
                  { id: 'limit_price', label: '주문가', right: true },
                  { id: '_accuracy', label: '정확도', right: true, tip: '모델 백테스트 예측 정확도 (%)' },
                  { id: '_riseProb', label: '상승확률', right: true, tip: 'AI 모델 예측 상승 확률 (%)' },
                  { id: '_reason', label: '사유', tip: '매수/매도 근거 요약' },
                  { id: 'success', label: '성공', tip: '주문 접수 성공 여부' },
                ].map(({ id, label, right, tip }) => (
                  <SortableTh
                    key={id}
                    colId={id}
                    label={label}
                    align={right ? 'right' : 'left'}
                    sortKey={hk}
                    sortDir={hd}
                    onSort={hr}
                    style={{ ...thColHead, textAlign: right ? 'right' : 'left' }}
                    tip={tip}
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {history.loading && (
                <tr><td colSpan={10} style={{ ...tdBase, textAlign: 'center', color: theme.onSurfaceVariant }}>주문 히스토리 조회 중…</td></tr>
              )}
              {history.error && (
                <tr><td colSpan={10} style={{ ...tdBase, color: theme.negative }}>조회 실패: {history.error}</td></tr>
              )}
              {!history.loading && !history.error && hRows.length === 0 && (
                <tr><td colSpan={10} style={{ ...tdBase, textAlign: 'center', color: theme.onSurfaceVariant }}>주문 내역 없음</td></tr>
              )}
              {sortedHist.map((o) => {
                const isBuy = String(o.side).toLowerCase().includes('buy') || String(o.side).includes('매수')
                return (
                  <tr key={o.id}>
                    <td style={{ ...tdBase, fontFamily: monoFont, fontSize: 11 }}>{formatKst(o.kst_at)}</td>
                    <td style={{ ...tdBase, fontWeight: 900, color: isBuy ? theme.positive : theme.negative }}>{o.side ?? '—'}</td>
                    <td style={{ ...tdBase, fontWeight: 800 }}>{o.ticker ?? '—'}</td>
                    <td style={{ ...tdBase, fontSize: 12 }}>{o.stock_name ?? '—'}</td>
                    <td style={{ ...tdBase, textAlign: 'right' }}>{o.quantity ?? '—'}</td>
                    <td style={{ ...tdBase, textAlign: 'right' }}>{o.limit_price != null ? `$${Number(o.limit_price).toFixed(2)}` : '—'}</td>
                    <td style={{ ...tdBase, textAlign: 'right' }}>{o._accuracy != null ? `${o._accuracy.toFixed(1)}%` : '—'}</td>
                    <td style={{ ...tdBase, textAlign: 'right' }}>{o._riseProb != null ? `${o._riseProb.toFixed(1)}%` : '—'}</td>
                    <td style={{ ...tdBase, fontSize: 12, color: theme.onSurfaceVariant, maxWidth: 360, whiteSpace: 'normal' }}>{o._reason}</td>
                    <td style={{ ...tdBase, fontSize: 12 }}>{o.success == null ? '—' : (o.success ? 'Y' : 'N')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
