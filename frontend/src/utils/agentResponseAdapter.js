const AGENT_NAMES = {
  diagnosis: 'DiagnosisAgent',
  knowledge: 'KnowledgeAgent',
  tool: 'ToolAgent',
}

function uniqueSources(sources) {
  const seen = new Set()
  return sources.filter((source) => {
    const key = `${source.filename}|${source.page_number}|${source.section_title}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function diagnosisSummary(response) {
  if (!response?.steps?.length) return '暂未生成诊断步骤，请补充硬件型号和故障现象。'
  return `已识别为 ${response.device || '未知设备'} 的 ${response.fault_type || '硬件故障'}，建议按以下 ${response.steps.length} 个步骤依次排查。`
}

export function agentResponseAdapter(routing, response) {
  const route = routing?.route?.toLowerCase() || 'unknown'
  const steps = route === 'diagnosis' ? response?.steps || [] : []
  const sources = route === 'diagnosis'
    ? uniqueSources(steps.flatMap((step) => step.sources || []))
    : uniqueSources(response?.sources || [])

  return {
    query: response?.query || routing?.query || '',
    route: routing?.route || 'unknown',
    intent: routing?.intent || 'unknown',
    agent: AGENT_NAMES[route] || '—',
    answer: route === 'diagnosis'
      ? diagnosisSummary(response)
      : response?.answer || '当前系统主要支持智能硬件客服问题，请换一种硬件相关描述。',
    steps,
    sources,
    tool_name: response?.tool_name || '',
    tool_input: response?.tool_input || {},
    tool_result: response?.tool_result || {},
    raw_response: response || {},
    device: response?.device || routing?.device_type || 'unknown',
    fault_type: response?.fault_type || routing?.fault_type || 'unknown',
  }
}
