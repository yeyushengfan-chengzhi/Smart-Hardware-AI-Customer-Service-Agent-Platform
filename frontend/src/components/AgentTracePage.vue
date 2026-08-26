<script setup>
import { computed, onMounted, ref } from 'vue'
import { getTraceDetail, getTraces } from '../services/traceApi'

const props = defineProps({ initialTraceId: { type: String, default: '' } })

const traces = ref([])
const loading = ref(false)
const error = ref('')
const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const drawerOpen = ref(false)
const page = ref(1)
const pageSize = ref(20)
const filters = ref({ route: '', agent_name: '', status: '', handoff: '' })

const filteredTraces = computed(() => filters.value.handoff === ''
  ? traces.value
  : traces.value.filter((trace) => String(trace.handoff_suggested) === filters.value.handoff))
const pageRows = computed(() => filteredTraces.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const stats = computed(() => {
  const all = traces.value
  const success = all.filter((item) => item.status === 'success').length
  const latency = all.map((item) => Number(item.total_latency_ms)).filter(Number.isFinite)
  return {
    total: all.length, success, failed: all.filter((item) => item.status === 'failed').length,
    average: latency.length ? Math.round(latency.reduce((sum, value) => sum + value, 0) / latency.length) : 0,
    tools: all.filter((item) => item.agent_name === 'ToolAgent' || item.route === 'tool').length,
    handoffs: all.filter((item) => item.handoff_suggested).length,
  }
})
const timeline = computed(() => {
  if (!detail.value) return []
  const data = detail.value
  const nodes = [{ title: 'User Query', text: data.query }]
  nodes.push({ title: 'Supervisor Routing', text: `route=${data.route || 'unknown'}` })
  if (data.agent_name) nodes.push({ title: data.agent_name, text: data.intent || 'Agent execution' })
  if (data.tool_name) nodes.push({ title: 'Tool Calling', text: data.tool_name })
  nodes.push({ title: 'Final Response', text: data.status === 'success' ? 'Completed' : (data.error_message || 'Failed') })
  return nodes
})

onMounted(() => {
  loadTraces()
  if (props.initialTraceId) openDetail({ trace_id: decodeURIComponent(props.initialTraceId) })
})

async function loadTraces() {
  loading.value = true; error.value = ''
  try {
    traces.value = await getTraces({ route: filters.value.route, agent_name: filters.value.agent_name, status: filters.value.status, limit: 200 })
    page.value = 1
  } catch { error.value = 'Trace服务暂不可用，请检查后端服务。'; traces.value = [] }
  finally { loading.value = false }
}
async function openDetail(row) {
  drawerOpen.value = true; detail.value = null; detailError.value = ''; detailLoading.value = true
  try { detail.value = await getTraceDetail(row.trace_id) }
  catch { detailError.value = 'Trace详情加载失败。' }
  finally { detailLoading.value = false }
}
function formatTime(value) { return value ? new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value)) : '-' }
function latency(value) { return Number.isFinite(Number(value)) ? `${value} ms` : '-' }
function sourceKey(source, index) { return `${source.filename || source.file_name || 'source'}-${source.page_number || source.page || index}` }
function sourceLabel(source) { return ({ official_manual_seed: '官方说明书依据', community_experience: '社区经验提示', uploaded: '用户上传资料' })[source?.source_type] || '知识库来源' }
</script>

