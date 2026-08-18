<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiFetch } from '../api'

const summary = ref(null)
const loading = ref(false)

const distributionChartRef = ref(null)
const trendChartRef = ref(null)
let distributionChart = null
let trendChart = null

async function loadSummary() {
  loading.value = true
  try {
    const res = await apiFetch('/api/dashboard/summary')
    const data = await res.json()
    summary.value = data
    await nextTick()
    renderCharts()
  } catch (e) {
    // 加载失败时静默处理，页面显示默认 0
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!summary.value) return

  // 库存分布柱状图
  if (distributionChartRef.value) {
    if (!distributionChart) {
      distributionChart = echarts.init(distributionChartRef.value)
    }
    distributionChart.setOption({
      title: { text: '库存分布 TOP10', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, bottom: 50, top: 40 },
      xAxis: {
        type: 'category',
        data: summary.value.stock_distribution.map((i) => i.name),
        axisLabel: { rotate: 30, interval: 0 },
      },
      yAxis: { type: 'value', name: '库存' },
      series: [
        {
          type: 'bar',
          data: summary.value.stock_distribution.map((i) => i.value),
          itemStyle: { color: '#409eff' },
          barMaxWidth: 40,
        },
      ],
    })
  }

  // 出入库趋势折线图
  if (trendChartRef.value) {
    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value)
    }
    trendChart.setOption({
      title: { text: '近7天出入库趋势', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['入库', '出库'], top: 25 },
      grid: { left: 50, right: 20, bottom: 30, top: 60 },
      xAxis: { type: 'category', data: summary.value.stock_trend.map((i) => i.date) },
      yAxis: { type: 'value', name: '数量' },
      series: [
        {
          name: '入库',
          type: 'line',
          smooth: true,
          data: summary.value.stock_trend.map((i) => i.in),
          itemStyle: { color: '#67c23a' },
        },
        {
          name: '出库',
          type: 'line',
          smooth: true,
          data: summary.value.stock_trend.map((i) => i.out),
          itemStyle: { color: '#e6a23c' },
        },
      ],
    })
  }
}

function handleResize() {
  if (distributionChart) distributionChart.resize()
  if (trendChart) trendChart.resize()
}

onMounted(() => {
  loadSummary()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (distributionChart) distributionChart.dispose()
  if (trendChart) trendChart.dispose()
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <!-- 统计卡片 -->
    <div class="cards">
      <div class="card">
        <div class="card-label">商品总数</div>
        <div class="card-value">{{ summary ? summary.product_count : 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">库存总量</div>
        <div class="card-value">{{ summary ? summary.total_stock : 0 }}</div>
      </div>
      <div class="card card-danger">
        <div class="card-label">紧急补货</div>
        <div class="card-value">{{ summary ? summary.urgent_count : 0 }}</div>
      </div>
      <div class="card card-warning">
        <div class="card-label">需补货商品</div>
        <div class="card-value">{{ summary ? summary.replenish_count : 0 }}</div>
      </div>
    </div>

    <!-- 补货告警列表 -->
    <el-card class="panel">
      <template #header>补货告警</template>
      <el-empty
        v-if="summary && !summary.replenish_list.length"
        description="暂无需要补货的商品"
        :image-size="60"
      />
      <el-table v-else :data="summary ? summary.replenish_list : []" size="small" border>
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="current_stock" label="当前库存" width="110" />
        <el-table-column prop="suggest_quantity" label="建议补货量" width="120" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'urgent' ? 'danger' : 'warning'" size="small">
              {{ row.status === 'urgent' ? '紧急补货' : '建议补货' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 图表 -->
    <div class="charts">
      <el-card class="chart-card">
        <div ref="distributionChartRef" class="chart"></div>
      </el-card>
      <el-card class="chart-card">
        <div ref="trendChartRef" class="chart"></div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 20px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.card {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 20px;
}
.card-label {
  color: #909399;
  font-size: 13px;
  margin-bottom: 10px;
}
.card-value {
  font-size: 30px;
  font-weight: 600;
  color: #303133;
}
.card-danger .card-value {
  color: #f56c6c;
}
.card-warning .card-value {
  color: #e6a23c;
}
.panel {
  margin-bottom: 16px;
}
.charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.chart {
  height: 360px;
  width: 100%;
}
@media (max-width: 900px) {
  .cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .charts {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 480px) {
  .cards {
    grid-template-columns: 1fr;
  }
  .dashboard {
    padding: 12px;
  }
}
</style>
