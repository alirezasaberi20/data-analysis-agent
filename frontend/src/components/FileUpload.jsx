import React, { useState, useRef } from 'react'
import { Upload, FileSpreadsheet, FileText, X, Loader2, CheckCircle } from 'lucide-react'

const ACCEPTED = '.csv,.tsv,.xlsx,.xls,.sql'

export default function FileUpload({ onUploadComplete }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const handleFile = async (file) => {
    if (!file) return
    setUploading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Upload failed')
      } else {
        setResult(data.message)
        onUploadComplete?.(data.tables)
        setTimeout(() => setResult(null), 5000)
      }
    } catch (err) {
      setError(`Upload error: ${err.message}`)
    }
    setUploading(false)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const onDragOver = (e) => {
    e.preventDefault()
    setDragging(true)
  }

  const getFileIcon = (name) => {
    if (!name) return <Upload size={16} />
    if (name.endsWith('.sql')) return <FileText size={16} />
    return <FileSpreadsheet size={16} />
  }

  return (
    <div className="upload-section">
      <div
        className={`drop-zone ${dragging ? 'dragging' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setDragging(false)}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED}
          onChange={(e) => handleFile(e.target.files?.[0])}
          hidden
        />
        {uploading ? (
          <div className="upload-status">
            <Loader2 size={18} className="spinner" />
            <span>Uploading...</span>
          </div>
        ) : (
          <div className="upload-prompt">
            <Upload size={18} />
            <span>Drop CSV, Excel, or SQL file here</span>
          </div>
        )}
      </div>

      {result && (
        <div className="upload-result success">
          <CheckCircle size={14} />
          <span>{result}</span>
          <button className="dismiss-btn" onClick={() => setResult(null)}>
            <X size={12} />
          </button>
        </div>
      )}

      {error && (
        <div className="upload-result error">
          <span>{error}</span>
          <button className="dismiss-btn" onClick={() => setError(null)}>
            <X size={12} />
          </button>
        </div>
      )}
    </div>
  )
}
