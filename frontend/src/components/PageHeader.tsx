import { theme } from '../theme'

export default function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header style={{ marginBottom: theme.gutter }}>
      <div
        className="trader-preview-pill"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '5px 12px',
          borderRadius: 999,
          fontFamily: theme.fontSans,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: theme.primaryBright,
          background: 'rgba(79, 70, 229, 0.1)',
          border: `1px solid rgba(79, 70, 229, 0.2)`,
          marginBottom: 12,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: theme.positive,
            boxShadow: `0 0 8px ${theme.positive}`,
          }}
        />
        모의 프리뷰
      </div>
      <h1
        style={{
          margin: 0,
          fontSize: 32,
          fontWeight: 800,
          letterSpacing: '-0.035em',
          lineHeight: 1.15,
          fontFamily: theme.fontDisplay,
          background: `linear-gradient(105deg, ${theme.onSurface} 0%, ${theme.primaryBright} 55%, ${theme.accentCyan} 100%)`,
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          style={{
            margin: '10px 0 0',
            fontSize: 15,
            lineHeight: 1.55,
            color: theme.onSurfaceVariant,
            fontFamily: theme.fontSans,
            maxWidth: 520,
          }}
        >
          {subtitle}
        </p>
      )}
    </header>
  )
}
