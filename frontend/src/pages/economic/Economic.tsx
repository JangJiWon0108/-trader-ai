import { useState } from 'react'
import Card from '../../components/Card'
import PageHeader from '../../components/PageHeader'
import Tooltip from '../../components/Tooltip'
import { theme } from '../../theme'
import { useApi } from '../../hooks/useApi'
import { fetchEconomicLatest } from '../../api'

const PAGE_SIZE = 15

const ECON: [string, string, string][] = [
  ['10년 기대 인플레이션율','10년 기대 인플레이션율','향후 10년 시장 평균 인플레이션 기대치 (FRED)'],
  ['장단기 금리차','장단기 금리차 (10Y-2Y)','10년 - 2년 국채 수익률 차이 · 음수 → 경기침체 신호'],
  ['기준금리','연준 기준금리','미국 연방준비위원회 기준금리 (FFR)'],
  ['미시간대 소비자 심리지수','미시간 소비자심리','소비자 경기 체감 · 100 기준, 높을수록 낙관'],
  ['실업률','실업률','미국 비농업 실업률 (%) · 낮을수록 고용 호황'],
  ['2년 만기 미국 국채 수익률','미국 2년 국채','단기 금리 기대 반영 수익률'],
  ['10년 만기 미국 국채 수익률','미국 10년 국채','장기 성장·인플레 기대 반영 · 글로벌 기준금리'],
  ['금융스트레스지수','금융 스트레스 지수','FRED FSI · 0↑ 스트레스 상승 / 음수 안정'],
  ['개인 소비 지출','PCE (개인소비지출)','연준 선호 인플레 척도 · 목표 2%'],
  ['소비자 물가지수','CPI','전월/전년 대비 소비자 물가 상승률'],
  ['5년 변동금리 모기지','5년 변동금리 모기지','주택담보대출 금리 · 부동산 선행 지표'],
  ['미국 달러 환율','USD 환율','달러 대 주요 통화 환율 지수'],
  ['통화 공급량 M2','통화공급 M2','현금+예금 합산 유동성 지표'],
  ['가계 부채 비율','가계부채 비율','가처분소득 대비 부채 비율 · 높을수록 리스크'],
  ['GDP 성장률','GDP 성장률','전분기 대비 실질 GDP 성장률 (%)'],
]

const STOCK: [string, string, string][] = [
  ['나스닥 종합지수','나스닥 종합','나스닥 전 종목 시가총액 가중 지수'],
  ['S&P 500 지수','S&P 500','미국 상위 500대 기업 주가 지수 · 시장 벤치마크'],
  ['금 가격','금 가격 (USD/oz)','온스당 국제 금 현물가 · 안전자산 척도'],
  ['달러 인덱스','달러 인덱스 (DXY)','6개 주요 통화 대비 달러 강세 · 100 기준'],
  ['나스닥 100','나스닥 100','시총 상위 100개 비금융주 지수'],
  ['VIX 지수','VIX 공포지수','시장 변동성 기대 · 20↑ 불안 / 30↑ 극공포'],
  ['닛케이 225','닛케이 225','일본 도쿄증권거래소 225개 종목 지수'],
  ['상해종합','상해종합지수','중국 상하이 전체 종목 지수'],
  ['항셍','항셍지수','홍콩 증권거래소 주요 종목 지수'],
  ['달러/엔','USD/JPY','1달러 = 몇 엔'],
  ['달러/위안','USD/CNY','1달러 = 몇 위안'],
  ['애플','AAPL','애플 주식 종가 (USD)'],
  ['마이크로소프트','MSFT','마이크로소프트 주식 종가 (USD)'],
  ['아마존','AMZN','아마존 주식 종가 (USD)'],
  ['구글 A','GOOGL','알파벳 Class A 종가 (USD)'],
  ['메타','META','메타 플랫폼스 종가 (USD)'],
  ['테슬라','TSLA','테슬라 종가 (USD)'],
  ['엔비디아','NVDA','엔비디아 종가 (USD)'],
  ['AMD','AMD','AMD 종가 (USD)'],
  ['브로드컴','AVGO','브로드컴 종가 (USD)'],
]

function fmtVal(v: number | null, key: string) {
  if (v == null) return '—'
  if (/실업률|금리|수익률|인플레이션|모기지|부채|GDP|PCE|스트레스/.test(key)) return `${v.toFixed(2)}%`
  if (/M2|소비 지출/.test(key)) return v.toLocaleString('en-US', { maximumFractionDigits: 0 })
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const th = { padding: '10px 14px', fontSize: 12, fontWeight: 600, color: theme.onSurfaceVariant, borderBottom: `1px solid ${theme.outline}`, textAlign: 'left' as const, whiteSpace: 'nowrap' as const }
const td = { padding: '11px 14px', fontSize: 14, borderBottom: `1px solid ${theme.surfaceContainer}`, color: theme.onSurface, fontVariantNumeric: 'tabular-nums' as const }

function Grid({ rows, raw }: { rows: [string,string,string][]; raw: Record<string, number|null> }) {
  const [page, setPage] = useState(0)
  const total = Math.ceil(rows.length / PAGE_SIZE)
  const slice = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
  return (
    <>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={th}>지표명</th>
              <th style={{ ...th, textAlign: 'right' }}>최신값</th>
            </tr>
          </thead>
          <tbody>
            {slice.map(([key, label, tip]) => (
              <tr key={key} style={{ transition: 'background .12s' }} className="trader-list-row">
                <td style={td}>
                  <Tooltip tip={tip}>{label}</Tooltip>
                </td>
                <td style={{ ...td, textAlign: 'right', fontWeight: 700 }}>{fmtVal(raw[key] ?? null, key)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > 1 && (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 16 }}>
          {Array.from({ length: total }).map((_, i) => (
            <button key={i} onClick={() => setPage(i)} style={{
              width: 32, height: 32, borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 700,
              background: page === i ? theme.primary : theme.surfaceContainer,
              color: page === i ? '#fff' : theme.onSurfaceVariant,
            }}>{i + 1}</button>
          ))}
        </div>
      )}
    </>
  )
}

export default function Economic() {
  const [tab, setTab] = useState<'econ' | 'stock'>('econ')
  const { data, loading, error } = useApi(fetchEconomicLatest)
  const raw = (data?.data ?? {}) as Record<string, number | null>

  const tabBtn = (t: typeof tab, label: string) => (
    <button onClick={() => setTab(t)} style={{ padding: '8px 18px', borderRadius: theme.radiusMd, fontSize: 13, fontWeight: 700, cursor: 'pointer', border: 'none', background: tab === t ? theme.primary : 'transparent', color: tab === t ? '#fff' : theme.onSurfaceVariant }}>
      {label}
    </button>
  )

  return (
    <div style={{ padding: theme.pagePadding, fontFamily: theme.fontSans, minHeight: '100%' }}>
      <PageHeader title="경제 지표" subtitle={data?.date ? `기준일: ${data.date} · 실제 수집 데이터` : '주요 거시 지표'} />
      {error && <div style={{ marginBottom: 16, color: theme.negative, fontSize: 14 }}>오류: {error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: theme.gutter }}>
        {tabBtn('econ', '경제 지표')}
        {tabBtn('stock', '주요 자산 가격')}
      </div>
      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: theme.onSurfaceVariant }}>로딩 중…</div>
      ) : (
        <Card title={tab === 'econ' ? `경제 지표 (${ECON.length}개)` : `주요 자산 (${STOCK.length}개)`}>
          <Grid rows={tab === 'econ' ? ECON : STOCK} raw={raw} />
        </Card>
      )}
    </div>
  )
}
