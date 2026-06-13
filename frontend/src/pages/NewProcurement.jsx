import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { procurementsAPI, vendorListsAPI, specAPI } from '../lib/api'
import toast from 'react-hot-toast'
import api from '../lib/api'

export default function NewProcurement() {
  const navigate = useNavigate()
  const company = JSON.parse(localStorage.getItem('company') || '{}')
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [specWarnings, setSpecWarnings] = useState([])
  const [vendorWarning, setVendorWarning] = useState(null)
  const [vendorWarningLoading, setVendorWarningLoading] = useState(false)
  const [showSpecModal, setShowSpecModal] = useState(false)
  const [specChecking, setSpecChecking] = useState(false)
  const [rewriting, setRewriting] = useState(false)
  const [procurement, setProcurement] = useState(null)
  const [vendors, setVendors] = useState([])
  const [selectedVendors, setSelectedVendors] = useState([])
  const [vendorLists, setVendorLists] = useState([])
  const [selectedList, setSelectedList] = useState(null)
  const [form, setForm] = useState({
    title: '', item_name: '', quantity: 1, unit: 'units',
    category_tag: '', notes: '', deadline: '', required_by: '',
    rfq_template: company.default_template || 'Standard',
    price_weight: company.price_weight || 80,
    delivery_weight: company.delivery_weight || 80,
    quality_weight: company.quality_weight || 80,
    compliance_weight: company.compliance_weight || 50,
  })

  async function handleCreate(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const r = await procurementsAPI.create(form)
      setProcurement(r.data.procurement)
      const [vr, lr] = await Promise.all([
        procurementsAPI.findSuppliers(r.data.procurement.id),
        vendorListsAPI.list()
      ])
      setVendors(vr.data.vendors)
      setVendorLists(lr.data.lists)
      setSelectedVendors(vr.data.vendors.filter(v => v.pre_selected).map(v => v.vendor_id))
      setStep(2)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to create')
    } finally { setLoading(false) }
  }

  async function handleSelectVendors() {
    if (!selectedVendors.length) return toast.error('Select at least one vendor')
    setLoading(true)
    try {
      await procurementsAPI.selectVendors(procurement.id, selectedVendors)
      setStep(3)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed')
    } finally { setLoading(false) }
  }

  async function handleSendRFQ() {
    setSpecChecking(true)
    try {
      const r = await specAPI.check({
        item_name: procurement.item_name,
        quantity: procurement.quantity,
        unit: procurement.unit,
        deadline: procurement.deadline,
        notes: procurement.notes
      })
      setSpecChecking(false)
      if (r.data.warnings && r.data.warnings.length > 0) {
        setSpecWarnings(r.data.warnings)
        setShowSpecModal(true)
        return
      }
    } catch {
      setSpecChecking(false)
    }
    await doSendRFQ()
  }

  async function handleAIFix() {
    setRewriting(true)
    try {
      const r = await api.post('/api/rfq-rewrite', {
        item_name: procurement.item_name,
        quantity: procurement.quantity,
        unit: procurement.unit,
        deadline: procurement.deadline,
        notes: procurement.notes,
        warnings: specWarnings
      })
      const rw = r.data.rewritten
      // Update the procurement object with rewritten values
      setProcurement(prev => ({
        ...prev,
        item_name: rw.item_name || prev.item_name,
        quantity: rw.quantity || prev.quantity,
        unit: rw.unit || prev.unit,
        deadline: rw.deadline || prev.deadline,
        notes: rw.notes || prev.notes,
      }))
      // Also update form so if user goes back it's prefilled
      setForm(prev => ({
        ...prev,
        item_name: rw.item_name || prev.item_name,
        quantity: rw.quantity || prev.quantity,
        unit: rw.unit || prev.unit,
        deadline: rw.deadline || prev.deadline,
        notes: rw.notes || prev.notes,
      }))
      setShowSpecModal(false)
      toast.success(rw.changes_summary || 'RFQ improved by AI!')
      // Auto-proceed to send
      await doSendRFQ()
    } catch (err) {
      toast.error('AI rewrite failed, please fix manually')
    } finally {
      setRewriting(false)
    }
  }

  async function doSendRFQ() {
    setShowSpecModal(false)
    setLoading(true)
    try {
      const r = await procurementsAPI.sendRFQ(procurement.id)
      toast.success(r.data.message)
      navigate(`/procurements/${procurement.id}`)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to send')
    } finally { setLoading(false) }
  }

  async function toggleVendor(id) {
    const updated = selectedVendors.includes(id)
      ? selectedVendors.filter(v => v !== id)
      : [...selectedVendors, id]
    setSelectedVendors(updated)
    setVendorWarning(null)

    if (updated.length === 1) {
      const selectedVendor = vendors.find(v => v.vendor_id === updated[0])
      if (!selectedVendor) return
      setVendorWarningLoading(true)
      try {
        const res = await api.post('/api/vendor-warning', {
          vendor_name: selectedVendor.vendor_name,
          vendor_reliability: selectedVendor.reliability_score,
          category: form.category_tag || '',
          deadline: procurement?.deadline || form.deadline || '',
          item_name: procurement?.item_name || form.item_name || '',
          available_vendors: vendors.filter(v => v.vendor_id !== updated[0]).map(v => v.vendor_name)
        })
        setVendorWarning(res.data)
      } catch {
        setVendorWarning({
          warning: `${selectedVendor.vendor_name} is your only option if something goes wrong. Adding 2 more vendors takes one click and protects your deadline.`,
          risk_level: 'medium'
        })
      } finally {
        setVendorWarningLoading(false)
      }
    }
  }

  const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }
  const labelStyle = { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }

  return (
    <div style={{ padding: 32, maxWidth: 700 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
        {['1. Details', '2. Select Vendors', '3. Send RFQ'].map((s, i) => (
          <div key={s} style={{
            padding: '8px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600,
            background: step === i + 1 ? '#1e3a5f' : step > i + 1 ? '#10b981' : '#f3f4f6',
            color: step >= i + 1 ? '#fff' : '#6b7280'
          }}>{s}</div>
        ))}
      </div>

      {step === 1 && (
        <div style={{ background: '#fff', padding: 32, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 24, color: '#1e3a5f' }}>Procurement Details</h2>
          <form onSubmit={handleCreate}>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Title *</label>
              <input required style={inputStyle} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Q3 Office Supplies" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={labelStyle}>Item Name *</label>
                <input required style={inputStyle} value={form.item_name} onChange={e => setForm({ ...form, item_name: e.target.value })} placeholder="e.g. A4 Paper" />
              </div>
              <div>
                <label style={labelStyle}>Quantity *</label>
                <input required type="number" min={1} style={inputStyle} value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })} />
              </div>
              <div>
                <label style={labelStyle}>Unit</label>
                <input style={inputStyle} value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })} placeholder="units, kg, boxes" />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={labelStyle}>Category</label>
                <input style={inputStyle} value={form.category_tag} onChange={e => setForm({ ...form, category_tag: e.target.value })} placeholder="e.g. Office Supplies" />
              </div>
              <div>
                <label style={labelStyle}>Quote Deadline</label>
                <input type="datetime-local" style={inputStyle} value={form.deadline} onChange={e => setForm({ ...form, deadline: e.target.value })} />
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Notes / Specifications</label>
              <textarea rows={3} style={inputStyle} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder="Any specific requirements..." />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>RFQ Template</label>
              <select style={inputStyle} value={form.rfq_template} onChange={e => setForm({ ...form, rfq_template: e.target.value })}>
                <option value="Standard">Standard — Basic quote request</option>
                <option value="Advanced">Advanced — Includes capacity, certifications, experience</option>
              </select>
            </div>
            <div style={{ background: '#f8faff', padding: 16, borderRadius: 8, marginBottom: 20 }}>
              <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#1e3a5f' }}>Scoring Weights (AI ranking criteria)</p>
              {[
                { label: 'Price', key: 'price_weight' },
                { label: 'Delivery Speed', key: 'delivery_weight' },
                { label: 'Quality/Reliability', key: 'quality_weight' },
                { label: 'Compliance', key: 'compliance_weight' },
              ].map(w => (
                <div key={w.key} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                  <span style={{ width: 130, fontSize: 13, color: '#374151' }}>{w.label}</span>
                  <input type="range" min={0} max={100} value={form[w.key]} onChange={e => setForm({ ...form, [w.key]: parseInt(e.target.value) })} style={{ flex: 1 }} />
                  <span style={{ width: 36, fontSize: 13, fontWeight: 600, color: '#1e3a5f' }}>{form[w.key]}</span>
                </div>
              ))}
            </div>
            <button type="submit" disabled={loading} style={{ width: '100%', padding: 12, background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: 'pointer' }}>
              {loading ? 'Creating...' : 'Continue → Select Vendors'}
            </button>
          </form>
        </div>
      )}

      {step === 2 && (
        <div style={{ background: '#fff', padding: 32, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: '#1e3a5f' }}>Select Vendors</h2>
          <p style={{ color: '#6b7280', marginBottom: 20, fontSize: 14 }}>Pick a Vendor List — AI will pre-select top 3. You can adjust.</p>

          {vendorLists.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#374151' }}>Choose a Vendor List</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                {vendorLists.map(list => (
                  <button key={list.id} onClick={async () => {
                    setSelectedList(list.id)
                    const r = await vendorListsAPI.topVendors(list.id)
                    const listVendors = r.data.all_vendors.map(v => ({
                      vendor_id: v.id,
                      vendor_name: v.company_name,
                      vendor_email: v.contact_email,
                      reliability_score: v.reliability_score,
                      pre_selected: r.data.top3.includes(v.id),
                      is_recommended: r.data.top3.includes(v.id)
                    }))
                    setVendors(listVendors)
                    setSelectedVendors(r.data.top3)
                    setVendorWarning(null)
                  }} style={{
                    padding: '8px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    background: selectedList === list.id ? '#1e3a5f' : '#f3f4f6',
                    color: selectedList === list.id ? '#fff' : '#374151',
                    border: 'none'
                  }}>
                    📋 {list.name} ({list.vendor_count})
                  </button>
                ))}
                <button onClick={() => {
                  setSelectedList('all')
                  procurementsAPI.findSuppliers(procurement.id).then(vr => {
                    setVendors(vr.data.vendors)
                    setSelectedVendors(vr.data.vendors.filter(v => v.pre_selected).map(v => v.vendor_id))
                    setVendorWarning(null)
                  })
                }} style={{
                  padding: '8px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  background: selectedList === 'all' ? '#1e3a5f' : '#f3f4f6',
                  color: selectedList === 'all' ? '#fff' : '#374151',
                  border: 'none'
                }}>
                  🏢 All Vendors
                </button>
              </div>
            </div>
          )}

          {!vendors.length ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>
              <p>{vendorLists.length === 0 ? 'No vendor lists yet.' : 'Select a list above to see vendors.'} <a href="/vendors" style={{ color: '#2563eb' }}>Add vendors first →</a></p>
            </div>
          ) : (
            vendors.map(v => (
              <div key={v.vendor_id} onClick={() => toggleVendor(v.vendor_id)} style={{
                padding: 16, border: `2px solid ${selectedVendors.includes(v.vendor_id) ? '#1e3a5f' : '#e5e7eb'}`,
                borderRadius: 10, marginBottom: 10, cursor: 'pointer',
                background: selectedVendors.includes(v.vendor_id) ? '#f0f4ff' : '#fff',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{v.vendor_name}</div>
                  <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>{v.vendor_email || 'No email'}</div>
                  {v.is_recommended && <span style={{ fontSize: 11, background: '#d1fae5', color: '#065f46', padding: '2px 8px', borderRadius: 10, marginTop: 4, display: 'inline-block' }}>⭐ AI Top Pick</span>}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 13, color: '#6b7280' }}>Reliability</div>
                  <div style={{ fontWeight: 700, color: '#1e3a5f' }}>{v.reliability_score}%</div>
                  <div style={{ fontSize: 12, marginTop: 4, color: selectedVendors.includes(v.vendor_id) ? '#059669' : '#9ca3af' }}>
                    {selectedVendors.includes(v.vendor_id) ? '✓ Selected' : 'Click to select'}
                  </div>
                </div>
              </div>
            ))
          )}

          {selectedVendors.length === 1 && vendors.length > 1 && (
            <div style={{
              background: vendorWarning?.risk_level === 'high' ? '#fef2f2' : '#fffbeb',
              border: `1px solid ${vendorWarning?.risk_level === 'high' ? '#fca5a5' : '#fcd34d'}`,
              borderRadius: 10, padding: 16, marginTop: 16
            }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: vendorWarning?.risk_level === 'high' ? '#dc2626' : '#92400e', marginBottom: 6 }}>
                {vendorWarning?.risk_level === 'high' ? '🔴' : '⚠️'} Single Vendor Risk Detected
              </div>
              <div style={{ fontSize: 13, color: '#92400e', marginBottom: 12, lineHeight: 1.6 }}>
                {vendorWarningLoading ? '🔍 Analyzing risk...' : vendorWarning?.warning || `If ${vendors.find(v => v.vendor_id === selectedVendors[0])?.vendor_name} is busy or raises their price, you have no backup.`}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => {
                  const unselected = vendors.filter(v => !selectedVendors.includes(v.vendor_id))
                  const toAdd = unselected.slice(0, 2).map(v => v.vendor_id)
                  setSelectedVendors(prev => [...prev, ...toAdd])
                  setVendorWarning(null)
                  toast.success(`Added ${toAdd.length} more vendor${toAdd.length > 1 ? 's' : ''}`)
                }} style={{ padding: '8px 16px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
                  ✅ Add 2 More Vendors
                </button>
                <button onClick={handleSelectVendors} style={{ padding: '8px 16px', background: '#f3f4f6', color: '#6b7280', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
                  Proceed with one
                </button>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button onClick={handleSelectVendors} disabled={loading || !selectedVendors.length} style={{ flex: 1, padding: 12, background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
              {loading ? 'Saving...' : `Continue → Review RFQ (${selectedVendors.length} selected)`}
            </button>
          </div>
        </div>
      )}

      {/* SPEC MODAL */}
      {showSpecModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, width: 520, maxHeight: '80vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
            <div style={{ background: '#1e3a5f', padding: '20px 24px', borderRadius: '12px 12px 0 0' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>⚠️ Spec Intelligence Warning</div>
              <div style={{ fontSize: 13, color: '#93c5fd', marginTop: 4 }}>AI found issues that may cost you money or reduce supplier responses</div>
            </div>
            <div style={{ padding: 24 }}>
              {specWarnings.map((w, i) => (
                <div key={i} style={{
                  background: w.severity === 'high' ? '#fef2f2' : '#fffbeb',
                  border: `1px solid ${w.severity === 'high' ? '#fca5a5' : '#fcd34d'}`,
                  borderRadius: 8, padding: 14, marginBottom: 12
                }}>
                  <div style={{ fontWeight: 700, fontSize: 15, color: w.severity === 'high' ? '#dc2626' : '#92400e', marginBottom: 8 }}>
                    {w.severity === 'high' ? '🔴' : '🟡'} {w.message}
                  </div>
                  <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 8, lineHeight: 1.5 }}>
                    <strong>Why it matters:</strong> {w.impact}
                  </div>
                  <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.5 }}>
                    <strong>Fix:</strong> {w.fix}
                  </div>
                </div>
              ))}

              {/* AI FIX BUTTON */}
              <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 10, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0369a1', marginBottom: 6 }}>✨ Let AI fix it for you</div>
                <div style={{ fontSize: 13, color: '#0c4a6e', marginBottom: 12 }}>AI will rewrite your RFQ applying all fixes above, then send automatically.</div>
                <button onClick={handleAIFix} disabled={rewriting} style={{
                  width: '100%', padding: 12, background: '#0369a1', color: '#fff',
                  border: 'none', borderRadius: 8, fontWeight: 700, fontSize: 14, cursor: 'pointer'
                }}>
                  {rewriting ? '✨ Rewriting RFQ...' : '✨ Fix & Send with AI'}
                </button>
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={() => { setShowSpecModal(false); setStep(1) }} style={{
                  flex: 1, padding: 12, background: '#f3f4f6', color: '#374151',
                  border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer'
                }}>
                  ← Fix Manually
                </button>
                <button onClick={doSendRFQ} style={{
                  flex: 1, padding: 12, background: '#6b7280', color: '#fff',
                  border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer'
                }}>
                  Send Anyway →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {step === 3 && (
        <div style={{ background: '#fff', padding: 32, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: '#1e3a5f' }}>
            {loading ? 'Sending...' : specChecking ? '🔍 Checking specs...' : '📧 Send RFQ to All Selected Vendors'}
          </h2>
          <p style={{ color: '#6b7280', marginBottom: 20, fontSize: 14 }}>Review the details below. Click Send to email all selected vendors.</p>
          <div style={{ background: '#f8faff', padding: 20, borderRadius: 8, marginBottom: 20 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {[
                ['Item', procurement?.item_name],
                ['Quantity', `${procurement?.quantity} ${procurement?.unit}`],
                ['Template', procurement?.rfq_template],
                ['Deadline', procurement?.deadline ? new Date(procurement.deadline).toLocaleDateString() : 'Not set'],
                ['Vendors', `${selectedVendors.length} selected`],
              ].map(([k, v]) => (
                <div key={k}>
                  <div style={{ fontSize: 12, color: '#6b7280', textTransform: 'uppercase' }}>{k}</div>
                  <div style={{ fontWeight: 600, color: '#111827', marginTop: 2 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
          <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', padding: 14, borderRadius: 8, marginBottom: 20, fontSize: 13, color: '#92400e' }}>
            ⚠️ This will send real emails to vendors. You are in control — AI only ranks, you decide.
          </div>
          <button onClick={handleSendRFQ} disabled={loading} style={{ width: '100%', padding: 12, background: '#059669', color: '#fff', border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: 'pointer' }}>
            {loading ? 'Sending...' : '📧 Send RFQ to All Selected Vendors'}
          </button>
        </div>
      )}
    </div>
  )
}