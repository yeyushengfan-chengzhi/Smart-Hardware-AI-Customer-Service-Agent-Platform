import { apiRequest, friendlyApiErrorMessage } from './apiClient'

export class AgentRequestError extends Error {
  constructor(stage, message, routing = null, options = {}) {
    super(message, options)
    this.name = 'AgentRequestError'
    this.stage = stage
    this.routing = routing
    this.status = options.cause?.status || 0
    this.code = options.cause?.code || ''
  }
}

const post = (path, body) => apiRequest(path, {
  method: 'POST',
  body: JSON.stringify(body),
})

export const routeAgent = (query) => post('/agent/route', { query })
export const askKnowledgeAgent = (query) => post('/agent/knowledge', { query })
export const askDiagnosisAgent = (query) => post('/agent/diagnosis', { query })
export const askToolAgent = (query) => post('/agent/tool', { query })

export async function executeAgent(query, { onStage = () => {} } = {}) {
  const totalStarted = performance.now()
  const timing = {
    route_start_time: new Date().toISOString(),
    route_end_time: null,
    agent_start_time: null,
    agent_end_time: null,
    route_latency_ms: null,
    agent_latency_ms: null,
    total_latency_ms: null,
  }

  onStage('routing')
  const routeStarted = performance.now()
  let routing
  try {
    routing = await routeAgent(query)
  } catch (error) {
    timing.route_end_time = new Date().toISOString()
    timing.route_latency_ms = Math.round(performance.now() - routeStarted)
    timing.total_latency_ms = Math.round(performance.now() - totalStarted)
    throw new AgentRequestError('routing', friendlyApiErrorMessage(error), null, { cause: error })
  }

  timing.route_end_time = new Date().toISOString()
  timing.route_latency_ms = Math.round(performance.now() - routeStarted)
  const route = routing.route?.toLowerCase()
  let request
  let generatingTimer

  if (route === 'diagnosis') {
    onStage('calling_agent', route)
    request = () => askDiagnosisAgent(query)
  } else if (route === 'knowledge') {
    onStage('retrieving', route)
    generatingTimer = setTimeout(() => onStage('generating', route), 900)
    request = () => askKnowledgeAgent(query)
  } else if (route === 'tool') {
    onStage('calling_agent', route)
    request = () => askToolAgent(query)
  } else {
    timing.total_latency_ms = Math.round(performance.now() - totalStarted)
    onStage('completed', route)
    return { routing, response: null, timing }
  }

  timing.agent_start_time = new Date().toISOString()
  const agentStarted = performance.now()
  let response
  try {
    response = await request()
  } catch (error) {
    throw new AgentRequestError('agent', friendlyApiErrorMessage(error), routing, { cause: error })
  } finally {
    clearTimeout(generatingTimer)
    timing.agent_end_time = new Date().toISOString()
    timing.agent_latency_ms = Math.round(performance.now() - agentStarted)
    timing.total_latency_ms = Math.round(performance.now() - totalStarted)
  }

  onStage('completed', route)
  return { routing, response, timing }
}
