<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { addTicketMessage, getTicket, listTickets, updateTicketStatus } from '../services/ticketApi'
import { userRole } from '../stores/authStore'

const emit = defineEmits(['open-trace'])
const tickets = ref([])
const loading = ref(false)
const detailLoading = ref(false)
const drawerOpen = ref(false)
const selected = ref(null)
const statusFilter = ref('')
const priorityFilter = ref('')
const reply = ref('')
const submittingReply = ref(false)

const openCount = computed(() => tickets.value.filter((item) => item.status === 'open').length)
const latestAiAnswer = computed(() => [...(selected.value?.messages || [])].reverse().find((item) => item.sender_type === 'ai')?.content || '暂无 AI 回答')
const canViewTrace = computed(() => userRole.value === 'admin')

const statusLabels = { open: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭' }
const priorityLabels = { low: '低', medium: '中', high: '高', urgent: '紧急' }
const sourceLabels = { ai_handoff: 'AI 转人工', user_request: '用户主动' }

function tagType(value) {
  return ({ open: 'danger', processing: 'warning', resolved: 'success', closed: 'info' })[value] || 'info'
}

function priorityType(value) {
  return ({ low: 'info', medium: '', high: 'warning', urgent: 'danger' })[value] || 'info'
}

function formatTime(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

async function loadTickets() {
  loading.value = true
  try {
    tickets.value = await listTickets({ status: statusFilter.value, priority: priorityFilter.value })
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

async function openDetail(item) {
  drawerOpen.value = true
  detailLoading.value = true
  reply.value = ''
  try {
    selected.value = await getTicket(item.ticket_id)
  } catch (error) {
    drawerOpen.value = false
    ElMessage.error(error.message)
  } finally {
    detailLoading.value = false
  }
}

async function changeStatus(status) {
  if (!selected.value || status === selected.value.status) return
  try {
    await updateTicketStatus(selected.value.ticket_id, status)
    selected.value.status = status
    const listItem = tickets.value.find((item) => item.ticket_id === selected.value.ticket_id)
    if (listItem) listItem.status = status
    ElMessage.success('工单状态已更新')
    if (statusFilter.value && statusFilter.value !== status) await loadTickets()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

async function submitReply() {
  const content = reply.value.trim()
  if (!selected.value || !content || submittingReply.value) return
  submittingReply.value = true
  try {
    const ticketId = selected.value.ticket_id
    const shouldAutoProcess = selected.value.status === 'open'
    await addTicketMessage(ticketId, content)
    if (shouldAutoProcess) {
      try {
        await updateTicketStatus(ticketId, 'processing')
      } catch (statusError) {
        reply.value = ''
        selected.value = await getTicket(ticketId)
        ElMessage.warning('回复已发送，但工单状态自动更新失败，请手动修改')
        return
      }
    }
    reply.value = ''
    selected.value = await getTicket(ticketId)
    const listItem = tickets.value.find((item) => item.ticket_id === ticketId)
    if (listItem) listItem.status = selected.value.status
    if (statusFilter.value && statusFilter.value !== selected.value.status) await loadTickets()
    ElMessage.success('回复已发送')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    submittingReply.value = false
  }
}

onMounted(loadTickets)
</script>

<template>
  <section class="ticket-center">
    <div class="ticket-heading">
      <div><span>CUSTOMER SERVICE</span><h2>工单管理</h2><p>查看 AI 转人工与用户主动提交的售后工单。</p></div>
      <div class="ticket-stat"><strong>{{ openCount }}</strong><span>当前待处理</span></div>
    </div>

    <div class="ticket-filters">
      <el-select v-model="statusFilter" placeholder="全部状态" clearable @change="loadTickets">
        <el-option label="待处理" value="open" />
        <el-option label="处理中" value="processing" />
        <el-option label="已解决" value="resolved" />
        <el-option label="已关闭" value="closed" />
      </el-select>
      <el-select v-model="priorityFilter" placeholder="全部优先级" clearable @change="loadTickets">
        <el-option label="低" value="low" /><el-option label="中" value="medium" />
        <el-option label="高" value="high" /><el-option label="紧急" value="urgent" />
      </el-select>
      <button class="refresh-button" :disabled="loading" @click="loadTickets">刷新</button>
    </div>

    <div class="ticket-table-card" v-loading="loading">
      <el-table :data="tickets" empty-text="暂无工单" @row-click="openDetail">
        <el-table-column prop="ticket_id" label="Ticket ID" width="170"><template #default="{ row }"><code>{{ row.ticket_id }}</code></template></el-table-column>
        <el-table-column label="用户" width="105"><template #default="{ row }">#{{ row.user_id }}</template></el-table-column>
        <el-table-column prop="title" label="问题" min-width="240" show-overflow-tooltip />
        <el-table-column label="来源" width="120"><template #default="{ row }">{{ sourceLabels[row.source] }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="tagType(row.status)">{{ statusLabels[row.status] }}</el-tag></template></el-table-column>
        <el-table-column label="优先级" width="100"><template #default="{ row }"><el-tag effect="plain" :type="priorityType(row.priority)">{{ priorityLabels[row.priority] }}</el-tag></template></el-table-column>
        <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.created_time) }}</template></el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawerOpen" size="620px" :title="selected ? `工单 ${selected.ticket_id}` : '工单详情'">
      <div v-if="selected" v-loading="detailLoading" class="ticket-detail">
        <div class="detail-meta">
          <el-tag :type="tagType(selected.status)">{{ statusLabels[selected.status] }}</el-tag>
          <el-tag effect="plain" :type="priorityType(selected.priority)">{{ priorityLabels[selected.priority] }}优先级</el-tag>
          <span>{{ sourceLabels[selected.source] }}</span><time>{{ formatTime(selected.created_time) }}</time>
        </div>

        <section class="session-info"><label>用户与 Session</label><div><span>用户 #{{ selected.user_id }}</span><code>Session #{{ selected.session_id }}</code></div></section>
        <section><label>客户问题</label><h3>{{ selected.title }}</h3></section>
        <section><label>AI 回答</label><p>{{ latestAiAnswer }}</p></section>
        <section class="handoff-reason"><label>Handoff 原因</label><p>{{ selected.handoff_reason || '用户主动要求人工处理' }}</p></section>
        <section class="trace-link"><label>AI 执行信息</label><div><span>{{ selected.agent_name || '未执行 Agent' }}</span><button v-if="selected.trace_id && canViewTrace" @click="emit('open-trace', selected.trace_id)">查看 Agent Trace →</button></div></section>

        <section><label>聊天记录</label><div class="ticket-timeline">
          <article v-for="message in selected.messages" :key="message.id" :class="message.sender_type">
            <div><strong>{{ message.sender_type === 'customer' ? '客户' : message.sender_type === 'ai' ? 'AI 客服' : '人工客服' }}</strong><time>{{ formatTime(message.created_time) }}</time></div>
            <p>{{ message.content }}</p>
          </article>
        </div></section>

        <section><label>处理状态</label><el-select :model-value="selected.status" @change="changeStatus">
          <el-option label="待处理" value="open" /><el-option label="处理中" value="processing" />
          <el-option label="已解决" value="resolved" /><el-option label="已关闭" value="closed" />
        </el-select></section>

        <section><label>客服回复</label><el-input v-model="reply" type="textarea" :rows="4" maxlength="20000" show-word-limit placeholder="请输入要发送给用户的人工客服回复" />
          <button class="reply-button" :disabled="!reply.trim() || submittingReply" @click="submitReply">{{ submittingReply ? '发送中…' : '发送回复' }}</button>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.ticket-center{padding:28px 34px;color:#172033}.ticket-heading{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:22px}.ticket-heading>div>span{font-size:11px;letter-spacing:.15em;color:#6c63d9;font-weight:800}.ticket-heading h2{margin:7px 0 5px;font-size:27px}.ticket-heading p{margin:0;color:#748096}.ticket-stat{min-width:135px;padding:14px 18px;border:1px solid #e4e8f1;border-radius:14px;background:#fff;display:flex;flex-direction:column}.ticket-stat strong{font-size:25px;color:#6c63d9}.ticket-stat span{font-size:12px;color:#8791a4}.ticket-filters{display:flex;gap:12px;margin-bottom:16px}.ticket-filters .el-select{width:160px}.refresh-button,.reply-button{border:0;border-radius:9px;padding:0 18px;background:#665cd7;color:#fff;cursor:pointer;font-weight:700}.ticket-table-card{background:#fff;border:1px solid #e4e8f1;border-radius:14px;overflow:hidden}.ticket-table-card code{color:#5f56c9;font-weight:700}.ticket-table-card :deep(.el-table__row){cursor:pointer}.ticket-detail{display:flex;flex-direction:column;gap:16px}.detail-meta{display:flex;align-items:center;gap:9px;color:#7c8799;font-size:12px}.detail-meta time{margin-left:auto}.ticket-detail section{padding:16px;border:1px solid #e6e9f0;border-radius:12px;background:#fff}.ticket-detail label{display:block;margin-bottom:10px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#8a94a7;font-weight:800}.ticket-detail h3{margin:0 0 8px;font-size:17px}.ticket-detail p{margin:0;line-height:1.65;white-space:pre-wrap}.handoff-reason{border-left:4px solid #ef9f35!important;background:#fffaf2!important}.trace-link>div{display:flex;justify-content:space-between;align-items:center}.trace-link button{border:0;background:transparent;color:#6359d2;font-weight:700;cursor:pointer}.ticket-timeline{display:flex;flex-direction:column;gap:10px}.ticket-timeline article{padding:12px 14px;border-radius:10px;background:#f5f7fb}.ticket-timeline article.ai{border-left:3px solid #6d63d9}.ticket-timeline article.human_agent{border-left:3px solid #29a677;background:#f1fbf7}.ticket-timeline article.customer{border-left:3px solid #8090a8}.ticket-timeline article>div{display:flex;justify-content:space-between;margin-bottom:6px}.ticket-timeline time{font-size:11px;color:#929bad}.reply-button{height:38px;margin-top:10px;float:right}.reply-button:disabled,.refresh-button:disabled{opacity:.55;cursor:not-allowed}
.session-info>div{display:flex;justify-content:space-between;align-items:center}.session-info span{font-weight:700;color:#3f4a5e}.session-info code{padding:5px 8px;border-radius:6px;color:#5f56c9;background:#f1efff}
</style>
