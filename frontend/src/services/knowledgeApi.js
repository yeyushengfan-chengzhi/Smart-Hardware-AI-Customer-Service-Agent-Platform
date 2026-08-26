import { apiRequest } from './apiClient'

function queryString(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  return search.size ? `?${search}` : ''
}

export const getKnowledgeDocuments = (params) => apiRequest(`/knowledge/documents${queryString(params)}`)
export const getKnowledgeDocument = (id) => apiRequest(`/knowledge/documents/${encodeURIComponent(id)}`)
export const getKnowledgeChunks = (id) => apiRequest(`/knowledge/documents/${encodeURIComponent(id)}/chunks`)
export const getManualSeedStatus = () => apiRequest('/knowledge/manual-seed-status')
export const importManualSeeds = () => apiRequest('/knowledge/import-manual-seeds', { method: 'POST' })
export const searchKnowledge = (query, topK = 5) => apiRequest('/knowledge/search_test', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, top_k: topK }),
})
