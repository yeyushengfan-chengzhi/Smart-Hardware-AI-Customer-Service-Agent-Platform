const API_PREFIX = import.meta.env.VITE_API_BASE_URL || '/api'
const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 65000)

export class ApiError extends Error {
  constructor(message, status = 0, payload = null, options = {}) {
    super(message, options)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
    this.code = options.code || ''
  }
}

export function getAccessToken() {
  return localStorage.getItem('access_token') || ''
}

export function withAuthorization(headers = {}) {
  const token = getAccessToken()
  return token ? { ...headers, Authorization: `Bearer ${token}` } : { ...headers }
}

export function friendlyApiErrorMessage(error) {
  const detail = String(error?.payload?.detail || error?.message || '')
  if (error?.status === 401) return '登录已失效，请重新登录。'
  if (/LLM_API_KEY|API Key.+not configured|API.?Key.+未配置/i.test(detail)) {
    return '大模型 API Key 未配置，请在 backend/.env 中配置 LLM_API_KEY。'
  }
  if (error?.code === 'REQUEST_TIMEOUT' || error?.status === 408 || error?.status === 504 || /timeout|超时/i.test(detail)) {
    return '请求超时，请稍后重试。'
  }
  if (error?.status === 0 || error?.code === 'NETWORK_UNAVAILABLE') {
    return '后端服务未启动或无法连接，请启动后端服务后重试。'
  }
  return detail || '请求失败，请稍后重试。'
}

export async function apiRequest(path, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  let response
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: withAuthorization({ 'Content-Type': 'application/json', ...fetchOptions.headers }),
    })
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new ApiError('请求超时，请稍后重试。', 0, null, { cause: error, code: 'REQUEST_TIMEOUT' })
    }
    throw new ApiError('后端服务未启动或无法连接，请启动后端服务后重试。', 0, null, {
      cause: error,
      code: 'NETWORK_UNAVAILABLE',
    })
  } finally {
    clearTimeout(timeoutId)
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : `请求失败（HTTP ${response.status}）`
    const error = new ApiError(detail, response.status, payload)
    error.message = friendlyApiErrorMessage(error)
    throw error
  }
  return payload
}
