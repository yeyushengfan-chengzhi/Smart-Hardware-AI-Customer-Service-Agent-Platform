import { apiRequest } from './apiClient'

export const getAgents = () => apiRequest('/agents')
export const getAgent = (name) => apiRequest(`/agents/${encodeURIComponent(name)}`)
export const updateAgentStatus = (name, status) => apiRequest(`/agents/${encodeURIComponent(name)}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
export const updateAgentPrompt = (name, prompt, version) => apiRequest(`/agents/${encodeURIComponent(name)}/prompt`, { method: 'PATCH', body: JSON.stringify({ prompt, version }) })
