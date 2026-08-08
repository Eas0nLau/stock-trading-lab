<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { fetchIndexEmotion } from '../modules/emotion/api.js'

const props = defineProps({
  active: {
    type: Boolean,
    default: true,
  },
})

const loading = ref(false)
const errorMessage = ref('')
const cycleData = ref(null)
const indexChartRef = ref(null)
const limitCompareChartRef = ref(null)
const breadthCompareChartRef = ref(null)
let indexChart = null
let limitCompareChart = null
let breadthCompareChart = null

const indexCycle = computed(() => cycleData.value?.indexCycle || null)
const indexStateClass = computed(() => stateClass(indexCycle.value?.cycleState))

onMounted(() => {
  fetchData()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  if (indexChart) indexChart.dispose()
  if (limitCompareChart) limitCompareChart.dispose()
  if (breadthCompareChart) breadthCompareChart.dispose()
  indexChart = null
  limitCompareChart = null
  breadthCompareChart = null
})

watch(() => props.active, async (isActive) => {
  if (!isActive) return
  if (!cycleData.value) await fetchData()
  await nextTick()
  resizeCharts()
})

async function fetchData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await fetchIndexEmotion()
    cycleData.value = data
    await nextTick()
    renderIndexChart()
    renderMarketCompareCharts()
  } catch (error) {
    errorMessage.value = `获取情绪周期失败：${error.message}`
  } finally {
    loading.value = false
  }
}

function renderIndexChart() {
  const chartDom = indexChartRef.value
  const rows = indexCycle.value?.volatilityChart || []
  if (!chartDom || !rows.length) return
  if (!indexChart) indexChart = echarts.init(chartDom)

  indexChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 42, right: 48, top: 58, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#334155',
      textStyle: { color: '#e5e7eb' },
      formatter: buildIndexTooltip,
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#94a3b8' },
      data: ['情绪分', '收盘', '周期状态'],
    },
    xAxis: {
      type: 'category',
      data: rows.map(row => formatDateShort(row.tradeDate)),
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: [
      {
        type: 'value',
        min: 0,
        max: 100,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
      },
      {
        type: 'value',
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '情绪分',
        type: 'line',
        yAxisIndex: 0,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: { color: 'rgba(34, 211, 238, 0.10)' },
        data: rows.map(row => row.emotionScore),
      },
      {
        name: '收盘',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#f87171' },
        data: rows.map(row => row.closePrice),
      },
      {
        name: '周期状态',
        type: 'scatter',
        yAxisIndex: 0,
        symbolSize: 8,
        z: 6,
        itemStyle: {
          color: params => chartStateColor(params.data?.cycleState),
          borderColor: '#0f172a',
          borderWidth: 1,
        },
        label: {
          show: true,
          position: 'top',
          distance: 6,
          color: '#e2e8f0',
          fontSize: 10,
          fontWeight: 600,
          backgroundColor: 'rgba(15, 23, 42, 0.78)',
          borderColor: 'rgba(148, 163, 184, 0.28)',
          borderWidth: 1,
          borderRadius: 3,
          padding: [2, 4],
          formatter: params => params.data?.cycleState || '',
        },
        emphasis: {
          label: { color: '#ffffff', backgroundColor: 'rgba(15, 23, 42, 0.95)' },
        },
        data: rows.map(row => ({
          value: row.emotionScore,
          cycleState: row.cycleState,
        })),
      },
    ],
  }, true)
}

function resizeCharts() {
  if (indexChart) indexChart.resize()
  if (limitCompareChart) limitCompareChart.resize()
  if (breadthCompareChart) breadthCompareChart.resize()
}

