<script setup>
import { computed, onMounted, ref } from 'vue'
import { getEvaluationResults, getEvaluationRuns } from '../services/evaluationApi'
import BenchmarkReport from './BenchmarkReport.vue'

const emit = defineEmits(['open-trace'])
const results = ref([])
const runs = ref([])
const loading = ref(false)
const error = ref('')
const statusFilter = ref('')
const categoryFilter = ref('')
const page = ref(1)
const pageSize = 15
const drawerOpen = ref(false)
const selected = ref(null)

const filtered = computed(() => results.value.filter((item) =>
  (!statusFilter.value || item.status === statusFilter.value)
  && (!categoryFilter.value || item.category === categoryFilter.value)))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const stats = computed(() => {
  const total = results.value.length
  const passed = results.value.filter((item) => item.status === 'passed').length
  const failed = total - passed
  const average = total ? results.value.reduce((sum, item) => sum + Number(item.score || 0), 0) / total : 0
  return { total, passed, failed, rate: total ? passed / total : 0, average }
})
const agentDistribution = computed(() => ['KnowledgeAgent', 'DiagnosisAgent', 'ToolAgent', 'GeneralAgent'].map((name) => ({
  name, count: results.value.filter((item) => item.actual_agent === name).length,
})))
const failureReasons = computed(() => {
  const failed = results.value.filter((item) => item.status === 'failed')
  return [
    { name: 'Route错误', count: failed.filter((item) => !item.route_match).length },
    { name: 'Agent错误', count: failed.filter((item) => !item.agent_match).length },
    { name: 'Tool错误', count: failed.filter((item) => !item.tool_match).length },
    { name: 'Keyword不足', count: failed.filter((item) => Number(item.keyword_score) < 1).length },
  ]
})
const maxAgentCount = computed(() => Math.max(1, ...agentDistribution.value.map((item) => item.count)))
const maxFailureCount = computed(() => Math.max(1, ...failureReasons.value.map((item) => item.count)))

onMounted(loadData)

async function loadData() {
  loading.value = true; error.value = ''
  try { [results.value, runs.value] = await Promise.all([getEvaluationResults(), getEvaluationRuns()]); page.value = 1 }
  catch { error.value = 'Evaluation服务暂不可用，请检查后端服务。'; results.value = []; runs.value = [] }
  finally { loading.value = false }
}
function formatTime(value) { return value ? new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '-' }
function percent(value) { return `${(Number(value || 0) * 100).toFixed(1)}%` }
function showFailure(row) { selected.value = row; drawerOpen.value = true }
function changeFilter() { page.value = 1 }
</script>

