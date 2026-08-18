<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiFetch } from '../api'

const stats = ref(null)
const loading = ref(false)
const range = ref('day')

const trendChartRef = ref(null)
const inRankChartRef = ref(null)
const outRankChartRef = ref(null)
let trendChart = null
let inRankChart = null
let outRankChart = null

async function loadStats() {
  loading.value = true
  try {
    const res = await apiFetch('/api/stats/overview?range=' + range.value)
    const data = await res.json()
    stats.value = data
    await nextTick()
    renderCharts()
  } catch (e) {
    // 加载失败时静默处理
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!stats.value) return

  // 出入库趋势折线图
  if (trendChartRef.value) {
    if (!trendChart) trendChart = echarts.init(trendChartRef.value)
    trendChart.setOption({
      title: { text: '出入库趋势', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['入库', '出库'], top: 25 },
      grid: { left: 50, right: 20, bottom: 40, top: 60 },
      xAxis: {
        type: 'category',
        data: stats.value.trend.map((i) => i.label),
        axisLabel: { rotate: 30, interval: 0 },
      },
      yAxis: { type: 'value', name: '数量' },
      series: [
        {
          name: '入库',
          type: 'line',
          smooth: true,
          data: stats.value.trend.map((i) => i.in),
          itemStyle: { color: '#67c23a' },
        },
        {
          name: '出库',
          type: 'line',
          smooth: true,
          data: stats.value.trend.map((i) => i.out),
          itemStyle: { color: '#e6a23c' },
        },
      ],
    })
  }

  // 入库排行（横向柱状图）
  if (inRankChartRef.value) {
    if (!inRankChart) inRankChart = echarts.init(inRankChartRef.value)
    inRankChart.setOption({
      title: { text: '入库 TOP10', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 90, right: 30, bottom: 30, top: 40 },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: stats.value.in_rank.map((i) => i.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: stats.value.in_rank.map((i) => i.value),
          itemStyle: { color: '#67c23a' },
          barMaxWidth: 20,
        },
      ],
    })
  }

  // 出库排行（横向柱状图）
  if (outRankChartRef.value) {
    if (!outRankChart) outRankChart = echarts.init(outRankChartRef.value)
    outRankChart.setOption({
      title: { text: '出库 TOP10', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 90, right: 30, bottom: 30, top: 40 },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: stats.value.out_rank.map((i) => i.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: stats.value.out_rank.map((i) => i.value),
          itemStyle: { color: '#e6a23c' },
          barMaxWidth: 20,
        },
      ],
    })
  }
}

function handleResize() {
  if (trendChart) trendChart.resize()
  if (inRankChart) inRankChart.resize()
  if (outRankChart) outRankChart.resize()
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (trendChart) trendChart.dispose()
  if (inRankChart) inRankChart.dispose()
  if (outRankChart) outRankChart.dispose()
})
</script>

<template>
  <div class="stats-page" v-loading="loading">
    <!-- 统计汇总卡片 -->
    <div class="cards">
      <div class="card">
        <div class="card-label">总入库量</div>
        <div class="card-value card-in">{{ stats ? stats.total_in : 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">总出库量</div>
        <div class="card-value card-out">{{ stats ? stats.total_out : 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">入库次数</div>
        <div class="card-value">{{ stats ? stats.in_count : 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">出库次数</div>
        <div class="card-value">{{ stats ? stats.out_count : 0 }}</div>
      </div>
    </div>

    <!-- 出入库趋势图 -->
    <el-card class="panel">
      <div class="trend-header">
        <span class="panel-title">出入库趋势</span>
        <el-radio-group v-model="range" size="small" @change="loadStats">
          <el-radio-button label="day">日</el-radio-button>
          <el-radio-button label="week">周</el-radio-button>
          <el-radio-button label="month">月</el-radio-button>
        </el-radio-group>
      </div>
      <div ref="trendChartRef" class="chart trend-chart"></div>
    </el-card>

    <!-- 出入库排行 -->
    <div class="rank-row">
      <el-card class="rank-card">
        <div ref="inRankChartRef" class="chart rank-chart"></div>
      </el-card>
      <el-card class="rank-card">
        <div ref="outRankChartRef" class="chart rank-chart"></div>
      </el-card>
    </div>

    <!-- 库存周转分析 -->
    <el-card class="panel">
      <template #header>库存周转分析（按 30 天周期估算）</template>
      <el-empty
        v-if="stats && !stats.turnover.length"
        description="暂无周转数据，请先添加商品并做出库操作"
        :image-size="60"
      />
      <el-table v-else :data="stats ? stats.turnover : []" size="small" border>
        <el-table-column prop="name" label="商品" />
        <el-table-column prop="out_qty" label="出库总量" width="110" />
        <el-table-column prop="current_stock" label="当前库存" width="110" />
        <el-table-column prop="rate" label="周转率（次）" width="120" />
        <el-table-column label="周转天数" width="120">
          <template #default="{ row }">
            {{ row.days == null ? '—' : row.days + ' 天' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.stats-page {
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
.card-in {
  color: #67c23a;
}
.card-out {
  color: #e6a23c;
}
.panel {
  margin-bottom: 16px;
}
.trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.trend-chart {
  height: 360px;
  width: 100%;
}
.rank-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.rank-chart {
  height: 320px;
  width: 100%;
}
@media (max-width: 900px) {
  .cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .rank-row {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 480px) {
  .cards {
    grid-template-columns: 1fr;
  }
  .stats-page {
    padding: 12px;
  }
}
</style>
