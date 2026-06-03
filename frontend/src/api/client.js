import axios from 'axios'

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 10000,
})

export const getOverview      = () => API.get('/analytics/overview')
export const getSegments      = () => API.get('/segments/')
export const getAlerts        = () => API.get('/alerts/')
export const getRevenueTrend  = () => API.get('/analytics/revenue-trend')
export const getCohortData    = () => API.get('/analytics/cohort-retention')
export const getTopCustomers  = (limit=10) => API.get(`/analytics/top-customers?limit=${limit}`)
export const getCustomers     = (params={}) => API.get('/customers/', { params })
export const getCustomer      = (id) => API.get(`/customers/${id}`)
export const getCustomerRisk  = (id) => API.get(`/customers/${id}/risk`)
export const resolveAlert     = (id) => API.patch(`/alerts/${id}/resolve`)
export const runWhatIf        = (data) => API.post('/simulate/what-if', data)

export default API