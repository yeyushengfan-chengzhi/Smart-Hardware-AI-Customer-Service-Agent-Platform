<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getKnowledgeChunks,
  getKnowledgeDocument,
  getKnowledgeDocuments,
  getManualSeedStatus,
  importManualSeeds,
  searchKnowledge,
} from '../services/knowledgeApi'

const documents = ref([])
const loading = ref(false)
const error = ref('')
const filters = ref({ product_name: '', source_type: '', status: '', embedding_status: '' })
const page = ref(1)
const pageSize = 15
const drawerOpen = ref(false)
const detail = ref(null)
const chunks = ref([])
const detailLoading = ref(false)
const chunkPage = ref(1)
const chunkPageSize = 8
const searchQuery = ref('B850主板支持DDR5吗')
const searchLoading = ref(false)
const searchError = ref('')
const searchResults = ref([])
const seedStatus = ref({
  manifest_total: 0,
  manifest_downloaded: 0,
  manifest_needs_review: 0,
  imported_documents: 0,
  completed_documents: 0,
  total_chunks: 0,
})
const seedLoading = ref(false)
const seedImporting = ref(false)
const seedError = ref('')

const pageRows = computed(() => documents.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const chunkRows = computed(() => chunks.value.slice((chunkPage.value - 1) * chunkPageSize, chunkPage.value * chunkPageSize))
const stats = computed(() => ({
  total: documents.value.length,
  active: documents.value.filter((item) => item.status === 'active').length,
  completed: documents.value.filter((item) => item.embedding_status === 'completed').length,
  chunks: documents.value.reduce((sum, item) => sum + Number(item.chunk_count || 0), 0),
}))

onMounted(() => {
  loadDocuments()
  loadManualSeedStatus()
})

async function loadDocuments() {
  loading.value = true; error.value = ''
  try { documents.value = await getKnowledgeDocuments({ ...filters.value, limit: 500 }); page.value = 1 }
  catch { error.value = '知识文档服务暂不可用，请检查后端服务。'; documents.value = [] }
  finally { loading.value = false }
}
async function openDocument(row) {
  drawerOpen.value = true; detailLoading.value = true; detail.value = null; chunks.value = []; chunkPage.value = 1
  try { [detail.value, chunks.value] = await Promise.all([getKnowledgeDocument(row.id), getKnowledgeChunks(row.id)]) }
  catch { detail.value = { ...row, load_error: '文档详情或Chunk加载失败。' } }
  finally { detailLoading.value = false }
}
async function runSearch() {
  if (!searchQuery.value.trim()) return
  searchLoading.value = true; searchError.value = ''
  try { searchResults.value = (await searchKnowledge(searchQuery.value.trim(), 5)).results || [] }
  catch { searchError.value = '知识检索测试失败。'; searchResults.value = [] }
  finally { searchLoading.value = false }
}
function manifestErrorMessage(error) {
  const detail = String(error?.payload?.detail || error?.message || '')
  if (detail.includes('download_manifest.json may be updating')) {
    return 'Hermes 可能正在更新 manifest，请稍后重试。'
  }
  return detail || 'Manual Seed Dataset 状态暂不可用。'
}
async function loadManualSeedStatus() {
  seedLoading.value = true; seedError.value = ''
  try { seedStatus.value = await getManualSeedStatus() }
  catch (error) { seedError.value = manifestErrorMessage(error) }
  finally { seedLoading.value = false }
}
async function runManualSeedImport() {
  seedImporting.value = true; seedError.value = ''
  try {
    const result = await importManualSeeds()
    ElMessage.success(`增量导入完成：新增 ${result.imported}，跳过 ${result.skipped}，失败 ${result.failed}`)
    await Promise.all([loadManualSeedStatus(), loadDocuments()])
  } catch (error) {
    seedError.value = manifestErrorMessage(error)
    ElMessage.warning(seedError.value)
  } finally {
    seedImporting.value = false
  }
}
function formatTime(value) { return value ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '-' }
function statusType(value) { return value === 'completed' || value === 'active' ? 'success' : value === 'failed' ? 'danger' : value === 'processing' ? 'warning' : 'info' }
const sourceLabels = { official_manual_seed: '官方说明书', community_experience: '社区经验', uploaded: '用户上传' }
function sourceLabel(item) { return sourceLabels[item?.source_type] || '知识库来源' }
function sourceTagType(item) { return item?.source_type === 'community_experience' ? 'warning' : item?.source_type === 'uploaded' ? 'primary' : 'success' }
function verificationLabel(item) { return item?.verified ? '已验证' : '未验证 / 需谨慎使用' }
function displayLoadError(message) {
  return String(message || '').includes('document contains no extractable text')
    ? '该 PDF 可能是图片型说明书，当前无 OCR，暂无法抽取文本。'
    : message
}
</script>

<template>
  <section class="knowledge-page">
    <div class="knowledge-head"><div><span class="section-kicker">KNOWLEDGE / ENTERPRISE ASSETS</span><h2>Knowledge Center</h2><p>管理产品文档、查看切片结果并验证知识召回。</p></div><el-button type="primary" :loading="loading" @click="loadDocuments">刷新文档</el-button></div>
    <div class="knowledge-stats"><article><span>Documents</span><strong>{{ stats.total }}</strong></article><article><span>Active</span><strong>{{ stats.active }}</strong></article><article><span>Embedded</span><strong>{{ stats.completed }}</strong></article><article><span>Total Chunks</span><strong>{{ stats.chunks }}</strong></article></div>
    <section class="manual-seed-card" v-loading="seedLoading">
      <div class="manual-seed-heading"><div><span class="section-kicker">KNOWLEDGE EXPANSION</span><h3>Manual Seed Dataset</h3></div><el-button type="primary" :loading="seedImporting" @click="runManualSeedImport">Import New Manuals</el-button></div>
      <div class="manual-seed-metrics"><div><span>Manifest</span><strong>{{ seedStatus.manifest_total }}</strong></div><div><span>Downloaded</span><strong>{{ seedStatus.manifest_downloaded }}</strong></div><div><span>Needs Review</span><strong>{{ seedStatus.manifest_needs_review }}</strong></div><div><span>Imported</span><strong>{{ seedStatus.imported_documents }}</strong></div><div><span>Completed</span><strong>{{ seedStatus.completed_documents }}</strong></div><div><span>Chunks</span><strong>{{ seedStatus.total_chunks }}</strong></div></div>
      <el-alert v-if="seedError" type="warning" :closable="false" :title="seedError"/>
    </section>
    <div class="knowledge-workspace">
      <section class="knowledge-panel document-panel"><div class="knowledge-toolbar"><div><el-input v-model="filters.product_name" clearable placeholder="搜索产品名称" @keyup.enter="loadDocuments"/><el-select v-model="filters.source_type" clearable placeholder="全部来源" @change="loadDocuments"><el-option label="官方说明书" value="official_manual_seed"/><el-option label="社区经验" value="community_experience"/><el-option label="用户上传" value="uploaded"/></el-select><el-select v-model="filters.status" clearable placeholder="全部状态" @change="loadDocuments"><el-option label="Active" value="active"/><el-option label="Inactive" value="inactive"/></el-select><el-select v-model="filters.embedding_status" clearable placeholder="Embedding状态" @change="loadDocuments"><el-option label="Pending" value="pending"/><el-option label="Processing" value="processing"/><el-option label="Completed" value="completed"/><el-option label="Failed" value="failed"/></el-select><el-button @click="loadDocuments">查询</el-button></div></div><el-alert v-if="error" type="error" :closable="false" :title="error"/>
        <el-table v-else v-loading="loading" :data="pageRows" height="calc(100vh - 545px)" @row-click="openDocument"><el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip/><el-table-column prop="vendor" label="品牌" width="105"><template #default="{ row }">{{ row.vendor || '-' }}</template></el-table-column><el-table-column label="产品" width="165"><template #default="{ row }">{{ row.product_name || '-' }}</template></el-table-column><el-table-column prop="product_category" label="分类" width="105"><template #default="{ row }">{{ row.product_category || '-' }}</template></el-table-column><el-table-column label="来源" width="135"><template #default="{ row }"><el-tag v-if="row.source_type" size="small" :type="sourceTagType(row)">{{ sourceLabel(row) }}</el-tag><span v-else>-</span></template></el-table-column><el-table-column label="校验" width="170"><template #default="{ row }"><el-tag size="small" :type="row.verified ? 'success' : 'warning'">{{ verificationLabel(row) }}</el-tag></template></el-table-column><el-table-column prop="chunk_count" label="Chunks" width="85"/><el-table-column label="Embedding" width="115"><template #default="{ row }"><el-tag size="small" :type="statusType(row.embedding_status)">{{ row.embedding_status }}</el-tag></template></el-table-column><el-table-column label="" width="70"><template #default="{ row }"><el-button link type="primary" @click.stop="openDocument(row)">详情</el-button></template></el-table-column></el-table><div class="trace-pagination"><span>共 {{ documents.length }} 份文档</span><el-pagination v-model:current-page="page" layout="prev, pager, next" :page-size="pageSize" :total="documents.length"/></div></section>
      <section class="knowledge-panel search-test"><span class="section-kicker">RETRIEVAL TEST</span><h3>知识检索验证</h3><p>输入管理员问题，验证当前 Active 文档的 Top 5 召回结果。</p><el-input v-model="searchQuery" type="textarea" :rows="3" placeholder="例如：B850主板支持DDR5吗"/><el-button type="primary" :loading="searchLoading" :disabled="!searchQuery.trim()" @click="runSearch">开始检索</el-button><el-alert v-if="searchError" type="error" :closable="false" :title="searchError"/><div class="search-results"><article v-for="(item, index) in searchResults" :key="`${item.filename}-${item.page_number}-${index}`"><div><b>#{{ index + 1 }}</b><strong>{{ item.filename }}</strong><em>{{ (Number(item.score) * 100).toFixed(1) }}%</em></div><span>{{ sourceLabel(item) }} · Page {{ item.page_number ?? '-' }} · {{ item.section_title || '未标注章节' }}</span><p>{{ item.content }}</p></article><div v-if="!searchResults.length && !searchLoading" class="knowledge-empty">运行检索后在此查看召回内容</div></div></section>
    </div>
    <el-drawer v-model="drawerOpen" title="知识文档详情" size="680px" append-to-body><div class="knowledge-drawer" v-loading="detailLoading"><template v-if="detail"><el-alert v-if="detail.load_error" type="error" :closable="false" :title="displayLoadError(detail.load_error)"/><el-alert v-if="detail.embedding_status === 'failed'" type="error" :closable="false" title="该 PDF 可能是图片型说明书，当前无 OCR，暂无法抽取文本。"/><el-alert v-if="detail.source_type === 'community_experience'" type="warning" :closable="false" title="社区经验仅作为装机风险提示，不代表官方规格结论。"/><section><h3>基础信息</h3><dl><div><dt>文件名</dt><dd>{{ detail.filename }}</dd></div><div><dt>原始文件名</dt><dd>{{ detail.original_filename || detail.filename }}</dd></div><div><dt>品牌</dt><dd>{{ detail.vendor || '-' }}</dd></div><div><dt>产品</dt><dd>{{ detail.product_name || '-' }}</dd></div><div><dt>产品分类</dt><dd>{{ detail.product_category || '-' }}</dd></div><div><dt>文档类型</dt><dd>{{ detail.document_type || '-' }}</dd></div><div><dt>来源类型</dt><dd><el-tag size="small" :type="sourceTagType(detail)">{{ sourceLabel(detail) }}</el-tag></dd></div><div><dt>校验状态</dt><dd><el-tag size="small" :type="detail.verified ? 'success' : 'warning'">{{ verificationLabel(detail) }}</el-tag></dd></div><div><dt>状态 / Embedding</dt><dd>{{ detail.status }} / {{ detail.embedding_status }}</dd></div><div><dt>Chunk数量</dt><dd>{{ detail.chunk_count }}</dd></div><div><dt>文件来源</dt><dd><a v-if="detail.file_url || detail.source_url" :href="detail.file_url || detail.source_url" target="_blank" rel="noopener noreferrer">打开来源 URL</a><span v-else>-</span></dd></div><div><dt>支持页面</dt><dd><a v-if="detail.support_url" :href="detail.support_url" target="_blank" rel="noopener noreferrer">打开支持页面</a><span v-else>-</span></dd></div><div><dt>更新时间</dt><dd>{{ formatTime(detail.updated_time) }}</dd></div></dl></section><section><div class="chunk-heading"><h3>Chunk切片</h3><span>{{ chunks.length }} chunks</span></div><article v-for="chunk in chunkRows" :key="chunk.chunk_id" class="chunk-card"><div><b>Chunk #{{ chunk.chunk_id }}</b><span>Page {{ chunk.page_number ?? '-' }}</span></div><strong>{{ chunk.section_title || '未标注章节' }}</strong><p>{{ chunk.content }}</p></article><div class="trace-pagination"><span>第 {{ chunkPage }} 页</span><el-pagination v-model:current-page="chunkPage" layout="prev, pager, next" :page-size="chunkPageSize" :total="chunks.length"/></div></section><el-collapse><el-collapse-item title="文档原始 JSON"><pre>{{ JSON.stringify(detail, null, 2) }}</pre></el-collapse-item></el-collapse></template></div></el-drawer>
  </section>
</template>
