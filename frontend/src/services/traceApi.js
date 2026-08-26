import { apiRequest } from './apiClient'

async function get(path, params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  return apiRequest(`${path}${search.size ? `?${search}` : ''}`)
}

export const getTraces = (params) => get('/traces', params)
export const getTraceDetail = (traceId) => get(`/traces/${encodeURIComponent(traceId)}`)
