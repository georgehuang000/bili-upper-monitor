const API_BASE = '/api'

async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    throw new Error(`API错误: ${resp.status} ${resp.statusText}`)
  }
  return resp.json()
}

export const api = {
  getUppers: () => fetchAPI('/uppers'),
  getVideos: (upperId = 0, page = 1, pageSize = 20) =>
    fetchAPI(`/videos?upper_id=${upperId}&page=${page}&page_size=${pageSize}`),
  getDynamics: (upperId = 0, page = 1, pageSize = 20) =>
    fetchAPI(`/dynamics?upper_id=${upperId}&page=${page}&page_size=${pageSize}`),
  getSummaries: (date = '') =>
    fetchAPI(`/summaries${date ? `?date=${date}` : ''}`),
  getStats: () => fetchAPI('/stats'),
  triggerCrawl: () => fetchAPI('/crawl', { method: 'POST' }),
  triggerSummarize: (period = 'full') =>
    fetchAPI(`/summarize?period=${period}`, { method: 'POST' }),
}
