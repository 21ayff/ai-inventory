<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import ProductList from './components/ProductList.vue'
import Dashboard from './components/Dashboard.vue'
import Statistics from './components/Statistics.vue'
import ProfileDialog from './components/ProfileDialog.vue'

const username = ref('')
const password = ref('')
const loading = ref(false)
const token = ref(localStorage.getItem('token') || '')
const currentUser = ref(localStorage.getItem('username') || '')
const currentPage = ref('dashboard')
const profileVisible = ref(false)
const isRegister = ref(false)
const confirmPassword = ref('')

function applyLogin(data) {
  token.value = data.access_token
  currentUser.value = data.username
  localStorage.setItem('token', data.access_token)
  localStorage.setItem('username', data.username)
}

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    const data = await res.json()
    if (res.ok) {
      applyLogin(data)
      ElMessage.success('登录成功')
    } else {
      ElMessage.error(data.detail || '登录失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    const data = await res.json()
    if (res.ok) {
      applyLogin(data)
      ElMessage.success('注册成功，已自动登录')
    } else {
      ElMessage.error(data.detail || '注册失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

function switchMode(reg) {
  isRegister.value = reg
  password.value = ''
  confirmPassword.value = ''
}

function handleLogout() {
  token.value = ''
  currentUser.value = ''
  currentPage.value = 'dashboard'
  localStorage.removeItem('token')
  localStorage.removeItem('username')
}

function handleUserCommand(cmd) {
  if (cmd === 'profile') {
    profileVisible.value = true
  } else if (cmd === 'logout') {
    handleLogout()
  }
}
</script>

<template>
  <div v-if="!token" class="login-page">
    <el-card class="login-card">
      <h2 class="title">AI智能库存助手</h2>
      <el-form @submit.prevent>
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            @keyup.enter="isRegister ? handleRegister() : handleLogin()"
          />
        </el-form-item>
        <el-form-item v-if="isRegister">
          <el-input
            v-model="confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          style="width: 100%"
          @click="isRegister ? handleRegister() : handleLogin()"
        >
          {{ isRegister ? '注 册' : '登 录' }}
        </el-button>
      </el-form>
      <div class="tips">
        <span v-if="isRegister">已有账号？<a class="link" @click="switchMode(false)">去登录</a></span>
        <span v-else>没有账号？<a class="link" @click="switchMode(true)">立即注册</a></span>
      </div>
    </el-card>
  </div>

  <div v-else class="main-page">
    <div class="header">
      <div class="header-left">
        <span class="logo">AI智能库存助手</span>
        <nav class="nav">
          <span
            :class="['nav-item', currentPage === 'dashboard' ? 'active' : '']"
            @click="currentPage = 'dashboard'"
          >仪表盘</span>
          <span
            :class="['nav-item', currentPage === 'products' ? 'active' : '']"
            @click="currentPage = 'products'"
          >商品管理</span>
          <span
            :class="['nav-item', currentPage === 'stats' ? 'active' : '']"
            @click="currentPage = 'stats'"
          >统计分析</span>
        </nav>
      </div>
      <div class="user">
        <el-dropdown trigger="click" @command="handleUserCommand">
          <span class="username">
            {{ currentUser }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
    <Dashboard v-if="currentPage === 'dashboard'" />
    <ProductList v-else-if="currentPage === 'products'" />
    <Statistics v-else />
    <ProfileDialog v-model="profileVisible" :username="currentUser" @logout="handleLogout" />
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 360px;
  max-width: 90%;
  padding: 20px;
}
.title {
  text-align: center;
  margin-bottom: 20px;
  color: #333;
}
.tips {
  text-align: center;
  color: #999;
  font-size: 13px;
  margin-top: 12px;
}
.link {
  color: #409eff;
  cursor: pointer;
  margin-left: 4px;
}
.main-page {
  background-color: #ffffff;
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid #e5e5e5;
}
.logo {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 32px;
}
.nav {
  display: flex;
  gap: 8px;
}
.nav-item {
  padding: 6px 16px;
  border-radius: 4px;
  cursor: pointer;
  color: #606266;
  font-size: 14px;
}
.nav-item:hover {
  color: #409eff;
}
.nav-item.active {
  color: #ffffff;
  background-color: #409eff;
}
.user {
  display: flex;
  align-items: center;
  gap: 10px;
}
.username {
  color: #606266;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  outline: none;
}
@media (max-width: 600px) {
  .header {
    padding: 10px 12px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .header-left {
    gap: 12px;
    flex-wrap: wrap;
  }
  .logo {
    font-size: 16px;
  }
  .nav {
    gap: 4px;
  }
  .nav-item {
    padding: 5px 10px;
    font-size: 13px;
  }
}
</style>
