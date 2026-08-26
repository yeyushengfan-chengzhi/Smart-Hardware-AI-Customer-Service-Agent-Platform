import { apiRequest } from './apiClient'

export const createSession = (title) => apiRequest('/chat/sessions', { method: 'POST', body: JSON.stringify({ title }) })
export const listSessions = () => apiRequest('/chat/sessions')
export const getSessionMessages = (id) => apiRequest(`/chat/sessions/${id}/messages`)
export const saveSessionMessage = (id, message) => apiRequest(`/chat/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify(message) })
