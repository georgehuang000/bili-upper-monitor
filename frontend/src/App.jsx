import React, { useState, useEffect, useCallback } from 'react'
import { api } from './api.js'
import SummaryPanel from './components/SummaryPanel.jsx'
import UpperNav from './components/UpperNav.jsx'
import VideoList from './components/VideoList.jsx'
import DynamicsList from './components/DynamicsList.jsx'
import StatsBar from './components/StatsBar.jsx'

export default function App() {
  const [uppers, setUppers] = useState([])
  const [selectedUpperId, setSelectedUpperId] = useState(0)
  const [videos, setVideos] = useState([])
  const [dynamics, setDynamics] = useState([])
  const [summaries, setSummaries] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [activeTab, setActiveTab] = useState('videos')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [uppersData, statsData, summariesData] = await Promise.all([
        api.getUppers(),
        api.getStats(),
        api.getSummaries(),
      ])
      setUppers(uppersData)
      setStats(statsData)
      setSummaries(summariesData)

      const [videosData, dynamicsData] = await Promise.all([
        api.getVideos(selectedUpperId, 1, 30),
        api.getDynamics(selectedUpperId, 1, 30),
      ])
      setVideos(videosData.videos || [])
      setDynamics(dynamicsData.dynamics || [])
    } catch (e) {
      setMessage(`加载失败: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }, [selectedUpperId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleCrawl = async () => {
    setActionLoading(true)
    setMessage('正在爬取数据...')
    try {
      const result = await api.triggerCrawl()
      setMessage(`爬取完成: ${result.results?.length || 0} 位UP主已处理`)
      await loadData()
    } catch (e) {
      setMessage(`爬取失败: ${e.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleSummarize = async () => {
    setActionLoading(true)
    setMessage('正在生成AI总结...')
    try {
      const result = await api.triggerSummarize('full')
      if (result.status === 'success') {
        setMessage('总结生成成功')
      } else if (result.status === 'skip') {
        setMessage('没有新内容需要总结')
      } else {
        setMessage(`总结失败: ${result.message}`)
      }
      await loadData()
    } catch (e) {
      setMessage(`总结失败: ${e.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      {/* 头部 */}
      <header style={styles.header}>
        <h1 style={styles.title}>B站UP主监控面板</h1>
        <div style={styles.actions}>
          <button
            style={{ ...styles.btn, ...(actionLoading ? styles.btnDisabled : {}) }}
            onClick={handleCrawl}
            disabled={actionLoading}
          >
            {actionLoading ? '处理中...' : '手动爬取'}
          </button>
          <button
            style={{ ...styles.btn, ...styles.btnPrimary, ...(actionLoading ? styles.btnDisabled : {}) }}
            onClick={handleSummarize}
            disabled={actionLoading}
          >
            生成AI总结
          </button>
        </div>
      </header>

      {/* 消息提示 */}
      {message && (
        <div style={styles.messageBar} onClick={() => setMessage('')}>
          {message}
        </div>
      )}

      {/* 统计栏 */}
      {stats && <StatsBar stats={stats} />}

      {/* AI总结面板 */}
      <SummaryPanel summaries={summaries} />

      {/* UP主导航 */}
      <UpperNav
        uppers={uppers}
        selectedId={selectedUpperId}
        onSelect={setSelectedUpperId}
      />

      {/* Tab切换 */}
      <div style={styles.tabs}>
        <button
          style={{ ...styles.tab, ...(activeTab === 'videos' ? styles.tabActive : {}) }}
          onClick={() => setActiveTab('videos')}
        >
          视频列表
        </button>
        <button
          style={{ ...styles.tab, ...(activeTab === 'dynamics' ? styles.tabActive : {}) }}
          onClick={() => setActiveTab('dynamics')}
        >
          动态列表
        </button>
      </div>

      {/* 内容区域 */}
      {loading ? (
        <div style={styles.loading}>加载中...</div>
      ) : activeTab === 'videos' ? (
        <VideoList videos={videos} />
      ) : (
        <DynamicsList dynamics={dynamics} />
      )}
    </div>
  )
}

const styles = {
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    color: '#333',
    background: '#f5f5f5',
    minHeight: '100vh',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
    flexWrap: 'wrap',
    gap: '12px',
  },
  title: {
    fontSize: '24px',
    fontWeight: 700,
    margin: 0,
    color: '#1a1a2e',
  },
  actions: {
    display: 'flex',
    gap: '8px',
  },
  btn: {
    padding: '8px 20px',
    border: '1px solid #ddd',
    borderRadius: '6px',
    background: '#fff',
    cursor: 'pointer',
    fontSize: '14px',
    transition: 'all 0.2s',
  },
  btnPrimary: {
    background: '#00a1d6',
    color: '#fff',
    border: 'none',
  },
  btnDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
  messageBar: {
    padding: '10px 16px',
    background: '#fff3cd',
    border: '1px solid #ffeaa7',
    borderRadius: '6px',
    marginBottom: '12px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  tabs: {
    display: 'flex',
    gap: '4px',
    marginBottom: '16px',
    background: '#fff',
    borderRadius: '8px',
    padding: '4px',
    width: 'fit-content',
  },
  tab: {
    padding: '8px 24px',
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    borderRadius: '6px',
    fontSize: '14px',
    color: '#666',
  },
  tabActive: {
    background: '#00a1d6',
    color: '#fff',
    fontWeight: 600,
  },
  loading: {
    textAlign: 'center',
    padding: '60px 0',
    fontSize: '16px',
    color: '#999',
  },
}
