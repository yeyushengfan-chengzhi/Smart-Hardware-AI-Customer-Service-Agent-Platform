<script setup>
import { computed, onMounted, ref } from 'vue'
import { getNextDiagnosticCheck } from '../services/adaptiveDiagnosisApi'

const emit = defineEmits(['ask'])

const scenarios = [
  { id: 'black-screen', label: '开机黑屏', query: '主机开机黑屏，没有任何画面', faultType: 'no_display' },
  { id: 'overheating', label: '温度过高', query: 'CPU 待机温度很高并且容易降频', faultType: 'overheating' },
  { id: 'safety', label: '闻到焦味', query: '电源冒烟并且闻到焦味', faultType: 'boot_failure' },
]

const selectedScenario = ref(scenarios[0])
const observations = ref([])
const diagnosis = ref(null)
const loading = ref(false)
const error = ref('')
const completedSteps = computed(() => observations.value.length)
const topHypothesis = computed(() => diagnosis.value?.hypotheses?.[0])

async function loadDecision() {
  loading.value = true
  error.value = ''
  try {
    diagnosis.value = await getNextDiagnosticCheck({
      query: selectedScenario.value.query,
      fault_type: selectedScenario.value.faultType,
      observations: observations.value,
    })
  } catch (requestError) {
    error.value = requestError.message || '诊断服务暂时不可用'
  } finally {
    loading.value = false
  }
}

async function chooseScenario(scenario) {
  selectedScenario.value = scenario
  observations.value = []
  diagnosis.value = null
  await loadDecision()
}

async function recordOutcome(outcome) {
  const checkId = diagnosis.value?.next_check?.check_id
  if (!checkId || loading.value) return
  observations.value.push({ check_id: checkId, outcome })
  await loadDecision()
}

function probability(value) {
  return Math.round(Number(value || 0) * 100)
}

function restart() {
  observations.value = []
  loadDecision()
}

onMounted(loadDecision)
</script>

<template>
  <section class="triage-stage">
    <div class="triage-copy">
      <div class="live-kicker"><i></i> LIVE DIAGNOSTIC COPILOT</div>
      <h2>别猜是哪坏了。<br><span>让每一步检查缩小答案。</span></h2>
      <p class="triage-lead">面向 DIY 电脑售后的可解释诊断 Agent。它会根据你的反馈更新故障概率，并选择下一项最有价值的检查。</p>

      <div class="scenario-label">选择一个现场故障，直接看系统怎么推理</div>
      <div class="scenario-switcher">
        <button
          v-for="scenario in scenarios"
          :key="scenario.id"
          :class="{ active: selectedScenario.id === scenario.id }"
          @click="chooseScenario(scenario)"
        >
          <span>{{ scenario.id === 'black-screen' ? '◉' : scenario.id === 'overheating' ? '⌁' : '⚠' }}</span>
          {{ scenario.label }}
        </button>
      </div>

      <div class="proof-strip">
        <div><strong>4</strong><span>候选原因实时排序</span></div>
        <div><strong>IG</strong><span>信息增益选下一步</span></div>
        <div><strong>SAFE</strong><span>危险信号强制中止</span></div>
      </div>
    </div>

    <div class="reasoning-console" :class="{ danger: diagnosis?.status === 'safety_stop' }">
      <header>
        <div>
          <span class="console-dot"></span>
          <small>DIAGNOSIS SESSION · {{ selectedScenario.id.toUpperCase() }}</small>
        </div>
        <span class="step-counter">STEP {{ completedSteps + 1 }}</span>
      </header>

      <div v-if="loading && !diagnosis" class="console-state">
        <span class="decision-spinner"></span>
        <strong>正在计算最优检查路径...</strong>
      </div>

      <div v-else-if="error" class="console-state error-state">
        <strong>诊断服务未连接</strong>
        <p>{{ error }}</p>
        <button @click="loadDecision">重新连接</button>
      </div>

      <template v-else-if="diagnosis">
        <div class="signal-row">
          <span>用户信号</span>
          <p>“{{ selectedScenario.query }}”</p>
        </div>

        <div v-if="diagnosis.hypotheses.length" class="hypothesis-panel">
          <div class="panel-heading">
            <span>故障原因后验概率</span>
            <small>CONFIDENCE {{ probability(diagnosis.confidence) }}%</small>
          </div>
          <div v-for="item in diagnosis.hypotheses" :key="item.code" class="probability-row">
            <div><span>{{ item.label }}</span><b>{{ probability(item.probability) }}%</b></div>
            <div class="probability-track"><i :style="{ width: probability(item.probability) + '%' }"></i></div>
          </div>
        </div>

        <div v-if="diagnosis.next_check" class="next-action">
          <div class="action-heading">
            <span>{{ diagnosis.status === 'safety_stop' ? 'SAFETY OVERRIDE' : 'NEXT BEST CHECK' }}</span>
            <b :class="'risk-' + diagnosis.next_check.risk_level">{{ diagnosis.next_check.risk_level }}</b>
          </div>
          <h3>{{ diagnosis.next_check.action }}</h3>
          <p>{{ diagnosis.next_check.question }}</p>
          <small>{{ diagnosis.next_check.instructions }}</small>
          <div v-if="diagnosis.status !== 'safety_stop'" class="outcome-actions">
            <button :disabled="loading" @click="recordOutcome('normal')">恢复正常</button>
            <button class="abnormal" :disabled="loading" @click="recordOutcome('abnormal')">仍然异常</button>
            <button class="unknown" :disabled="loading" @click="recordOutcome('unknown')">无法确认</button>
          </div>
          <button v-else class="handoff-button" @click="emit('ask', selectedScenario.query)">转人工并携带诊断记录 →</button>
        </div>

        <div v-else class="complete-state">
          <span>DIAGNOSIS COMPLETE</span>
          <h3>{{ topHypothesis?.label || '建议人工进一步检测' }}</h3>
          <p>{{ diagnosis.explanation }}</p>
          <button @click="restart">重新演示</button>
        </div>

        <footer>
          <span><i></i> {{ diagnosis.explanation }}</span>
          <button v-if="completedSteps" @click="restart">重置路径</button>
        </footer>
      </template>
    </div>
  </section>
