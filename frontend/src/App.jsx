import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Vendors from './pages/Vendors'
import VendorLists from './pages/VendorLists'
import SmartUpload from './pages/SmartUpload'
import NewProcurement from './pages/NewProcurement'
import ProcurementDetail from './pages/ProcurementDetail'
import Settings from './pages/Settings'
import QuotePortal from './pages/QuotePortal'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/quote/:token" element={<QuotePortal />} />
        <Route path="/" element={<ProtectedRoute />}>
          <Route index element={<Navigate to="/dashboard" />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="vendors" element={<Vendors />} />
          <Route path="vendor-lists" element={<VendorLists />} />
          <Route path="smart-upload" element={<SmartUpload />} />
          <Route path="procurements/new" element={<NewProcurement />} />
          <Route path="procurements/:id" element={<ProcurementDetail />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}