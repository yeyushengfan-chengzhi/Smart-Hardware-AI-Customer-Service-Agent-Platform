import { apiRequest } from './apiClient'

function queryString(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  return search.size ? `?${search}` : ''
}

export const createTicket = (payload) => apiRequest('/tickets', {
  method: 'POST',
  body: JSON.stringify(payload),
})

export const listTickets = (params = {}) => apiRequest(`/tickets${queryString(params)}`)
export const getTicket = (ticketId) => apiRequest(`/tickets/${encodeURIComponent(ticketId)}`)
export const updateTicketStatus = (ticketId, status) => apiRequest(`/tickets/${encodeURIComponent(ticketId)}/status`, {
  method: 'PATCH',
  body: JSON.stringify({ status }),
})
export const addTicketMessage = (ticketId, content) => apiRequest(`/tickets/${encodeURIComponent(ticketId)}/messages`, {
  method: 'POST',
  body: JSON.stringify({ sender_type: 'human_agent', content }),
})