function renderMarketCompareCharts() {
  const rows = recentMarketRows()
  if (!rows.length) return

  limitCompareChart = renderCompareChart({
    chart: limitCompareChart,
    chartDom: limitCompareChartRef.value,
    rows,
    legend: ['涨停', '跌停'],
    colors: ['#f87171', '#34d399'],
    series: [
      { name: '涨停', data: rows.map(row => Number(row.limitUpCount ?? 0)) },
      { name: '跌停', data: rows.map(row => Number(row.limitDownCount ?? 0)) },
    ],
  })

  breadthCompareChart = renderCompareChart({
    chart: breadthCompareChart,
    chartDom: breadthCompareChartRef.value,
    rows,
    legend: ['上涨家数', '下跌家数'],
    colors: ['#f87171', '#34d399'],
    series: [
      { name: '上涨家数', data: rows.map(row => Number(row.advancingCount ?? 0)) },
      { name: '下跌家数', data: rows.map(row => Number(row.decliningCount ?? 0)) },
    ],
  })
}

function renderCompareChart({ chart, chartDom, rows, legend, colors, series }) {
  if (!chartDom) return chart
  const instance = chart || echarts.init(chartDom)
  instance.setOption({
    backgroundColor: 'transparent',
    color: colors,
    grid: { left: 46, right: 18, top: 42, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#111827',
      borderColor: '#334155',
      textStyle: { color: '#e5e7eb' },
    },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#94a3b8' },
      data: legend,
    },
    xAxis: {
      type: 'category',
      data: rows.map(row => formatDateShort(row.tradeDate)),
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
    },
    series: series.map(item => ({
      name: item.name,
      type: 'bar',
      barMaxWidth: 18,
      data: item.data,
    })),
  }, true)
  return instance
}

function recentMarketRows() {
  return (indexCycle.value?.recentTrend || []).slice(-10)
}

function formatDate(date) {
  const text = String(date || '')
  if (text.length !== 8) return text || '-'
  return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`
}

function formatDateShort(date) {
  const text = String(date || '')
  if (text.length !== 8) return text || '-'
  return `${text.slice(4, 6)}-${text.slice(6, 8)}`
}

function formatNumber(value, digits = 2) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return number.toFixed(digits)
}

function formatPercent(value, digits = 2) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${number.toFixed(digits)}%`
}

function buildIndexTooltip(params) {
  const index = params?.[0]?.dataIndex ?? 0
  const row = indexCycle.value?.volatilityChart?.[index] || {}
  const upRatio = row.advanceRatio === null || row.advanceRatio === undefined ? '-' : formatPercent(row.advanceRatio, 1)
  return [
    `<div style="margin-bottom:4px;color:#f8fafc;font-weight:600">${formatDate(row.tradeDate)} ${row.cycleState || ''}</div>`,
    `情绪分：${formatNumber(row.emotionScore, 1)}`,
    `收盘：${formatNumber(row.closePrice, 2)}`,
    `涨跌幅：${formatPercent(row.changePct, 2)}`,
    `上涨占比：${upRatio}`,
  ].join('<br/>')
}

function chartStateColor(state) {
  if (['高潮', '过热高潮'].includes(state)) return '#f87171'
  if (state === '高潮分歧') return '#fbbf24'
  if (state === '发酵') return '#fb923c'
  if (state === '震荡') return '#22d3ee'
  if (state === '弱修复') return '#34d399'
  if (state === '冰点') return '#38bdf8'
  if (state === '退潮') return '#a78bfa'
  return '#94a3b8'
}

function stateClass(state) {
  if (['高潮', '过热高潮'].includes(state)) return 'text-red-200 border-red-400/40 bg-red-500/15'
  if (state === '高潮分歧') return 'text-amber-100 border-amber-300/40 bg-amber-400/15'
  if (state === '发酵') return 'text-orange-100 border-orange-300/40 bg-orange-400/15'
  if (state === '震荡') return 'text-cyan-100 border-cyan-300/40 bg-cyan-400/15'
  if (state === '弱修复') return 'text-emerald-100 border-emerald-300/40 bg-emerald-400/15'
  if (state === '冰点') return 'text-sky-100 border-sky-300/40 bg-sky-400/15'
  if (state === '退潮') return 'text-violet-100 border-violet-300/40 bg-violet-400/15'
  return 'text-slate-100 border-slate-500/40 bg-slate-700/40'
}

