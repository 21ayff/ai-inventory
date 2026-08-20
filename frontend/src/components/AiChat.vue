<script setup>
import { ref, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiFetch } from '../api'

// 悬浮球聊天组件：AI 库存管理员"小库"
// 常驻右下角，点击展开聊天面板，支持多轮对话和历史记录

const visible = ref(false)
const messages = ref([])          // [{ role: 'user' | 'ai', content: '...' }]
const input = ref('')
const sending = ref(false)
const historyLoaded = ref(false)
const listRef = ref(null)

const WELCOME =
  '你好，我是小库，你的AI库存管理员。\n可以问我：哪些货该补了？哪种货压钱最多？哪些货卖得慢？'

function toggle() {
  visible.value = !visible.value
  if (visible.value && !historyLoaded.value) {
    loadHistory()
  }
}

async function loadHistory() {
  try {
    const res = await apiFetch('/api/ai/history')
    const data = await res.json()
    if (Array.isArray(data) && data.length) {
      // 后端一问一答存一条，前端拆成两条气泡
      messages.value = data.flatMap((r) => [
        { role: 'user', content: r.question },
        { role: 'ai', content: r.answer },
      ])
    } else {
      messages.value = [{ role: 'ai', content: WELCOME }]
    }
    historyLoaded.value = true
    scrollToBottom()
  } catch (e) {
    // 历史加载失败不阻塞聊天
    messages.value = [{ role: 'ai', content: WELCOME }]
    historyLoaded.value = true
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  scrollToBottom()
  try {
    const res = await apiFetch('/api/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message: text }),
    })
    const data = await res.json()
    if (res.ok) {
      messages.value.push({ role: 'ai', content: data.answer })
    } else {
      messages.value.push({ role: 'ai', content: '出错了：' + (data.detail || '请稍后再试') })
    }
  } catch (e) {
    messages.value.push({ role: 'ai', content: '网络错误，请确认后端已启动' })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function clearHistory() {
  try {
    await ElMessageBox.confirm('确定清空所有对话记录吗？', '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await apiFetch('/api/ai/history', { method: 'DELETE' })
    messages.value = [{ role: 'ai', content: WELCOME }]
    ElMessage.success('对话已清空')
  } catch (e) {
    ElMessage.error('清空失败，请稍后再试')
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}
</script>

<template>
  <div class="ai-chat">
    <!-- 聊天面板 -->
    <transition name="ai-slide">
      <div v-show="visible" class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="dot"></span>
            AI 库存管理员
          </div>
          <div class="panel-actions">
            <span class="action" title="清空对话" @click="clearHistory">清空</span>
            <span class="action" title="收起" @click="visible = false">✕</span>
          </div>
        </div>

        <div ref="listRef" class="messages">
          <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
            <div class="bubble">{{ m.content }}</div>
          </div>
          <div v-if="sending" class="msg ai">
            <div class="bubble thinking">
              正在思考<span class="dots"><i></i><i></i><i></i></span>
            </div>
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="input"
            placeholder="例如：哪些商品该补货了？"
            maxlength="500"
            :disabled="sending"
            @keyup.enter="send"
          />
          <el-button type="primary" :loading="sending" @click="send">发送</el-button>
        </div>
      </div>
    </transition>

    <!-- 悬浮球 -->
    <button class="ball" :title="visible ? '收起' : 'AI 库存管理员'" @click="toggle">
      <span v-if="!visible" class="ball-text">AI</span>
      <span v-else class="ball-text">✕</span>
    </button>
  </div>
</template>

<style scoped>
/* ---------- 悬浮球 ---------- */
.ball {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  z-index: 1000;
  background: linear-gradient(135deg, var(--primary) 0%, #764ba2 100%);
  color: #fff;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ball:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}
.ball-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
}

/* ---------- 聊天面板 ---------- */
.panel {
  position: fixed;
  right: 24px;
  bottom: 92px;
  width: 380px;
  max-width: calc(100vw - 32px);
  height: 560px;
  max-height: calc(100vh - 130px);
  display: flex;
  flex-direction: column;
  z-index: 1000;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background-color: var(--card);
  border-bottom: 1px solid var(--border);
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--foreground);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #22c55e;
}
.panel-actions {
  display: flex;
  gap: 12px;
}
.action {
  font-size: 13px;
  color: var(--muted-foreground);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.action:hover {
  color: var(--primary);
  background-color: var(--muted);
}

/* ---------- 消息区 ---------- */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background-color: var(--background);
}
.msg {
  display: flex;
}
.msg.user {
  justify-content: flex-end;
}
.msg.ai {
  justify-content: flex-start;
}
.bubble {
  max-width: 78%;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 12px;
}
.msg.user .bubble {
  background-color: var(--primary);
  color: var(--primary-foreground);
  border-bottom-right-radius: 4px;
}
.msg.ai .bubble {
  background-color: var(--card);
  color: var(--foreground);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

/* 思考中的三个点动画 */
.thinking .dots {
  display: inline-flex;
  gap: 3px;
  margin-left: 2px;
  vertical-align: middle;
}
.thinking .dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: var(--muted-foreground);
  animation: blink 1.2s infinite both;
}
.thinking .dots i:nth-child(2) {
  animation-delay: 0.2s;
}
.thinking .dots i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; }
  40% { opacity: 1; }
}

/* ---------- 输入区 ---------- */
.input-area {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--border);
  background-color: var(--card);
}

/* ---------- 展开动画 ---------- */
.ai-slide-enter-active,
.ai-slide-leave-active {
  transition: all 0.25s ease;
}
.ai-slide-enter-from,
.ai-slide-leave-to {
  opacity: 0;
  transform: translateY(16px);
}

/* ---------- 手机适配 ---------- */
@media (max-width: 600px) {
  .ball {
    right: 16px;
    bottom: 16px;
    width: 50px;
    height: 50px;
  }
  .panel {
    right: 16px;
    bottom: 78px;
    height: 65vh;
  }
}
</style>
