import { useState, useEffect } from 'react'
import { vendorsAPI } from '../lib/api'
import toast from 'react-hot-toast'

export default function Vendors() {
  const [vendors, setVendors] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ company_name: '', contact_email: '', phone: '', categories: '', reliability_score: 80, notes: '' })
  const [editId, setEditId] = useState(null)
  const [selected, setSelected] = useState([])
  const [deleting, setDeleting] = useState(false)

  useEffect(() => { load() }, [search])

  useEffect(() => {
    const interval = setInterval(() => { if (!deleting) load() }, 10000)
    return () => clearInterval(interval)
  }, [search, deleting])

  async function load() {
    setLoading(true)
    try {
      const r = await vendorsAPI.list({ search })
      setVendors(r.data.vendors)
      setSelected([])
    } catch { toast.error('Failed to load vendors') }
    finally { setLoading(false) }
  }

  async function handleSave() {
    try {
      if (editId) {
        await vendorsAPI.update(editId, form)
        toast.success('Vendor updated')
      } else {
        await vendorsAPI.create(form)
        toast.success('Vendor added')
      }
      setShowAdd(false)
      setEditId(null)
      setForm({ company_name: '', contact_email: '', phone: '', categories: '', reliability_score: 80, notes: '' })
      load()
    } catch (err) { toast.error(err.response?.data?.error || 'Failed to save') }
  }

  async function handleDelete(id) {
    if (!confirm('Remove this vendor?')) return
    try {
      await vendorsAPI.remove(id)
      toast.success('Vendor removed')
      load()
    } catch { toast.error('Failed to remove') }
  }

  async function handleDeleteSelected() {
    if (!confirm(`Delete ${selected.length} selected vendor${selected.length > 1 ? 's' : ''}?`)) return
    setDeleting(true)
    let done = 0
    const toDelete = [...selected]
    for (const id of toDelete) {
      try { await vendorsAPI.remove(id); done++ } catch {}
    }
    toast.success(`${done} vendor${done > 1 ? 's' : ''} deleted`)
    setDeleting(false)
    load()
  }

  async function handleCSV(e) {
    const file = e.target.files[0]
    if (!file) return
    try {
      const r = await vendorsAPI.importCSV(file)
      toast.success(r.data.message)
      load()
    } catch (err) { toast.error(err.response?.data?.error || 'Import failed') }
  }

  function startEdit(v) {
    setForm({ company_name: v.company_name, contact_email: v.contact_email || '', phone: v.phone || '', categories: v.categories?.join(',') || '', reliability_score: v.reliability_score, notes: v.notes || '' })
    setEditId(v.id)
    setShowAdd(true)
  }

  const allSelected = vendors.length > 0 && selected.length === vendors.length
  function toggleAll() { setSelected(allSelected ? [] : vendors.map(v => v.id)) }
  function toggleOne(id) { setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]) }

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1e3a5f' }}>Vendors</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          {selected.length > 0 && (
            <button onClick={handleDeleteSelected} style={{ padding: '10px 18px', background: '#fef2f2', color: '#ef4444', border: '2px solid #ef4444', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
              🗑️ Delete {selected.length} Selected
            </button>
          )}
          <label style={{ padding: '10px 18px', background: '#fff', border: '2px solid #1e3a5f', color: '#1e3a5f', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
            📥 Import CSV
            <input type="file" accept=".csv,.xlsx" onChange={handleCSV} style={{ display: 'none' }} />
          </label>
          <button onClick={() => { setShowAdd(true); setEditId(null); setForm({ company_name: '', contact_email: '', phone: '', categories: '', reliability_score: 80, notes: '' }) }} style={{ padding: '10px 18px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
            ➕ Add Vendor
          </button>
        </div>
      </div>

      <input placeholder="Search vendors..." value={search} onChange={e => setSearch(e.target.value)}
        style={{ width: '100%', padding: '10px 14px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14, marginBottom: 20 }} />

      {showAdd && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', padding: 32, borderRadius: 12, width: 480, maxHeight: '90vh', overflowY: 'auto' }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>{editId ? 'Edit Vendor' : 'Add Vendor'}</h2>
            {[
              { label: 'Company Name *', key: 'company_name', type: 'text' },
              { label: 'Email', key: 'contact_email', type: 'email' },
              { label: 'Phone', key: 'phone', type: 'text' },
              { label: 'Categories (comma separated)', key: 'categories', type: 'text' },
            ].map(f => (
              <div key={f.key} style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 5 }}>{f.label}</label>
                <input type={f.type} value={form[f.key]} onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', border: '1px solid #d1d5db', borderRadius: 7, fontSize: 14 }} />
              </div>
            ))}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 5 }}>Reliability Score: {form.reliability_score}%</label>
              <input type="range" min={0} max={100} value={form.reliability_score} onChange={e => setForm({ ...form, reliability_score: e.target.value })} style={{ width: '100%' }} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 5 }}>Notes</label>
              <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={3}
                style={{ width: '100%', padding: '9px 12px', border: '1px solid #d1d5db', borderRadius: 7, fontSize: 14 }} />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={handleSave} style={{ flex: 1, padding: '11px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Save</button>
              <button onClick={() => { setShowAdd(false); setEditId(null) }} style={{ flex: 1, padding: '11px', background: '#f3f4f6', color: '#374151', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div style={{ background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#9ca3af' }}>Loading...</div>
        ) : !vendors.length ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#9ca3af' }}>
            <div style={{ fontSize: 40 }}>🏢</div>
            <p style={{ marginTop: 12 }}>No vendors yet. Add your first vendor or import a CSV.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={{ padding: '12px 16px', width: 40 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} style={{ cursor: 'pointer', width: 16, height: 16 }} />
                </th>
                {['Company', 'Email', 'Categories', 'Reliability', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vendors.map(v => (
                <tr key={v.id} style={{ borderTop: '1px solid #f3f4f6', background: selected.includes(v.id) ? '#f0f4ff' : 'transparent' }}>
                  <td style={{ padding: '14px 16px' }}>
                    <input type="checkbox" checked={selected.includes(v.id)} onChange={() => toggleOne(v.id)} style={{ cursor: 'pointer', width: 16, height: 16 }} />
                  </td>
                  <td style={{ padding: '14px 16px', fontWeight: 600 }}>{v.company_name}</td>
                  <td style={{ padding: '14px 16px', color: '#6b7280', fontSize: 13 }}>{v.contact_email || '—'}</td>
                  <td style={{ padding: '14px 16px', fontSize: 13, color: '#6b7280' }}>{v.categories?.slice(0, 3).join(', ') || '—'}</td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{ color: v.reliability_score >= 80 ? '#10b981' : '#f59e0b', fontWeight: 600 }}>{v.reliability_score}%</span>
                  </td>
                  <td style={{ padding: '14px 16px', display: 'flex', gap: 8 }}>
                    <button onClick={() => startEdit(v)} style={{ padding: '6px 12px', background: '#eff6ff', color: '#2563eb', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>Edit</button>
                    <button onClick={() => handleDelete(v.id)} style={{ padding: '6px 12px', background: '#fef2f2', color: '#ef4444', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>Remove</button>
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