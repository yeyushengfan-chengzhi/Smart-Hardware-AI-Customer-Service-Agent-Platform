import { computed, ref } from 'vue'
import { loginUser, registerUser } from '../services/authApi'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'smart-hardware-ai-auth-user-v1'

function decodeTokenUser(token) {
  try {
    const rawPayload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = rawPayload.padEnd(Math.ceil(rawPayload.length / 4) * 4, '=')
    const decoded = JSON.parse(decodeURIComponent(atob(payload).split('').map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`).join('')))
    const role = ['user', 'agent', 'admin'].includes(decoded.role) ? decoded.role : 'user'
    return { id: decoded.sub || '', username: decoded.username || '', role, exp: Number(decoded.exp) || 0 }
  } catch {
    return { id: '', username: '', role: 'user', exp: 0 }
  }
}

function readUser(token) {
  const tokenUser = decodeTokenUser(token)
  try {
    const stored = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    if (!tokenUser.username && stored?.username) tokenUser.username = stored.username
  } catch {
    localStorage.removeItem(USER_KEY)
  }
  return tokenUser
}

let initialToken = localStorage.getItem(TOKEN_KEY) || ''
let initialUser = readUser(initialToken)
if (initialToken && (!initialUser.exp || initialUser.exp * 1000 <= Date.now())) {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  initialToken = ''
  initialUser = { id: '', username: '', role: 'user', exp: 0 }
}

export const accessToken = ref(initialToken)
export const authUser = ref(initialUser)
export const isAuthenticated = computed(() => Boolean(accessToken.value))
export const userRole = computed(() => authUser.value.role || 'user')

function saveAuth(token, username) {
  const tokenUser = decodeTokenUser(token)
  const user = { ...tokenUser, username: tokenUser.username || username }
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  accessToken.value = token
  authUser.value = user
}

export async function login(username, password) {
  const response = await loginUser(username, password)
  saveAuth(response.access_token, username)
  return authUser.value
}

export async function register(username, password) {
  await registerUser(username, password)
  return login(username, password)
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  accessToken.value = ''
  authUser.value = { id: '', username: '', role: 'user', exp: 0 }
}