</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-950 text-slate-100">
    <div class="flex items-center justify-between border-b border-slate-800 bg-slate-900 px-5 py-4">
      <div>
        <h1 class="text-lg font-semibold text-white">情绪周期</h1>
        <div class="mt-1 text-xs text-slate-400">指数周期，基于现有日线和市场宽度计算</div>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="indexCycle" class="text-xs text-slate-400">交易日 {{ formatDate(indexCycle.tradeDate) }}</span>
        <button
          class="rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:border-cyan-400/60 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
          @click="fetchData">
          {{ loading ? '刷新中' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="errorMessage" class="m-5 rounded border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
      {{ errorMessage }}
    </div>

    <div v-if="indexCycle" class="strategy-scrollbar min-h-0 flex-1 overflow-auto p-5">
      <section class="grid gap-4 lg:grid-cols-[1.05fr_1.95fr]">
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-xs text-slate-400">指数周期</div>
              <div class="mt-3 inline-flex rounded border px-4 py-2 text-2xl font-semibold" :class="indexStateClass">
                {{ indexCycle.cycleState }}
              </div>
            </div>
            <div class="text-right">
              <div class="text-xs text-slate-400">情绪分</div>
              <div class="mt-2 text-5xl font-semibold text-white">{{ formatNumber(indexCycle.cycleScore, 1) }}</div>
            </div>
          </div>
          <p class="mt-5 text-sm leading-6 text-slate-300">{{ indexCycle.summary }}</p>
        </div>

        <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-white">指数周期波动</h2>
            <span class="text-xs text-slate-500">情绪分 / 上证收盘 / 周期状态</span>
          </div>
          <div ref="indexChartRef" class="h-[320px] w-full"></div>
        </div>
      </section>

      <section class="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-400">上证收盘</div>
          <div class="mt-2 text-2xl font-semibold text-white">{{ formatNumber(indexCycle.indexQuote.closePrice, 2) }}</div>
          <div class="mt-1 text-sm" :class="indexCycle.indexQuote.changePct >= 0 ? 'text-red-300' : 'text-emerald-300'">
            {{ formatPercent(indexCycle.indexQuote.changePct, 2) }}
          </div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-400">市场宽度</div>
          <div class="mt-2 text-2xl font-semibold text-white">{{ formatPercent(indexCycle.marketBreadth.advanceRatio, 1) }}</div>
          <div class="mt-1 text-sm text-slate-400">上涨 {{ indexCycle.marketBreadth.advancingCount }} / 下跌 {{ indexCycle.marketBreadth.decliningCount }}</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-400">普通主板涨跌停</div>
          <div class="mt-2 text-2xl font-semibold text-white">{{ indexCycle.marketBreadth.limitUpCount }} / {{ indexCycle.marketBreadth.limitDownCount }}</div>
          <div class="mt-1 text-sm text-slate-400">涨停 / 跌停</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-400">成交额比例</div>
          <div class="mt-2 text-2xl font-semibold text-white">{{ formatNumber(indexCycle.marketBreadth.turnoverRatio, 2) }}x</div>
          <div class="mt-1 text-sm text-slate-400">相对近 20 日</div>
        </div>
      </section>

      <section class="mt-4 grid gap-4 xl:grid-cols-2">
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-white">近10日普通主板涨跌停对比</h2>
            <span class="text-xs text-slate-500">普通主板涨停 / 普通主板跌停</span>
          </div>
          <div ref="limitCompareChartRef" class="h-[260px] w-full"></div>
        </div>

        <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-white">近10日涨跌家数对比</h2>
            <span class="text-xs text-slate-500">上涨家数 / 下跌家数</span>
          </div>
          <div ref="breadthCompareChartRef" class="h-[260px] w-full"></div>
        </div>
      </section>
    </div>

    <div v-else-if="loading" class="flex flex-1 items-center justify-center text-sm text-slate-400">
      正在计算情绪周期...
    </div>
  </div>
</template>

<style scoped>
.strategy-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.strategy-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.75);
}
.strategy-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(71, 85, 105, 0.9);
  border-radius: 999px;
}
.strategy-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(103, 232, 249, 0.75);
}
</style>
