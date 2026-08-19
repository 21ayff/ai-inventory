<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { apiFetch } from '../api'

const loading = ref(false)
const data = ref(null)
const restockExpanded = ref(true)

async function loadAnalysis() {
  loading.value = true
  try {
    const res = await apiFetch('/api/analysis/overview')
    const json = await res.json()
    if (res.ok) {
      data.value = json
    } else {
      ElMessage.error(json.detail || '加载失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

function formatMoney(v) {
  if (!v && v !== 0) return '0'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

onMounted(loadAnalysis)
</script>

<template>
  <div class="analysis-page" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title">数据分析</h2>
      <p class="page-subtitle">今天赚了多少钱 · 该进什么货 · 钱变成了什么货</p>
      <el-button size="small" @click="loadAnalysis">刷新</el-button>
    </div>

    <div v-if="data" class="cards">
      <!-- 板块1：今日生意 -->
      <div class="card today-card">
        <div class="card-header">
          <span class="card-icon">1</span>
          <span class="card-title">今日生意</span>
        </div>
        <div class="today-body">
          <div class="today-row">
            <span class="today-label">今日卖了</span>
            <span class="today-money">¥{{ formatMoney(data.today.today_sales) }}</span>
          </div>
          <div class="today-row">
            <span class="today-label">赚了</span>
            <span class="today-profit">¥{{ formatMoney(data.today.today_profit) }}</span>
          </div>
          <div class="today-row best-seller" v-if="data.today.best_seller_name">
            <span class="today-label">最好卖</span>
            <span class="best-name">{{ data.today.best_seller_name }}</span>
            <span class="best-qty">{{ formatMoney(data.today.best_seller_qty) }}{{ data.today.best_seller_unit }}</span>
          </div>
          <div v-else class="today-empty">今天还没有销售记录</div>
        </div>
      </div>

      <!-- 板块2：该进货了 -->
      <div class="card restock-card">
        <div class="card-header restock-toggle" @click="restockExpanded = !restockExpanded">
          <span class="card-icon">2</span>
          <span class="card-title">该进货了</span>
          <span class="card-count" v-if="data.restock.count > 0">{{ data.restock.count }} 个商品</span>
          <el-icon class="expand-icon" :class="{ expanded: restockExpanded }">
            <ArrowDown />
          </el-icon>
        </div>
        <div v-show="restockExpanded" class="restock-body">
          <div v-if="data.restock.items.length === 0" class="empty-tip">
            库存充足，暂无进货需求
          </div>
          <ul v-else class="restock-list">
            <li v-for="(item, idx) in data.restock.items" :key="item.product_id" class="restock-item">
              <span class="restock-no">{{ idx + 1 }}</span>
              <span class="restock-name">{{ item.name }}</span>
              <span class="restock-arrow">→</span>
              <span class="restock-qty">进{{ formatMoney(item.suggest_qty) }}{{ item.unit }}</span>
              <span class="restock-cost">¥{{ formatMoney(item.total_cost) }}</span>
              <span v-if="item.supplier_name || item.supplier_phone" class="restock-supplier">
                📞 {{ item.supplier_name || '' }} {{ item.supplier_phone || '' }}
              </span>
            </li>
          </ul>
          <div v-if="data.restock.count > 0" class="restock-total">
            预估总成本：<b>¥{{ formatMoney(data.restock.total_cost) }}</b>
          </div>
        </div>
      </div>

      <!-- 板块3：钱压在哪 -->
      <div class="card money-card">
        <div class="card-header">
          <span class="card-icon">3</span>
          <span class="card-title">钱压在哪</span>
        </div>
        <div class="money-body">
          <div class="money-total">
            <span class="money-label">店里货值</span>
            <span class="money-value">¥{{ formatMoney(data.money_stuck.total_stock_value) }}</span>
          </div>

          <div v-if="data.money_stuck.top_items.length > 0" class="money-section">
            <div class="section-title">最压钱 TOP{{ data.money_stuck.top_items.length }}</div>
            <div v-for="item in data.money_stuck.top_items" :key="item.product_id" class="top-item">
              <span class="top-name">{{ item.name }}</span>
              <span class="top-value">¥{{ formatMoney(item.stock_value) }}</span>
              <span class="top-days" v-if="item.days_no_sale !== null">（放了{{ item.days_no_sale }}天）</span>
            </div>
          </div>

          <div v-if="data.money_stuck.slow_moving.length > 0" class="money-section slow-section">
            <div class="section-title">滞销品清仓建议</div>
            <p class="slow-tip">
              这 {{ data.money_stuck.slow_moving.length }} 个商品超过 30 天没出库，打折卖可回笼
              <b class="release-amount">¥{{ formatMoney(data.money_stuck.releasable_amount) }}</b>
            </p>
            <div v-for="item in data.money_stuck.slow_moving" :key="item.product_id" class="slow-item">
              <span class="slow-name">{{ item.name }}</span>
              <span class="slow-info">{{ formatMoney(item.current_stock) }}{{ item.unit }} · ¥{{ formatMoney(item.stock_value) }} · {{ item.days_no_sale }}天没卖</span>
            </div>
          </div>

          <div v-if="data.money_stuck.slow_moving.length === 0 && data.money_stuck.top_items.length === 0" class="empty-tip">
            暂无库存数据
          </div>
        </div>
      </div>
    </div>

    <!-- 一句话总结 -->
    <div v-if="data" class="summary">
      <span class="summary-icon">💡</span>
      <span class="summary-text">
        今天赚了 <b>¥{{ formatMoney(data.today.today_profit) }}</b>，
        需要进货 <b>{{ data.restock.count }}</b> 个商品（预估 <b>¥{{ formatMoney(data.restock.total_cost) }}</b>），
        店里货值 <b>¥{{ formatMoney(data.money_stuck.total_stock_value) }}</b>
        <span v-if="data.money_stuck.slow_moving.length > 0">
          ，有 <b>{{ data.money_stuck.slow_moving.length }}</b> 个滞销品可回笼 <b>¥{{ formatMoney(data.money_stuck.releasable_amount) }}</b>
        </span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.analysis-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.page-subtitle {
  font-size: 13px;
  color: var(--muted-foreground);
  margin: 0;
  flex: 1;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}
.card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: var(--shadow-sm);
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--primary);
  color: var(--primary-foreground);
  font-size: 13px;
  font-weight: 600;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--foreground);
  flex: 1;
}
.card-count {
  font-size: 12px;
  color: var(--primary);
  background-color: var(--secondary);
  padding: 2px 8px;
  border-radius: 10px;
}
.restock-toggle {
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;
}
.restock-toggle:hover {
  background-color: var(--muted);
}
.expand-icon {
  margin-left: auto;
  color: var(--muted-foreground);
  transition: transform 0.3s ease;
  font-size: 16px;
}
.expand-icon.expanded {
  transform: rotate(180deg);
}

/* 板块1：今日生意 */
.today-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 8px 0;
}
.today-label {
  color: var(--muted-foreground);
  font-size: 14px;
}
.today-money {
  font-size: 24px;
  font-weight: 600;
  color: var(--primary);
}
.today-profit {
  font-size: 20px;
  font-weight: 600;
  color: var(--chart-5);
}
.best-seller {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}
.best-name {
  font-weight: 600;
  color: var(--foreground);
}
.best-qty {
  color: var(--muted-foreground);
  font-size: 13px;
}
.today-empty {
  color: var(--muted-foreground);
  font-size: 13px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}

/* 板块2：该进货了 */
.restock-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.restock-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--border);
  font-size: 14px;
  flex-wrap: wrap;
}
.restock-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background-color: var(--muted);
  color: var(--foreground);
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.restock-name {
  font-weight: 500;
  color: var(--foreground);
}
.restock-arrow {
  color: var(--muted-foreground);
}
.restock-qty {
  color: var(--primary);
  font-weight: 500;
}
.restock-cost {
  color: var(--destructive);
  font-weight: 600;
  margin-left: auto;
}
.restock-supplier {
  width: 100%;
  font-size: 12px;
  color: var(--muted-foreground);
  padding-left: 26px;
}
.restock-total {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  text-align: right;
  color: var(--foreground);
  font-size: 14px;
}
.restock-total b {
  color: var(--destructive);
  font-size: 16px;
}

