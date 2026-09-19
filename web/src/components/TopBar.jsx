import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { getStatus, postCrawl, postSummarize } from '../api'
import LoginDialog from './LoginDialog'
import { useToast } from './Toast'

const POLL_MS = 30000

function TvIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7.5 2.5 5 5.5M16.5 2.5 19 5.5" />
      <rect x="2.5" y="5.5" width="19" height="14" rx="4" />
      <path d="M8.5 11v3M15.5 11v3" />
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  )
}

function PenIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  )
}

function LoginIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <path d="M14 14h3v3h-3zM20 14v3M17.5 20h3" />
    </svg>
  )
}

/** 全局顶栏:导航 + 立即爬取/总结 + 30s 轮询状态指示 */
export default function TopBar() {
  const toast = useToast()
  const [status, setStatus] = useState(null) // null=未知(后端可能没起)
  const [crawlPending, setCrawlPending] = useState(false)
  const [sumPending, setSumPending] = useState(false)
  const [loginOpen, setLoginOpen] = useState(false)
  const timerRef = useRef(null)

  const poll = async () => {
    try {
      const s = await getStatus()
      setStatus(s)
    } catch {
      setStatus(null)
    }
  }

  useEffect(() => {
    poll()
    timerRef.current = setInterval(poll, POLL_MS)
    return () => clearInterval(timerRef.current)
  }, [])

  const handleCrawl = async () => {
    setCrawlPending(true)
    try {
      const r = await postCrawl()
      toast(r.message || '已触发爬取,后台执行中')
      setTimeout(poll, 1500) // 触发后尽快刷新状态
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setCrawlPending(false)
    }
  }

  const handleSummarize = async () => {
    setSumPending(true)
    try {
      const r = await postSummarize()
      toast(r.message || '已触发总结,后台执行中')
      setTimeout(poll, 1500)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setSumPending(false)
    }
  }

  const crawling = status?.crawling
  const summarizing = status?.summarizing

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <NavLink to="/" className="brand">
          <span className="brand-logo">
            <TvIcon />
          </span>
          <span className="brand-mark">财经哨站</span>
          <span className="brand-sub">UP MONITOR</span>
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            总览
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            历史总结
          </NavLink>
        </nav>
        <div className="topbar-right">
          {status === null ? (
            <span className="status-chip">
              <span className="dot gray" />
              <span className="chip-text">后端离线</span>
            </span>
          ) : status.login_required ? (
            <span className="status-chip error" title="B站登录态已失效，请在 .env 更新 BILI_SESSDATA / BILI_JCT（见 README 登录 SOP）">
              <span className="dot red" />
              <span className="chip-text">登录态失效</span>
            </span>
          ) : crawling || summarizing ? (
            <span className="status-chip busy">
              <span className="spinner" />
              <span className="chip-text">{crawling ? '爬取中' : '总结中'}</span>
            </span>
          ) : (
            <span className="status-chip">
              <span className="dot" />
              <span className="chip-text">空闲</span>
            </span>
          )}
          <button
            className={`btn ${status?.login_required ? 'primary' : ''}`}
            onClick={() => setLoginOpen(true)}
            title="用 B站 App 扫码登录，登录态自动写入 .env"
          >
            <LoginIcon />
            <span className="btn-text">扫码登录</span>
          </button>
          <button className="btn" onClick={handleCrawl} disabled={crawlPending || crawling}>
            {crawling ? <span className="spinner" /> : <RefreshIcon />}
            <span className="btn-text">立即爬取</span>
          </button>
          <button className="btn primary" onClick={handleSummarize} disabled={sumPending || summarizing}>
            {summarizing ? <span className="spinner" /> : <PenIcon />}
            <span className="btn-text">立即总结</span>
          </button>
        </div>
      </div>
      <LoginDialog
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLoggedIn={() => {
          toast('B站登录成功，登录态已生效')
          poll()
        }}
      />
    </header>
  )
}
