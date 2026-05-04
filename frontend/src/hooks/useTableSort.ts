import { useCallback, useMemo, useReducer } from 'react'

export type SortDirection = 'asc' | 'desc'

type SortState = { key: string | null; dir: SortDirection }

type Action = { type: 'toggle'; column: string; validKeys: Set<string> }

function sortReducer(state: SortState, action: Action): SortState {
  if (action.type === 'toggle') {
    if (!action.validKeys.has(action.column)) return state
    if (state.key !== action.column) return { key: action.column, dir: 'asc' }
    return { key: action.column, dir: state.dir === 'asc' ? 'desc' : 'asc' }
  }
  return state
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === 'number' && typeof b === 'number') {
    return a === b ? 0 : a < b ? -1 : 1
  }
  return String(a).localeCompare(String(b), 'ko', { numeric: true, sensitivity: 'base' })
}

/**
 * 테이블 컬럼 정렬. `accessors` 객체 레퍼런스는 렌더마다 바뀌지 않게 두는 것이 좋습니다(모듈 상수 또는 useMemo).
 */
export function useTableSort<T>(
  rows: T[],
  accessors: Record<string, (row: T) => string | number>,
  initial?: { key: string; dir?: SortDirection },
) {
  const validKeys = useMemo(() => new Set(Object.keys(accessors)), [accessors])

  const [state, dispatch] = useReducer(sortReducer, {
    key: initial?.key ?? null,
    dir: initial?.dir ?? 'asc',
  } satisfies SortState)

  const requestSort = useCallback(
    (column: string) => {
      dispatch({ type: 'toggle', column, validKeys })
    },
    [validKeys],
  )

  const sortedRows = useMemo(() => {
    const { key, dir } = state
    if (!key || !accessors[key]) return rows
    const get = accessors[key]
    const mul = dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => mul * compareValues(get(a), get(b)))
  }, [rows, state, accessors])

  return {
    sortedRows,
    sortKey: state.key,
    sortDir: state.dir,
    requestSort,
  }
}
