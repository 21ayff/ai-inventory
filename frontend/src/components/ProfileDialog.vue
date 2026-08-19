<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { apiFetch } from '../api'

const props = defineProps({
  modelValue: Boolean,
  username: String,
})
const emit = defineEmits(['update:modelValue', 'logout'])

const userInfo = ref(null)
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)

// 打开弹窗时重置表单并加载用户信息
watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      oldPassword.value = ''
      newPassword.value = ''
      confirmPassword.value = ''
      userInfo.value = null
      loadUserInfo()
    }
  }
)

async function loadUserInfo() {
  try {
    const res = await apiFetch('/api/auth/me?username=' + encodeURIComponent(props.username))
    if (res.ok) {
      userInfo.value = await res.json()
    }
  } catch (e) {
    // 加载失败时静默处理
  }
}

async function changePassword() {
  if (!oldPassword.value) {
    ElMessage.warning('请输入旧密码')
    return
  }
  if (!newPassword.value) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (newPassword.value.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  loading.value = true
  try {
    const res = await apiFetch('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        username: props.username,
        old_password: oldPassword.value,
        new_password: newPassword.value,
      }),
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success('密码修改成功，请用新密码重新登录')
      emit('update:modelValue', false)
      emit('logout')
    } else {
      ElMessage.error(data.detail || '修改失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="个人中心"
    width="440px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <!-- 个人信息 -->
    <div class="info-box">
      <div class="info-row">
        <span class="info-label">用户名</span>
        <span class="info-value">{{ username }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">注册时间</span>
        <span class="info-value">
          {{ userInfo && userInfo.created_at ? userInfo.created_at.slice(0, 10) : '—' }}
        </span>
      </div>
    </div>

    <el-divider>修改密码</el-divider>

    <el-form label-width="90px">
      <el-form-item label="旧密码" required>
        <el-input
          v-model="oldPassword"
          type="password"
          placeholder="请输入当前密码"
          show-password
        />
      </el-form-item>
      <el-form-item label="新密码" required>
        <el-input
          v-model="newPassword"
          type="password"
          placeholder="至少 6 位"
          show-password
        />
      </el-form-item>
      <el-form-item label="确认新密码" required>
        <el-input
          v-model="confirmPassword"
          type="password"
          placeholder="再次输入新密码"
          show-password
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="changePassword">
        修改密码
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.info-box {
  padding: 8px 4px;
}
.info-row {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
}
.info-label {
  width: 90px;
  color: var(--muted-foreground);
  font-size: 14px;
}
.info-value {
  color: var(--foreground);
  font-size: 14px;
  font-weight: 500;
}
</style>
