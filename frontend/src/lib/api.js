jimport axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('company')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

export const authAPI = {
  register:       data  => api.post('/auth/register', data),
  login:          data  => api.post('/auth/login', data),
  me:             ()    => api.get('/auth/me'),
  industries:     ()    => api.get('/auth/industries'),
  invite:         data  => api.post('/auth/invite', data),
  team:           ()    => api.get('/auth/team'),
  updateMember:   (id, data) => api.put(`/auth/team/${id}`, data),
  changePassword: data  => api.post('/auth/change-password', data),
}

export const vendorListsAPI = {
  list:         ()              => api.get('/vendor-lists'),
  create:       data            => api.post('/vendor-lists', data),
  remove:       id              => api.delete(`/vendor-lists/${id}`),
  addMember:    (id, vendor_id) => api.post(`/vendor-lists/${id}/members`, { vendor_id }),
  removeMember: (id, vendor_id) => api.delete(`/vendor-lists/${id}/members/${vendor_id}`),
  topVendors:   id              => api.get(`/vendor-lists/${id}/top-vendors`),
}

export const vendorsAPI = {
  list:      params => api.get('/vendors', { params }),
  create:    data   => api.post('/vendors', data),
  update:    (id, data) => api.put(`/vendors/${id}`, data),
  remove:    id     => api.delete(`/vendors/${id}`),
  importCSV: file   => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/vendors/import-csv', fd)
  },
}

export const procurementsAPI = {
  list:          params => api.get('/procurements', { params }),
  create:        data   => api.post('/procurements', data),
  get:           id     => api.get(`/procurements/${id}`),
  update:        (id, data) => api.put(`/procurements/${id}`, data),
  findSuppliers: id     => api.get(`/procurements/${id}/find-suppliers`),
  selectVendors: (id, vendor_ids) => api.post(`/procurements/${id}/select-vendors`, { vendor_ids }),
  sendRFQ:       id     => api.post(`/procurements/${id}/send-rfq`),
  getQuotes:     id     => api.get(`/procurements/${id}/quotes`),
  selectWinner:  (id, pv_id) => api.post(`/procurements/${id}/select-winner`, { pv_id }),
  approve:       id     => api.post(`/procurements/${id}/approve`),
  reject:        (id, reason) => api.post(`/procurements/${id}/reject`, { reason }),
  discountDraft: (id, data)   => api.post(`/procurements/${id}/discount-draft`, data),
  stats:         ()     => api.get('/procurements/stats/dashboard'),
}

export const specAPI = {
  check: (data) => api.post('/api/spec-check', data)
}

export const poAPI = {
  generate: proc_id => api.post(`/po/${proc_id}/generate`),
  download: po_id   => api.get(`/po/${po_id}/download`, { responseType: 'blob' }),
  list:     ()      => api.get('/po'),
}

export const portalAPI = {
  getInfo: token        => api.get(`/api/quote/${token}`),
  submit:  (token, data) => api.post(`/api/quote/${token}/submit`, data),
  decline: token        => api.post(`/api/quote/${token}/decline`),
}

export const uploadAPI = {
  file: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}