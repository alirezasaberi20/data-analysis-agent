import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, User, ChevronDown, ChevronUp, Image, AlertCircle, Zap } from 'lucide-react'

export default function ChatMessage({ message }) {
  const { role, content, charts = [], sql_results = [], isError, cached } = message
  const [showSql, setShowSql] = useState(false)
  const isUser = role === 'user'

  return (
    <div className={`message ${isUser ? 'user-message' : 'assistant-message'} ${isError ? 'error-message' : ''}`}>
      <div className="message-avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      <div className="message-content">
        {isError ? (
          <div className="error-banner">
            <AlertCircle size={16} />
            <span>{content}</span>
          </div>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <div className="table-wrapper">
                    <table>{children}</table>
                  </div>
                ),
              }}
            >{content}</ReactMarkdown>
          </div>
        )}

        {cached && (
          <div className="cached-badge">
            <Zap size={12} />
            Cached response — no tokens used
          </div>
        )}

        {sql_results.length > 0 && (
          <div className="sql-section">
            <button className="toggle-btn" onClick={() => setShowSql(!showSql)}>
              {showSql ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              SQL Results ({sql_results.length} queries)
            </button>
            {showSql && (
              <div className="sql-results">
                {sql_results.map((result, i) => (
                  <pre key={i} className="sql-block">{result}</pre>
                ))}
              </div>
            )}
          </div>
        )}

        {charts.length > 0 && (
          <div className="charts-section">
            <div className="charts-label">
              <Image size={14} />
              Generated Charts
            </div>
            <div className="charts-grid">
              {charts.map((chart, i) => (
                <div key={i} className="chart-card">
                  <img
                    src={chart}
                    alt={`Analysis chart ${i + 1}`}
                    loading="lazy"
                    onClick={() => window.open(chart, '_blank')}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
