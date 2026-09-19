export default function UpperNav({ uppers, selectedId, onSelect }) {
  return (
    <div style={styles.nav}>
      <button
        style={{
          ...styles.chip,
          ...(selectedId === 0 ? styles.chipActive : {}),
        }}
        onClick={() => onSelect(0)}
      >
        全部
      </button>
      {uppers.map((u) => (
        <button
          key={u.id}
          style={{
            ...styles.chip,
            ...(selectedId === u.id ? styles.chipActive : {}),
            ...(u.uid === 0 ? styles.chipInactive : {}),
          }}
          onClick={() => onSelect(u.id)}
          title={u.uid === 0 ? 'UID未解析' : `UID: ${u.uid}`}
        >
          {u.avatar && (
            <img src={u.avatar} alt="" style={styles.avatar} />
          )}
          {u.name}
          {u.uid === 0 && <span style={styles.badge}>?</span>}
        </button>
      ))}
    </div>
  )
}

const styles = {
  nav: {
    display: 'flex',
    gap: '8px',
    marginBottom: '16px',
    flexWrap: 'wrap',
    background: '#fff',
    borderRadius: '8px',
    padding: '12px',
  },
  chip: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 16px',
    border: '1px solid #e0e0e0',
    borderRadius: '20px',
    background: '#f9f9f9',
    cursor: 'pointer',
    fontSize: '14px',
    transition: 'all 0.2s',
    color: '#333',
  },
  chipActive: {
    background: '#00a1d6',
    color: '#fff',
    borderColor: '#00a1d6',
    fontWeight: 600,
  },
  chipInactive: {
    opacity: 0.5,
  },
  avatar: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    objectFit: 'cover',
  },
  badge: {
    display: 'inline-block',
    marginLeft: '4px',
    padding: '0 6px',
    background: '#ff9800',
    color: '#fff',
    borderRadius: '10px',
    fontSize: '10px',
    fontWeight: 600,
  },
}
