<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { apiFetch } from '../api'

const products = ref([])
const search = ref('')
const stockFilter = ref('')
const loading = ref(false)
const showBackToTop = ref(false)
const replenishExpanded = ref(true)
const highlightId = ref(null)

const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({})

// 默认分类策略（与后端 stock_math.py 默认值保持一致）
const DEFAULT_TARGET_DAYS = 7
const DEFAULT_Z_SCORE = 1.65
const DEFAULT_DEMAND_CV = 0.20
const SHELF_LIFE_SAFE_RATIO = 0.5
// EOQ 默认参数（与后端 eoq.py 默认值保持一致）
const DEFAULT_ORDER_COST = 20
const DEFAULT_HOLDING_COST_RATE = 0.25

const defaultForm = () => ({
  name: '',
  sku: '',
  category_id: null,
  unit: '个',
  current_stock: 0,
  daily_sales: 0,
  lead_time_days: 0,
  shelf_life_days: null,
  cost_price: null,
  supplier_name: '',
  supplier_phone: '',
})

// AI 自动计算库存参数预览（公式与后端 stock_math.py 保持一致）
const calcParams = computed(() => {
  const d = Number(form.value.daily_sales) || 0
  const l = Number(form.value.lead_time_days) || 0
  if (d <= 0) {
    return { daily_sales: d, lead_time_days: l, lead_time_demand: 0, min_stock: 0, rop: 0, eoq: 0, sellable_days: null }
  }

  const cur = Number(form.value.current_stock) || 0
  const shelfLife = form.value.shelf_life_days ? Number(form.value.shelf_life_days) : null

  // 1. 提前期需求
  const lead_time_demand = d * l

  // 2. 安全库存 = Z × σ_d × √L，没有历史标准差时用 20% 波动系数估算
  const sigma_d = d * DEFAULT_DEMAND_CV
  const min_stock = Math.round(DEFAULT_Z_SCORE * sigma_d * Math.sqrt(Math.max(l, 0)) * 100) / 100

  // 3. 订货点
  const rop = Math.round((lead_time_demand + min_stock) * 100) / 100

  // 4. 目标库存
  let target_inventory = d * DEFAULT_TARGET_DAYS

  // 5. 保质期约束
  let shelf_life_cap = null
  if (shelfLife && shelfLife > 0) {
    shelf_life_cap = d * shelfLife * SHELF_LIFE_SAFE_RATIO
    target_inventory = Math.min(target_inventory, shelf_life_cap)
  }

  // 6. EOQ 经济订货量（预览用默认参数，保存时后端用实际设置值）
  const costPrice = form.value.cost_price ? Number(form.value.cost_price) : null
  let eoq_value = 0
  if (costPrice && costPrice > 0) {
    const annualDemand = d * 365
    const holdingCostPerUnit = costPrice * DEFAULT_HOLDING_COST_RATE
    if (holdingCostPerUnit > 0) {
      eoq_value = Math.round(Math.sqrt(2 * annualDemand * DEFAULT_ORDER_COST / holdingCostPerUnit) * 100) / 100
    }
  }

  // 7. 建议补货量 = min(目标库存 - 当前库存 + 提前期需求, EOQ)
  //    按目标库存补货，补货后库存恢复到目标库存
  //    EOQ 作为上限，防止单次补货过多占用资金
  const gap = Math.max(target_inventory - cur + lead_time_demand, 0)
  const eoq = eoq_value > 0 ? Math.round(Math.min(gap, eoq_value) * 100) / 100 : Math.round(gap * 100) / 100

  const sellable_days = cur > 0 ? Math.round((cur / d) * 100) / 100 : null
  return {
    daily_sales: d,
    lead_time_days: l,
    lead_time_demand: Math.round(lead_time_demand * 100) / 100,
    min_stock,
    rop,
    eoq,
    eoq_value,
    sellable_days,
    target_days: DEFAULT_TARGET_DAYS,
    shelf_life_cap: shelf_life_cap ? Math.round(shelf_life_cap * 100) / 100 : null,
  }
})