</template>

<style scoped>
.triage-stage {
  width: min(1180px, 100%);
  display: grid;
  grid-template-columns: minmax(0, .9fr) minmax(460px, 1.1fr);
  gap: 42px;
  align-items: center;
  padding: 38px 18px 28px;
  text-align: left;
}
.live-kicker {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #16c7a5;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .18em;
}
.live-kicker i, .console-dot, footer i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1de9b6;
  box-shadow: 0 0 0 5px rgba(29, 233, 182, .12), 0 0 18px rgba(29, 233, 182, .65);
}
.triage-copy h2 {
  margin: 22px 0 18px;
  color: #ecf7ff;
  font-size: clamp(38px, 4vw, 64px);
  line-height: 1.04;
  letter-spacing: -.045em;
}
.triage-copy h2 span {
  color: transparent;
  background: linear-gradient(100deg, #7ee8fa, #80ffdb 55%, #f6d365);
  background-clip: text;
}
.triage-lead {
  max-width: 610px;
  color: #91a7bb;
  font-size: 16px;
  line-height: 1.8;
}
.scenario-label {
  margin: 32px 0 12px;
  color: #6f879b;
  font-size: 12px;
}
.scenario-switcher {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
}
.scenario-switcher button {
  border: 1px solid #253d51;
  border-radius: 10px;
  background: #101f2c;
  color: #91a7bb;
  padding: 10px 14px;
  cursor: pointer;
}
.scenario-switcher button span { margin-right: 6px; }
.scenario-switcher button.active {
  border-color: #20d5b0;
  background: rgba(23, 205, 166, .12);
  color: #cffff4;
  box-shadow: inset 0 0 20px rgba(23, 205, 166, .06);
}
.proof-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  margin-top: 34px;
  overflow: hidden;
  border: 1px solid #203747;
  border-radius: 12px;
  background: #203747;
}
.proof-strip div {
  display: flex;
  min-height: 72px;
  flex-direction: column;
  justify-content: center;
  padding: 12px;
  background: #0d1a25;
}
.proof-strip strong { color: #e9faff; font-size: 18px; }
.proof-strip span { margin-top: 5px; color: #61798d; font-size: 10px; }

.reasoning-console {
  min-height: 570px;
  overflow: hidden;
  border: 1px solid #29485d;
  border-radius: 20px;
  background:
    linear-gradient(rgba(16, 34, 47, .97), rgba(8, 19, 28, .99)),
    repeating-linear-gradient(0deg, transparent 0 23px, rgba(58, 113, 140, .12) 24px);
  box-shadow: 0 30px 80px rgba(0, 8, 15, .46), inset 0 1px rgba(255,255,255,.04);
}
.reasoning-console.danger {
  border-color: rgba(255, 100, 72, .7);
  box-shadow: 0 30px 80px rgba(48, 10, 5, .36), inset 0 0 80px rgba(255, 61, 39, .06);
}
.reasoning-console > header {
  display: flex;
  justify-content: space-between;
  padding: 18px 21px;
  border-bottom: 1px solid #213b4c;
  background: rgba(5, 15, 22, .5);
}
.reasoning-console header div { display: flex; align-items: center; gap: 10px; }
.reasoning-console header small { color: #7290a6; font: 700 10px/1 monospace; letter-spacing: .12em; }
.step-counter { color: #42ddbd; font: 700 10px/1 monospace; }
.signal-row { padding: 19px 22px 4px; }
.signal-row span, .panel-heading span, .action-heading span, .complete-state > span {
  color: #5f7f94;
  font: 700 10px/1 monospace;
  letter-spacing: .13em;
}
.signal-row p { margin: 8px 0; color: #cfe5f2; font-size: 13px; }
.hypothesis-panel { padding: 16px 22px; }
.panel-heading, .action-heading { display: flex; justify-content: space-between; align-items: center; }
.panel-heading small { color: #8aa1b2; font: 700 9px/1 monospace; }
.probability-row { margin-top: 12px; }
.probability-row > div:first-child { display: flex; justify-content: space-between; color: #9eb2c1; font-size: 11px; }
.probability-row b { color: #e5f8ff; font: 700 11px/1 monospace; }
.probability-track { height: 4px; margin-top: 6px; overflow: hidden; border-radius: 3px; background: #1b3141; }
.probability-track i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, #18bea0, #66e5ff); transition: width .45s ease; }
.next-action {
  margin: 6px 18px 18px;
  padding: 18px;
  border: 1px solid #2d5268;
  border-radius: 14px;
  background: rgba(16, 42, 56, .72);
}
.action-heading b { padding: 4px 7px; border-radius: 5px; background: #1b4950; color: #7dffe7; font: 700 9px/1 monospace; text-transform: uppercase; }
.action-heading b.risk-critical { background: rgba(255, 76, 54, .16); color: #ff806c; }
.next-action h3 { margin: 12px 0 7px; color: #f1fbff; font-size: 18px; }
.next-action p { margin: 0 0 9px; color: #bed0dc; font-size: 13px; }
.next-action > small { display: block; color: #718b9c; font-size: 11px; line-height: 1.55; }
.outcome-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; margin-top: 16px; }
.outcome-actions button, .handoff-button, .complete-state button, .error-state button {
  border: 1px solid #2d675f;
  border-radius: 8px;
  background: #123c39;
  color: #b9fff0;
  padding: 9px 7px;
  cursor: pointer;
  font-size: 11px;
}
.outcome-actions .abnormal { border-color: #784d42; background: #442821; color: #ffc0ad; }
.outcome-actions .unknown { border-color: #405264; background: #22313f; color: #b3c4d1; }
.handoff-button { width: 100%; margin-top: 16px; border-color: #8d4438; background: #5a271f; color: #ffe2d8; }
.reasoning-console footer {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 0 21px 18px;
  color: #587386;
  font-size: 10px;
}
.reasoning-console footer span { display: flex; flex: 1; gap: 9px; align-items: flex-start; line-height: 1.5; }
.reasoning-console footer i { width: 5px; height: 5px; margin-top: 4px; flex: 0 0 auto; }
.reasoning-console footer button { border: 0; background: none; color: #7392a7; cursor: pointer; font-size: 10px; }
.console-state, .complete-state { min-height: 490px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 30px; text-align: center; color: #9bb2c2; }
.decision-spinner { width: 30px; height: 30px; margin-bottom: 18px; border: 2px solid #244657; border-top-color: #24d7b3; border-radius: 50%; animation: spin .8s linear infinite; }
.complete-state h3 { margin: 15px 0 8px; color: #effbff; }
.complete-state p, .error-state p { color: #7790a2; line-height: 1.6; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 980px) {
  .triage-stage { grid-template-columns: 1fr; padding-top: 15px; }
  .reasoning-console { min-height: 520px; }
}
@media (max-width: 620px) {
  .triage-stage { padding-inline: 0; }
  .triage-copy h2 { font-size: 38px; }
  .proof-strip { grid-template-columns: 1fr; }
  .proof-strip div { min-height: 56px; }
  .outcome-actions { grid-template-columns: 1fr; }
}
</style>
