import ReactMarkdown from 'react-markdown'

/** 仅放行 http/https 协议的链接 */
const SAFE_HREF = /^https?:\/\//i

/**
 * 安全链接渲染:
 * - http/https 链接 -> 新标签页打开,带 noopener noreferrer
 * - 其他协议(javascript:/data:/vbscript: 等)-> 渲染为纯文本,不产生可点击链接
 */
function SafeLink({ href, children }) {
  if (typeof href === 'string' && SAFE_HREF.test(href)) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  }
  return <span>{children}</span>
}

/**
 * 统一的安全 Markdown 渲染组件。
 * 所有渲染 LLM 输出等不可信 Markdown 的地方都应使用本组件,
 * 而不要直接使用 ReactMarkdown。
 */
export default function SafeMarkdown({ children }) {
  return <ReactMarkdown components={{ a: SafeLink }}>{children}</ReactMarkdown>
}
