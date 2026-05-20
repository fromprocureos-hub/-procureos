import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authAPI } from '../lib/api'
import toast from 'react-hot-toast'

export default function Register() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ company_name: '', email: '', password: '', full_name: '', industry_id: '' })
  const [industries, setIndustries] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    authAPI.industries().then(r => setIndustries(r.data.industries))
  }, [])

  const filtered = industries.filter(i => i.name.toLowerCase().includes(search.toLowerCase()))

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.industry_id) return toast.error('Please select an industry')
    setLoading(true)
    try {
      const res = await authAPI.register(form)
      localStorage.setItem('token', res.data.token)
      localStorage.setItem('user', JSON.stringify(res.data.user))
      localStorage.setItem('company', JSON.stringify(res.data.company))
      toast.success('Account created!')
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f0f4ff', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div style={{ background: '#fff', padding: 40, borderRadius: 12, width: 480, boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: '#1e3a5f', marginBottom: 8 }}>Create Account</h1>
        <p style={{ color: '#6b7280', marginBottom: 28 }}>Start your free trial — no credit card needed</p>
        <form onSubmit={handleSubmit}>
          {[
            { label: 'Company Name', key: 'company_name', type: 'text' },
            { label: 'Your Full Name', key: 'full_name', type: 'text' },
            { label: 'Email', key: 'email', type: 'email' },
            { label: 'Password', key: 'password', type: 'password' },
          ].map(f => (
            <div key={f.key} style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }}>{f.label}</label>
              <input
                type={f.type} required
                value={form[f.key]}
                onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }}
              />
            </div>
          ))}

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }}>Industry</label>
            <input
              placeholder="Search industry..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14, marginBottom: 6 }}
            />
            <select
              required
              value={form.industry_id}
              onChange={e => setForm({ ...form, industry_id: e.target.value })}
              size={5}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }}
            >
              <option value="">-- Select your industry --</option>
              {filtered.map(i => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </select>
            {form.industry_id && (
              <p style={{ fontSize: 12, color: '#059669', marginTop: 4 }}>
                ✓ {industries.find(i => i.id == form.industry_id)?.name}
              </p>
            )}
          </div>

          <button type="submit" disabled={loading} style={{
            width: '100%', padding: '12px', background: '#1e3a5f',
            color: '#fff', border: 'none', borderRadius: 8,
            fontSize: 15, fontWeight: 600, cursor: 'pointer'
          }}>
            {loading ? 'Creating account...' : 'Start Free Trial'}
          </button>
        </form>
        <p style={{ marginTop: 20, textAlign: 'center', fontSize: 14, color: '#6b7280' }}>
          Already have an account? <Link to="/login" style={{ color: '#2563eb' }}>Sign in</Link>
        </p>
      </div>
    </div>
  )
}