/* 板块3：钱压在哪 */
.money-total {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 14px;
}
.money-label {
  color: var(--muted-foreground);
  font-size: 14px;
}
.money-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--primary);
}
.money-section {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground);
  margin-bottom: 8px;
}
.top-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 6px 0;
  font-size: 13px;
  flex-wrap: wrap;
}
.top-name {
  color: var(--foreground);
  font-weight: 500;
}
.top-value {
  color: var(--destructive);
  font-weight: 600;
}
.top-days {
  color: var(--muted-foreground);
  font-size: 12px;
}
.slow-section {
  background-color: var(--secondary);
  padding: 10px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
}
.slow-tip {
  font-size: 13px;
  color: var(--foreground);
  margin: 0 0 8px 0;
  line-height: 1.6;
}
.release-amount {
  color: var(--chart-5);
  font-weight: 600;
}
.slow-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 6px 0;
  font-size: 12px;
}
.slow-name {
  color: var(--foreground);
  font-weight: 500;
}
.slow-info {
  color: var(--muted-foreground);
}
.empty-tip {
  color: var(--muted-foreground);
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}

/* 一句话总结 */
.summary {
  margin-top: 20px;
  padding: 14px 16px;
  background-color: var(--secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--foreground);
  line-height: 1.6;
}
.summary-icon {
  font-size: 18px;
}
.summary-text b {
  color: var(--primary);
}

@media (max-width: 600px) {
  .analysis-page {
    padding: 12px;
  }
  .cards {
    grid-template-columns: 1fr;
  }
  .today-money, .money-value {
    font-size: 20px;
  }
}
</style>
