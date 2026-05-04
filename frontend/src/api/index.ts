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
  }
}

export const fetchOverseasBalance = (exchange = 'NASD') =>
  get<KisOverseasBalance>(`/balance/overseas?ovrs_excg_cd=${exchange}`)

// All exchanges combined
export async function fetchAllBalances(): Promise<KisOverseasBalance> {
  const exchanges = ['NASD', 'NYSE', 'AMEX']
  const results = await Promise.allSettled(exchanges.map(fetchOverseasBalance))
  const allHoldings: KisHolding[] = []
  let summary: KisOverseasBalance['output2'] = {}
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value.rt_cd === '0') {
      allHoldings.push(...(r.value.output1 ?? []))
      if (r.value.output2) summary = r.value.output2
    }
  }
  return { rt_cd: '0', output1: allHoldings, output2: summary }
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
}

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
