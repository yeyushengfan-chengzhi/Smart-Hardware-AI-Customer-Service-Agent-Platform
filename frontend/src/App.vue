<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AgentTracePage from './components/AgentTracePage.vue'
import EvaluationDashboard from './components/EvaluationDashboard.vue'
import KnowledgeCenter from './components/KnowledgeCenter.vue'
import AgentManagementCenter from './components/AgentManagementCenter.vue'
import TicketCenter from './components/TicketCenter.vue'
import AuthGate from './components/AuthGate.vue'
import DiagnosticWorkbench from './components/DiagnosticWorkbench.vue'
import { AgentRequestError, executeAgent } from './services/agentApi'
import { ApiError, getAccessToken } from './services/apiClient'
import { createTicket, getTicket } from './services/ticketApi'
import { agentResponseAdapter } from './utils/agentResponseAdapter'
import { detectHandoffReason } from './stores/handoffStore'
import { accessToken, authUser, isAuthenticated, logout, userRole } from './stores/authStore'
import { appendMessage, chatMessages, chatSessions, clearSessionCache, currentSessionId, ensureSession, hasBackendSession, initializeSessions, newSession, selectSession } from './stores/chatSessionStore'

const query = ref('')
const loading = ref(false)
const loadingStage = ref('idle')
const activeRoute = ref('')
const submittedQuery = ref('')
const initialPath = window.location.pathname

function navFromPath(path) {
  if (path.startsWith('/admin/trace')) return 'trace'
  if (path === '/admin/tickets') return 'tickets'
  if (path === '/admin/evaluation') return 'evaluation'
  if (path === '/admin/knowledge') return 'knowledge'
  if (path === '/admin/agents') return 'agents'
  if (path === '/admin' || path === '/admin/dashboard') return 'admin'
  return 'chat'
}

const activeNav = ref(navFromPath(initialPath))
const requestedTraceId = ref(initialPath.match(/^\/admin\/trace\/([^/]+)$/)?.[1] || '')
const result = ref(null)
const routeResponse = ref(null)
const agentResponse = ref(null)
const requestTiming = ref(null)
const handoffSuggestion = ref('')
const messagesContainer = ref(null)
const sessionTicketIds = reactive(new Map())
const customerTicketDetail = ref(null)
const customerTicketLoading = ref(false)
const authInitializing = ref(false)

const examples = [
  'B760 DDR4 支持什么内存？',
  'LANCOOL 216 支持多大水冷？',
  'M-ATX 主板装 ATX 机箱会不会不好看？',
  '360 水冷装前面会不会影响显卡长度？',
  '开机无显示怎么办？',
]

const portalNavItems = [
  { id: 'chat', icon: '✦', label: 'AI Self-Service Chat', meta: 'AI 自助客服' },
]

const allAdminNavItems = [
  { id: 'admin', icon: '▦', label: 'Dashboard', meta: '企业运营总览' },
  { id: 'knowledge', icon: '▤', label: 'Knowledge Center', meta: '企业知识资产' },
  { id: 'agents', icon: '◈', label: 'Agent Management', meta: 'Agent 配置与版本管理' },
  { id: 'trace', icon: '⌘', label: 'Agent Trace', meta: 'AI 执行链路' },
  { id: 'evaluation', icon: '✓', label: 'Evaluation', meta: '回归测试质量' },
  { id: 'tickets', icon: '◎', label: 'Customer Service', meta: '人工接管与工单' },
]

const adminRoles = {
  admin: ['admin'],
  knowledge: ['admin'],
  agents: ['admin'],
  trace: ['admin'],
  evaluation: ['admin'],
  tickets: ['agent', 'admin'],
}

const visibleAdminNavItems = computed(() => allAdminNavItems.filter((item) => (
  isAuthenticated.value && adminRoles[item.id]?.includes(userRole.value)
)))
const showPortalNav = computed(() => !isAuthenticated.value || userRole.value !== 'agent')
const agentChatRestricted = computed(() => (
  isAuthenticated.value && userRole.value === 'agent' && activeNav.value === 'chat'
))

const accessDenied = computed(() => activeNav.value !== 'chat' && (
  !isAuthenticated.value || !adminRoles[activeNav.value]?.includes(userRole.value)
))

