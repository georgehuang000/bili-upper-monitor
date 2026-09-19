export default function DynamicsList({ dynamics }) {
  if (!dynamics || dynamics.length === 0) {
    return (
      <div style={styles.empty}>
        暂无动态数据。点击上方"手动爬取"按钮获取最新动态。
      </div>
    )
  }

  return (
    <div style={styles.timeline}>
      {dynamics.map((d) => {
        let pictures = []
        try {
          pictures = JSON.parse(d.pictures || '[]')
        } catch {
          pictures = []
        }

        return (
          <div key={d.id} style={styles.item}>
            <div style={styles.dot} />
            <div style={styles.card}>
              <div style={styles.cardHeader}>
                <a
                  href={d.upper_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.upperLink}
                >
                  {d.upper_name}
                </a>
                <span style={styles.type}>{d.dynamic_type || '动态'}</span>
                <span style={styles.date}>{d.pub_date}</span>
              </div>
              <div style={styles.content}>
                {d.content || '(无文字内容)'}
              </div>
              {pictures.length > 0 && (
                <div style={styles.pics}>
                  {pictures.slice(0, 4).map((pic, i) => (
                    <img
                      key={i}
                      src={pic}
                      alt=""
                      style={styles.pic}
                      loading="lazy"
                    />
                  ))}
                  {pictures.length > 4 && (
                    <div style={styles.picMore}>
                      +{pictures.length - 4}
                    </div>
                  )}
                </div>
              )}
              <a
                href={d.bilibili_url}
                target="_blank"
                rel="noopener noreferrer"
                style={styles.viewBtn}
              >
                查看原文
              </a>
            </div>
          </div>
        )
      })}
    </div>
  )
}

const styles = {
  timeline: {
    position: 'relative',
    paddingLeft: '24px',
  },
  item: {
    position: 'relative',
    marginBottom: '16px',
  },
  dot: {
    position: 'absolute',
    left: '-24px',
    top: '20px',
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    background: '#00a1d6',
    border: '2px solid #fff',
    zIndex: 1,
  },
  card: {
    background: '#fff',
    borderRadius: '8px',
    padding: '16px',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px',
  },
  upperLink: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#00a1d6',
    textDecoration: 'none',
  },
  type: {
    fontSize: '11px',
    padding: '2px 6px',
    background: '#f0f0f0',
    borderRadius: '4px',
    color: '#999',
  },
  date: {
    fontSize: '12px',
    color: '#bbb',
    marginLeft: 'auto',
  },
  content: {
    fontSize: '14px',
    lineHeight: '1.6',
    color: '#333',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    maxHeight: '200px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: '-webkit-box',
    WebkitLineClamp: 6,
    WebkitBoxOrient: 'vertical',
  },
  pics: {
    display: 'flex',
    gap: '6px',
    marginTop: '10px',
    flexWrap: 'wrap',
  },
  pic: {
    width: '80px',
    height: '80px',
    objectFit: 'cover',
    borderRadius: '4px',
  },
  picMore: {
    width: '80px',
    height: '80px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#f0f0f0',
    borderRadius: '4px',
    fontSize: '14px',
    color: '#999',
  },
  viewBtn: {
    display: 'inline-block',
    marginTop: '10px',
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
