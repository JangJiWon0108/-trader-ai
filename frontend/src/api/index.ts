const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// ── Balance ────────────────────────────────────────────────────────
export interface KisHolding {
  ovrs_pdno: string
  ovrs_item_name: string
  ovrs_cblc_qty: string
  pchs_avg_pric: string
  now_pric2: string
  frcr_evlu_pfls_amt: string
  evlu_pfls_rt: string
  frcr_buy_amt_smtl1: string
}

export interface KisOverseasBalance {
  rt_cd: string
  msg1?: string
  output1: KisHolding[]
  output2?: {
    frcr_pchs_amt1?: string
    ovrs_tot_pfls?: string
    tot_evlu_pfls_amt?: string
    tot_pftrt?: string
    evlu_amt_smtl?: string
    frcr_evlu_amt?: string
    frcr_ord_psbl_amt1?: string
    ovrs_ord_psbl_amt?: string
    ord_psbl_frcr_amt?: string
  }
  /** fetchAllBalances: 거래소별 output2 중 주문가능外화 추정 최댓값 */
  cashUsdBestEffort?: number
}

export const fetchOverseasBalance = (exchange = 'NASD') =>
  get<KisOverseasBalance>(`/balance/overseas?ovrs_excg_cd=${exchange}`)

// All exchanges combined
export async function fetchAllBalances(): Promise<KisOverseasBalance> {
  const exchanges = ['NASD', 'NYSE', 'AMEX']
  const results = await Promise.allSettled(exchanges.map(fetchOverseasBalance))
  const allHoldings: KisHolding[] = []
  let summary: KisOverseasBalance['output2'] = {}
  let cashUsdBestEffort = 0
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value.rt_cd === '0') {
      allHoldings.push(...(r.value.output1 ?? []))
      if (r.value.output2) summary = r.value.output2
      const o2 = r.value.output2 as Record<string, string | undefined> | undefined
      if (o2) {
        for (const k of ['frcr_ord_psbl_amt1', 'ovrs_ord_psbl_amt', 'ord_psbl_frcr_amt'] as const) {
          const v = parseFloat(o2[k] || '')
          if (!isNaN(v) && v > cashUsdBestEffort) cashUsdBestEffort = v
        }
      }
    }
  }
  // 거래소별 조회 결과를 합칠 때 동일 티커가 중복되는 경우가 있음 (예: NASD·NYSE 모두 PEP)
  const byTicker = new Map<string, KisHolding>()
  for (const h of allHoldings) {
    const sym = (h.ovrs_pdno || '').trim()
    if (!sym) continue
    if (!byTicker.has(sym)) byTicker.set(sym, h)
  }
  const deduped = [...byTicker.values()]
  return { rt_cd: '0', output1: deduped, output2: summary, cashUsdBestEffort }
}

// ── Stocks / AI predictions ────────────────────────────────────────
export interface StockPrediction {
  stock: string
  last_price: number | null
  predicted_price: number | null
  rise_probability: number | null
  recommendation: string | null
  analysis: string | null
}

export const fetchPredictions = () =>
  get<StockPrediction[]>('/stocks/predictions')

// ── Recommendations ────────────────────────────────────────────────
export interface CombinedRecommendation {
  ticker: string
  stock_name: string
  accuracy?: number
  rise_probability: number
  // actual field names from API
  last_price: number
  predicted_price: number
  recommendation: string
  analysis?: string
  sentiment_score?: number
  average_sentiment_score?: number  // alias support
  article_count?: number
  sentiment_date?: string
  calculation_date?: string
  // technical fields
  golden_cross?: boolean
  macd_buy_signal?: boolean
  rsi?: number
  sma20?: number
  sma50?: number
  composite_score?: number
}

export interface RecommendationsResponse {
  results: CombinedRecommendation[]
  message?: string
}

export const fetchCombinedRecommendations = () =>
  get<RecommendationsResponse>('/stocks/recommendations/recommended-stocks/with-technical-and-sentiment')

export const fetchRecommendedStocks = () =>
  get<RecommendationsResponse>('/stocks/recommendations/recommended-stocks')

export const fetchSellCandidates = () =>
  get<{ results: unknown[] }>('/stocks/recommendations/sell-candidates')

