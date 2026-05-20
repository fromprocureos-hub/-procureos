import { useState, useEffect } from 'react'
import { authAPI } from '../lib/api'
import toast from 'react-hot-toast'

export default function Settings() {
  const [team, setTeam] = useState([])
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', full_name: '', role: 'requester', spend_limit: 0 })
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '' })
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const company = JSON.parse(localStorage.getItem('company') || '{}')

  useEffect(() => { loadTeam() }, [])

  async function loadTeam() {
    try {
      const r = await authAPI.team()
      setTeam(r.data.team)
    } catch {}
  }

  async function handleInvite() {
    try {
      const r = await authAPI.invite(inviteForm)
      toast.success(`Invited! Temp password: ${r.data.temp_password}`)
      setShowInvite(false)
      setInviteForm({ email: '', full_name: '', role: 'requester', spend_limit: 0 })
      loadTeam()
    } catch (err) { toast.error(err.response?.data?.error || 'Failed') }
  }

  async function handleChangePassword() {
    if (!pwForm.current_password || !pwForm.new_password) return toast.error('Fill both fields')
    try {
      await authAPI.changePassword(pwForm)
      toast.success('Password changed!')
      setPwForm({ current_password: '', new_password: '' })
    } catch (err) { toast.error(err.response?.data?.error || 'Failed') }
  }

  async function toggleActive(member) {
    try {
      await authAPI.updateMember(member.id, { is_active: !member.is_active })
      toast.success('Updated')
      loadTeam()
    } catch { toast.error('Failed') }
  }

  const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }
  const labelStyle = { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#374151' }

  return (
    <div style={{ padding: 32, maxWidth: 800 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1e3a5f', marginBottom: 28 }}>Settings</h1>

      {/* Company Info */}
      <div style={{ background: '#fff', padding: 24, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, color: '#1e3a5f' }}>Company</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {[
            ['Company Name', company.name],
            ['Industry', company.industry_name],
            ['Your Role', user.role],
            ['Your Email', user.email],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 12, color: '#6b7280', textTransform: 'uppercase', marginBottom: 4 }}>{k}</div>
              <div style={{ fontWeight: 600, color: '#111827' }}>{v || '—'}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Change Password */}
      <div style={{ background: '#fff', padding: 24, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, color: '#1e3a5f' }}>Change Password</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>Current Password</label>
            <input type="password" style={inputStyle} value={pwForm.current_password} onChange={e => setPwForm({ ...pwForm, current_password: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>New Password</label>
            <input type="password" style={inputStyle} value={pwForm.new_password} onChange={e => setPwForm({ ...pwForm, new_password: e.target.value })} />
          </div>
        </div>
        <button onClick={handleChangePassword} style={{ padding: '10px 20px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
          Update Password
        </button>
      </div>

      {/* Team */}
      {user.role === 'admin' && (
        <div style={{ background: '#fff', padding: 24, borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1e3a5f' }}>Team Members</h2>
            <button onClick={() => setShowInvite(true)} style={{ padding: '8px 16px', background: '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
              + Invite Member
            </button>
          </div>

          {showInvite && (
            <div style={{ background: '#f8faff', padding: 20, borderRadius: 8, marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>Invite Team Member</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                  <label style={labelStyle}>Full Name</label>
                  <input style={inputStyle} value={inviteForm.full_name} onChange={e => setInviteForm({ ...inviteForm, full_name: e.target.value })} />
                </div>
                <div>
                  <label style={labelStyle}>Email</label>
                  <input type="email" style={inputStyle} value={inviteForm.email} onChange={e => setInviteForm({ ...inviteForm, email: e.target.value })} />
                </div>
                <div>
                  <label style={labelStyle}>Role</label>
                  <select style={inputStyle} value={inviteForm.role} onChange={e => setInviteForm({ ...inviteForm, role: e.target.value })}>
                    <option value="requester">Requester — can create RFQs</option>
                    <option value="approver">Approver — can approve</option>
                    <option value="admin">Admin — full access</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Spend Limit ($) — 0 = no limit</label>
                  <input type="number" style={inputStyle} value={inviteForm.spend_limit} onChange={e => setInviteForm({ ...inviteForm, spend_limit: e.target.value })} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={handleInvite} style={{ padding: '9px 18px', background: '#059669', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Send Invite</button>
                <button onClick={() => setShowInvite(false)} style={{ padding: '9px 18px', background: '#f3f4f6', color: '#374151', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
              </div>
            </div>
          )}

          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                {['Name', 'Email', 'Role', 'Status', 'Action'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {team.map(m => (
                <tr key={m.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '12px 14px', fontWeight: 600 }}>{m.full_name}</td>
                  <td style={{ padding: '12px 14px', color: '#6b7280', fontSize: 13 }}>{m.email}</td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: m.role === 'admin' ? '#ede9fe' : m.role === 'approver' ? '#d1fae5' : '#f3f4f6', color: m.role === 'admin' ? '#7c3aed' : m.role === 'approver' ? '#065f46' : '#374151' }}>
                      {m.role}
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ color: m.is_active ? '#059669' : '#ef4444', fontWeight: 600, fontSize: 13 }}>
                      {m.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    {m.id !== user.id && (
                      <button onClick={() => toggleActive(m)} style={{ padding: '5px 12px', background: '#f3f4f6', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>
                        {m.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}