import { Link, useLocation, useNavigate } from 'react-router-dom'

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const company = JSON.parse(localStorage.getItem('company') || '{}')

  function logout() {
    localStorage.clear()
    navigate('/login')
  }

  const links = [
    { to: '/dashboard', label: '🏠 Dashboard' },
    { to: '/vendors', label: '🏢 Vendors' },
    { to: '/vendor-lists', label: '📋 Vendor Lists' },
    { to: '/smart-upload', label: '📤 Smart Upload' },
    { to: '/procurements/new', label: '➕ New RFQ' },
    { to: '/settings', label: '⚙️ Settings' },
  ]

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div style={{
        width: 220, background: '#1e3a5f', color: '#fff',
        display: 'flex', flexDirection: 'column', padding: '24px 0'
      }}>
        <div style={{ padding: '0 20px 24px', borderBottom: '1px solid #2d5a8e' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#60a5fa' }}>ProcureOS</div>
          <div style={{ fontSize: 12, color: '#93c5fd', marginTop: 4 }}>{company.name || 'Your Company'}</div>
        </div>
        <nav style={{ flex: 1, padding: '16px 0' }}>
          {links.map(l => (
            <Link key={l.to} to={l.to} style={{
              display: 'block', padding: '10px 20px',
              color: location.pathname === l.to ? '#60a5fa' : '#cbd5e1',
              background: location.pathname === l.to ? '#2d5a8e' : 'transparent',
              textDecoration: 'none', fontSize: 14, fontWeight: 500
            }}>{l.label}</Link>
          ))}
        </nav>
        <div style={{ padding: '16px 20px', borderTop: '1px solid #2d5a8e' }}>
          <div style={{ fontSize: 13, color: '#93c5fd' }}>{user.full_name || user.email}</div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{user.role}</div>
          <button onClick={logout} style={{
            marginTop: 10, width: '100%', padding: '8px',
            background: '#dc2626', color: '#fff', border: 'none',
            borderRadius: 6, cursor: 'pointer', fontSize: 13
          }}>Logout</button>
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {children}
      </div>
    </div>
  )
}