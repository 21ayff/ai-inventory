<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { apiFetch } from '../api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

const dialogVisible = ref(props.modelValue)
watch(() => props.modelValue, (v) => {
  dialogVisible.value = v
  if (v) loadSettings()
})
watch(dialogVisible, (v) => {
  if (v !== props.modelValue) emit('update:modelValue', v)
})

const form = ref({
  order_cost: 20,
  holding_cost_rate: 0.25,
})
const loading = ref(false)
const saving = ref(false)

async function loadSettings() {
  loading.value = true
  try {
    const res = await apiFetch('/api/settings')
    const data = await res.json()
    if (res.ok) {
      form.value.order_cost = data.order_cost
      form.value.holding_cost_rate = data.holding_cost_rate
    }
  } catch (e) {
    ElMessage.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  if (form.value.order_cost < 0) {
    ElMessage.warning('订货成本不能为负数')
    return
  }
  if (form.value.holding_cost_rate < 0 || form.value.holding_cost_rate > 1) {
    ElMessage.warning('持有成本率应在 0 ~ 1 之间（如 0.25 表示 25%）')
    return
  }
  saving.value = true
  try {
    const res = await apiFetch('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(form.value),
    })
    if (res.ok) {
      ElMessage.success('设置保存成功')
      dialogVisible.value = false
    } else {
      const data = await res.json()
      ElMessage.error(data.detail || '保存失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="EOQ 经济订货量设置" width="500px">
    <div v-loading="loading">
      <div class="settings-tips">
        <p>EOQ 公式：Q = √(2 × 年需求量 × 订货成本 / 持有成本)</p>
        <p>这些参数会用于所有商品的经济订货量计算，影响建议补货量。</p>
      </div>
      <el-form label-width="140px">
        <el-form-item label="订货成本">
          <el-input-number v-model="form.order_cost" :min="0" :precision="2" :step="10" />
          <span class="form-tip">元/次（含运费、人工费等固定费用）</span>
        </el-form-item>
        <el-form-item label="持有成本率">
          <el-input-number v-model="form.holding_cost_rate" :min="0" :max="1" :precision="2" :step="0.05" />
          <span class="form-tip">（如 0.25 表示 25%，含仓储、资金占用、损耗）</span>
        </el-form-item>
      </el-form>
      <div class="formula-explain">
        <p><strong>计算示例：</strong></p>
        <p>假设商品日均销量 10 件，成本价 5 元，订货成本 20 元/次，持有成本率 25%</p>
        <p>年需求量 = 10 × 365 = 3650 件</p>
        <p>持有成本 = 5 × 0.25 = 1.25 元/件</p>
        <p>EOQ = √(2 × 3650 × 20 / 1.25) ≈ 342 件</p>
      </div>
    </div>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveSettings">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.settings-tips {
  background-color: var(--secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 10px 14px;
  margin-bottom: 16px;
}
.settings-tips p {
  margin: 4px 0;
  color: var(--primary);
  font-size: 13px;
  line-height: 1.6;
}
.form-tip {
  margin-left: 8px;
  color: var(--muted-foreground);
  font-size: 12px;
}
.formula-explain {
  margin-top: 16px;
  padding: 10px 14px;
  background-color: var(--muted);
  border-radius: 4px;
}
.formula-explain p {
  margin: 4px 0;
  color: var(--foreground);
  font-size: 12px;
  line-height: 1.6;
}
.formula-explain strong {
  color: var(--foreground);
}
</style>
