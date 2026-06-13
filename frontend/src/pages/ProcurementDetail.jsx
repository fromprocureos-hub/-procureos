import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { procurementsAPI, poAPI } from '../lib/api'
import api from '../lib/api'
import toast from 'react-hot-toast'

export default function ProcurementDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [quotes, setQuotes] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [showReminder, setShowReminder] = useState(false)
  const [reminderData, setReminderData] = useState(null)
  const [selectedPvIds, setSelectedPvIds] = useState([])
  const [sendingReminder, setSendingReminder] = useState(false)
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  useEffect(() => { load() }, [id])

  async function load() {
    try {
      const [dr, qr] = await Promise.all([
        procurementsAPI.get(id),
        procurementsAPI.getQuotes(id)
      ])
      setData(dr.data)
      setQuotes(qr.data)
    } catch { toast.error('Failed to load') }
    finally { setLoading(false) }
  }

  async function openReminderModal() {
    try {
      const r = await api.get(`/api/procurements/${id}/reminder-status`)
      setReminderData(r.data)
      // default: select all non-replied vendors that need a reminder
      const defaults = r.data.vendors
        .filter(v => v.status !== 'replied')
        .map(v => v.pv_id)
      setSelectedPvIds(defaults)
      setShowReminder(true)
    } catch {
      toast.error('Failed to load vendor status')
    }
  }

  function toggleVendor(pv_id) {
    setSelectedPvIds(prev =>
      prev.includes(pv_id) ? prev.filter(x => x !== pv_id) : [...prev, pv_id]
    )
  }

  async function sendReminders() {
    if (!selectedPvIds.length) {
      toast.error('Select at least one vendor')
      return
    }
    setSendingReminder(true)
    try {
      const r = await api.post(`/api/procurements/${id}/send-reminders`, { pv_ids: selectedPvIds })
      toast.success(r.data.message)
      setShowReminder(false)
      load()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to send reminders')
    } finally {
      setSendingReminder(false)
    }
  }

  async function handleSelectWinner(pv_id) {
    if (!confirm('Select this vendor as winner?')) return
    setSending(true)
    try {
      await procurementsAPI.selectWinner(id, pv_id)
      toast.success('Winner selected!')
      load()
    } catch (err) { toast.error(err.response?.data?.error || 'Failed') }
    finally { setSending(false) }
  }

  async function handleApprove() {
    if (!confirm('Approve this procurement?')) return
    setSending(true)
    try {
      await procurementsAPI.approve(id)
      toast.success('Approved!')
      load()
    } catch (err) { toast.error(err.response?.data?.error || 'Failed') }
    finally { setSending(false) }
  }

  async function handleReject() {
    const reason = prompt('Reason for rejection?')
    if (reason === null) return
    setSending(true)
    try {
      await procurementsAPI.reject(id, reason)
      toast.success('Rejected')
      load()
    } catch (err) { toast.error(err.response?.data?.error || 'Failed') }
    finally { setSending(false) }
  }

  async function handleGeneratePO() {
    if (!confirm('Generate and send Purchase Order?')) return
    setSending(true)
    try {
      const r = await poAPI.generate(id)
      toast.success(r.data.message)
      load()
    } catch (err) { toast.error(err.response?.data?.error || 'Failed') }
    finally { setSending(false) }
  }

  const statusColor = {
    draft: '#6b7280', pending_quotes: '#3b82f6',
    pending_approval: '#f59e0b', approved: '#10b981',
    rejected: '#ef4444', completed: '#8b5cf6',
  }

  const vendorStatusBadge = {
    replied: { bg: '#d1fae5', color: '#065f46', label: 'Replied' },
    opened: { bg: '#dbeafe', color: '#1e40af', label: 'Sent' },
    not_opened: { bg: '#f3f4f6', color: '#6b7280', label: 'Not sent' },
  }

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>Loading...</div>
  if (!data) return <div style={{ padding: 40 }}>Not found</div>

  const proc = data.procurement
  const status = proc.status
  const canRemind = status === 'pending_quotes'

  return (
    <div style={{ padding: 32, maxWidth: 900 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <button onClick={() => navigate('/dashboard')} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 14, marginBottom: 8 }}>← Back</button>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1e3a5f' }}>{proc.title}</h1>
          <p style={{ color: '#6b7280', marginTop: 4 }}>{proc.item_name} × {proc.quantity} {proc.unit}</p>
        </div>
        <span style={{ padding: '6px 14px', borderRadius: 20, fontSize: 13, fontWeight: 600, background: `${statusColor[status]}20`, color: statusColor[status] }}>
          {status.replace(/_/g, ' ').toUpperCase()}
        </span>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        {canRemind && (
          <button onClick={openReminderModal} style={{ padding: '10px 20px', background: '#f59e0b', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
            🔔 Remind Vendors
          </button>
        )}
        {status === 'pending_approval' && user.role !== 'requester' && (
          <>
            <button onClick={handleApprove} disabled={sending} style={{ padding: '10px 20px', background: '#059669', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
              ✓ Approve
            </button>
            <button onClick={handleReject} disabled={sending} style={{ padding: '10px 20px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
              ✕ Reject
            </button>
          </>
        )}
        {status === 'approved' && user.role !== 'requester' && (
          <button onClick={handleGeneratePO} disabled={sending} style={{ padding: '10px 20px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
            📄 Generate & Send PO
          </button>
        )}
      </div>

      {/* Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div style={{ background: '#fff', padding: 20, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: '#1e3a5f' }}>Procurement Info</h3>
          {[
            ['Created by', proc.creator_name],
            ['Category', proc.category_tag || '—'],
            ['Deadline', proc.deadline ? new Date(proc.deadline).toLocaleDateString() : '—'],
            ['Template', proc.rfq_template],
            ['Notes', proc.notes || '—'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13 }}>
              <span style={{ color: '#6b7280' }}>{k}</span>
              <span style={{ fontWeight: 500 }}>{v}</span>
            </div>
          ))}
        </div>
        <div style={{ background: '#fff', padding: 20, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: '#1e3a5f' }}>Scoring Weights</h3>
          {[
            ['Price', proc.price_weight],
            ['Delivery', proc.delivery_weight],
            ['Quality', proc.quality_weight],
            ['Compliance', proc.compliance_weight],
          ].map(([k, v]) => (
            <div key={k} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 3 }}>
                <span style={{ color: '#6b7280' }}>{k}</span>
                <span style={{ fontWeight: 600 }}>{v}</span>
              </div>
              <div style={{ background: '#f3f4f6', borderRadius: 4, height: 6 }}>
                <div style={{ background: '#1e3a5f', width: `${v}%`, height: 6, borderRadius: 4 }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quotes */}
      <div style={{ background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: 24 }}>
        <div style={{ padding: '18px 24px', borderBottom: '1px solid #f3f4f6' }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1e3a5f' }}>
            Quotes Received ({quotes?.quotes_received || 0} / {quotes?.total_vendors || 0})
          </h3>
        </div>
        {!quotes?.quoted?.length ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>
            <p>No quotes received yet. Waiting for vendors to respond.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                {['Rank', 'Vendor', 'Price', 'Delivery', 'Score', 'Action'].map(h => (
                  <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {quotes.quoted.map((q, i) => (
                <tr key={q.pv_id} style={{ borderTop: '1px solid #f3f4f6', background: i === 0 ? '#f0fff4' : '#fff' }}>
                  <td style={{ padding: '14px 16px' }}>
                    {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 600 }}>{q.vendor_name}</div>
                    {q.recommendation_reason && <div style={{ fontSize: 11, color: '#059669', marginTop: 2 }}>{q.recommendation_reason}</div>}
                  </td>
                  <td style={{ padding: '14px 16px', fontWeight: 600 }}>${q.price?.toLocaleString()}</td>
                  <td style={{ padding: '14px 16px', color: '#6b7280' }}>{q.delivery_days ? `${q.delivery_days} days` : '—'}</td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{ background: '#eff6ff', color: '#1d4ed8', padding: '4px 10px', borderRadius: 20, fontWeight: 700, fontSize: 13 }}>{q.score}/100</span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    {status === 'pending_quotes' && (
                      <button onClick={() => handleSelectWinner(q.pv_id)} disabled={sending} style={{ padding: '7px 14px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                        Select Winner
                      </button>
                    )}
                    {proc.selected_vendor_id === q.vendor_id && (
                      <span style={{ color: '#059669', fontWeight: 600, fontSize: 13 }}>✔ Selected</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {quotes?.pending?.length > 0 && (
          <div style={{ padding: '12px 24px', borderTop: '1px solid #f3f4f6' }}>
            <p style={{ fontSize: 13, color: '#6b7280' }}>
              ⏳ Waiting for: {quotes.pending.map(p => p.vendor_name).join(', ')}
            </p>
          </div>
        )}
      </div>

      {/* Activity */}
      <div style={{ background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ padding: '18px 24px', borderBottom: '1px solid #f3f4f6' }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1e3a5f' }}>Activity Log</h3>
        </div>
        <div style={{ padding: '16px 24px' }}>
          {data.activities?.length ? data.activities.map(a => (
            <div key={a.id} style={{ display: 'flex', gap: 12, marginBottom: 12, fontSize: 13 }}>
              <span style={{ color: '#9ca3af', whiteSpace: 'nowrap' }}>{new Date(a.timestamp).toLocaleString()}</span>
              <span><strong>{a.actor}</strong> — {a.action} {a.detail ? `(${a.detail})` : ''}</span>
            </div>
          )) : <p style={{ color: '#9ca3af' }}>No activity yet.</p>}
        </div>
      </div>

      {/* REMINDER MODAL */}
      {showReminder && reminderData && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 32, width: 520, maxWidth: '95vw', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#1e3a5f', margin: 0 }}>🔔 Remind Vendors</h2>
              <button onClick={() => setShowReminder(false)} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#9ca3af' }}>×</button>
            </div>

            <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 20 }}>
              Select vendors to send a reminder email for <strong>{reminderData.procurement_title}</strong>.
            </p>

            {/* Remind all non-replied */}
            <button
              onClick={() => {
                const nonReplied = reminderData.vendors.filter(v => v.status !== 'replied').map(v => v.pv_id)
                setSelectedPvIds(nonReplied)
              }}
              style={{ width: '100%', padding: '10px', background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: 8, fontWeight: 600, cursor: 'pointer', marginBottom: 16, fontSize: 13 }}
            >
              Select all who haven't replied ({reminderData.vendors.filter(v => v.status !== 'replied').length})
            </button>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
              {reminderData.vendors.map(v => {
                const badge = vendorStatusBadge[v.status]
                const selected = selectedPvIds.includes(v.pv_id)
                return (
                  <div
                    key={v.pv_id}
                    onClick={() => v.status !== 'replied' && toggleVendor(v.pv_id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '14px 16px', borderRadius: 10,
                      border: selected ? '2px solid #1e3a5f' : '1.5px solid #e5e7eb',
                      background: selected ? '#f0f4ff' : '#fafafa',
                      cursor: v.status !== 'replied' ? 'pointer' : 'default',
                      opacity: v.status === 'replied' ? 0.6 : 1,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => {}}
                      disabled={v.status === 'replied'}
                      style={{ width: 16, height: 16, accentColor: '#1e3a5f' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontWeight: 600, fontSize: 14 }}>{v.vendor_name}</span>
                        {v.urgent && (
                          <span style={{ background: '#fef2f2', color: '#dc2626', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20 }}>
                            URGENT — deadline &lt;24h
                          </span>
                        )}
                        {v.suggest_reminder && !v.urgent && (
                          <span style={{ background: '#fffbeb', color: '#92400e', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20 }}>
                            No reply in 48h
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{v.vendor_email || 'No email'}</div>
                      {v.email_sent_at && (
                        <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
                          Sent {new Date(v.email_sent_at).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                    <span style={{ background: badge.bg, color: badge.color, fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 20, whiteSpace: 'nowrap' }}>
                      {badge.label}
                    </span>
                  </div>
                )
              })}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setShowReminder(false)}
                style={{ flex: 1, padding: '12px', background: '#f3f4f6', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer', color: '#374151' }}
              >
                Cancel
              </button>
              <button
                onClick={sendReminders}
                disabled={sendingReminder || !selectedPvIds.length}
                style={{ flex: 2, padding: '12px', background: selectedPvIds.length ? '#1e3a5f' : '#9ca3af', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: selectedPvIds.length ? 'pointer' : 'not-allowed' }}
              >
                {sendingReminder ? 'Sending...' : `Send Reminder to ${selectedPvIds.length} vendor${selectedPvIds.length !== 1 ? 's' : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}