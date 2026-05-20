import { useState, useRef } from 'react'
import { uploadAPI, vendorListsAPI, vendorsAPI } from '../lib/api'
import toast from 'react-hot-toast'


export default function SmartUpload() {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [listName, setListName] = useState('')
  const [importing, setImporting] = useState(false)
  const fileRef = useRef()

  async function handleFile(file) {
    if (!file) return
    setUploading(true)
    setResult(null)
    try {
      const r = await uploadAPI.file(file)
      setResult(r.data)
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Upload failed')
      setResult(data)
      const autoName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
      setListName(autoName)
    } catch (err) {
      toast.error(err.message || 'Upload failed. Try a clearer file.')
    } finally {
      setUploading(false)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  async function handleImport() {
    const vendors = result?.vendors || []
    if (!vendors.length) return toast.error('No vendors to import')
    if (!listName.trim()) return toast.error('Please enter a list name')

    setImporting(true)
    try {
      // Step 1 — create vendor list
      const listRes = await vendorListsAPI.create({
        name: listName.trim(),
        description: `Imported via Smart Upload on ${new Date().toLocaleDateString()}`
      })
      const listId = listRes.data.id

      // Step 2 — get all existing vendors
      const vr = await vendorsAPI.list({})
      const freshVendors = vr.data.vendors

      let added = 0
      let skipped = 0
      let addedToList = 0

      for (const v of vendors) {
        if (!v.name) continue
        let vendorId = null

        try {
          const res = await vendorsAPI.create({
            company_name: v.name,
            contact_email: v.email || '',
            phone: v.phone || '',
            categories: v.category || '',
            reliability_score: 80,
            notes: v.products?.map(p => `${p.name}: ${p.currency || ''} ${p.price || ''}`).join(', ') || ''
          })
          vendorId = res.data.id || res.data.vendor?.id
          added++
        } catch (err) {
          if (err.response?.status === 409) {
            vendorId = err.response?.data?.vendor_id || null
            if (!vendorId) {
              const existing = freshVendors.find(av =>
                av.contact_email === v.email ||
                av.company_name?.toLowerCase() === v.name?.toLowerCase()
              )
              if (existing) vendorId = existing.id
            }
            skipped++
          }
        }

        if (vendorId) {
          try {
            await vendorListsAPI.addMember(listId, vendorId)
            addedToList++
          } catch {}
        }
      }

      const parts = []
      if (added > 0) parts.push(`${added} new vendors created`)
      if (skipped > 0) parts.push(`${skipped} already existed`)
      toast.success(`List "${listName}" created with ${addedToList} vendors!`)
      setResult(null)
      setListName('')
    } catch (err) {
      toast.error('Failed to create list')
      console.error(err)
    } finally {
      setImporting(false)
    }
  }

  const vendors = result?.vendors || []

  return (
    <div style={{ padding: 32, maxWidth: 860, margin: '0 auto' }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1e3a5f' }}>📤 Smart Upload</h1>
        <p style={{ color: '#6b7280', marginTop: 4, fontSize: 14 }}>
          Upload any file — WhatsApp screenshot, invoice photo, CSV, Excel, PDF, or Word doc. AI extracts vendor information automatically and creates a vendor list.
        </p>
      </div>

      {/* Drop Zone */}
      {!result && (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current.click()}
          style={{
            border: `2px dashed ${dragging ? '#1e3a5f' : '#d1d5db'}`,
            borderRadius: 16,
            padding: 60,
            textAlign: 'center',
            cursor: 'pointer',
            background: dragging ? '#f0f4ff' : '#fafafa',
            transition: 'all 0.2s'
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept="image/*,.pdf,.csv,.xlsx,.xls,.docx,.doc"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
          {uploading ? (
            <div>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🔍</div>
              <p style={{ fontSize: 16, fontWeight: 600, color: '#1e3a5f' }}>AI is reading your file...</p>
              <p style={{ fontSize: 13, color: '#9ca3af', marginTop: 6 }}>Extracting vendor names, contacts and prices</p>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📂</div>
              <p style={{ fontSize: 16, fontWeight: 600, color: '#1e3a5f' }}>Drop any file here or click to upload</p>
              <p style={{ fontSize: 13, color: '#9ca3af', marginTop: 6 }}>AI reads any format and extracts vendor data automatically</p>
              <div style={{ marginTop: 20, display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
                {['📱 WhatsApp Screenshot', '🧾 Invoice PDF', '📊 Excel/CSV', '📄 Word Doc', '📸 Photo of Quote'].map(label => (
                  <span key={label} style={{ padding: '4px 12px', background: '#f3f4f6', borderRadius: 20, fontSize: 12, color: '#6b7280' }}>{label}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Result */}
      {result && (
        <div>
          {/* AI Summary */}
          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 12, padding: 20, marginBottom: 24, display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 28 }}>🤖</span>
            <div>
              <p style={{ fontWeight: 600, color: '#065f46', fontSize: 15, marginBottom: 4 }}>AI found {vendors.length} vendor{vendors.length !== 1 ? 's' : ''} in your file</p>
              <p style={{ color: '#047857', fontSize: 14 }}>{result.message}</p>
            </div>
          </div>

          {/* List name input */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }}>
              Name this vendor list *
            </label>
            <input
              value={listName}
              onChange={e => setListName(e.target.value)}
              placeholder="e.g. Chemical Suppliers, Cleaning Vendors..."
              style={{ width: '100%', padding: '10px 14px', border: '2px solid #1e3a5f', borderRadius: 8, fontSize: 14, fontWeight: 600 }}
            />
          </div>

          {/* Vendor Cards */}
          {vendors.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              {vendors.map((v, i) => (
                <div key={i} style={{ background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', padding: 20, marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: v.products?.length ? 12 : 0 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 16, color: '#1e3a5f' }}>🏢 {v.name || 'Unknown Vendor'}</div>
                      <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>
                        {v.phone && <span style={{ marginRight: 12 }}>📞 {v.phone}</span>}
                        {v.email && <span style={{ marginRight: 12 }}>✉️ {v.email}</span>}
                        {v.category && <span>🏷️ {v.category}</span>}
                      </div>
                    </div>
                    {v.products?.length > 0 && (
                      <span style={{ background: '#dbeafe', color: '#1d4ed8', fontSize: 12, padding: '3px 10px', borderRadius: 20, fontWeight: 600 }}>
                        {v.products.length} product{v.products.length !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>

                  {v.products?.length > 0 && (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: '#f9fafb' }}>
                          {['Product', 'Qty', 'Price', 'Notes'].map(h => (
                            <th key={h} style={{ padding: '7px 10px', textAlign: 'left', color: '#6b7280', fontWeight: 600, fontSize: 12 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {v.products.map((p, j) => (
                          <tr key={j} style={{ borderTop: '1px solid #f3f4f6' }}>
                            <td style={{ padding: '7px 10px', fontWeight: 600 }}>{p.name || '—'}</td>
                            <td style={{ padding: '7px 10px', color: '#6b7280' }}>{p.quantity ? `${p.quantity} ${p.unit || ''}` : '—'}</td>
                            <td style={{ padding: '7px 10px', color: '#059669', fontWeight: 600 }}>{p.price ? `${p.currency || 'Rs.'} ${p.price}` : '—'}</td>
                            <td style={{ padding: '7px 10px', color: '#9ca3af', fontSize: 12 }}>{p.notes || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={handleImport}
              disabled={importing || !listName.trim() || !vendors.length}
              style={{ flex: 1, padding: '14px', background: importing ? '#9ca3af' : '#059669', color: '#fff', border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 15, cursor: importing ? 'not-allowed' : 'pointer' }}
            >
              {importing ? 'Creating list...' : `✅ Create Vendor List with ${vendors.length} Vendor${vendors.length !== 1 ? 's' : ''}`}
            </button>
            <button
              onClick={() => { setResult(null); setListName('') }}
              style={{ padding: '14px 24px', background: '#f3f4f6', color: '#374151', border: 'none', borderRadius: 10, fontWeight: 600, fontSize: 14, cursor: 'pointer' }}
            >
              Upload Another
            </button>
          </div>
        </div>
      )}
    </div>
  )
}