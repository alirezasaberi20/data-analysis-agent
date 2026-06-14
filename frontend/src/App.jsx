import React, { useState, useRef, useEffect, useCallback } from 'react'
import ChatMessage from './components/ChatMessage'
import StepIndicator from './components/StepIndicator'
import FileUpload from './components/FileUpload'
import TablesPanel from './components/TablesPanel'
import { Send, Database, BarChart3, Bot, Trash2, Plus, PanelRightOpen, PanelRightClose } from 'lucide-react'
import './styles.css'

const SAMPLE_QUESTIONS = [
  "Why did sales drop in Q3 2024?",
  "Which product has the highest revenue?",
  "Compare regional performance across 2024",
  "What's the discount impact on revenue?",
  "Show monthly sales trend for 2024",
]

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [currentStep, setCurrentStep] = useState('')
  const [progress, setProgress] = useState(0)
  const [tables, setTables] = useState([])
  const [showSidebar, setShowSidebar] = useState(true)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const wsRef = useRef(null)

  const fetchTables = useCallback(async () => {
    try {
      const res = await fetch('/api/tables')
      const data = await res.json()
      setTables(data.tables || [])
    } catch (err) {
      console.error('Failed to fetch tables:', err)
    }
  }, [])

  useEffect(() => {
    fetchTables()
  }, [fetchTables])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const connectWebSocket = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => console.log('WebSocket connected')

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'session') {
        setSessionId(data.session_id)
      } else if (data.type === 'step') {
        setCurrentStep(data.step)
        setProgress(data.progress)
      } else if (data.type === 'response') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response,
          charts: data.charts || [],
          sql_results: data.sql_results || [],
          cached: data.cached || false,
        }])
        setLoading(false)
        setCurrentStep('')
        setProgress(0)
      } else if (data.type === 'error') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Error: ${data.error}`,
          isError: true,
        }])
        setLoading(false)
        setCurrentStep('')
        setProgress(0)
      }
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting...')
      setTimeout(connectWebSocket, 2000)
    }

    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connectWebSocket()
    return () => wsRef.current?.close()
  }, [connectWebSocket])

  const sendMessage = useCallback(async (messageText) => {
    const text = messageText || input.trim()
    if (!text || loading) return

    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInput('')
    setLoading(true)

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: text }))
    } else {
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, session_id: sessionId }),
        })
        const data = await res.json()
        setSessionId(data.session_id)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response,
          charts: data.charts || [],
          sql_results: data.sql_results || [],
        }])
      } catch (err) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Connection error: ${err.message}`,
          isError: true,
        }])
      }
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const clearChat = () => {
    setMessages([])
    if (wsRef.current) {
      wsRef.current.close()
      connectWebSocket()
    }
  }

  return (
    <div className={`app-layout ${showSidebar ? 'sidebar-open' : ''}`}>
      <div className="app">
        <header className="header">
          <div className="header-left">
            <div className="logo">
              <Bot size={28} />
            </div>
            <div>
              <h1>Data Analysis Agent</h1>
              <p className="subtitle">SQL + Python + Charts powered by AI</p>
            </div>
          </div>
          <div className="header-right">
            {sessionId && (
              <span className="session-badge">
                Session: {sessionId.slice(0, 8)}
              </span>
            )}
            <button className="icon-btn" onClick={() => setShowSidebar(s => !s)} title="Data panel">
              {showSidebar ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
            </button>
            <button className="icon-btn" onClick={clearChat} title="New chat">
              <Plus size={18} />
            </button>
          </div>
        </header>

        <main className="chat-container">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">
                <BarChart3 size={48} />
              </div>
              <h2>Ask me anything about your data</h2>
              <p>Upload CSV, Excel, or SQL files — or use the built-in sales dataset. I'll write queries, analyze, chart, and explain.</p>
              <div className="sample-questions">
                {SAMPLE_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    className="sample-btn"
                    onClick={() => sendMessage(q)}
                  >
                    <Database size={14} />
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((msg, i) => (
                <ChatMessage key={i} message={msg} />
              ))}
              {loading && (
                <StepIndicator step={currentStep} progress={progress} />
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>

        <footer className="input-area">
          <div className="input-wrapper">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your data... e.g., 'Why did sales drop in Q3?'"
              rows={1}
              disabled={loading}
            />
            <button
              className="send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
            >
              <Send size={18} />
            </button>
          </div>
        </footer>
      </div>

      {showSidebar && (
        <aside className="sidebar">
          <FileUpload onUploadComplete={(newTables) => setTables(newTables)} />
          <TablesPanel
            tables={tables}
            onDelete={(name) => {
              setTables(prev => prev.filter(t => t.name !== name))
            }}
          />
        </aside>
      )}
    </div>
  )
}