<template>
  <section class="trace-page">
    <div class="trace-page-head"><div><span class="section-kicker">OBSERVABILITY / AGENT TRACE</span><h2>Agent Trace</h2><p>查看 AI 路由、Agent 执行、工具调用与人工接管信号。</p></div><el-button type="primary" :loading="loading" @click="loadTraces">刷新</el-button></div>
    <div class="trace-stats"><article><span>Trace总数量</span><strong>{{ stats.total }}</strong></article><article><span>成功数量</span><strong class="success-text">{{ stats.success }}</strong></article><article><span>失败数量</span><strong class="failed-text">{{ stats.failed }}</strong></article><article><span>平均响应时间</span><strong>{{ stats.average }} ms</strong></article><article><span>Tool调用次数</span><strong>{{ stats.tools }}</strong></article><article><span>Handoff次数</span><strong>{{ stats.handoffs }}</strong></article></div>
    <div class="trace-table-card"><div class="trace-filters"><el-select v-model="filters.route" placeholder="Route：全部" clearable @change="loadTraces"><el-option label="全部" value=""/><el-option label="knowledge" value="knowledge"/><el-option label="diagnosis" value="diagnosis"/><el-option label="tool" value="tool"/><el-option label="GeneralAgent" value="GeneralAgent"/></el-select><el-select v-model="filters.agent_name" placeholder="Agent：全部" clearable @change="loadTraces"><el-option label="全部" value=""/><el-option label="KnowledgeAgent" value="KnowledgeAgent"/><el-option label="DiagnosisAgent" value="DiagnosisAgent"/><el-option label="ToolAgent" value="ToolAgent"/><el-option label="GeneralAgent" value="GeneralAgent"/></el-select><el-select v-model="filters.status" placeholder="Status：全部" clearable @change="loadTraces"><el-option label="全部" value=""/><el-option label="success" value="success"/><el-option label="failed" value="failed"/></el-select><el-select v-model="filters.handoff" placeholder="Handoff：全部" clearable @change="page = 1"><el-option label="全部" value=""/><el-option label="需要人工" value="true"/><el-option label="无需人工" value="false"/></el-select></div>
      <el-alert v-if="error" type="error" :closable="false" show-icon :title="error"/>
      <el-table v-else v-loading="loading" :data="pageRows" height="calc(100vh - 405px)" @row-click="openDetail"><el-table-column prop="trace_id" label="Trace ID" width="160"><template #default="{ row }"><code class="trace-short-id">{{ row.trace_id }}</code></template></el-table-column><el-table-column prop="query" label="用户问题" min-width="210" show-overflow-tooltip/><el-table-column prop="route" label="Route" width="110"/><el-table-column prop="agent_name" label="Agent" width="150"/><el-table-column label="Status" width="100"><template #default="{ row }"><el-tag size="small" :type="row.status === 'success' ? 'success' : 'danger'">{{ row.status }}</el-tag></template></el-table-column><el-table-column label="Handoff" width="105"><template #default="{ row }"><el-tag size="small" :type="row.handoff_suggested ? 'warning' : 'info'">{{ row.handoff_suggested ? '需要人工' : '无需人工' }}</el-tag></template></el-table-column><el-table-column label="耗时" width="95"><template #default="{ row }">{{ latency(row.total_latency_ms) }}</template></el-table-column><el-table-column label="创建时间" width="155"><template #default="{ row }">{{ formatTime(row.created_time) }}</template></el-table-column><el-table-column label="" width="80"><template #default="{ row }"><el-button link type="primary" @click.stop="openDetail(row)">详情</el-button></template></el-table-column></el-table>
      <div class="trace-pagination"><span>共 {{ filteredTraces.length }} 条</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev, pager, next" :total="filteredTraces.length" :page-sizes="[20]"/></div>
    </div>
    <el-drawer v-model="drawerOpen" title="Trace 详情" size="640px" append-to-body><div class="trace-drawer" v-loading="detailLoading"><el-alert v-if="detailError" type="error" :closable="false" :title="detailError"/><template v-else-if="detail"><section class="trace-detail-section"><h3>基础信息</h3><dl class="trace-basics"><div><dt>Trace ID</dt><dd>{{ detail.trace_id }}</dd></div><div><dt>Query</dt><dd>{{ detail.query }}</dd></div><div><dt>Route</dt><dd>{{ detail.route }}</dd></div><div><dt>Intent</dt><dd>{{ detail.intent }}</dd></div><div><dt>Device Type</dt><dd>{{ detail.device_type }}</dd></div><div><dt>Fault Type</dt><dd>{{ detail.fault_type }}</dd></div><div><dt>Agent Name</dt><dd>{{ detail.agent_name }}</dd></div><div><dt>Status</dt><dd>{{ detail.status }}</dd></div></dl></section><section class="trace-detail-section"><h3>执行链路 Timeline</h3><div class="trace-timeline"><div v-for="(node, index) in timeline" :key="node.title" class="timeline-node"><i>✓</i><div><strong>{{ node.title }}</strong><small>{{ node.text }}</small></div><span v-if="index < timeline.length - 1"></span></div></div></section><el-collapse><el-collapse-item title="Route Response 原始 JSON"><pre>{{ JSON.stringify(detail.route_response, null, 2) }}</pre></el-collapse-item><el-collapse-item title="Agent Response 原始 JSON"><pre>{{ JSON.stringify(detail.agent_response, null, 2) }}</pre></el-collapse-item></el-collapse><section v-if="detail.tool_name" class="trace-detail-section"><h3>Tool Panel</h3><div class="trace-tool"><strong>{{ detail.tool_name }}</strong><el-collapse><el-collapse-item title="Tool 原始输入 / 输出"><label>Input</label><pre>{{ JSON.stringify(detail.tool_input, null, 2) }}</pre><label>Output</label><pre>{{ JSON.stringify(detail.tool_result, null, 2) }}</pre></el-collapse-item></el-collapse></div></section><section v-if="detail.sources?.length" class="trace-detail-section"><h3>RAG Sources</h3><div v-for="(source, index) in detail.sources" :key="sourceKey(source, index)" class="trace-source"><b>{{ source.source_type === 'community_experience' ? '经验' : '文档' }}</b><div><strong>{{ sourceLabel(source) }} · {{ source.filename || source.file_name || '未知文件' }}</strong><span>Page {{ source.page_number ?? source.page ?? '-' }} · {{ source.section_title || source.section || '-' }}</span></div></div></section><section class="trace-detail-section"><h3>Latency</h3><div class="latency-grid"><div><span>Route latency</span><strong>{{ latency(detail.latency?.route_latency_ms) }}</strong></div><div><span>Agent latency</span><strong>{{ latency(detail.latency?.agent_latency_ms) }}</strong></div><div><span>Total latency</span><strong>{{ latency(detail.latency?.total_latency_ms) }}</strong></div></div></section><section v-if="detail.handoff_suggested" class="trace-handoff"><strong>需要人工接管</strong><span>原因：{{ detail.handoff_reason || 'unknown' }}</span></section></template></div></el-drawer>
  </section>
</template>