async function loadProducts() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (stockFilter.value === 'name' && search.value) {
      params.set('search', search.value)
    } else if (stockFilter.value === 'low') {
      params.set('stock_filter', 'low')
    }
    const res = await apiFetch('/api/products?' + params.toString())
    const data = await res.json()
    products.value = data
  } catch (e) {
    ElMessage.error('加载商品失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = defaultForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = { ...defaultForm(), ...row }
  dialogVisible.value = true
}

async function saveProduct() {
  if (!form.value.name) {
    ElMessage.warning('请输入商品名称')
    return
  }
  const url = editingId.value ? `/api/products/${editingId.value}` : '/api/products'
  const method = editingId.value ? 'PUT' : 'POST'
  try {
    const res = await apiFetch(url, {
      method,
      body: JSON.stringify(form.value),
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success(editingId.value ? '修改成功' : '新增成功')
      dialogVisible.value = false
      loadProducts()
    } else {
      ElMessage.error(data.detail || '操作失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  }
}

async function deleteProduct(row) {
  try {
    await ElMessageBox.confirm(`确定删除商品「${row.name}」吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  const res = await apiFetch(`/api/products/${row.id}`, { method: 'DELETE' })
  if (res.ok) {
    ElMessage.success('删除成功')
    loadProducts()
  } else {
    ElMessage.error('删除失败')
  }
}

// ---------- 入库 / 出库 ----------
const stockDialogVisible = ref(false)
const stockForm = ref({ product_id: null, product_name: '', type: 'in', quantity: 1, remark: '' })

function openStock(row, type) {
  stockForm.value = {
    product_id: row.id,
    product_name: row.name,
    type,
    quantity: 1,
    remark: '',
  }
  stockDialogVisible.value = true
}

async function saveStock() {
  if (!stockForm.value.quantity || stockForm.value.quantity <= 0) {
    ElMessage.warning('请输入大于 0 的数量')
    return
  }
  try {
    const res = await apiFetch('/api/stock/records', {
      method: 'POST',
      body: JSON.stringify({
        product_id: stockForm.value.product_id,
        type: stockForm.value.type,
        quantity: stockForm.value.quantity,
        remark: stockForm.value.remark,
      }),
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success(stockForm.value.type === 'in' ? '入库成功' : '出库成功')
      stockDialogVisible.value = false
      loadProducts()
    } else {
      ElMessage.error(data.detail || '操作失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  }
}

// ---------- 补货提醒 ----------
const suggestions = ref([])

async function loadSuggestions() {
  try {
    const res = await apiFetch('/api/ai/replenish')
    const data = await res.json()
    suggestions.value = data
  } catch (e) {
    // 忽略加载失败
  }
}

// ---------- AI 问答 ----------
const askDialogVisible = ref(false)
const askQuestion = ref('')
const askAnswer = ref('')
const askLoading = ref(false)

function openAsk() {
  askQuestion.value = ''
  askAnswer.value = ''
  askDialogVisible.value = true
}

async function askAi() {
  if (!askQuestion.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  askLoading.value = true
  try {
    const res = await apiFetch('/api/ai/ask', {
      method: 'POST',
      body: JSON.stringify({ question: askQuestion.value }),
    })
    const data = await res.json()
    askAnswer.value = data.answer
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    askLoading.value = false
  }
}

// ---------- 导入 Excel ----------
const importVisible = ref(false)
const importFile = ref(null)
const importResult = ref(null)
const importing = ref(false)

function openImport() {
  importVisible.value = true
  importFile.value = null
  importResult.value = null
}

function onFileChange(e) {
  importFile.value = e.target.files[0] || null
}

async function downloadTemplate() {
  try {
    const res = await apiFetch('/api/products/import-template')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '商品导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载模板失败')
  }
}

async function doImport() {
  if (!importFile.value) {
    ElMessage.warning('请先选择 Excel 文件')
    return
  }
  importing.value = true
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    const token = localStorage.getItem('token')
    const res = await fetch('/api/products/import', {
      method: 'POST',
      headers: token ? { Authorization: 'Bearer ' + token } : {},
      body: formData,
    })
    const data = await res.json()
    if (res.ok) {
      importResult.value = data
      ElMessage.success(`导入完成：成功 ${data.success} 条，失败 ${data.failed_count} 条`)
      loadProducts()
      loadSuggestions()
    } else {
      ElMessage.error(data.detail || '导入失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    importing.value = false
  }
}

// ---------- 回到顶部 ----------
function handleScroll() {
  const el = document.querySelector('.product-page')
  if (el) {
    showBackToTop.value = el.scrollTop > 200 || window.scrollY > 200
  } else {
    showBackToTop.value = window.scrollY > 200
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
  const el = document.querySelector('.product-page')
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
}

// ---------- 补货提醒定位到商品 ----------
function goToProduct(productId) {
  // 先找到商品信息
  const product = products.value.find(p => p.id === productId)
  if (!product) {
    ElMessage.warning('未找到该商品，请刷新页面重试')
    return
  }

  // 关闭补货面板
  replenishExpanded.value = false
  // 高亮商品行
  highlightId.value = productId

  // 从补货建议里找到对应的建议量
  const suggestion = suggestions.value.find(s => s.product_id === productId)
  const suggestQty = suggestion ? suggestion.suggest_quantity : 0

  // 弹出确认框，询问是否立即补货
  ElMessageBox.confirm(
    `商品：${product.name}\n` +
    `当前库存：${product.current_stock} ${product.unit}\n` +
    `建议补货量：${suggestQty} ${product.unit}`,
    '补货提醒',
    {
      confirmButtonText: '立即补货',
      cancelButtonText: '仅定位',
      type: 'warning',
    }
  ).then(() => {
    // 用户点击「立即补货」：弹出入库对话框，预填建议补货量
    stockForm.value = {
      product_id: product.id,
      product_name: product.name,
      type: 'in',
      quantity: suggestQty > 0 ? suggestQty : 1,
      remark: '补货提醒-自动填入建议量',
    }
    stockDialogVisible.value = true
  }).catch(() => {
    // 用户点击「仅定位」或关闭：只滚动到商品行
  })

  // 等待 DOM 更新后滚动到对应行
  nextTick(() => {
    setTimeout(() => {
      const highlightRow = document.querySelector('.highlight-row')
      if (highlightRow) {
        highlightRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else {
        const table = document.querySelector('.el-table')
        if (table) {
          table.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }
    }, 300)

    // 5 秒后取消高亮
    setTimeout(() => {
      highlightId.value = null
    }, 5000)
  })
}

function rowClassName({ row }) {
  return row.id === highlightId.value ? 'highlight-row' : ''
}

onMounted(() => {
  loadProducts()
  loadSuggestions()
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <div class="product-page">
    <div v-if="suggestions.length" class="replenish-area">
      <div class="replenish-header" @click="replenishExpanded = !replenishExpanded">
        <span class="replenish-title">补货提醒（{{ suggestions.length }}）</span>
        <el-icon class="expand-icon" :class="{ expanded: replenishExpanded }">
          <ArrowDown />
        </el-icon>
      </div>
      <div v-show="replenishExpanded" class="replenish-content">
        <el-collapse>
          <el-collapse-item
            v-for="s in suggestions"
            :key="s.product_id"
            :name="s.product_id"
          >
            <template #title>
              <span class="item-name">{{ s.product_name }}</span>
              <el-tag :type="s.status === 'urgent' ? 'danger' : 'warning'" size="small">
                {{ s.status === 'urgent' ? '紧急补货' : '建议补货' }}
              </el-tag>
              <span class="item-summary">
                当前库存 {{ s.current_stock }} {{ s.unit }}，建议补 {{ s.suggest_quantity }} {{ s.unit }}
              </span>
            </template>
            <div class="explain">
              <p><strong>数据依据：</strong>{{ s.data_basis }}</p>
              <p><strong>理论依据：</strong>{{ s.theory_basis }}</p>
              <p><strong>计算过程：</strong>{{ s.calc_process }}</p>
              <el-button size="small" type="primary" @click.stop="goToProduct(s.product_id)">定位到商品</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <div class="toolbar">
      <el-select
        v-model="stockFilter"
        placeholder="筛选"
        clearable
        style="width: 140px"
        @change="loadProducts"
      >
        <el-option label="库存不足" value="low" />
        <el-option label="商品名称" value="name" />
      </el-select>
      <el-input
        v-if="stockFilter === 'name'"
        v-model="search"
        placeholder="输入商品名称或SKU"
        clearable
        style="width: 220px"
        @keyup.enter="loadProducts"
        @clear="loadProducts"
      />
      <el-button type="primary" @click="openCreate">新增商品</el-button>
      <el-button @click="openImport">导入 Excel</el-button>
      <el-button type="success" @click="openAsk">AI问答</el-button>
    </div>

    <el-table :data="products" v-loading="loading" border :row-class-name="rowClassName">
      <el-table-column prop="name" label="商品名称" min-width="140" />
      <el-table-column prop="sku" label="SKU" width="120" />
      <el-table-column prop="unit" label="单位" width="80" />
      <el-table-column prop="current_stock" label="当前库存" width="100" />
      <el-table-column prop="min_stock" label="安全库存" width="100" />
      <el-table-column prop="rop" label="订货点" width="100" />
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="openStock(row, 'in')">入库</el-button>
          <el-button size="small" type="warning" @click="openStock(row, 'out')">出库</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteProduct(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑商品' : '新增商品'"
      width="500px"
    >
      <el-form label-width="110px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="商品名称" />
        </el-form-item>
        <el-form-item label="SKU">
          <el-input v-model="form.sku" placeholder="SKU 编码（可选）" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" />
        </el-form-item>
        <el-form-item label="当前库存">
          <el-input-number v-model="form.current_stock" :min="0" />
        </el-form-item>
        <el-form-item label="日均销量">
          <el-input-number v-model="form.daily_sales" :min="0" />
          <span class="form-tip">件/天</span>
        </el-form-item>
        <el-form-item label="到货天数">
          <el-input-number v-model="form.lead_time_days" :min="0" />
          <span class="form-tip">天</span>
        </el-form-item>
        <el-form-item label="保质期">
          <el-input-number v-model="form.shelf_life_days" :min="0" :controls="false" />
          <span class="form-tip">天（可选，不填则不约束）</span>
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number v-model="form.cost_price" :min="0" :controls="false" />
          <span class="form-tip">元/件（单价，非总价；用于 EOQ 计算）</span>
        </el-form-item>
        <el-form-item label="供应商名称">
          <el-input v-model="form.supplier_name" placeholder="选填，如：张三粮油" />
        </el-form-item>
        <el-form-item label="供应商电话">
          <el-input v-model="form.supplier_phone" placeholder="选填，如：13800138000" />
        </el-form-item>
      </el-form>

      <div class="ai-calc-box">
        <div class="ai-calc-title">AI 已为你计算库存参数</div>
        <template v-if="calcParams.min_stock > 0">
          <div class="ai-calc-row">
            <span>安全库存</span>
            <b>{{ calcParams.min_stock }} {{ form.unit }}</b>
          </div>
          <div class="ai-calc-row">
            <span>订货点</span>
            <b>{{ calcParams.rop }} {{ form.unit }}</b>
          </div>
          <div class="ai-calc-row">
            <span>建议补货量</span>
            <b>{{ calcParams.eoq }} {{ form.unit }}</b>
          </div>
          <div v-if="calcParams.sellable_days !== null" class="ai-calc-row">
            <span>预计可售天数</span>
            <b>{{ calcParams.sellable_days }} 天</b>
          </div>
          <el-collapse class="ai-calc-basis">
            <el-collapse-item title="查看计算依据" name="1">
              <p>提前期需求 = 日均销量 × 到货天数 = {{ calcParams.daily_sales }} × {{ calcParams.lead_time_days }} = {{ calcParams.lead_time_demand }}</p>
              <p>安全库存 = Z × 日销量标准差 × √到货天数 = {{ DEFAULT_Z_SCORE }} × ({{ calcParams.daily_sales }} × 20%) × √{{ calcParams.lead_time_days }} ≈ {{ calcParams.min_stock }}</p>
              <p class="std-hint">注：此处为预览值（用 20% 估算标准差）。保存时后端会查询最近 30 天出库记录计算真实标准差，历史数据不足 7 天时仍用估算值。</p>
              <p>订货点 = 提前期需求 + 安全库存 = {{ calcParams.lead_time_demand }} + {{ calcParams.min_stock }} = {{ calcParams.rop }}</p>
              <p>目标库存 = 日均销量 × 目标库存天数 = {{ calcParams.daily_sales }} × {{ calcParams.target_days }} = {{ Math.round(calcParams.daily_sales * calcParams.target_days * 100) / 100 }}</p>
              <p v-if="calcParams.shelf_life_cap !== null">保质期约束 = 日均销量 × 保质期 × 50% = {{ calcParams.daily_sales }} × {{ form.shelf_life_days }} × 50% = {{ calcParams.shelf_life_cap }}</p>
              <p v-if="calcParams.eoq_value > 0">EOQ 经济订货量 = √(2 × 年需求 × 订货成本 / 持有成本) = √(2 × {{ calcParams.daily_sales * 365 }} × {{ DEFAULT_ORDER_COST }} / {{ form.cost_price * DEFAULT_HOLDING_COST_RATE }}) ≈ {{ calcParams.eoq_value }}</p>
              <p v-else class="eoq-hint">EOQ 经济订货量：请填写「成本价」后计算（公式：√(2 × 年需求 × 订货成本 / 持有成本)）</p>
              <p>建议补货量 = min(目标库存 - 当前库存 + 提前期需求<span v-if="calcParams.eoq_value > 0">, EOQ</span>) = {{ calcParams.eoq }}</p>
              <p class="eoq-hint">注：EOQ 预览用默认参数（订货成本 {{ DEFAULT_ORDER_COST }} 元/次，持有成本率 {{ DEFAULT_HOLDING_COST_RATE }}）。实际值以「EOQ 设置」中的配置为准。<span v-if="calcParams.eoq_value === 0">未填写成本价时，建议补货量暂不考虑 EOQ 约束。</span></p>
            </el-collapse-item>
          </el-collapse>
        </template>
        <p v-else class="ai-calc-hint">填写「日均销量」和「到货天数」后，系统会自动算出安全库存、订货点、建议补货量。</p>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProduct">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="stockDialogVisible"
      :title="stockForm.type === 'in' ? '入库' : '出库'"
      width="420px"
    >
      <el-form label-width="70px">
        <el-form-item label="商品">
          <span>{{ stockForm.product_name }}</span>
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="stockForm.quantity" :min="0.1" :step="1" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stockForm.remark" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStock">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="askDialogVisible" title="AI库存问答" width="500px">
      <el-input
        v-model="askQuestion"
        placeholder="例如：哪些商品缺货？"
        @keyup.enter="askAi"
      />
      <el-button
        type="primary"
        :loading="askLoading"
        style="margin-top: 10px; width: 100%"
        @click="askAi"
      >
        提问
      </el-button>
      <div v-if="askAnswer" class="answer">{{ askAnswer }}</div>
    </el-dialog>

    <el-dialog v-model="importVisible" title="导入 Excel" width="500px">
      <div class="import-tips">
        <p>1. 先下载模板，按模板填写：商品名称、SKU、单位、当前库存、日均销量、到货天数、保质期天数、成本价</p>
        <p>2. 上传后系统会自动算出安全库存、订货点、建议补货量</p>
        <p>3. 同名商品将被导入数据覆盖</p>
      </div>
      <div class="import-actions">
        <el-button size="small" @click="downloadTemplate">下载模板</el-button>
        <input type="file" accept=".xlsx" @change="onFileChange" />
      </div>
      <div v-if="importResult" class="import-result">
        <p>成功导入：{{ importResult.success }} 条</p>
        <p>失败：{{ importResult.failed_count }} 条</p>
        <div v-if="importResult.failed && importResult.failed.length">
          <p v-for="(msg, idx) in importResult.failed" :key="idx" class="fail-msg">{{ msg }}</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">开始导入</el-button>
      </template>
    </el-dialog>

    <transition name="fade">
      <button
        v-show="showBackToTop"
        class="back-to-top"
        @click="scrollToTop"
      >
        ↑
      </button>
    </transition>
  </div>
</template>

<style scoped>
.product-page {
  padding: 20px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.replenish-area {
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
}
.replenish-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--el-fill-color);
  cursor: pointer;
  user-select: none;
}
.replenish-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.expand-icon {
  transition: transform 0.3s;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.expand-icon.expanded {
  transform: rotate(180deg);
}
.replenish-content {
  padding: 8px 14px;
}
.item-name {
  font-weight: 600;
  margin-right: 8px;
}
.item-summary {
  margin-left: 8px;
  color: var(--foreground);
  font-size: 13px;
}
.explain p {
  margin: 4px 0;
  color: var(--foreground);
  font-size: 13px;
}
.answer {
  margin-top: 16px;
  padding: 12px;
  background-color: var(--muted);
  border-radius: 4px;
  white-space: pre-wrap;
  color: var(--foreground);
  font-size: 14px;
  line-height: 1.6;
}
.import-tips {
  color: var(--foreground);
  font-size: 13px;
  line-height: 1.8;
  margin-bottom: 12px;
}
.import-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.import-result {
  padding: 12px;
  background-color: var(--muted);
  border-radius: 4px;
  font-size: 13px;
  color: var(--foreground);
}
.fail-msg {
  color: var(--destructive);
  margin-top: 4px;
}
.form-tip {
  margin-left: 8px;
  color: var(--muted-foreground);
  font-size: 13px;
}
.ai-calc-box {
  margin-top: 4px;
  padding: 12px 14px;
  background-color: var(--secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
}
.ai-calc-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 10px;
}
.ai-calc-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  color: var(--foreground);
  font-size: 13px;
}
.ai-calc-row b {
  color: var(--foreground);
}
.ai-calc-hint {
  color: var(--muted-foreground);
  font-size: 13px;
  margin: 0;
}
.ai-calc-basis {
  margin-top: 6px;
  border-top: 1px dashed var(--border);
}
.ai-calc-basis p {
  margin: 4px 0;
  color: var(--muted-foreground);
  font-size: 12px;
  line-height: 1.6;
}
.std-hint {
  color: var(--chart-3) !important;
  font-style: italic;
}
.eoq-hint {
  color: var(--primary) !important;
  font-style: italic;
}
@media (max-width: 600px) {
  .product-page {
    padding: 12px;
  }
}

/* 高亮商品行 - Element Plus 表格需要 :deep() 穿透 */
:deep(.el-table .highlight-row > td) {
  background-color: var(--secondary) !important;
  animation: highlight-pulse 3s ease-out;
}
@keyframes highlight-pulse {
  0% { background-color: var(--primary) !important; }
  30% { background-color: var(--accent) !important; }
  100% { background-color: transparent !important; }
}

/* 回到顶部按钮 */
.back-to-top {
  position: fixed;
  right: 30px;
  bottom: 30px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  border: none;
  font-size: 20px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  z-index: 999;
  transition: opacity 0.3s, transform 0.3s;
}
.back-to-top:hover {
  transform: translateY(-3px);
  opacity: 0.9;
}
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