const accessDeniedMessage = computed(() => {
  if (!isAuthenticated.value) return '请先登录后访问企业后台'
  if (userRole.value === 'agent') return '当前客服账号仅可访问 Customer Service'
  return '当前账号无权限访问企业后台'
})

const adminModules = [
  { icon: '▤', title: 'Knowledge Center', text: 'PDF 管理、Chunk 浏览与检索测试。', color: 'green' },
  { icon: '◈', title: 'Agent Management', text: '管理 Agent 状态、Prompt 版本及能力绑定。', color: 'blue' },
  { icon: '⌘', title: 'Agent Trace', text: '查看 Supervisor、Agent、RAG 与 Tool 调用链。', color: 'purple' },
  { icon: '✓', title: 'Evaluation', text: '测试集、路由准确率、RAG 命中率与工具准确率。', color: 'orange' },
  { icon: '◎', title: 'Customer Service', text: '处理 AI 转人工和用户主动提交的售后工单。', color: 'slate' },
]

const pageTitle = computed(() => accessDenied.value ? '访问受限' : agentChatRestricted.value ? '客服工作台入口' : ({
  chat: 'PCWise Agent',
  admin: 'Enterprise Dashboard',
  knowledge: 'Knowledge Center',
  agents: 'Agent Management',
  trace: 'Agent Trace',
  evaluation: 'Evaluation Harness',
  tickets: 'Customer Service 工单中心',
})[activeNav.value] || 'Enterprise Admin Console')

const technicalJson = computed(() => JSON.stringify({
  route_response: routeResponse.value,
  agent_response: agentResponse.value,
  sources: result.value?.sources || [],
  tool_result: result.value?.tool_result || {},
  timing: requestTiming.value,
}, null, 2))
const sourceLabels = {
  official_manual_seed: '官方说明书依据',
  community_experience: '社区经验提示',
  uploaded: '用户上传资料',
}
const sourceLabel = (source) => sourceLabels[source?.source_type] || '知识库来源'
const sourceFilename = (source) => source?.filename || source?.file_name || '未命名资料'
const hasCommunitySources = (sources = []) => sources.some((source) => source.source_type === 'community_experience')
const agentNames = { knowledge: 'KnowledgeAgent', diagnosis: 'DiagnosisAgent', tool: 'ToolAgent' }
const messageAgentLabel = (message) => {
  const metadata = message?.metadata || {}
  const explicitName = metadata.agent_response?.agent_name || metadata.agent_response?.agent
  const route = String(metadata.route_response?.route || '').toLowerCase()
  return explicitName || agentNames[route] || 'PCWise Agent'
}
const messageTraceId = (message) => (
  message?.metadata?.trace_id
  || message?.metadata?.agent_response?.trace_id
  || message?.metadata?.route_response?.trace_id
  || ''
)

const loadingStageText = computed(() => 'AI 正在分析...')

