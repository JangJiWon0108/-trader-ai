export const botStatus = {
  running: true,
  mode: '페이퍼 트레이딩',
  startedAt: '2026-05-01 09:30 ET',
  lastHeartbeat: '방금',
  todayTrades: 3,
  todayPnl: 124.5,
}

export const rules = [
  { id: 'r1', name: '모멘텀 브레이크아웃', enabled: true, maxNotional: 2500 },
  { id: 'r2', name: 'AI 추천 종목만', enabled: true, maxNotional: 5000 },
  { id: 'r3', name: '손절 -3% / 익절 +6%', enabled: true, maxNotional: 0 },
]

export const recentBotOrders = [
  { time: '10:22', symbol: 'AMD', side: 'BUY' as const, qty: 4, status: '체결' },
  { time: '10:05', symbol: 'VOO', side: 'BUY' as const, qty: 2, status: '체결' },
  { time: '09:58', symbol: 'META', side: 'SELL' as const, qty: 1, status: '부분체결' },
]
