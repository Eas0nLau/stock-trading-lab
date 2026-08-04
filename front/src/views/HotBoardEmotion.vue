<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  active: {
    type: Boolean,
    default: true,
  },
})

const API_URL = '/api/hot-board-emotion/current'
const loading = ref(false)
const errorMessage = ref('')
const pageData = ref(null)
const selectedDate = ref(null)
const selectedBoardName = ref('')
const comparisonChartRef = ref(null)
const emotionChartRef = ref(null)
let comparisonChart = null
let emotionChart = null

const BOARD_LINE_COLORS = ['#22d3ee', '#fb7185', '#fbbf24', '#a78bfa', '#60a5fa', '#34d399', '#f97316', '#e879f9', '#94a3b8']

const availableDates = computed(() => pageData.value?.可选日期 || [])
const entryThreshold = computed(() => numeric(pageData.value?.配置?.热门板块入选数量阈值) || 10)
const climaxThreshold = computed(() => numeric(pageData.value?.配置?.高潮数量阈值) || 20)
const boardList = computed(() => {
  const date = Number(selectedDate.value || pageData.value?.最新交易日 || 0)
  return (pageData.value?.板块列表 || [])
    .map(board => {
      const trend = board.近期走势 || []
      const record = trend.find(item => Number(item.日期) === date) || null
      const recentStrength = calculateRecentStrength(trend, date)
      const state = record?.综合状态 || '沉寂'
      const score = numeric(record?.情绪分)
      return {
        ...board,
        当前记录: record,
        当前状态: state,
        当前情绪分: score,
        选择日期近期强度: recentStrength,
        排序值: stateRank(state) * 1000 + score * 5 + recentStrength,
      }
    })
    .sort((left, right) => right.排序值 - left.排序值 || right.近30日峰值数量 - left.近30日峰值数量 || left.板块.localeCompare(right.板块))
})
const selectedBoard = computed(() => {
  return boardList.value.find(board => board.板块 === selectedBoardName.value) || boardList.value[0] || null
})
const selectedTrend = computed(() => selectedBoard.value?.近期走势 || [])
const selectedRecord = computed(() => {
  const date = Number(selectedDate.value || 0)
  return selectedTrend.value.find(item => Number(item.日期) === date) || selectedTrend.value.at(-1) || null
})

onMounted(() => {
  fetchData()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  if (comparisonChart) comparisonChart.dispose()
  if (emotionChart) emotionChart.dispose()
  comparisonChart = null
  emotionChart = null
})

watch(() => props.active, async isActive => {
  if (!isActive) return
  if (!pageData.value) await fetchData()
  await nextTick()
  resizeCharts()
})

watch([selectedBoardName, selectedDate], async () => {
  await nextTick()
  renderCharts()
})

