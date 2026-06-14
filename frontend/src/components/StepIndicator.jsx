import React from 'react'
import { Loader2 } from 'lucide-react'

export default function StepIndicator({ step, progress }) {
  return (
    <div className="step-indicator">
      <div className="step-content">
        <Loader2 size={18} className="spinner" />
        <span>{step || 'Processing...'}</span>
      </div>
      {progress > 0 && (
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  )
}
