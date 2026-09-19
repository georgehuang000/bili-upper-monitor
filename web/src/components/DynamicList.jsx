import { useState } from 'react'
import { fmtTime } from '../utils'
import Placeholder from './Placeholder'

const TYPE_LABEL = { video: '投稿', text: '动态', forward: '转发' }
const COLLAPSE_LEN = 120 // 超过该字数默认折叠

function DynCard({ dyn, index }) {
  const [expanded, setExpanded] = useState(false)
  const long = (dyn.text || '').length > COLLAPSE_LEN

  return (
    <div className="dyn-card" style={{ animationDelay: `${Math.min(index, 12) * 0.04}s` }}>
      <div className="dyn-head">
        <span className={`tag ${dyn.type === 'video' ? 'accent' : ''}`}>{TYPE_LABEL[dyn.type] || dyn.type}</span>
        <a className="dyn-link" href={dyn.url} target="_blank" rel="noopener noreferrer">
          打开原动态 ↗
        </a>
        <span className="dyn-time">{fmtTime(dyn.pub_ts)}</span>
      </div>
      <div
        className={`dyn-text ${long && !expanded ? 'collapsed' : ''}`}
        onClick={() => window.open(dyn.url, '_blank', 'noopener')}
        title="点击打开原动态"
      >
        {dyn.text || '(无文本内容)'}
      </div>
      {long && (
        <button className="dyn-toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? '收起 ▲' : '展开全文 ▼'}
        </button>
      )}
    </div>
  )
}

/** 动态列表:文本(过长折叠)/ 时间,点击打开 url */
export default function DynamicList({ dynamics, loading, error, onRetry }) {
  if (loading || error || !dynamics?.length) {
    return (
      <Placeholder
        loading={loading}
        error={error}
        empty={!dynamics?.length}
        emptyText="暂无动态数据,可点击顶栏「立即爬取」"
        onRetry={onRetry}
      />
    )
  }
  return (
    <div className="dyn-list">
      {dynamics.map((d, i) => (
        <DynCard key={d.dyn_id} dyn={d} index={i} />
      ))}
    </div>
  )
}