const latencySummary = computed(() => requestTiming.value ? [
  { label: '总耗时', value: requestTiming.value.total_latency_ms },
  { label: '路由耗时', value: requestTiming.value.route_latency_ms },
  { label: 'Agent 耗时', value: requestTiming.value.agent_latency_ms },
] : [])
const traceId = computed(() => agentResponse.value?.trace_id || routeResponse.value?.trace_id || '')
const shouldEmphasizeHandoff = computed(() => Boolean(
  handoffSuggestion.value
  || result.value?.tool_result?.compatible === 'unknown'
  || agentResponse.value?.data_missing
  || result.value?.tool_result?.data_missing
))
const handoffCardTitle = computed(() => (
  result.value?.tool_result?.compatible === 'unknown'
    ? '当前信息不足，建议人工进一步确认'
    : '当前问题建议人工进一步确认'
))
const ticketStatusLabels = { open: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭' }
const currentTicketSummary = computed(() => {
  const sessionKey = String(currentSessionId.value)
  const activeTicket = sessionTicketIds.get(sessionKey)
  if (activeTicket) return activeTicket
  const eventMessage = [...chatMessages.value].reverse().find((message) => message.metadata?.ticket_id)
  if (!eventMessage) return null
  return {
    ticket_id: eventMessage.metadata.ticket_id,
    status: eventMessage.metadata.ticket_status || 'open',
    handoff_reason: eventMessage.metadata.handoff_reason || '',
  }
})
const humanAgentReplies = computed(() => (
  customerTicketDetail.value?.messages?.filter((message) => message.sender_type === 'human_agent') || []
))
const visibleHistoryMessages = computed(() => {
  const messages = chatMessages.value.filter((message) => message.metadata?.message_type !== 'ticket_created')
  if (result.value && messages.at(-1)?.role === 'assistant') return messages.slice(0, -1)
  return messages
})

function syncNavigation() {
  activeNav.value = navFromPath(window.location.pathname)
  requestedTraceId.value = window.location.pathname.match(/^\/admin\/trace\/([^/]+)$/)?.[1] || ''
}

onMounted(async () => {
  window.addEventListener('popstate', syncNavigation)
  if (isAuthenticated.value) await prepareAuthenticatedChat()
  else clearSessionCache()
})
onBeforeUnmount(() => window.removeEventListener('popstate', syncNavigation))

async function scrollMessagesToBottom() {
  await nextTick()
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
}

watch(() => chatMessages.value.length, scrollMessagesToBottom)
watch([loadingStage, result, currentSessionId], scrollMessagesToBottom, { flush: 'post' })
watch(currentSessionId, () => {
  customerTicketDetail.value = null
})
watch(isAuthenticated, async (authenticated, wasAuthenticated) => {
  if (authenticated && !wasAuthenticated) await handleAuthenticated()
})

async function submit() {
  const cleanQuery = query.value.trim()
  if (!cleanQuery || loading.value) return
  if (!isAuthenticated.value || !getAccessToken()) {
    ElMessage.warning('请先登录后使用智能客服')
    return
  }
  if (authInitializing.value) {
    ElMessage.info('正在连接您的客服会话，请稍候')
    return
  }
  loading.value = true
  loadingStage.value = 'routing'
  activeRoute.value = ''
  submittedQuery.value = cleanQuery
  result.value = null
  routeResponse.value = null
  agentResponse.value = null
  requestTiming.value = null
  handoffSuggestion.value = ''
  try {
    await ensureSession(cleanQuery)
    await appendMessage({ role: 'user', content: cleanQuery, metadata: {} })
    if (/^(请)?(帮我)?(转人工|联系人工|人工客服|我要人工客服|我要找客服|找人工客服|找客服)[！!。.？?]*$/.test(cleanQuery)) {
      const answer = '已为您创建人工客服工单，客服可在后台查看本次会话的完整上下文。'
      result.value = {
        query: cleanQuery, route: 'human_handoff', intent: 'human_handoff', agent: '—', answer,
        steps: [], sources: [], tool_name: '', tool_input: {}, tool_result: {}, raw_response: {},
        device: 'unknown', fault_type: 'unknown', error: false,
      }
      await appendMessage({ role: 'assistant', content: answer, metadata: { handoff_suggested: true, handoff_reason: '用户主动要求转人工', handoff_source: 'user_request' } })
      const ticket = await createTicketForCurrentSession('用户主动要求转人工', 'user_request')
      clearComposer()
      ElMessage.success(`人工客服工单 ${ticket.ticket_id} 已创建`)
      return
    }
    const { routing, response, timing } = await executeAgent(cleanQuery, {
      onStage(stage, route = '') {
        loadingStage.value = stage
        if (route) activeRoute.value = route
      },
    })
    routeResponse.value = routing
    agentResponse.value = response
    requestTiming.value = timing
    result.value = agentResponseAdapter(routing, response)
    handoffSuggestion.value = detectHandoffReason(routing, response, result.value)
    await appendMessage({
      role: 'assistant',
      content: result.value.answer,
      metadata: {
        route_response: routing,
        agent_response: response || {},
        sources: result.value.sources,
        tool_result: result.value.tool_result,
        latency: timing,
        handoff_suggested: Boolean(handoffSuggestion.value),
        handoff_reason: handoffSuggestion.value,
        trace_id: response?.trace_id || routing?.trace_id || '',
      },
    })
    clearComposer()
  } catch (error) {
    loadingStage.value = 'error'
    routeResponse.value = error instanceof AgentRequestError ? error.routing : null
    const message = error instanceof AgentRequestError
      ? error.message
      : (error?.message || '当前请求失败，请稍后重试。')
    result.value = {
      query: cleanQuery,
      route: routeResponse.value?.route || 'unknown',
      intent: routeResponse.value?.intent || 'unknown',
      agent: '—',
      answer: message,
      steps: [],
      sources: [],
      tool_name: '',
      tool_input: {},
      tool_result: {},
      raw_response: {},
      device: routeResponse.value?.device_type || 'unknown',
      fault_type: routeResponse.value?.fault_type || 'unknown',
      error: true,
    }
    handoffSuggestion.value = error instanceof AgentRequestError && error.stage === 'agent'
      ? 'AI 处理请求失败，建议转人工继续处理'
      : '后端服务当前不可用，您可以稍后重试或转人工'
    if (hasBackendSession()) {
      await appendMessage({ role: 'assistant', content: message, metadata: { error: true, handoff_suggested: true, handoff_reason: handoffSuggestion.value } }).catch(() => {})
    }
    if (error?.status === 401) {
      logout()
      clearSessionCache()
    }
    ElMessage.error(message)
  } finally {
    loading.value = false
    if (loadingStage.value !== 'error') loadingStage.value = 'completed'
  }
}

function fillExample(example) {
  if (loading.value || authInitializing.value) return
  query.value = example
  nextTick(resizeActiveComposer)
}

function clearComposer() {
  query.value = ''
  nextTick(resizeActiveComposer)
}

function handleComposerKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  submit()
}

