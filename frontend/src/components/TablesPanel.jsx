import React from 'react'
import { Database, Trash2, Table2 } from 'lucide-react'

const PROTECTED_TABLES = new Set(['products', 'regions', 'sales_reps', 'sales', 'customers'])

export default function TablesPanel({ tables, onDelete }) {
  if (!tables || tables.length === 0) return null

  const handleDelete = async (tableName) => {
    if (!confirm(`Delete table "${tableName}"? This cannot be undone.`)) return
    try {
      const res = await fetch(`/api/tables/${tableName}`, { method: 'DELETE' })
      if (res.ok) {
        onDelete?.(tableName)
      }
    } catch (err) {
      console.error('Delete error:', err)
    }
  }

  return (
    <div className="tables-panel">
      <div className="tables-header">
        <Database size={14} />
        <span>Database Tables ({tables.length})</span>
      </div>
      <div className="tables-list">
        {tables.map((t) => (
          <div key={t.name} className="table-item">
            <div className="table-info">
              <Table2 size={13} />
              <span className="table-name">{t.name}</span>
              <span className="table-meta">
                {t.rows.toLocaleString()} rows, {t.columns} cols
              </span>
            </div>
            {!PROTECTED_TABLES.has(t.name) && (
              <button
                className="table-delete-btn"
                onClick={() => handleDelete(t.name)}
                title="Delete table"
              >
                <Trash2 size={12} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