async function fetchData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${API_URL}?days=30`)
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
    const data = await response.json()
    if (data?.状态 !== 'success') throw new Error(data?.错误信息 || '热门板块情绪数据不可用')
    pageData.value = data
    selectedDate.value = data.最新交易日
    const boardNames = new Set((data.板块列表 || []).map(item => item.板块))
    if (!boardNames.has(selectedBoardName.value)) selectedBoardName.value = data.板块列表?.[0]?.板块 || ''
    await nextTick()
    renderCharts()
  } catch (error) {
    errorMessage.value = `获取热门板块情绪失败：${error.message}`
  } finally {
    loading.value = false
  }
}

function selectBoard(board) {
  selectedBoardName.value = board.板块
}

function renderCharts() {
  renderComparisonChart()
  renderEmotionChart()
}

function renderComparisonChart() {
  const chartDom = comparisonChartRef.value
  const dates = availableDates.value
  const boards = boardList.value
  if (!chartDom) return
  if (!comparisonChart) comparisonChart = echarts.init(chartDom)
  if (!dates.length || !boards.length) {
    comparisonChart.clear()
    return
  }

  const selectedDateLabel = formatDateShort(selectedDate.value)
  const originalBoardNames = (pageData.value?.板块列表 || []).map(item => item.板块)
  const series = boards.map((board, index) => {
    const trendMap = new Map((board.近期走势 || []).map(row => [Number(row.日期), row]))
    const colorIndex = Math.max(originalBoardNames.indexOf(board.板块), 0)
    const color = BOARD_LINE_COLORS[colorIndex % BOARD_LINE_COLORS.length]
    const selected = board.板块 === selectedBoardName.value
    return {
      name: board.板块,
      type: 'line',
      smooth: true,
      connectNulls: false,
      showSymbol: false,
      z: selected ? 6 : 2,
      lineStyle: { color, width: selected ? 3.5 : 1.8, opacity: selected ? 1 : 0.68 },
      itemStyle: { color },
      emphasis: { focus: 'series', lineStyle: { width: 4 } },
      data: dates.map(date => {
        const row = trendMap.get(Number(date))
        return { value: row?.情绪分 ?? null, row, boardName: board.板块 }
      }),
      markLine: index === 0 ? {
        silent: true,
        symbol: ['none', 'none'],
        label: { show: false },
        lineStyle: { color: '#f8fafc', opacity: 0.24, type: 'dashed' },
        data: selectedDateLabel ? [{ xAxis: selectedDateLabel }] : [],
      } : undefined,
    }
  })

  comparisonChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 48, right: 22, top: 58, bottom: 38 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#334155',
      textStyle: { color: '#e5e7eb' },
      formatter: buildComparisonTooltip,
    },
    legend: {
      type: 'scroll',
      top: 0,
      left: 0,
      right: 0,
      pageIconColor: '#22d3ee',
      pageIconInactiveColor: '#475569',
      pageTextStyle: { color: '#94a3b8' },
      textStyle: { color: '#94a3b8' },
      data: boards.map(board => board.板块),
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates.map(formatDateShort),
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', interval: 2 },
    },
    yAxis: {
      type: 'value',
      name: '情绪分',
      min: 0,
      max: 100,
      nameTextStyle: { color: '#64748b' },
      axisLabel: { color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
    },
    series,
  }, true)

  comparisonChart.off('click')
  comparisonChart.on('click', params => {
    const row = params?.data?.row
    const boardName = params?.data?.boardName || params?.seriesName
    if (boardName) selectedBoardName.value = boardName
    if (row?.日期) selectedDate.value = Number(row.日期)
  })
}

function renderEmotionChart() {
  const chartDom = emotionChartRef.value
  const rows = selectedTrend.value
  if (!chartDom) return
  if (!emotionChart) emotionChart = echarts.init(chartDom)
  if (!rows.length) {
    emotionChart.clear()
    return
  }

  const selectedDateLabel = formatDateShort(selectedDate.value)
  emotionChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 48, right: 54, top: 58, bottom: 38 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#334155',
      textStyle: { color: '#e5e7eb' },
      formatter: buildEmotionTooltip,
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#94a3b8' },
      data: ['情绪分', '上榜数量', '情绪状态'],
    },
    xAxis: {
      type: 'category',
      data: rows.map(row => formatDateShort(row.日期)),
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', interval: 2 },
    },
    yAxis: [
      {
        type: 'value',
        name: '情绪分',
        min: 0,
        max: 100,
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
      },
      {
        type: 'value',
        name: '上榜数量',
        min: 0,
        nameTextStyle: { color: '#64748b' },
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
        z: 4,
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: { color: 'rgba(34, 211, 238, 0.10)' },
        data: rows.map(row => ({ value: row.情绪分, row })),
        markLine: {
          silent: true,
          symbol: ['none', 'none'],
          label: { show: false },
          lineStyle: { color: '#f8fafc', opacity: 0.22, type: 'dashed' },
          data: selectedDateLabel ? [{ xAxis: selectedDateLabel }] : [],
        },
      },
      {
        name: '上榜数量',
        type: 'bar',
        yAxisIndex: 1,
        barMaxWidth: 15,
        z: 1,
        itemStyle: { color: 'rgba(248, 113, 113, 0.30)', borderColor: 'rgba(248, 113, 113, 0.58)', borderWidth: 1 },
        label: {
          show: true,
          position: 'top',
          distance: 4,
          color: '#fda4af',
          fontSize: 9,
          fontWeight: 600,
          formatter: params => numeric(params.data?.row?.当日板块数量) >= climaxThreshold.value
            ? `${formatDateShort(params.data.row.日期)} 高潮`
            : '',
        },
        data: rows.map(row => ({ value: row.当日板块数量, row })),
        markLine: {
          silent: true,
          symbol: ['none', 'none'],
          lineStyle: { color: '#fb7185', type: 'dashed', width: 1.5 },
          label: { formatter: `高潮线 ${climaxThreshold.value}`, color: '#fda4af', position: 'insideEndTop' },
          data: [{ yAxis: climaxThreshold.value }],
        },
      },
      {
        name: '情绪状态',
        type: 'scatter',
        yAxisIndex: 0,
        symbolSize: 8,
        z: 7,
        itemStyle: {
          color: params => stateColor(params.data?.row?.综合状态),
          borderColor: '#0f172a',
          borderWidth: 1,
        },
        label: {
          show: true,
          position: 'top',
          distance: 6,
          color: '#e2e8f0',
          fontSize: 9,
          fontWeight: 600,
          backgroundColor: 'rgba(15, 23, 42, 0.82)',
          borderColor: 'rgba(148, 163, 184, 0.25)',
          borderWidth: 1,
          borderRadius: 3,
          padding: [2, 4],
          formatter: params => ['高潮', '沉寂', '未上榜'].includes(params.data?.row?.综合状态) ? '' : params.data?.row?.综合状态 || '',
        },
        data: rows.map(row => ({ value: row.情绪分 ?? 0, row })),
      },
    ],
  }, true)

  emotionChart.off('click')
  emotionChart.on('click', params => {
    const date = params?.data?.row?.日期
    if (date) selectedDate.value = Number(date)
  })
}

function buildEmotionTooltip(params) {
  const row = params?.find(item => item?.data?.row)?.data?.row
  if (!row) return ''
  return [
    `<div style="font-weight:600;margin-bottom:6px">${formatDate(row.日期)} · ${row.综合状态 || '-'}</div>`,
    `情绪分：${formatNumber(row.情绪分, 1)}`,
    `当日上榜：${row.当日板块数量 ?? '-'} 只（${row.热度阶段 || '-'}）`,
    `高潮判定：${numeric(row.当日板块数量) >= climaxThreshold.value ? '是' : '否'}（阈值 ${climaxThreshold.value} 只）`,
    `样本来源：${formatDate(row.样本来源日期)}，股票池 ${row.前日股票池数量 ?? 0} 只`,
    `平均涨幅：${formatPercent(row.平均涨跌幅)}，平均振幅：${formatPercent(row.平均振幅)}`,
    `旧池晋级：${row.晋级家数 ?? 0} 只（${formatPercent(row.晋级率)}），新增涨停：${row.新晋级家数 ?? 0} 只（${formatPercent(row.新晋级率)}）`,
    `红盘率：${formatPercent(row.红盘率)}，大跌率：${formatPercent(row.大跌率)}`,
  ].join('<br/>')
}

function buildComparisonTooltip(params) {
  const items = (params || [])
    .filter(item => item?.data?.row)
    .sort((left, right) => numeric(right.value) - numeric(left.value))
  if (!items.length) return ''
  const date = items[0].data.row.日期
  const rows = items.map(item => {
    const row = item.data.row
    return `${item.marker}${item.seriesName}：${formatNumber(row.情绪分, 1)} · ${row.综合状态 || '-'} · 上榜 ${row.当日板块数量 ?? '-'}只`
  })
  return [`<div style="font-weight:600;margin-bottom:6px">${formatDate(date)}</div>`, ...rows].join('<br/>')
}

function calculateRecentStrength(trend, date) {
  const rows = (trend || []).filter(item => Number(item.日期) <= date).slice(-3)
  if (!rows.length) return 0
  const weights = [0.2, 0.3, 0.5].slice(-rows.length)
  const sum = weights.reduce((total, value) => total + value, 0)
  return rows.reduce((total, row, index) => total + numeric(row.情绪分) * weights[index], 0) / sum
}

function resizeCharts() {
  if (comparisonChart) comparisonChart.resize()
  if (emotionChart) emotionChart.resize()
}

function stateRank(state) {
  return {
    高潮: 100,
    强势延续: 90,
    良性承接: 80,
    升温: 70,
    分化: 60,
    活跃: 55,
    分歧: 40,
    数据不足: 30,
    退潮: 20,
    沉寂: 10,
    数据缺失: 0,
  }[state] ?? 0
}

function stateColor(state) {
  return {
    高潮: '#fb7185',
    强势延续: '#f87171',
    良性承接: '#22d3ee',
    升温: '#fbbf24',
    分化: '#c084fc',
    活跃: '#60a5fa',
    分歧: '#f59e0b',
    退潮: '#34d399',
    数据不足: '#94a3b8',
    沉寂: '#475569',
    数据缺失: '#64748b',
  }[state] || '#94a3b8'
}

function stateClass(state) {
  return {
    高潮: 'border-rose-400/60 bg-rose-500/15 text-rose-200',
    强势延续: 'border-red-400/60 bg-red-500/15 text-red-200',
    良性承接: 'border-cyan-400/60 bg-cyan-500/15 text-cyan-200',
    升温: 'border-amber-400/60 bg-amber-500/15 text-amber-200',
    分化: 'border-purple-400/60 bg-purple-500/15 text-purple-200',
    活跃: 'border-blue-400/60 bg-blue-500/15 text-blue-200',
    分歧: 'border-orange-400/60 bg-orange-500/15 text-orange-200',
    退潮: 'border-emerald-400/60 bg-emerald-500/15 text-emerald-200',
    数据不足: 'border-slate-500 bg-slate-800 text-slate-300',
    沉寂: 'border-slate-700 bg-slate-900 text-slate-400',
    数据缺失: 'border-slate-600 bg-slate-800 text-slate-400',
  }[state] || 'border-slate-600 bg-slate-800 text-slate-300'
}

function formatDate(date) {
  const text = String(date || '')
  return text.length === 8 ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}` : '-'
}