<template>
  <section class="evaluation-page">
    <div class="evaluation-head"><div><span class="section-kicker">QUALITY / REGRESSION EVALUATION</span><h2>Evaluation Harness</h2><p>查看 Agent 回归测试、失败案例和质量分布。</p></div><el-button type="primary" :loading="loading" @click="loadData">刷新数据</el-button></div>
    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error"/>
    <BenchmarkReport />
    <template v-else>
      <div class="evaluation-stats"><article><span>Total Cases</span><strong>{{ stats.total }}</strong></article><article><span>Passed</span><strong class="success-text">{{ stats.passed }}</strong></article><article><span>Failed</span><strong class="failed-text">{{ stats.failed }}</strong></article><article><span>Pass Rate</span><strong>{{ percent(stats.rate) }}</strong></article><article><span>Average Score</span><strong>{{ stats.average.toFixed(1) }}</strong></article></div>
      <div class="evaluation-scroll" v-loading="loading">
        <div class="evaluation-overview"><section class="evaluation-panel"><h3>Evaluation Runs</h3><div class="run-list"><article v-for="run in runs" :key="run.run_id"><div><strong>{{ run.run_name }}</strong><span>{{ formatTime(run.created_time) }}</span></div><dl><div><dt>Total</dt><dd>{{ run.total_cases }}</dd></div><div><dt>Passed</dt><dd>{{ run.passed_cases }}</dd></div><div><dt>Failed</dt><dd>{{ run.failed_cases }}</dd></div><div><dt>Pass Rate</dt><dd>{{ percent(run.pass_rate) }}</dd></div></dl></article><p v-if="!runs.length" class="evaluation-empty">暂无历史评测任务</p></div></section><section class="evaluation-panel chart-panel"><h3>Agent分布</h3><div class="mini-bars"><div v-for="item in agentDistribution" :key="item.name"><label><span>{{ item.name }}</span><b>{{ item.count }}</b></label><i><em :style="{ width: `${item.count / maxAgentCount * 100}%` }"></em></i></div></div></section><section class="evaluation-panel chart-panel"><h3>失败原因统计</h3><div class="mini-bars failure-bars"><div v-for="item in failureReasons" :key="item.name"><label><span>{{ item.name }}</span><b>{{ item.count }}</b></label><i><em :style="{ width: `${item.count / maxFailureCount * 100}%` }"></em></i></div></div></section></div>
        <section class="evaluation-panel result-panel"><div class="result-head"><div><h3>测试结果</h3><span>当前展示最新 Run，共 {{ filtered.length }} 条</span></div><div><el-select v-model="categoryFilter" placeholder="全部分类" clearable @change="changeFilter"><el-option label="Knowledge" value="knowledge"/><el-option label="Diagnosis" value="diagnosis"/><el-option label="Tool" value="tool"/><el-option label="General" value="general"/><el-option label="Handoff" value="handoff"/></el-select><el-select v-model="statusFilter" placeholder="全部状态" clearable @change="changeFilter"><el-option label="Passed" value="passed"/><el-option label="Failed" value="failed"/></el-select><el-button :type="statusFilter === 'failed' ? 'danger' : 'default'" @click="statusFilter = statusFilter === 'failed' ? '' : 'failed'; changeFilter()">只看失败</el-button></div></div>
          <el-table :data="pageRows" @row-click="showFailure"><el-table-column prop="question" label="Question" min-width="220" show-overflow-tooltip/><el-table-column prop="category" label="Category" width="100"/><el-table-column prop="expected_route" label="Expected Route" width="125"/><el-table-column prop="actual_route" label="Actual Route" width="115"/><el-table-column prop="expected_agent" label="Expected Agent" width="150"/><el-table-column prop="actual_agent" label="Actual Agent" width="145"/><el-table-column label="Score" width="80"><template #default="{ row }"><b :class="row.score >= 80 ? 'score-pass' : 'score-fail'">{{ Number(row.score).toFixed(0) }}</b></template></el-table-column><el-table-column label="Status" width="95"><template #default="{ row }"><el-tag size="small" :type="row.status === 'passed' ? 'success' : 'danger'">{{ row.status }}</el-tag></template></el-table-column><el-table-column label="操作" width="100"><template #default="{ row }"><el-button v-if="row.trace_id" link type="primary" @click.stop="emit('open-trace', row.trace_id)">查看Trace</el-button></template></el-table-column></el-table>
          <div class="trace-pagination"><span>第 {{ page }} 页</span><el-pagination v-model:current-page="page" layout="prev, pager, next" :page-size="pageSize" :total="filtered.length"/></div>
        </section>
      </div>
    </template>
    <el-drawer v-model="drawerOpen" title="Evaluation 结果详情" size="560px" append-to-body><div v-if="selected" class="evaluation-drawer"><el-tag :type="selected.status === 'passed' ? 'success' : 'danger'">{{ selected.status }}</el-tag><h2>{{ selected.question }}</h2><dl><div><dt>Category</dt><dd>{{ selected.category }}</dd></div><div><dt>Expected Route</dt><dd>{{ selected.expected_route }}</dd></div><div><dt>Actual Route</dt><dd>{{ selected.actual_route }}</dd></div><div><dt>Expected Agent</dt><dd>{{ selected.expected_agent }}</dd></div><div><dt>Actual Agent</dt><dd>{{ selected.actual_agent }}</dd></div><div><dt>Expected Tool</dt><dd>{{ selected.expected_tool || '-' }}</dd></div><div><dt>Actual Tool</dt><dd>{{ selected.actual_tool || '-' }}</dd></div><div><dt>Score</dt><dd>{{ selected.score }}</dd></div><div><dt>Trace ID</dt><dd><code>{{ selected.trace_id || '-' }}</code></dd></div></dl><section v-if="selected.status === 'failed'" class="failure-reason"><strong>Failure Reason</strong><p>{{ selected.error_message || '未提供失败原因' }}</p></section><el-collapse><el-collapse-item title="原始评测数据"><pre>{{ JSON.stringify(selected, null, 2) }}</pre></el-collapse-item></el-collapse><el-button v-if="selected.trace_id" type="primary" @click="emit('open-trace', selected.trace_id)">查看关联 Trace</el-button></div></el-drawer>
  </section>
</template>
