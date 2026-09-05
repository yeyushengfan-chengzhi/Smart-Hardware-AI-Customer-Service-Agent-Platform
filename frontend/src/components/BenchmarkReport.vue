<script setup>
import { computed, onMounted, ref } from 'vue'
import { getBenchmarkReport } from '../services/evaluationApi'

const report = ref(null)
const loading = ref(false)
const error = ref('')
const taskLabels = { route: '路由准确率', safety: '安全中止召回', diagnosis: '诊断原因 Top-1' }
const taskRows = computed(() => Object.entries(report.value?.tasks || {}).map(([key, value]) => ({
  key,
  label: taskLabels[key] || key,
  ...value,
})))

function percent(value) {
  return `${(Number(value || 0) * 100).toFixed(0)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try { report.value = await getBenchmarkReport() }
  catch (requestError) { error.value = requestError.message || 'Benchmark 暂不可用' }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <section class="benchmark-card" v-loading="loading">
    <header>
      <div>
        <span class="section-kicker">REPRODUCIBLE DOMAIN BENCHMARK</span>
        <h3>HW-Support-Bench <small>v{{ report?.benchmark?.version || '1.0.0' }}</small></h3>
        <p>用同一组可追溯案例比较通用 RAG 基线与领域增强方案。</p>
      </div>
      <button @click="load">重新运行</button>
    </header>

    <el-alert v-if="error" type="error" :closable="false" :title="error" />
    <template v-else-if="report">
      <div class="benchmark-scoreboard">
        <article class="baseline-score"><span>GENERIC RAG BASELINE</span><strong>{{ percent(report.baseline_overall) }}</strong></article>
        <div class="score-arrow">→ <small>领域规则 + 诊断决策</small></div>
        <article class="enhanced-score"><span>ENHANCED SYSTEM</span><strong>{{ percent(report.enhanced_overall) }}</strong></article>
        <article class="case-score"><span>VERSIONED CASES</span><strong>{{ report.case_count }}</strong></article>
      </div>
      <div class="benchmark-task-list">
        <div v-for="task in taskRows" :key="task.key" class="benchmark-task">
          <div class="task-title"><strong>{{ task.label }}</strong><span>{{ task.enhanced_passed }} / {{ task.total }} passed</span></div>
          <div class="compare-line"><label>通用 RAG</label><i><em class="baseline-bar" :style="{ width: percent(task.baseline_score) }"></em></i><b>{{ percent(task.baseline_score) }}</b></div>
          <div class="compare-line"><label>领域增强</label><i><em class="enhanced-bar" :style="{ width: percent(task.enhanced_score) }"></em></i><b>{{ percent(task.enhanced_score) }}</b></div>
        </div>
      </div>
      <footer>
        <span>数据声明</span>
        {{ report.benchmark.limitations }}
      </footer>
    </template>
  </section>
</template>

<style scoped>
.benchmark-card { margin: 18px 0; padding: 22px; border: 1px solid #253e51; border-radius: 16px; background: linear-gradient(135deg, #0b1822, #102634); color: #dcedf6; }
.benchmark-card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.benchmark-card h3 { margin: 7px 0 5px; font-size: 22px; }
.benchmark-card h3 small { color: #4eddbd; font: 700 11px/1 monospace; }
.benchmark-card header p { margin: 0; color: #7690a2; font-size: 12px; }
.benchmark-card header button { border: 1px solid #31536a; border-radius: 8px; background: #122c3b; color: #9fc5d6; padding: 8px 12px; cursor: pointer; }
.benchmark-scoreboard { display: grid; grid-template-columns: 1fr auto 1fr .8fr; gap: 10px; align-items: stretch; margin-top: 20px; }
.benchmark-scoreboard article { padding: 16px; border: 1px solid #274253; border-radius: 11px; background: rgba(5,14,20,.48); }
.benchmark-scoreboard span { display: block; color: #628094; font: 700 9px/1 monospace; letter-spacing: .1em; }
.benchmark-scoreboard strong { display: block; margin-top: 9px; font-size: 28px; }
.enhanced-score strong { color: #54e5c4; }
.score-arrow { display: flex; flex-direction: column; justify-content: center; align-items: center; color: #42d4b4; }
.score-arrow small { margin-top: 5px; color: #557286; font-size: 8px; white-space: nowrap; }
.benchmark-task-list { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }
.benchmark-task { padding: 14px; border: 1px solid #203948; border-radius: 10px; background: rgba(9,25,34,.65); }
.task-title { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 11px; }
.task-title span { color: #638096; }
.compare-line { display: grid; grid-template-columns: 56px 1fr 32px; gap: 7px; align-items: center; margin-top: 8px; color: #7892a4; font-size: 9px; }
.compare-line i { height: 5px; overflow: hidden; border-radius: 4px; background: #1b3342; }
.compare-line em { display: block; height: 100%; border-radius: 4px; }
.baseline-bar { background: #657e91; }
.enhanced-bar { background: linear-gradient(90deg, #1bbd9c, #5ce2c8); }
.compare-line b { color: #c5d9e4; font-family: monospace; }
.benchmark-card footer { margin-top: 14px; padding-top: 12px; border-top: 1px solid #203847; color: #607b8e; font-size: 10px; line-height: 1.5; }
.benchmark-card footer span { margin-right: 8px; color: #e1a95d; font-weight: 700; }
@media (max-width: 900px) {
  .benchmark-scoreboard { grid-template-columns: 1fr 1fr; }
  .score-arrow { display: none; }
  .benchmark-task-list { grid-template-columns: 1fr; }
}
</style>