// ── Scheduler ─────────────────────────────────────────────────────
export interface SchedulerStatus {
  buy_running: boolean
  sell_running: boolean
  message: string
  schedule_buy_time_kst?: string
  schedule_sell_interval_min?: number
  /** 다음 자동 매수 예정 (KST, ISO8601) */
  next_auto_buy_at?: string
  /** 장중 매도 점검 다음 분(UTC ISO). 장외·매도 중지 시 null */
  next_sell_check_at?: string | null
}

export interface OrderFillRow {
  odno?: string
  ord_dt?: string
  ord_tmd?: string
  pdno?: string
  prdt_name?: string
  sll_buy_dvsn_cd?: string
  sll_buy_dvsn_cd_name?: string
  ft_ccld_qty?: string
  ft_ccld_unpr3?: string
  ft_ccld_amt3?: string
  ovrs_excg_cd?: string
  prcs_stat_name?: string
  [key: string]: string | undefined
}

export interface OrderFillsResponse {
  rt_cd: string
  output: OrderFillRow[]
  count: number
}

export const fetchOrderFills = (days = 30) =>
  get<OrderFillsResponse>(`/balance/order-fills?days=${days}`)

export const fetchSchedulerStatus = () =>
  get<SchedulerStatus>('/stocks/recommendations/scheduler/status')

export const startBuyScheduler = () =>
  post<{ message: string }>('/stocks/recommendations/purchase/scheduler/start')

export const stopBuyScheduler = () =>
  post<{ message: string }>('/stocks/recommendations/purchase/scheduler/stop')

export const startSellScheduler = () =>
  post<{ message: string }>('/stocks/recommendations/sell/scheduler/start')

export const stopSellScheduler = () =>
  post<{ message: string }>('/stocks/recommendations/sell/scheduler/stop')

export const triggerBuy = () =>
  post<{ message: string }>('/stocks/recommendations/purchase/trigger')

export const triggerSell = () =>
  post<{ message: string }>('/stocks/recommendations/sell/trigger')

// ── Economic ──────────────────────────────────────────────────────
export interface EconomicLatest {
  date: string | null
  data: Record<string, number | null>
}

export const fetchEconomicLatest = () =>
  get<EconomicLatest>('/economic/latest')

export interface EconomicHistoryRow {
  date: string | null
  data: Record<string, number | null>
}

export interface EconomicHistoryResponse {
  items: EconomicHistoryRow[]
  total: number
  page: number
  page_size: number
}

export function fetchEconomicHistory(opts: {
  dateFrom?: string
  dateTo?: string
  page?: number
  pageSize?: number
}) {
  const q = new URLSearchParams()
  if (opts.dateFrom) q.set('date_from', opts.dateFrom)
  if (opts.dateTo) q.set('date_to', opts.dateTo)
  q.set('page', String(opts.page ?? 1))
  q.set('page_size', String(opts.pageSize ?? 10))
  const qs = q.toString()
  return get<EconomicHistoryResponse>(`/economic/history?${qs}`)
}

// ── Orders (NCCS) ─────────────────────────────────────────────────
export interface NccsItem {
  odno?: string
  ord_dt?: string
  ovrs_pdno?: string
  ovrs_item_name?: string
  sll_buy_dvsn_cd_name?: string
  ft_ord_qty?: string
  ft_ccld_qty?: string
  ft_ord_unpr3?: string
  ft_ccld_unpr3?: string
  ovrs_excg_cd?: string
  ord_stat_name?: string
  [key: string]: string | number | undefined
}

export interface NccsResponse {
  rt_cd: string
  msg1?: string
  output?: NccsItem[]
}

export const fetchOrders = (exchange = 'NASD') =>
  get<NccsResponse>(`/balance/nccs?ovrs_excg_cd=${exchange}`)

export async function fetchAllOrders(): Promise<NccsItem[]> {
  const exchanges = ['NASD', 'NYSE', 'AMEX']
  const results = await Promise.allSettled(exchanges.map(fetchOrders))
  const all: NccsItem[] = []
  for (const r of results) {
    if (r.status === 'fulfilled' && (r.value.rt_cd === '0' || r.value.rt_cd === '1')) {
      all.push(...(r.value.output ?? []))
    }
  }
  return all
}
