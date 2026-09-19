import { useState } from 'react'

export default function SummaryPanel({ summaries }) {
  const [expanded, setExpanded] = useState(true)
  const [selectedIdx, setSelectedIdx] = useState(0)

  if (!summaries || summaries.length === 0) {
    return (
      <div style={styles.empty}>
        暂无AI总结。点击上方"生成AI总结"按钮手动触发，或等待定时任务（每天9:00和17:00自动生成）。
      </div>
    )
  }

  const summary = summaries[selectedIdx] || summaries[0]

  return (
    <div style={styles.panel}>
      <div
        style={styles.header}
        onClick={() => setExpanded(!expanded)}
      >
        <span style={styles.icon}>{expanded ? '▼' : '▶'}</span>
        <h2 style={styles.title}>
          AI 每日总结 - {summary.summary_date} ({summary.summary_period})
        </h2>
        <span style={styles.date}>{summary.created_at}</span>
      </div>

      {expanded && (
        <>
          {summaries.length > 1 && (
            <div style={styles.dateTabs}>
              {summaries.map((s, i) => (
                <button
                  key={s.id}
                  style={{
                    ...styles.dateTab,
                    ...(i === selectedIdx ? styles.dateTabActive : {}),
                  }}
                  onClick={() => setSelectedIdx(i)}
                >
                  {s.summary_date} {s.summary_period}
                </button>
              ))}
            </div>
          )}
          <div style={styles.content}>
            {summary.content.split('\n').map((line, i) => (
              <div key={i} style={styles.line}>
                {line || '\u00A0'}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const styles = {
  panel: {
    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
    borderRadius: '10px',
    marginBottom: '16px',
    overflow: 'hidden',
    color: '#fff',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '14px 20px',
    cursor: 'pointer',
    background: 'rgba(255,255,255,0.05)',
  },
  icon: {
    fontSize: '14px',
    width: '20px',
  },
  title: {
    fontSize: '16px',
    fontWeight: 600,
    margin: 0,
    flex: 1,
  },
  date: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.5)',
  },
  dateTabs: {
    display: 'flex',
    gap: '4px',
    padding: '8px 20px',
    flexWrap: 'wrap',
  },
  dateTab: {
    padding: '4px 12px',
    border: '1px solid rgba(255,255,255,0.2)',
    background: 'transparent',
    color: 'rgba(255,255,255,0.6)',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '12px',
  },
  dateTabActive: {
    background: 'rgba(0,161,214,0.3)',
    borderColor: '#00a1d6',
    color: '#fff',
  },
  content: {
    padding: '16px 20px',
    fontSize: '14px',
    lineHeight: '1.8',
    maxHeight: '500px',
    overflowY: 'auto',
  },
  line: {
    minHeight: '1.2em',
    whiteSpace: 'pre-wrap',
  },
  empty: {
    background: '#fff',
    borderRadius: '8px',
    padding: '16px 20px',
    marginBottom: '16px',
    color: '#999',
    fontSize: '14px',
    textAlign: 'center',
  },
}
