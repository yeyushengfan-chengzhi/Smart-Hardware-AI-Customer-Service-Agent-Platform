import { ref } from 'vue'
import { createSession, getSessionMessages, listSessions, saveSessionMessage } from '../services/chatSessionApi'
import { getAccessToken } from '../services/apiClient'

const LEGACY_STORAGE_KEY = 'smart-hardware-ai-chat-sessions-v1'
const CURRENT_KEY = 'smart-hardware-ai-current-session-v1'

export const chatSessions = ref([])
export const currentSessionId = ref(localStorage.getItem(CURRENT_KEY) || '')
export const chatMessages = ref([])
export const usingLocalSessions = ref(false)

export function hasBackendSession() {
  const sessionId = Number(currentSessionId.value)
  return Number.isInteger(sessionId) && sessionId > 0
}

function setCurrentSession(id) {
  currentSessionId.value = id ? String(id) : ''
  if (id) localStorage.setItem(CURRENT_KEY, String(id))
  else localStorage.removeItem(CURRENT_KEY)
}

export function clearSessionCache() {
  setCurrentSession('')
  localStorage.removeItem(LEGACY_STORAGE_KEY)
  chatSessions.value = []
  chatMessages.value = []
  usingLocalSessions.value = false
}

export async function initializeSessions() {
  usingLocalSessions.value = false
  localStorage.removeItem(LEGACY_STORAGE_KEY)
  if (!getAccessToken()) {
    clearSessionCache()
    return
  }

  chatSessions.value = await listSessions()
  const savedSession = chatSessions.value.find((item) => String(item.session_id) === String(currentSessionId.value))
  if (savedSession) {
    await selectSession(savedSession.session_id)
    return
  }
  if (chatSessions.value.length) {
    await selectSession(chatSessions.value[0].session_id)
    return
  }
  setCurrentSession('')
  chatMessages.value = []
}

export function newSession() {
  setCurrentSession('')
  chatMessages.value = []
}

export async function ensureSession(title = '新会话') {
  if (!getAccessToken()) throw new Error('请先登录后使用智能客服')
  if (hasBackendSession()) return Number(currentSessionId.value)

  const cleanTitle = title.trim().slice(0, 20) || '新会话'
  const created = await createSession(cleanTitle)
  setCurrentSession(created.session_id)
  chatSessions.value = [created, ...chatSessions.value.filter((item) => item.session_id !== created.session_id)]
  chatMessages.value = []
  return Number(created.session_id)
}

export async function appendMessage(message) {
  if (!hasBackendSession()) throw new Error('后端会话尚未创建')
  const optimistic = { id: `temp-${Date.now()}-${Math.random()}`, created_time: new Date().toISOString(), metadata: {}, ...message }
  chatMessages.value.push(optimistic)
  try {
    const saved = await saveSessionMessage(Number(currentSessionId.value), message)
    Object.assign(optimistic, saved)
    await refreshSessions()
    return saved
  } catch (error) {
    chatMessages.value = chatMessages.value.filter((item) => item !== optimistic)
    throw error
  }
}

export async function selectSession(id) {
  const numericId = Number(id)
  if (!Number.isInteger(numericId) || numericId <= 0) throw new Error('无效的后端会话')
  const messages = await getSessionMessages(numericId)
  setCurrentSession(numericId)
  chatMessages.value = messages
}

export async function refreshSessions() {
  if (!getAccessToken()) {
    clearSessionCache()
    return
  }
  chatSessions.value = await listSessions()
}