function formatDateShort(date) {
  const text = String(date || '')
  return text.length === 8 ? `${text.slice(4, 6)}-${text.slice(6, 8)}` : ''
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '-'
}

function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(digits)}%` : '-'
}

function numeric(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-950 text-slate-100">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-5 py-4">
      <div>
        <h1 class="text-lg font-semibold text-white">热门板块情绪</h1>
        <div class="mt-1 text-xs text-slate-400">昨日股票池的今日承接表现 · 近30个交易日</div>
      </div>
      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 text-xs text-slate-400">
          展示日期
          <select
            v-model.number="selectedDate"
            class="rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/60">
            <option v-for="date in [...availableDates].reverse()" :key="date" :value="date">{{ formatDate(date) }}</option>
          </select>
        </label>
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

    <div v-if="pageData && boardList.length" class="hot-board-scrollbar min-h-0 flex-1 overflow-auto p-5">
      <section class="mb-4 rounded-lg border border-slate-800 bg-slate-900 p-5">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-white">热门板块情绪对比</h2>
          <span class="text-xs text-slate-500">入选 ≥ {{ entryThreshold }}只 · 高潮 ≥ {{ climaxThreshold }}只 · 点击曲线查看明细</span>
        </div>
        <div ref="comparisonChartRef" class="h-[360px] w-full"></div>
      </section>

      <section class="grid min-h-[470px] gap-4 xl:grid-cols-[310px_minmax(0,1fr)]">
        <aside class="flex min-h-0 flex-col rounded-lg border border-slate-800 bg-slate-900">
          <div class="border-b border-slate-800 px-4 py-3">
            <div class="text-sm font-semibold text-white">板块强弱排行</div>
            <div class="mt-1 text-xs text-slate-500">{{ formatDate(selectedDate) }} · 强势到弱势</div>
          </div>
          <div class="hot-board-scrollbar min-h-0 flex-1 space-y-2 overflow-auto p-3">
            <button
              v-for="(board, index) in boardList"
              :key="board.板块"
              class="w-full rounded-lg border px-3 py-3 text-left transition"
              :class="selectedBoard?.板块 === board.板块 ? 'border-cyan-400/60 bg-cyan-500/10' : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'"
              @click="selectBoard(board)">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <span class="mr-2 text-xs text-slate-500">{{ index + 1 }}</span>
                  <span class="font-medium text-white">{{ board.板块 }}</span>
                </div>
                <span class="shrink-0 rounded border px-2 py-1 text-[11px]" :class="stateClass(board.当前状态)">{{ board.当前状态 }}</span>
              </div>
              <div class="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div class="text-slate-500">情绪分</div>
                  <div class="mt-1 font-semibold text-cyan-200">{{ formatNumber(board.当前情绪分, 1) }}</div>
                </div>
                <div>
                  <div class="text-slate-500">上榜</div>
                  <div class="mt-1 text-slate-200">{{ board.当前记录?.当日板块数量 ?? '-' }}</div>
                </div>
                <div>
                  <div class="text-slate-500">平均涨幅</div>
                  <div
                    class="mt-1"
                    :class="numeric(board.当前记录?.平均涨跌幅) >= 0 ? 'text-red-300' : 'text-emerald-300'">
                    {{ formatPercent(board.当前记录?.平均涨跌幅) }}
                  </div>
                </div>
              </div>
            </button>
          </div>
        </aside>

        <div v-if="selectedBoard && selectedRecord" class="min-w-0 space-y-4">
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div class="text-xs text-slate-400">{{ selectedBoard.板块 }} · {{ formatDate(selectedRecord.日期) }}</div>
                <div class="mt-3 flex flex-wrap items-center gap-2">
                  <span class="rounded border px-4 py-2 text-xl font-semibold" :class="stateClass(selectedRecord.综合状态)">{{ selectedRecord.综合状态 }}</span>
                  <span class="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-300">热度 {{ selectedRecord.热度阶段 }}</span>
                  <span class="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-300">承接 {{ selectedRecord.承接情绪 }}</span>
                </div>
              </div>
              <div class="text-right">
                <div class="text-xs text-slate-400">情绪分</div>
                <div class="mt-1 text-5xl font-semibold text-white">{{ formatNumber(selectedRecord.情绪分, 1) }}</div>
                <div class="mt-1 text-xs text-slate-500">近30日峰值 {{ selectedBoard.近30日峰值数量 }} 只</div>
              </div>
            </div>
            <p class="mt-4 text-sm leading-6 text-slate-300">{{ selectedRecord.判定摘要 }}</p>
          </div>

          <div class="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div class="mb-3 flex items-center justify-between gap-3">
              <h2 class="text-sm font-semibold text-white">近期情绪走势</h2>
              <span class="text-xs text-slate-500">情绪分 / 上榜数量 / 综合状态</span>
            </div>
            <div ref="emotionChartRef" class="h-[350px] w-full"></div>
          </div>
        </div>
      </section>

      <section v-if="selectedRecord" class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-500">前日股票池</div>
          <div class="mt-2 text-xl font-semibold text-white">{{ selectedRecord.前日股票池数量 ?? 0 }} / {{ selectedRecord.前日板块数量 ?? '-' }}</div>
          <div class="mt-1 text-xs text-slate-500">落库明细 / 来源统计</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-500">平均涨幅</div>
          <div class="mt-2 text-xl font-semibold" :class="numeric(selectedRecord.平均涨跌幅) >= 0 ? 'text-red-300' : 'text-emerald-300'">{{ formatPercent(selectedRecord.平均涨跌幅) }}</div>
          <div class="mt-1 text-xs text-slate-500">中位数 {{ formatPercent(selectedRecord.中位数涨跌幅) }}</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-500">平均振幅</div>
          <div class="mt-2 text-xl font-semibold text-amber-200">{{ formatPercent(selectedRecord.平均振幅) }}</div>
          <div class="mt-1 text-xs text-slate-500">涨幅离散 {{ formatNumber(selectedRecord.涨幅标准差, 2) }}</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-500">晋级情况</div>
          <div class="mt-2 text-xl font-semibold text-red-300">{{ formatPercent(selectedRecord.晋级率) }}</div>
          <div class="mt-1 text-xs text-slate-500">旧池 {{ selectedRecord.晋级家数 ?? 0 }} / {{ selectedRecord.前日股票池数量 ?? 0 }} · 新增 {{ selectedRecord.新晋级家数 ?? 0 }} 只</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-500">红盘率</div>
          <div class="mt-2 text-xl font-semibold text-cyan-200">{{ formatPercent(selectedRecord.红盘率) }}</div>
          <div class="mt-1 text-xs text-slate-500">行情覆盖 {{ formatPercent(selectedRecord.行情覆盖率) }}</div>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div class="text-xs text-slate-500">大跌率</div>
          <div class="mt-2 text-xl font-semibold text-emerald-300">{{ formatPercent(selectedRecord.大跌率) }}</div>
          <div class="mt-1 text-xs text-slate-500">炸板率 {{ formatPercent(selectedRecord.炸板率) }}</div>
        </div>
      </section>

      <section v-if="selectedBoard" class="mt-4 overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
        <div class="border-b border-slate-800 px-5 py-4">
          <h2 class="text-sm font-semibold text-white">逐日情绪明细</h2>
        </div>
        <div class="hot-board-scrollbar overflow-x-auto">
          <table class="min-w-[1180px] w-full text-left text-xs">
            <thead class="bg-slate-950/70 text-slate-400">
              <tr>
                <th class="px-4 py-3 font-medium">日期</th>
                <th class="px-4 py-3 font-medium">综合状态</th>
                <th class="px-4 py-3 font-medium">热度 / 承接</th>
                <th class="px-4 py-3 font-medium">当日上榜</th>
                <th class="px-4 py-3 font-medium">样本来源</th>
                <th class="px-4 py-3 font-medium">股票池 / 有效</th>
                <th class="px-4 py-3 font-medium">平均涨幅</th>
                <th class="px-4 py-3 font-medium">平均振幅</th>
                <th class="px-4 py-3 font-medium">晋级率</th>
                <th class="px-4 py-3 font-medium">红盘率</th>
                <th class="px-4 py-3 font-medium">大跌率</th>
                <th class="px-4 py-3 font-medium">情绪分</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800">
              <tr
                v-for="row in [...selectedTrend].reverse()"
                :key="row.日期"
                class="cursor-pointer hover:bg-slate-800/60"
                :class="Number(row.日期) === Number(selectedDate) ? 'bg-cyan-500/5' : ''"
                @click="selectedDate = Number(row.日期)">
                <td class="whitespace-nowrap px-4 py-3 text-slate-300">{{ formatDate(row.日期) }}</td>
                <td class="px-4 py-3"><span class="rounded border px-2 py-1" :class="stateClass(row.综合状态)">{{ row.综合状态 }}</span></td>
                <td class="px-4 py-3 text-slate-400">{{ row.热度阶段 }} / {{ row.承接情绪 }}</td>
                <td class="px-4 py-3 text-slate-300">{{ row.当日板块数量 ?? '-' }}</td>
                <td class="px-4 py-3 text-slate-400">{{ formatDate(row.样本来源日期) }}</td>
                <td class="px-4 py-3 text-slate-300">{{ row.前日股票池数量 ?? 0 }} / {{ row.有效样本数 ?? 0 }}</td>
                <td class="px-4 py-3" :class="numeric(row.平均涨跌幅) >= 0 ? 'text-red-300' : 'text-emerald-300'">{{ formatPercent(row.平均涨跌幅) }}</td>
                <td class="px-4 py-3 text-amber-200">{{ formatPercent(row.平均振幅) }}</td>
                <td class="px-4 py-3 text-red-300">
                  {{ formatPercent(row.晋级率) }}
                  <div class="mt-1 whitespace-nowrap text-[11px] text-slate-500">旧 {{ row.晋级家数 ?? 0 }} · 新 {{ row.新晋级家数 ?? 0 }}</div>
                </td>
                <td class="px-4 py-3 text-cyan-200">{{ formatPercent(row.红盘率) }}</td>
                <td class="px-4 py-3 text-emerald-300">{{ formatPercent(row.大跌率) }}</td>
                <td class="px-4 py-3 font-semibold text-white">{{ formatNumber(row.情绪分, 1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-else-if="loading" class="flex flex-1 items-center justify-center text-sm text-slate-400">
      正在加载热门板块情绪...
    </div>
    <div v-else-if="pageData && !boardList.length" class="flex flex-1 items-center justify-center text-sm text-slate-400">
      最近30个交易日暂无符合条件的热门板块。
    </div>
  </div>
</template>

<style scoped>
.hot-board-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.hot-board-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.75);
}
.hot-board-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(71, 85, 105, 0.9);
  border-radius: 999px;
}
.hot-board-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(103, 232, 249, 0.75);
}
</style>
