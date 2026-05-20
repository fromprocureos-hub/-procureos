import { useState, useEffect } from 'react'
import { vendorListsAPI, vendorsAPI } from '../lib/api'
import toast from 'react-hot-toast'

export default function VendorLists() {
  const [lists, setLists] = useState([])
  const [allVendors, setAllVendors] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [expandedList, setExpandedList] = useState(null)
  const [showAddVendor, setShowAddVendor] = useState(null)
  const [csvPreview, setCsvPreview] = useState(null)
  const [csvListName, setCsvListName] = useState('')
  const [importing, setImporting] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    const [lr, vr] = await Promise.all([
      vendorListsAPI.list(),
      vendorsAPI.list({})
    ])
    setLists(lr.data.lists)
    setAllVendors(vr.data.vendors)
  }

  async function handleCreate() {
    if (!newName.trim()) return toast.error('Enter a list name')
    try {
      await vendorListsAPI.create({ name: newName, description: newDesc })
      toast.success('List created!')
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
      load()
    } catch { toast.error('Failed to create') }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this list?')) return
    try {
      await vendorListsAPI.remove(id)
      toast.success('Deleted')
      load()
    } catch { toast.error('Failed') }
  }

  async function handleAddVendor(listId, vendorId) {
    try {
      await vendorListsAPI.addMember(listId, vendorId)
      toast.success('Vendor added to list')
      load()
    } catch { toast.error('Failed') }
  }

  async function handleRemoveVendor(listId, vendorId) {
    try {
      await vendorListsAPI.removeMember(listId, vendorId)
      toast.success('Removed')
      load()
    } catch { toast.error('Failed') }
  }

  async function handleCSVUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    const Papa = (await import('papaparse')).default
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const rows = results.data
        if (!rows.length) return
        const headers = Object.keys(rows[0])

        function findCol(keywords) {
          return headers.find(h =>
            keywords.some(k => h.toLowerCase().replace(/[\s_\-]/g, '').includes(k))
          )
        }

        function findEmailCol() {
          const byName = findCol(['email', 'mail', 'emailaddress', 'contactemail'])
          if (byName) return byName
          return headers.find(h =>
            rows.filter(r => (r[h] || '').includes('@')).length > rows.length * 0.3
          )
        }

        const nameCol     = findCol(['vendorname', 'companyname', 'company', 'name', 'vendor', 'supplier', 'firm', 'business'])
        const emailCol    = findEmailCol()
        const categoryCol = findCol(['category', 'categories', 'type', 'industry', 'sector', 'product'])
        const phoneCol    = findCol(['phone', 'mobile', 'tel', 'number', 'cell'])

        const parsed = rows.map(row => {
          const name     = nameCol     ? (row[nameCol]     || '').trim() : ''
          const email    = emailCol    ? (row[emailCol]    || '').trim() : ''
          const category = categoryCol ? (row[categoryCol] || '').trim() : ''
          const phone    = phoneCol    ? (row[phoneCol]    || '').trim() : ''
          const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
          return { name, email, category, phone, valid: !!name && emailValid }
        })

        const autoName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
        setCsvListName(autoName)
        setCsvPreview(parsed)
      }
    })
    e.target.value = ''
  }

  async function handleCSVImport() {
    const valid = csvPreview.filter(v => v.valid)
    if (!valid.length) return toast.error('No valid vendors to import')
    if (!csvListName.trim()) return toast.error('Please enter a list name')

    setImporting(true)
    try {
      const listRes = await vendorListsAPI.create({
        name: csvListName.trim(),
        description: `Imported from CSV on ${new Date().toLocaleDateString()}`
      })
      const listId = listRes.data.id

      const vr = await vendorsAPI.list({})
      const freshVendors = vr.data.vendors

      let added = 0
      let skipped = 0
      let addedToList = 0

      for (const v of valid) {
        let vendorId = null
        try {
          const res = await vendorsAPI.create({
            company_name: v.name,
            contact_email: v.email,
            phone: v.phone || '',
            categories: v.category || '',
            reliability_score: 80,
            notes: ''
          })
          vendorId = res.data.id || res.data.vendor?.id
          added++
        } catch (err) {
          if (err.response?.status === 409) {
            const existing = freshVendors.find(av =>
              av.contact_email === v.email ||
              av.company_name?.toLowerCase() === v.name?.toLowerCase()
            )
            if (existing) vendorId = existing.id
            skipped++
          }
        }

        if (vendorId) {
          try {
            await vendorListsAPI.addMember(listId, vendorId)
            addedToList++
          } catch (err) {
            console.error('Failed to add to list:', vendorId, err.response?.data)
          }
        }
      }

      toast.success(`List "${csvListName}" created with ${addedToList} vendors!`)
      setCsvPreview(null)
      setCsvListName('')
      load()
    } catch (err) {
      toast.error('Failed to create list')
      console.error(err)
    } finally {
      setImporting(false)
    }
  }

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1e3a5f' }}>Vendor Lists</h1>
          <p style={{ color: '#6b7280', marginTop: 4, fontSize: 14 }}>Group vendors into lists to use when sending RFQs</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <a href="/vendors_template.csv" download style={{ padding: '10px 18px', background: '#fff', border: '2px solid #1e3a5f', color: '#1e3a5f', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600, textDecoration: 'none' }}>
            📥 Download Template
          </a>
          <label style={{ padding: '10px 18px', background: '#fff', border: '2px solid #1e3a5f', color: '#1e3a5f', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
            📂 Upload CSV
            <input type="file" accept=".csv" onChange={handleCSVUpload} style={{ display: 'none' }} />
          </label>
          <button onClick={() => setShowCreate(true)} style={{ padding: '10px 18px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
            + New List
          </button>
        </div>
      </div>

      {csvPreview && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', padding: 32, borderRadius: 12, width: 580, maxHeight: '85vh', overflowY: 'auto' }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Import CSV as New List</h2>
            <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 20 }}>
              Found <strong>{csvPreview.length}</strong> rows — <strong style={{ color: '#059669' }}>{csvPreview.filter(v => v.valid).length} valid</strong>, <strong style={{ color: '#ef4444' }}>{csvPreview.filter(v => !v.valid).length} skipped</strong>.
            </p>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }}>Name this vendor list *</label>
              <input
                value={csvListName}
                onChange={e => setCsvListName(e.target.value)}
                placeholder="e.g. Cleaning Suppliers, Chemical Vendors..."
                style={{ width: '100%', padding: '10px 12px', border: '2px solid #1e3a5f', borderRadius: 8, fontSize: 14, fontWeight: 600 }}
              />
            </div>
            <div style={{ maxHeight: 300, overflowY: 'auto', marginBottom: 20 }}>
              {csvPreview.map((v, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid #f3f4f6', fontSize: 13 }}>
                  <span style={{ fontSize: 16 }}>{v.valid ? '✅' : '⚠️'}</span>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontWeight: 600 }}>{v.name || 'No name'}</span>
                    <span style={{ color: '#6b7280', marginLeft: 8 }}>{v.email || 'missing email'}</span>
                    {v.category && <span style={{ color: '#9ca3af', marginLeft: 8 }}>— {v.category}</span>}
                  </div>
                  {!v.valid && <span style={{ color: '#ef4444', fontSize: 12 }}>skipped</span>}
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={handleCSVImport} disabled={importing || !csvListName.trim()}
                style={{ flex: 1, padding: '11px', background: importing ? '#9ca3af' : '#059669', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: importing ? 'not-allowed' : 'pointer' }}>
                {importing ? 'Creating list...' : `✅ Create List with ${csvPreview.filter(v => v.valid).length} Vendors`}
              </button>
              <button onClick={() => { setCsvPreview(null); setCsvListName('') }}
                style={{ flex: 1, padding: '11px', background: '#f3f4f6', color: '#374151', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {showCreate && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', padding: 32, borderRadius: 12, width: 440 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Create Vendor List</h2>
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>List Name *</label>
              <input value={newName} onChange={e => setNewName(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }}
                placeholder="e.g. Cleaning Suppliers" />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Description</label>
              <input value={newDesc} onChange={e => setNewDesc(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }}
                placeholder="Optional description" />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={handleCreate} style={{ flex: 1, padding: '11px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Create</button>
              <button onClick={() => setShowCreate(false)} style={{ flex: 1, padding: '11px', background: '#f3f4f6', color: '#374151', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {!lists.length ? (
        <div style={{ background: '#fff', padding: 60, borderRadius: 12, textAlign: 'center', color: '#9ca3af' }}>
          <div style={{ fontSize: 48 }}>📋</div>
          <p style={{ marginTop: 12 }}>No vendor lists yet. Create one to get started.</p>
        </div>
      ) : (
        lists.map(list => (
          <div key={list.id} style={{ background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: 16 }}>
            <div style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
              onClick={() => setExpandedList(expandedList === list.id ? null : list.id)}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16, color: '#1e3a5f' }}>📋 {list.name}</div>
                {list.description && <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>{list.description}</div>}
                <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>{list.vendor_count} vendor{list.vendor_count !== 1 ? 's' : ''}</div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button onClick={e => { e.stopPropagation(); setShowAddVendor(list.id) }}
                  style={{ padding: '6px 14px', background: '#eff6ff', color: '#2563eb', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                  + Add Vendor
                </button>
                <button onClick={e => { e.stopPropagation(); handleDelete(list.id) }}
                  style={{ padding: '6px 14px', background: '#fef2f2', color: '#ef4444', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
                  Delete
                </button>
                <span style={{ fontSize: 18, color: '#9ca3af' }}>{expandedList === list.id ? '▲' : '▼'}</span>
              </div>
            </div>

            {expandedList === list.id && (
              <div style={{ borderTop: '1px solid #f3f4f6', padding: '16px 24px' }}>
                {!list.vendors.length ? (
                  <p style={{ color: '#9ca3af', fontSize: 14 }}>No vendors in this list yet.</p>
                ) : (
                  list.vendors.map(v => (
                    <div key={v.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f9fafb' }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{v.company_name}</div>
                        <div style={{ fontSize: 12, color: '#6b7280' }}>{v.contact_email || 'No email'}</div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 13, color: v.reliability_score >= 80 ? '#059669' : '#f59e0b', fontWeight: 600 }}>{v.reliability_score}%</span>
                        <button onClick={() => handleRemoveVendor(list.id, v.id)}
                          style={{ padding: '4px 10px', background: '#fef2f2', color: '#ef4444', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>
                          Remove
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {showAddVendor === list.id && (
              <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                <div style={{ background: '#fff', padding: 32, borderRadius: 12, width: 480, maxHeight: '80vh', overflowY: 'auto' }}>
                  <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Add Vendor to "{list.name}"</h2>
                  {allVendors.filter(v => !list.vendors.find(lv => lv.id === v.id)).map(v => (
                    <div key={v.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
                      <div>
                        <div style={{ fontWeight: 600 }}>{v.company_name}</div>
                        <div style={{ fontSize: 12, color: '#6b7280' }}>{v.contact_email || 'No email'}</div>
                      </div>
                      <button onClick={() => { handleAddVendor(list.id, v.id); setShowAddVendor(null) }}
                        style={{ padding: '6px 14px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
                        Add
                      </button>
                    </div>
                  ))}
                  {allVendors.filter(v => !list.vendors.find(lv => lv.id === v.id)).length === 0 && (
                    <p style={{ color: '#9ca3af', textAlign: 'center', padding: 20 }}>All vendors are already in this list.</p>
                  )}
                  <button onClick={() => setShowAddVendor(null)} style={{ marginTop: 16, width: '100%', padding: '10px', background: '#f3f4f6', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>Close</button>
                </div>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}