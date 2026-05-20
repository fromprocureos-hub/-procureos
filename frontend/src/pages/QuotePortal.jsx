import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { portalAPI } from '../lib/api'
import toast from 'react-hot-toast'

export default function QuotePortal() {
  const { token } = useParams()
  const [info, setInfo] = useState(null)
  const [error, setError] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [declined, setDeclined] = useState(false)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [form, setForm] = useState({
    price: '', delivery_days: '', payment_terms: 'Net 30',
    availability: 'yes', notes: '', capacity: '',
    certifications: '', experience: ''
  })

  useEffect(() => {
    portalAPI.getInfo(token)
      .then(r => setInfo(r.data))
      .catch(err => setError(err.response?.data?.error || 'Invalid link'))
      .finally(() => setLoading(false))
  }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.price || parseFloat(form.price) <= 0) return toast.error('Enter a valid price')
    setSending(true)
    try {
      await portalAPI.submit(token, form)
      setSubmitted(true)
    } catch (err) { toast.error(err.response?.data?.error || 'Failed to submit') }
    finally { setSending(false) }
  }

  async function handleDecline() {
    if (!confirm('Are you sure you want to decline this request?')) return
    try {
      await portalAPI.decline(token)
      setDeclined(true)
    } catch { toast.error('Failed') }
  }

  const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }
  const labelStyle = { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }

  if (loading) return <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>

  if (error) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f9fafb' }}>
      <div style={{ background: '#fff', padding: 40, borderRadius: 12, textAlign: 'center', maxWidth: 400 }}>
        <div style={{ fontSize: 48 }}>⚠️</div>
        <h2 style={{ marginTop: 16, color: '#ef4444' }}>{error}</h2>
      </div>
    </div>
  )

  if (submitted) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0fff4' }}>
      <div style={{ background: '#fff', padding: 40, borderRadius: 12, textAlign: 'center', maxWidth: 400 }}>
        <div style={{ fontSize: 48 }}>✅</div>
        <h2 style={{ marginTop: 16, color: '#059669' }}>Quote Submitted!</h2>
        <p style={{ color: '#6b7280', marginTop: 8 }}>Thank you. {info?.buyer_name} will review your quote and be in touch.</p>
      </div>
    </div>
  )

  if (declined) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f9fafb' }}>
      <div style={{ background: '#fff', padding: 40, borderRadius: 12, textAlign: 'center', maxWidth: 400 }}>
        <div style={{ fontSize: 48 }}>👋</div>
        <h2 style={{ marginTop: 16, color: '#6b7280' }}>Quote Declined</h2>
        <p style={{ color: '#6b7280', marginTop: 8 }}>You have declined this quote request.</p>
      </div>
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#f0f4ff', padding: 20 }}>
      <div style={{ maxWidth: 600, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ background: '#1e3a5f', color: '#fff', padding: 28, borderRadius: '12px 12px 0 0', textAlign: 'center' }}>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Quote Request</h1>
          <p style={{ opacity: 0.8, marginTop: 4 }}>from {info?.buyer_name}</p>
        </div>

        {/* Item info */}
        <div style={{ background: '#fff', padding: 24, borderBottom: '1px solid #f3f4f6' }}>
          <div style={{ background: '#eef2ff', padding: 16, borderRadius: 8, borderLeft: '4px solid #6366f1' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#1e1b4b' }}>{info?.item_name}</div>
            <div style={{ color: '#6b7280', marginTop: 4 }}>Quantity: <strong>{info?.quantity} {info?.unit}</strong></div>
            {info?.notes && <div style={{ color: '#6b7280', marginTop: 4 }}>Notes: {info.notes}</div>}
            {info?.deadline && <div style={{ color: '#dc2626', marginTop: 4, fontWeight: 600 }}>Deadline: {new Date(info.deadline).toLocaleDateString()}</div>}
          </div>
        </div>

        {/* Form */}
        <div style={{ background: '#fff', padding: 24, borderRadius: '0 0 12px 12px' }}>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={labelStyle}>Unit Price * ($)</label>
                <input required type="number" step="0.01" min="0.01" style={inputStyle} value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} placeholder="0.00" />
              </div>
              <div>
                <label style={labelStyle}>Delivery (days)</label>
                <input type="number" min="1" style={inputStyle} value={form.delivery_days} onChange={e => setForm({ ...form, delivery_days: e.target.value })} placeholder="e.g. 7" />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={labelStyle}>Availability</label>
                <select style={inputStyle} value={form.availability} onChange={e => setForm({ ...form, availability: e.target.value })}>
                  <option value="yes">Yes — fully available</option>
                  <option value="partial">Partial availability</option>
                  <option value="no">Not available</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Payment Terms</label>
                <input style={inputStyle} value={form.payment_terms} onChange={e => setForm({ ...form, payment_terms: e.target.value })} placeholder="e.g. Net 30" />
              </div>
            </div>

            {info?.rfq_template === 'Advanced' && (
              <>
                <div style={{ marginBottom: 14 }}>
                  <label style={labelStyle}>Monthly Capacity</label>
                  <input style={inputStyle} value={form.capacity} onChange={e => setForm({ ...form, capacity: e.target.value })} placeholder="e.g. 10,000 units/month" />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <label style={labelStyle}>Certifications (ISO, CE, FDA, etc.)</label>
                  <input style={inputStyle} value={form.certifications} onChange={e => setForm({ ...form, certifications: e.target.value })} placeholder="e.g. ISO 9001, CE" />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <label style={labelStyle}>Experience in this category</label>
                  <textarea rows={2} style={inputStyle} value={form.experience} onChange={e => setForm({ ...form, experience: e.target.value })} placeholder="e.g. 8 years supplying office products" />
                </div>
              </>
            )}

            <div style={{ marginBottom: 20 }}>
              <label style={labelStyle}>Additional Notes</label>
              <textarea rows={3} style={inputStyle} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder="Any other information..." />
            </div>

            <button type="submit" disabled={sending} style={{ width: '100%', padding: 14, background: '#059669', color: '#fff', border: 'none', borderRadius: 8, fontSize: 16, fontWeight: 700, cursor: 'pointer', marginBottom: 10 }}>
              {sending ? 'Submitting...' : '✅ Submit My Quote'}
            </button>
            <button type="button" onClick={handleDecline} style={{ width: '100%', padding: 10, background: '#fff', color: '#ef4444', border: '1px solid #ef4444', borderRadius: 8, fontSize: 14, cursor: 'pointer' }}>
              Decline this request
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}