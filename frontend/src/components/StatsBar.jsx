export default function StatsBar({ stats }) {
  return (
    <div style={styles.bar}>
      <div style={styles.item}>
        <span style={styles.label}>UP主</span>
        <span style={styles.value}>
          {stats.active_uppers}/{stats.total_uppers}
        </span>
      </div>
      <div style={styles.item}>
        <span style={styles.label}>视频</span>
        <span style={styles.value}>{stats.total_videos}</span>
      </div>
      <div style={styles.item}>
        <span style={styles.label}>动态</span>
        <span style={styles.value}>{stats.total_dynamics}</span>
      </div>
      <div style={styles.item}>
        <span style={styles.label}>AI总结</span>
        <span style={styles.value}>{stats.total_summaries}</span>
      </div>
    </div>
  )
}

const styles = {
  bar: {
    display: 'flex',
    gap: '24px',
    background: '#fff',
    borderRadius: '8px',
    padding: '12px 20px',
    marginBottom: '16px',
    flexWrap: 'wrap',
  },
  item: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    minWidth: '60px',
  },
  label: {
    fontSize: '12px',
    color: '#999',
  },
  value: {
    fontSize: '20px',
    fontWeight: 700,
    color: '#00a1d6',
  },
}