function resizeComposer(event) {
  const textarea = event?.target
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`
}

function resizeActiveComposer() {
  const textarea = document.querySelector('.chat-composer textarea')
  if (textarea) resizeComposer({ target: textarea })
}

async function createTicketForCurrentSession(reason, source, linkedTraceId = '') {
  if (!isAuthenticated.value || !accessToken.value || !getAccessToken()) throw new Error('请先登录后创建人工工单')
  if (!hasBackendSession()) await ensureSession(reason || '人工服务会话')
  const sessionId = Number(currentSessionId.value)
  const existing = sessionTicketIds.get(String(sessionId)) || currentTicketSummary.value
  if (existing) return existing
  const created = await createTicket({
    session_id: sessionId,
    reason,
    source,
    priority: 'medium',
    trace_id: linkedTraceId || null,
  })
  const ticketSummary = { ...created, handoff_reason: reason }
  sessionTicketIds.set(String(sessionId), ticketSummary)
  await appendMessage({
    role: 'assistant',
    content: `人工客服工单 ${created.ticket_id} 已创建。您可以在当前会话中手动查看处理状态和客服回复。`,
    metadata: {
      ticket_id: created.ticket_id,
      ticket_status: created.status,
      handoff_reason: reason,
      message_type: 'ticket_created',
    },
  }).catch(() => {})
  return ticketSummary
}

async function requestHandoff(reason = '') {
  if (!isAuthenticated.value || !accessToken.value || !getAccessToken()) {
    ElMessage.warning('请先登录后创建人工工单')
    return
  }
  const lastUser = [...chatMessages.value].reverse().find((message) => message.role === 'user')
  const lastAssistant = [...chatMessages.value].reverse().find((message) => message.role === 'assistant')
  if (!lastUser || !lastAssistant) {
    ElMessage.warning('请先发送问题，AI 回答后即可转人工')
    return
  }
  const savedMetadata = lastAssistant?.metadata || {}
  try {
    const linkedTraceId = savedMetadata.trace_id || savedMetadata.agent_response?.trace_id || savedMetadata.route_response?.trace_id || traceId.value
    const source = savedMetadata.handoff_suggested || handoffSuggestion.value ? 'ai_handoff' : 'user_request'
    const ticket = await createTicketForCurrentSession(
      reason || handoffSuggestion.value || savedMetadata.handoff_reason || '用户主动要求人工处理',
      source,
      linkedTraceId,
    )
    ElMessage.success(`人工客服工单 ${ticket.ticket_id} 已创建，可在 Customer Service 中查看`)
  } catch (error) {
    ElMessage.error(error.message)
  }
}

async function viewTicketStatus() {
  const summary = currentTicketSummary.value
  if (!summary || customerTicketLoading.value) return
  customerTicketLoading.value = true
  try {
    const detail = await getTicket(summary.ticket_id)
    customerTicketDetail.value = detail
    sessionTicketIds.set(String(currentSessionId.value), {
      ticket_id: detail.ticket_id,
      status: detail.status,
      handoff_reason: detail.handoff_reason,
    })
  } catch (error) {
    ElMessage.error(error.status === 403 ? '当前账号无权查看该工单' : error.message)
  } finally {
    customerTicketLoading.value = false
  }
}

async function prepareAuthenticatedChat() {
  if (!isAuthenticated.value || authInitializing.value) return
  authInitializing.value = true
  try {
    await initializeSessions()
    if (!hasBackendSession()) await ensureSession('新会话')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      handleLogout(false)
      ElMessage.warning('登录状态已失效，请重新登录')
    } else {
      ElMessage.error(error.message || '聊天会话初始化失败，请稍后重试')
    }
  } finally {
    authInitializing.value = false
  }
}

async function handleAuthenticated() {
  clearSessionCache()
  sessionTicketIds.clear()
  customerTicketDetail.value = null
  const defaultNav = userRole.value === 'agent' ? 'tickets' : userRole.value === 'admin' ? 'admin' : 'chat'
  switchNav(defaultNav)
  if (defaultNav === 'chat') await prepareAuthenticatedChat()
}

function handleLogout(showMessage = true) {
  logout()
  clearSessionCache()
  sessionTicketIds.clear()
  customerTicketDetail.value = null
  result.value = null
  handoffSuggestion.value = ''
  query.value = ''
  switchNav('chat')
  if (showMessage) ElMessage.success('已退出登录并清理本地会话缓存')
}

function formatTime(value) {
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

async function openSession(id) {
  if (loading.value) return
  result.value = null
  submittedQuery.value = ''
  await selectSession(id)
}

function startNewSession() {
  if (loading.value) return
  newSession()
  result.value = null
  submittedQuery.value = ''
  query.value = ''
}

function switchNav(nav) {
  activeNav.value = nav
  requestedTraceId.value = ''
  const paths = { chat: '/', admin: '/admin', knowledge: '/admin/knowledge', agents: '/admin/agents', trace: '/admin/trace', evaluation: '/admin/evaluation', tickets: '/admin/tickets' }
  const path = paths[nav] || '/admin'
  window.history.pushState({}, '', path)
  if (nav === 'chat' && isAuthenticated.value) prepareAuthenticatedChat()
}

function openAgentTrace() {
  switchNav('trace')
}

function openEvaluation() {
  switchNav('evaluation')
}

function openKnowledgeCenter() {
  switchNav('knowledge')
}

function openAgentManagement() { switchNav('agents') }

function openLinkedTrace(traceId) {
  requestedTraceId.value = traceId
  activeNav.value = 'trace'
  window.history.pushState({}, '', `/admin/trace/${encodeURIComponent(traceId)}`)
}

async function handleTraceEntry(id) {
  if (!id) return
  if (['admin', 'agent'].includes(userRole.value)) {
    openLinkedTrace(id)
    return
  }
  try {
    await navigator.clipboard.writeText(id)
    ElMessage.success('Trace ID 已复制')
  } catch {
    ElMessage.info(`Trace ID：${id}`)
  }
}

function viewCurrentTrace() {
  handleTraceEntry(traceId.value)
}

function openAdminModule(title) {
  if (title === 'Customer Service') switchNav('tickets')
  if (title === 'Agent Trace') openAgentTrace()
  if (title === 'Evaluation') openEvaluation()
  if (title === 'Knowledge Center') openKnowledgeCenter()
  if (title === 'Agent Management') openAgentManagement()
}
</script>

<template>
  <div class="console-shell product-shell" :class="{ 'chat-active': activeNav === 'chat' }">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">PW</div><div><strong>PCWise Agent</strong><span>AI CUSTOMER SERVICE</span></div></div>
      <template v-if="showPortalNav">
        <div class="nav-caption">SERVICE PORTAL</div>
        <nav>
          <button v-for="item in portalNavItems" :key="item.id" class="nav-item" :class="{ active: activeNav === item.id }" @click="switchNav(item.id)">
            <span class="nav-icon">{{ item.icon }}</span>
            <span><b>{{ item.label }}</b><small>{{ item.meta }}</small></span>
          </button>
        </nav>
      </template>
      <div v-if="visibleAdminNavItems.length" class="nav-caption admin-nav-caption">ENTERPRISE CONSOLE</div>
      <nav v-if="visibleAdminNavItems.length">
        <button v-for="item in visibleAdminNavItems" :key="item.id" class="nav-item" :class="{ active: activeNav === item.id }" @click="switchNav(item.id)">
          <span class="nav-icon">{{ item.icon }}</span>
          <span><b>{{ item.label }}</b><small>{{ item.meta }}</small></span>
        </button>
      </nav>
      <div class="system-card"><div class="status-line"><span class="status-dot"></span> AI Service Online</div><strong>7 × 24 自助服务</strong><small>知识问答 · 故障诊断 · 兼容判断</small></div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div><div class="eyebrow">{{ activeNav === 'chat' ? 'AI CUSTOMER SERVICE FOR DIY PC HARDWARE' : 'SMART HARDWARE / ENTERPRISE CONSOLE' }}</div><h1>{{ pageTitle }}</h1></div>
        <div class="header-actions">
          <span class="environment"><i></i> Service Online</span>
          <div v-if="isAuthenticated" class="user-session"><span class="avatar">{{ (authUser.username || 'U').slice(0, 2).toUpperCase() }}</span><div><strong>{{ authUser.username || '已登录用户' }}</strong><small>{{ userRole.toUpperCase() }} ACCOUNT</small></div><button @click="handleLogout()">退出登录</button></div>
          <div v-else class="user-session signed-out"><span class="avatar">U</span><div><strong>未登录</strong><small>登录后保存会话</small></div></div>
        </div>
      </header>

      <AuthGate v-if="activeNav === 'chat' && !isAuthenticated" />

      <section v-else-if="agentChatRestricted" class="access-denied-page agent-workspace-entry">
        <div class="access-denied-card">
          <span class="access-denied-icon">CS</span>
          <div>
            <span class="section-kicker">CUSTOMER SERVICE WORKSPACE</span>
            <h2>当前为客服账号，请进入 Customer Service 工作台处理工单。</h2>
            <p>客服账号用于查看人工接管上下文、发送回复和更新工单状态。</p>
            <button @click="switchNav('tickets')">进入工单工作台</button>
          </div>
        </div>
      </section>

      <section v-else-if="activeNav === 'chat'" class="self-service-page session-page">
        <div class="session-layout">
          <aside class="session-history">
            <div class="history-heading"><div><span class="section-kicker">CONVERSATIONS</span><h2>历史会话</h2></div><button @click="startNewSession">＋ 新建</button></div>
            <div v-if="authInitializing" class="fallback-notice session-loading">正在连接您的客服会话...</div>
            <div v-if="!chatSessions.length" class="history-empty">发送第一条问题后，会话将保存在这里。</div>
            <button v-for="session in chatSessions" :key="session.session_id" class="session-item" :class="{ active: String(currentSessionId) === String(session.session_id) }" @click="openSession(session.session_id)">
              <strong>{{ session.title }}</strong><p>{{ session.last_message || '新会话' }}</p><time>{{ formatTime(session.updated_time) }}</time>
            </button>
          </aside>
          <div class="session-content">
            <div v-if="!chatMessages.length && !result && !loading" class="chat-empty-home">
              <DiagnosticWorkbench @ask="fillExample" />
              <div class="chat-composer home-composer">
                <div class="query-box customer-query">
                  <textarea v-model="query" rows="1" :disabled="loading || authInitializing" placeholder="询问主板说明书、装机兼容性或硬件故障..." aria-label="输入硬件问题" @input="resizeComposer" @keydown="handleComposerKeydown"></textarea>
                  <button class="send-button icon-send" :disabled="!query.trim() || loading || authInitializing" aria-label="发送问题" @click="submit"><span v-if="loading || authInitializing" class="spinner"></span><span v-else>↑</span></button>
                </div>
                <p v-if="authInitializing" class="composer-status">正在连接客服会话...</p>
                <div class="prompt-suggestions"><button v-for="item in examples" :key="item" :disabled="loading || authInitializing" @click="fillExample(item)">{{ item }}</button></div>
              </div>
            </div>

            <div v-else class="chat-card">
              <div ref="messagesContainer" class="messages-scroll">
                <div v-if="chatMessages.length" class="conversation-thread">
                  <template v-for="message in visibleHistoryMessages" :key="message.id">
                    <div v-if="message.role === 'user'" class="user-message"><div><p>{{ message.content }}</p></div><span>U</span></div>
                    <div v-else class="history-ai-message">
                      <div class="assistant-avatar">PW</div>
                      <div>
                        <strong>PCWise Agent</strong>
                        <p>{{ message.content }}</p>
                        <div class="answer-meta">
                          <span>{{ messageAgentLabel(message) }}</span>
                          <span v-if="message.metadata?.sources?.length">来源 {{ message.metadata.sources.length }}</span>
                          <span v-if="message.metadata?.tool_result && Object.keys(message.metadata.tool_result).length">规则判断</span>
                          <span v-if="hasCommunitySources(message.metadata?.sources)">社区经验提示</span>
                          <button v-if="messageTraceId(message)" @click="handleTraceEntry(messageTraceId(message))">Trace</button>
                        </div>
                        <details v-if="message.metadata?.sources?.length" class="source-disclosure">
                          <summary>查看来源</summary>
                          <div class="simple-sources">
                            <div v-for="(source, index) in message.metadata.sources.slice(0, 3)" :key="index"><span>{{ sourceLabel(source) }}</span><p><strong>{{ sourceFilename(source) }}</strong><small>第 {{ source.page_number ?? '—' }} 页 · {{ source.section_title || '未标注章节' }}</small></p></div>
                            <details v-if="message.metadata.sources.length > 3" class="more-sources"><summary>查看更多（{{ message.metadata.sources.length - 3 }}）</summary><div v-for="(source, index) in message.metadata.sources.slice(3)" :key="index" class="extra-source"><span>{{ sourceLabel(source) }}</span><p><strong>{{ sourceFilename(source) }}</strong><small>第 {{ source.page_number ?? '—' }} 页 · {{ source.section_title || '未标注章节' }}</small></p></div></details>
                          </div>
                        </details>
                        <p v-if="hasCommunitySources(message.metadata?.sources)" class="community-disclaimer">社区经验仅作为装机风险提示，不代表官方规格结论。</p>
                      </div>
                    </div>
                  </template>
                  <div v-if="loading" class="ai-placeholder"><div class="assistant-avatar">PW</div><div><strong>PCWise Agent</strong><p>{{ loadingStageText }}</p><span class="thinking-dots"><i></i><i></i><i></i></span></div></div>
                </div>

                <div v-if="result && !loading" class="customer-answer" :class="{ 'error-answer': result.error }">
                  <div class="answer-header"><div class="assistant-avatar">PW</div><div><strong>PCWise Agent</strong><small>{{ result.error ? '处理未完成' : '回答已生成' }}</small></div></div>
                  <p class="final-answer">{{ result.answer }}</p>
                  <div v-if="result.steps.length" class="customer-steps"><h3>建议您按以下步骤排查</h3><article v-for="(step, index) in result.steps" :key="index"><span>{{ index + 1 }}</span><div><strong>{{ step.action }}</strong><p>{{ step.reason }}</p></div></article></div>
                  <div class="answer-meta">
                    <span>{{ result.agent || 'PCWise Agent' }}</span>
                    <span v-if="result.sources.length">来源 {{ result.sources.length }}</span>
                    <span v-if="result.agent === 'ToolAgent' || result.tool_name">规则判断</span>
                    <span v-if="hasCommunitySources(result.sources)">社区经验提示</span>
                    <button v-if="traceId" @click="viewCurrentTrace">Trace</button>
                  </div>
                  <details v-if="result.sources.length" class="source-disclosure">
                    <summary>查看来源</summary>
                    <div class="simple-sources">
                      <div v-for="(source, index) in result.sources.slice(0, 3)" :key="index"><span>{{ sourceLabel(source) }}</span><p><strong>{{ sourceFilename(source) }}</strong><small>第 {{ source.page_number ?? '—' }} 页 · {{ source.section_title || '未标注章节' }}</small></p></div>
                      <details v-if="result.sources.length > 3" class="more-sources"><summary>查看更多（{{ result.sources.length - 3 }}）</summary><div v-for="(source, index) in result.sources.slice(3)" :key="index" class="extra-source"><span>{{ sourceLabel(source) }}</span><p><strong>{{ sourceFilename(source) }}</strong><small>第 {{ source.page_number ?? '—' }} 页 · {{ source.section_title || '未标注章节' }}</small></p></div></details>
                    </div>
                  </details>
                  <p v-if="hasCommunitySources(result.sources)" class="community-disclaimer">社区经验仅作为装机风险提示，不代表官方规格结论。</p>
                  <div v-if="shouldEmphasizeHandoff" class="handoff-suggestion"><span>!</span><div><strong>{{ handoffCardTitle }}</strong><p>原因：{{ handoffSuggestion || '当前数据不足，建议人工进一步确认。' }}</p></div><button @click="requestHandoff(handoffSuggestion)">创建人工工单</button></div>
                  <details class="technical-disclosure"><summary>技术详情</summary><pre>{{ technicalJson }}</pre></details>
                </div>

                <section v-if="currentTicketSummary" class="customer-ticket-status">
                  <div class="customer-ticket-head"><div><span>人工服务工单</span><strong>{{ currentTicketSummary.ticket_id }}</strong></div><em :class="`status-${customerTicketDetail?.status || currentTicketSummary.status}`">{{ ticketStatusLabels[customerTicketDetail?.status || currentTicketSummary.status] }}</em></div>
                  <p>{{ customerTicketDetail?.handoff_reason || currentTicketSummary.handoff_reason }}</p>
                  <button :disabled="customerTicketLoading" @click="viewTicketStatus"><span v-if="customerTicketLoading" class="spinner"></span>{{ customerTicketDetail ? '刷新工单状态' : '查看工单状态' }}</button>
                  <div v-if="customerTicketDetail" class="customer-ticket-replies"><span>客服回复</span><article v-for="message in humanAgentReplies" :key="message.id"><div><strong>人工客服</strong><time>{{ formatTime(message.created_time) }}</time></div><p>{{ message.content }}</p></article><p v-if="!humanAgentReplies.length" class="ticket-reply-empty">客服暂未回复，请稍后手动刷新查看。</p></div>
                </section>
              </div>
              <div class="chat-composer">
                <div class="query-box customer-query">
                  <textarea v-model="query" rows="1" :disabled="loading || authInitializing" placeholder="询问主板说明书、装机兼容性或硬件故障..." aria-label="输入硬件问题" @input="resizeComposer" @keydown="handleComposerKeydown"></textarea>
                  <button class="send-button icon-send" :disabled="!query.trim() || loading || authInitializing" aria-label="发送问题" @click="submit"><span v-if="loading || authInitializing" class="spinner"></span><span v-else>↑</span></button>
                </div>
                <p class="composer-status">{{ authInitializing ? '正在连接客服会话...' : (loading ? 'AI 正在分析...' : 'Enter 发送 · Shift + Enter 换行') }}</p>
              </div>
            </div>
            <div v-if="chatMessages.length || result" class="service-note"><span>仍需帮助？</span><button class="passive-handoff-button" @click="requestHandoff()">联系人工客服</button></div>
          </div>
        </div>
      </section>

      <section v-else-if="accessDenied" class="access-denied-page">
        <div class="access-denied-card"><span class="access-denied-icon">!</span><div><span class="section-kicker">ROLE-BASED ACCESS CONTROL</span><h2>{{ accessDeniedMessage }}</h2><p>当前登录角色：<strong>{{ isAuthenticated ? userRole : 'anonymous' }}</strong>。如需更高权限，请联系系统管理员调整账号角色。</p><button @click="switchNav(userRole === 'agent' ? 'tickets' : 'chat')">{{ userRole === 'agent' ? '进入工单工作台' : '返回 AI Chat' }}</button></div></div>
      </section>

      <TicketCenter v-else-if="activeNav === 'tickets'" @open-trace="openLinkedTrace" />

      <AgentTracePage v-else-if="activeNav === 'trace'" :initial-trace-id="requestedTraceId" />

      <EvaluationDashboard v-else-if="activeNav === 'evaluation'" @open-trace="openLinkedTrace" />

      <KnowledgeCenter v-else-if="activeNav === 'knowledge'" />

      <AgentManagementCenter v-else-if="activeNav === 'agents'" />

      <section v-else class="admin-page">
        <div class="admin-intro"><span class="hero-pill">ENTERPRISE MANAGEMENT</span><h2>企业 AI 客服运营控制台</h2><p>统一管理知识资产、Agent 配置、执行链路、质量评估和人工服务工单。</p></div>
        <div class="admin-grid"><article v-for="module in adminModules" :key="module.title"><span :class="['admin-icon', module.color]">{{ module.icon }}</span><div><strong>{{ module.title }}</strong><p>{{ module.text }}</p></div><button @click="openAdminModule(module.title)">打开</button></article></div>
      </section>
    </main>
  </div>
</template>
