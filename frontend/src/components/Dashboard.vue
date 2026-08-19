<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import { ArrowDown } from '@element-plus/icons-vue'
import { apiFetch } from '../api'

const summary = ref(null)
const replenishExpanded = ref(false)
const loading = ref(false)

const distributionChartRef = ref(null)
const trendChartRef = ref(null)
let distributionChart = null
let trendChart = null
let themeObserver = null

const isDark = computed(() => document.documentElement.classList.contains('dark'))

function getChartColors() {
  if (isDark.value) {
    return {
      primary: '#2dccd3',
      secondary: '#f1204a',
      tertiary: '#edbbe8',
      quaternary: '#fbeb35',
      quinary: '#baf6f0',
    }
  }
  return {
    primary: '#4285f4',
    secondary: '#ea4335',
    tertiary: '#fbbc05',
    quaternary: '#0043ad',
    quinary: '#34a853',
  }
}

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

  const colors = getChartColors()

  // 库存分布柱状图
  if (distributionChartRef.value) {
    if (!distributionChart) {
      distributionChart = echarts.init(distributionChartRef.value, isDark.value ? 'dark' : null)
    }
    distributionChart.setOption({
      backgroundColor: 'transparent',
      title: { text: '库存分布 TOP10', left: 'center', textStyle: { fontSize: 14, color: isDark.value ? '#eff1f4' : '#0e1115' } },
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, bottom: 50, top: 40 },
      xAxis: {
        type: 'category',
        data: summary.value.stock_distribution.map((i) => i.name),
        axisLabel: { rotate: 30, interval: 0, color: isDark.value ? '#949494' : '#7f8d9f' },
        axisLine: { lineStyle: { color: isDark.value ? '#404040' : '#ebebeb' } },
      },
      yAxis: {
        type: 'value',
        name: '库存',
        axisLabel: { color: isDark.value ? '#949494' : '#7f8d9f' },
        splitLine: { lineStyle: { color: isDark.value ? '#404040' : '#ebebeb' } },
      },
      series: [
        {
          type: 'bar',
          data: summary.value.stock_distribution.map((i) => i.value),
          itemStyle: { color: colors.primary, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 40,
        },
      ],
    })
  }

  // 出入库趋势折线图
  if (trendChartRef.value) {
    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value, isDark.value ? 'dark' : null)
    }
    trendChart.setOption({
      backgroundColor: 'transparent',
      title: { text: '近7天出入库趋势', left: 'center', textStyle: { fontSize: 14, color: isDark.value ? '#eff1f4' : '#0e1115' } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['入库', '出库'], top: 25, textStyle: { color: isDark.value ? '#949494' : '#7f8d9f' } },
      grid: { left: 50, right: 20, bottom: 30, top: 60 },
      xAxis: {
        type: 'category',
        data: summary.value.stock_trend.map((i) => i.date),
        axisLabel: { color: isDark.value ? '#949494' : '#7f8d9f' },
        axisLine: { lineStyle: { color: isDark.value ? '#404040' : '#ebebeb' } },
      },
      yAxis: {
        type: 'value',
        name: '数量',
        axisLabel: { color: isDark.value ? '#949494' : '#7f8d9f' },
        splitLine: { lineStyle: { color: isDark.value ? '#404040' : '#ebebeb' } },
      },
      series: [
        {
          name: '入库',
          type: 'line',
          smooth: true,
          data: summary.value.stock_trend.map((i) => i.in),
          itemStyle: { color: colors.quinary },
          lineStyle: { width: 3 },
          symbolSize: 6,
        },
        {
          name: '出库',
          type: 'line',
          smooth: true,
          data: summary.value.stock_trend.map((i) => i.out),
          itemStyle: { color: colors.secondary },
          lineStyle: { width: 3 },
          symbolSize: 6,
        },
      ],
    })
  }
}

function handleResize() {
  if (distributionChart) distributionChart.resize()
  if (trendChart) trendChart.resize()
}

function handleThemeChange() {
  renderCharts()
}

onMounted(() => {
  loadSummary()
  window.addEventListener('resize', handleResize)
  themeObserver = new MutationObserver(handleThemeChange)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (themeObserver) themeObserver.disconnect()
  if (distributionChart) distributionChart.dispose()
  if (trendChart) trendChart.dispose()
})
</script>

<template>
  <div class="dashboard page-container" v-loading="loading">
    <!-- 统计卡片 -->
    <div class="metric-cards">
      <div class="metric-card">
        <div class="metric-card-label">商品总数</div>
        <div class="metric-card-value">{{ summary ? summary.product_count : 0 }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-label">库存总量</div>
        <div class="metric-card-value">{{ summary ? summary.total_stock : 0 }}</div>
      </div>
      <div class="metric-card metric-danger">
        <div class="metric-card-label">紧急补货</div>
        <div class="metric-card-value">{{ summary ? summary.urgent_count : 0 }}</div>
      </div>
      <div class="metric-card metric-warning">
        <div class="metric-card-label">需补货商品</div>
        <div class="metric-card-value">{{ summary ? summary.replenish_count : 0 }}</div>
      </div>
    </div>

    <!-- 补货告警列表 -->
    <el-card class="panel-card" shadow="never">
      <template #header>
        <div class="panel-header" @click="replenishExpanded = !replenishExpanded">
          <span>补货告警</span>
          <el-icon class="expand-icon" :class="{ expanded: replenishExpanded }">
            <ArrowDown />
          </el-icon>
        </div>
      </template>
      <div v-show="replenishExpanded">
        <el-empty
          v-if="summary && !summary.replenish_list.length"
          description="暂无需要补货的商品"
          :image-size="60"
        />
        <el-table v-else :data="summary ? summary.replenish_list : []" size="small" :border="false">
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
      </div>
    </el-card>

    <!-- 图表 -->
    <div class="charts-row">
      <el-card class="chart-card" shadow="never">
        <div ref="distributionChartRef" class="chart"></div>
      </el-card>
      <el-card class="chart-card" shadow="never">
        <div ref="trendChartRef" class="chart"></div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  background: var(--background);
}
.metric-danger .metric-card-value {
  color: var(--destructive);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}
.expand-icon {
  transition: transform 0.3s ease;
  color: var(--muted-foreground);
}
.expand-icon.expanded {
  transform: rotate(180deg);
}
.metric-warning .metric-card-value {
  color: #fbbc05;
}
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.chart {
  height: 360px;
  width: 100%;
}
@media (max-width: 900px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}
</style>
