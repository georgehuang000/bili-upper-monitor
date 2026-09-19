function formatNumber(n) {
  if (!n || n === 0) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toString()
}

export default function VideoList({ videos }) {
  if (!videos || videos.length === 0) {
    return (
      <div style={styles.empty}>
        暂无视频数据。点击上方"手动爬取"按钮获取最新视频。
      </div>
    )
  }

  return (
    <div style={styles.grid}>
      {videos.map((v) => (
        <div key={v.id} style={styles.card}>
          <a href={v.bilibili_url} target="_blank" rel="noopener noreferrer">
            <div style={styles.coverWrap}>
              {v.cover_url ? (
                <img src={v.cover_url} alt={v.title} style={styles.cover} />
              ) : (
                <div style={styles.coverPlaceholder}>无封面</div>
              )}
              <div style={styles.playBadge}>
                {formatNumber(v.play_count)}
              </div>
            </div>
          </a>
          <div style={styles.info}>
            <a
              href={v.bilibili_url}
              target="_blank"
              rel="noopener noreferrer"
              style={styles.title}
              title={v.title}
            >
              {v.title}
            </a>
            <div style={styles.meta}>
              <span style={styles.upper}>
                <a
                  href={v.upper_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.upperLink}
                >
                  {v.upper_name}
                </a>
              </span>
              <span style={styles.date}>{v.pub_date}</span>
            </div>
            <div style={styles.stats}>
              <span>播放 {formatNumber(v.play_count)}</span>
              <span>弹幕 {formatNumber(v.danmaku_count)}</span>
            </div>
            <a
              href={v.bilibili_url}
              target="_blank"
              rel="noopener noreferrer"
              style={styles.viewBtn}
            >
              查看原文
            </a>
          </div>
        </div>
      ))}
    </div>
  )
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '16px',
  },
  card: {
    background: '#fff',
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
    transition: 'box-shadow 0.2s',
  },
  coverWrap: {
    position: 'relative',
    width: '100%',
    paddingTop: '56.25%',
    overflow: 'hidden',
    cursor: 'pointer',
  },
  cover: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  coverPlaceholder: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#eee',
    color: '#999',
    fontSize: '14px',
  },
  playBadge: {
    position: 'absolute',
    bottom: '8px',
    right: '8px',
    background: 'rgba(0,0,0,0.7)',
    color: '#fff',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '12px',
  },
  info: {
    padding: '12px',
  },
  title: {
    display: 'block',
    fontSize: '14px',
    fontWeight: 600,
    color: '#333',
    textDecoration: 'none',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    cursor: 'pointer',
    marginBottom: '8px',
  },
  meta: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '6px',
    fontSize: '12px',
    color: '#999',
  },
  upper: {
    flex: 1,
  },
  upperLink: {
    color: '#00a1d6',
    textDecoration: 'none',
  },
  date: {
    color: '#bbb',
  },
  stats: {
    display: 'flex',
    gap: '16px',
    fontSize: '12px',
    color: '#999',
    marginBottom: '10px',
  },
  viewBtn: {
    display: 'inline-block',
    padding: '4px 12px',
    background: '#00a1d6',
    color: '#fff',
    borderRadius: '4px',
    textDecoration: 'none',
    fontSize: '13px',
    cursor: 'pointer',
  },
  empty: {
    background: '#fff',
    borderRadius: '8px',
    padding: '40px 20px',
    textAlign: 'center',
    color: '#999',
    fontSize: '14px',
  },
}
