import { apiRequest } from './apiClient'

async function get(path, params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  return apiRequest(`${path}${search.size ? `?${search}` : ''}`)
}

async function getRawResults() {
  const [results, cases] = await Promise.all([
    get('/evaluation/results', { limit: 1000 }),
    get('/evaluation/cases', { limit: 1000 }),
  ])
  const categories = new Map(cases.map((item) => [item.id, item.category]))
  return results.map((item) => ({ ...item, category: categories.get(item.case_id) || 'unknown' }))
}

export async function getEvaluationResults(params = {}) {
  const results = await getRawResults()
  const latestRunId = results.reduce((latest, item) => Math.max(latest, Number(item.run_id) || 0), 0)
  const runId = params.run_id ?? latestRunId
  return results.filter((item) => (!runId || Number(item.run_id) === Number(runId))
    && (!params.status || item.status === params.status)
    && (!params.category || item.category === params.category))
}

export async function getEvaluationRuns() {
  const results = await getRawResults()
  const grouped = new Map()
  results.forEach((item) => {
    const run = grouped.get(item.run_id) || {
      run_id: item.run_id,
      run_name: `Evaluation Run #${item.run_id}`,
      total_cases: 0,
      passed_cases: 0,
      failed_cases: 0,
      created_time: item.created_time,
    }
    run.total_cases += 1
    run.passed_cases += item.status === 'passed' ? 1 : 0
    run.failed_cases += item.status === 'failed' ? 1 : 0
    if (item.created_time > run.created_time) run.created_time = item.created_time
    grouped.set(item.run_id, run)
  })
  return [...grouped.values()].map((run) => ({
    ...run,
    pass_rate: run.total_cases ? run.passed_cases / run.total_cases : 0,
  })).sort((a, b) => Number(b.run_id) - Number(a.run_id))
}
