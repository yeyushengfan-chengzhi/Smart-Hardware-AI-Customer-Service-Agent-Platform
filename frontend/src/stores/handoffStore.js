import { ref } from 'vue'

const STORAGE_KEY = 'smart-hardware-ai-handoffs-v1'

function loadHandoffs() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

export const handoffs = ref(loadHandoffs())

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(handoffs.value))
}

function sourceNames(sources) {
  return [...new Set((sources || []).map((source) => source.filename).filter(Boolean))]
}

export function detectHandoffReason(routing, response, adapted) {
  if (response?.handoff_suggested) return response.handoff_reason || 'AI 建议转人工进一步确认'
  const route = routing?.route?.toLowerCase()
  const answer = adapted?.answer || ''
  if (!route || ['generalagent', 'unknown'].includes(route)) return 'AI 无法识别为当前支持的硬件问题'
  if (route === 'knowledge' && !adapted.sources.length) return '知识库未返回可追溯来源'
  if (route === 'tool' && response?.tool_result?.compatible === 'unknown') {
    return '缺少关键型号或规格信息，AI 无法可靠判断。'
  }
  if (answer.includes('没有找到明确资料')) return 'AI 没有找到明确资料'
  if (answer.includes('建议联系人工客服')) return 'AI 建议联系人工客服'
  return ''
}

export function createHandoff({ query, routing, response, adapted, reason, handoffContext = null }) {
  const steps = adapted.steps.map((step) => step.action)
  const handoff = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    created_at: new Date().toISOString(),
    status: 'pending',
    user_query: query,
    ai_answer: adapted.answer,
    route_response: routing || {},
    agent_response: response || {},
    handoff_reason: reason || '用户主动要求人工 / AI 无法确认问题是否解决',
    handoff_context: handoffContext,
    summary: {
      user_issue: query,
      detected_route: routing?.route || 'unknown',
      device_type: adapted.device || 'unknown',
      fault_type: adapted.fault_type || 'unknown',
      ai_tried: steps.length ? steps : [adapted.answer],
      sources: sourceNames(adapted.sources),
      tool_result: adapted.tool_result || {},
      next_action: adapted.device === 'gpu'
        ? '确认显卡型号、电源型号和主板 Debug 灯颜色，并判断是否需要创建售后工单。'
        : '补充确认具体硬件型号、当前现象和已完成的排查步骤，必要时创建售后工单。',
    },
  }
  handoffs.value.unshift(handoff)
  persist()
  return handoff
}

export function resolveHandoff(id) {
  const item = handoffs.value.find((handoff) => handoff.id === id)
  if (item) {
    item.status = 'resolved'
    item.resolved_at = new Date().toISOString()
    persist()
  }
}
