import type { CSSProperties } from 'react'
import { useState } from 'react'
import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import SortableTh from '../../components/SortableTh'
import { useTableSort } from '../../hooks/useTableSort'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import { fetchAllOrders, type NccsItem } from '../../api'


const th: CSSProperties = {
  padding: '12px 10px',
  fontSize: 11,
  fontWeight: 600,
  color: theme.onSurfaceVariant,
  textAlign: 'left',
  borderBottom: `1px solid ${theme.outline}`,
  whiteSpace: 'nowrap',
}
const td: CSSProperties = {
  padding: '12px 10px',
  fontSize: 13,
  borderBottom: `1px solid ${theme.surfaceContainer}`,
  color: theme.onSurface,
  fontVariantNumeric: 'tabular-nums',
}

type Row = NccsItem & { _side: string; _price: number; _qty: number; _filled: number }

function buildRows(items: NccsItem[]): Row[] {
  return items.map((item) => ({
    ...item,
    _side: item.sll_buy_dvsn_cd_name ?? '',
    _price: parseFloat(item.ft_ord_unpr3 ?? '0') || 0,
    _qty: parseFloat(item.ft_ord_qty ?? '0') || 0,
    _filled: parseFloat(item.ft_ccld_qty ?? '0') || 0,
  }))
}

const accessors: Record<string, (r: Row) => string | number> = {
  odno: (r) => r.odno ?? '',
  ord_dt: (r) => r.ord_dt ?? '',
  ovrs_pdno: (r) => r.ovrs_pdno ?? '',
  ovrs_item_name: (r) => r.ovrs_item_name ?? '',
  _side: (r) => r._side,
  _qty: (r) => r._qty,
  _price: (r) => r._price,
  _filled: (r) => r._filled,
  ord_stat_name: (r) => r.ord_stat_name ?? '',
}

export default function Orders() {
  const [exchange, setExchange] = useState('NASD')
  const { data, loading, error } = useApi(fetchAllOrders, [exchange])

  const rows = buildRows(data ?? [])
  const { sortedRows, sortKey, sortDir, requestSort } = useTableSort(rows, accessors)

  const excBtnStyle = (ex: string): CSSProperties => ({
    padding: '6px 14px',
    borderRadius: theme.radiusMd,
    fontSize: 12,
    fontWeight: 700,
    cursor: 'pointer',
    border: 'none',
    background: exchange === ex ? theme.primary : theme.surfaceContainer,
    color: exchange === ex ? '#fff' : theme.onSurfaceVariant,
  })

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%' }}>
      <PageHeader title="주문 내역" subtitle="체결·미체결 내역 · 최근 7일" />

      <div style={{ display: 'flex', gap: 8, marginBottom: theme.gutter, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 13, color: theme.onSurfaceVariant }}>거래소:</span>
        {['NASD', 'NYSE', 'AMEX'].map((ex) => (
          <button key={ex} style={excBtnStyle(ex)} onClick={() => setExchange(ex)}>{ex}</button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: theme.onSurfaceVariant }}>
          {loading ? '로딩 중…' : `${rows.length}건`}
        </span>
      </div>

      <Card title="주문 히스토리">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr>
                {[
                  { id: 'odno', label: '주문번호', tip: '한국투자증권 발급 주문 고유번호' },
                  { id: 'ord_dt', label: '일자', tip: '주문 접수 날짜 (YYYYMMDD)' },
                  { id: 'ovrs_pdno', label: '티커' },
                  { id: 'ovrs_item_name', label: '종목명' },
                  { id: '_side', label: '구분', tip: '매수(BUY) 또는 매도(SELL)' },
                  { id: '_qty', label: '주문수량', right: true, tip: '주문한 총 주식 수 (주)' },
                  { id: '_price', label: '주문가', right: true, tip: '지정한 주문 단가 (USD)' },
                  { id: '_filled', label: '체결수량', right: true, tip: '실제로 체결(거래 완료)된 주식 수' },
                  { id: 'ord_stat_name', label: '상태', tip: '주문 처리 상태 (체결·미체결·취소 등)' },
                ].map(({ id, label, right, tip }) => (
                  <SortableTh key={id} colId={id} label={label} align={right ? 'right' : 'left'}
                    sortKey={sortKey} sortDir={sortDir} onSort={requestSort}
                    style={{ ...th, textAlign: right ? 'right' : 'left' }} tip={tip} />
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} style={{ ...td, textAlign: 'center', color: theme.onSurfaceVariant }}>주문 내역 조회 중…</td></tr>
              )}
              {error && (
                <tr><td colSpan={9} style={{ ...td, color: theme.negative }}>
                  조회 실패: {error}
                  {error.includes('지원') || error.includes('400') ? ' (모의투자 환경에서는 미체결 API가 제한될 수 있습니다)' : ''}
                </td></tr>
              )}
              {!loading && !error && rows.length === 0 && (
                <tr><td colSpan={9} style={{ ...td, textAlign: 'center', color: theme.onSurfaceVariant }}>주문 내역 없음</td></tr>
              )}
              {sortedRows.map((o, i) => {
                const isBuy = o._side.includes('매수') || o._side.toUpperCase().includes('BUY')
                return (
                  <tr key={o.odno ?? i}>
                    <td style={{ ...td, fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>{o.odno ?? '—'}</td>
                    <td style={{ ...td, color: theme.onSurfaceVariant, whiteSpace: 'nowrap' }}>{o.ord_dt ?? '—'}</td>
                    <td style={{ ...td, fontWeight: 600 }}>{o.ovrs_pdno ?? '—'}</td>
                    <td style={{ ...td, fontSize: 12 }}>{o.ovrs_item_name ?? '—'}</td>
                    <td style={{ ...td, fontWeight: 700, color: isBuy ? theme.positive : theme.negative }}>
                      {o._side || '—'}
                    </td>
                    <td style={{ ...td, textAlign: 'right' }}>{o._qty || '—'}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{o._price ? `$${o._price.toFixed(2)}` : '—'}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{o._filled || '0'}</td>
                    <td style={{ ...td, fontSize: 12 }}>{o.ord_stat_name ?? '—'}</td>
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
