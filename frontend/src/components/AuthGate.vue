<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { login, register } from '../stores/authStore'
import { seedDemoAccounts } from '../services/authApi'

const mode = ref('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const demoLoginRole = ref('')
const errorMessage = ref('')

const isRegister = computed(() => mode.value === 'register')
const demoAccounts = [
  { role: 'user', username: 'user_demo', label: '普通用户登录' },
  { role: 'agent', username: 'agent_demo', label: '客服账号登录' },
  { role: 'admin', username: 'admin_demo', label: '管理员登录' },
]

function switchMode(nextMode) {
  mode.value = nextMode
  errorMessage.value = ''
  password.value = ''
  confirmPassword.value = ''
}

function validate() {
  if (username.value.trim().length < 3) return '用户名至少需要 3 个字符'
  if (password.value.length < 6) return '密码至少需要 6 个字符'
  if (isRegister.value && password.value !== confirmPassword.value) return '两次输入的密码不一致'
  return ''
}

async function submit() {
  errorMessage.value = validate()
  if (errorMessage.value || submitting.value) return
  submitting.value = true
  try {
    const cleanUsername = username.value.trim()
    if (isRegister.value) {
      await register(cleanUsername, password.value)
      ElMessage.success('注册成功，已自动登录')
    } else {
      await login(cleanUsername, password.value)
      ElMessage.success('登录成功')
    }
  } catch (error) {
    if (error.status === 409) errorMessage.value = '该用户名已存在，请直接登录'
    else if (error.status === 401) errorMessage.value = '用户名或密码错误'
    else if (error.status === 422) errorMessage.value = '用户名或密码格式不符合要求'
    else errorMessage.value = error.message || '认证失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function quickLogin(account) {
  if (submitting.value || demoLoginRole.value) return
  errorMessage.value = ''
  demoLoginRole.value = account.role
  try {
    await seedDemoAccounts()
  } catch (error) {
    errorMessage.value = error.status === 404
      ? '演示账号入口当前不可用，请确认后端处于本地开发模式'
      : (error.message || '演示账号初始化失败，请确认后端服务已启动')
    demoLoginRole.value = ''
    return
  }

  try {
    await login(account.username, '123456')
    ElMessage.success(`已登录演示账号 ${account.username}`)
  } catch (error) {
    errorMessage.value = error.status === 401
      ? '演示账号登录失败，请重新初始化后再试'
      : (error.message || '演示账号登录失败，请稍后重试')
  } finally {
    demoLoginRole.value = ''
  }
}
</script>

<template>
  <section class="auth-gate">
    <div class="auth-card">
      <div class="auth-brand"><span>PW</span><div><strong>PCWise Agent</strong><small>AI CUSTOMER SERVICE FOR DIY PC HARDWARE</small></div></div>
      <div class="auth-heading"><span>SECURE SERVICE PORTAL</span><h2>{{ isRegister ? '创建客服账号' : '登录智能客服' }}</h2><p>登录后可保存聊天记录，并在需要时创建人工服务工单。</p></div>
      <div class="auth-tabs"><button :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button><button :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button></div>
      <form @submit.prevent="submit">
        <label><span>用户名</span><input v-model="username" autocomplete="username" maxlength="64" placeholder="请输入用户名" /></label>
        <label><span>密码</span><input v-model="password" :autocomplete="isRegister ? 'new-password' : 'current-password'" type="password" maxlength="128" placeholder="至少 6 个字符" /></label>
        <label v-if="isRegister"><span>确认密码</span><input v-model="confirmPassword" autocomplete="new-password" type="password" maxlength="128" placeholder="请再次输入密码" /></label>
        <p v-if="errorMessage" class="auth-error">{{ errorMessage }}</p>
        <button class="auth-submit" :disabled="submitting" type="submit"><span v-if="submitting" class="spinner"></span>{{ submitting ? '处理中...' : (isRegister ? '注册并登录' : '登录') }}</button>
      </form>
      <div class="demo-login">
        <div class="demo-login-heading"><span>演示账号快速登录</span><small>演示账号仅用于本地测试，不代表生产权限方案。</small></div>
        <div class="demo-login-actions">
          <button
            v-for="account in demoAccounts"
            :key="account.role"
            :class="`demo-${account.role}`"
            :disabled="submitting || Boolean(demoLoginRole)"
            type="button"
            @click="quickLogin(account)"
          >
            <span v-if="demoLoginRole === account.role" class="spinner"></span>
            {{ demoLoginRole === account.role ? '登录中...' : account.label }}
          </button>
        </div>
      </div>
      <p class="auth-footnote">登录状态仅保存在当前浏览器；退出登录会清理 Token、会话和用户缓存。</p>
    </div>
  </section>
</template>
