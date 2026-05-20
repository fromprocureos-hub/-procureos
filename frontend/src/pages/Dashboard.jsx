import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { procurementsAPI } from '../lib/api'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const company = JSON.parse(localStorage.getItem('company') || '{}')

  useEffect(() => {
    procurementsAPI.stats().then(r => setStats(r.data)).catch(() => {})
  }, [])

  const cards = stats ? [
    { label: 'Active RFQs', value: stats.active_rfqs, color: '#3b82f6', emoji: '📋' },
    { label: 'Pending Approval', value: stats.pending_approvals, color: '#f59e0b', emoji: '⏳' },
    { label: 'Approved', value: stats.approved, color: '#10b981', emoji: '✅' },
    { label: 'Total Vendors', value: stats.total_vendors, color: '#8b5cf6', emoji: '🏢' },
  ] : []

  const statusColor = {
    draft: '#6b7280',
    pending_quotes: '#3b82f6',
    pending_approval: '#f59e0b',
    approved: '#10b981',
    rejected: '#ef4444',
    completed: '#8b5cf6',
  }

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1e3a5f' }}>
          Welcome back, {user.full_name?.split(' ')[0] || 'there'} 👋
        </h1>
        <p style={{ color: '#6b7280', marginTop: 4 }}>{company.name} — {company.industry_name || 'Procurement Dashboard'}</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        {cards.map(c => (
          <div key={c.label} style={{
            background: '#fff', padding: 20, borderRadius: 12,
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)', borderLeft: `4px solid ${c.color}`
          }}>
            <div style={{ fontSize: 28 }}>{c.emoji}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: c.color, marginTop: 8 }}>{c.value}</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 32 }}>
        <button onClick={() => navigate('/procurements/new')} style={{
          padding: '12px 24px', background: '#1e3a5f', color: '#fff',
          border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer'
        }}>➕ New RFQ</button>
        <button onClick={() => navigate('/vendors')} style={{
          padding: '12px 24px', background: '#fff', color: '#1e3a5f',
          border: '2px solid #1e3a5f', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer'
        }}>🏢 Manage Vendors</button>
      </div>

      {/* Recent procurements */}
      <div style={{ background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #f3f4f6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1e3a5f' }}>Recent Procurements</h2>
        </div>
        {!stats?.recent_procurements?.length ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#9ca3af' }}>
            <div style={{ fontSize: 40 }}>📋</div>
            <p style={{ marginTop: 12 }}>No procurements yet.</p>
            <button onClick={() => navigate('/procurements/new')} style={{
              marginTop: 16, padding: '10px 20px', background: '#1e3a5f',
              color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer'
            }}>Create your first RFQ</button>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                {['Title', 'Item', 'Status', 'Created', ''].map(h => (
                  <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stats.recent_procurements.map(p => (
                <tr key={p.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '14px 16px', fontWeight: 600, color: '#111827' }}>{p.title}</td>
                  <td style={{ padding: '14px 16px', color: '#6b7280' }}>{p.item_name}</td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{
                      padding: '4px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                      background: `${statusColor[p.status]}20`, color: statusColor[p.status]
                    }}>{p.status.replace('_', ' ')}</span>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#6b7280', fontSize: 13 }}>
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <Link to={`/procurements/${p.id}`} style={{ color: '#2563eb', fontSize: 13 }}>View →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}