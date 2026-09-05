import { apiRequest } from './apiClient'

export function getNextDiagnosticCheck(payload) {
  return apiRequest('/agent/diagnosis/next-check', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
