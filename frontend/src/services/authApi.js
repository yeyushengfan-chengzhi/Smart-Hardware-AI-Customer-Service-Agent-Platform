import { apiRequest } from './apiClient'

export const registerUser = (username, password) => apiRequest('/auth/register', {
  method: 'POST',
  body: JSON.stringify({ username, password }),
})

export const loginUser = (username, password) => apiRequest('/auth/login', {
  method: 'POST',
  body: JSON.stringify({ username, password }),
})

export const seedDemoAccounts = () => apiRequest('/dev/seed-demo-accounts', {
  method: 'POST',
})
