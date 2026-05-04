import type { ReactNode } from 'react'

export default function Tooltip({ tip, children, below }: { tip: string; children: ReactNode; below?: boolean }) {
  return (
    <span className={`tt${below ? ' tt-below' : ''}`}>
      {children}
      <span className="tt-b">{tip}</span>
    </span>
  )
}
