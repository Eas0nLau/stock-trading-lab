<template>
  <div>
    <div class="flex items-center justify-between gap-4 mb-4">
      <div class="flex min-w-0 flex-1 items-center gap-3">
        <h2 class="text-2xl font-semibold tracking-tight text-white">{{ title }}</h2>
        <select
            v-model="selectedDate"
            @change="fetchData"
            class="h-9 flex-none rounded-lg border border-slate-700 bg-[#111827] px-3 text-sm text-slate-100 outline-none transition hover:border-slate-500 focus:border-sky-500">
          <option v-for="date in dateOptions" :key="date" :value="date">{{ formatDate(date) }}</option>
        </select>

        <label class="filter-control">
          <span class="filter-control-label">净额</span>
          <input
              v-model="filterAmount"
              @input="updateFilterAmount"
              type="number"
              min="0"
              step="1"
              class="filter-control-input filter-amount-input"
              aria-label="筛选净额"
              placeholder="3">
          <span class="filter-control-unit">亿</span>
        </label>
      </div>

      <div class="flex flex-none items-center gap-2">
        <button
            @click="requestNotificationPermission"
            :disabled="notificationPermission === 'granted' || notificationPermission === 'unsupported'"
            :title="notificationButtonTitle()"
            class="px-4 py-1.5 bg-white/10 hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-60 text-white text-sm rounded-lg transition flex items-center gap-1.5">
          <span>🔔</span>
          <span>{{ notificationButtonText() }}</span>
        </button>

        <button
            @click="retryFetch"
            class="px-4 py-1.5 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition flex items-center gap-1.5">
          <span>🔄</span>
          <span>手动刷新</span>
        </button>
      </div>
    </div>

    <div class="flex h-[calc(77vh)] min-h-0 gap-4">
      <aside class="filter-results-panel flex w-72 flex-none flex-col rounded-2xl border border-slate-800 bg-[#0f172a]/85 p-3">
        <div class="mb-3 flex items-center justify-between gap-2">
          <div class="text-sm font-semibold text-slate-100">命中结果</div>
          <div class="rounded-md border border-red-400/25 bg-red-500/10 px-2 py-0.5 font-mono text-xs text-red-200">
            {{ filterResults.length }}
          </div>
        </div>

        <div class="filter-results-list flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          <div
              v-for="item in filterResults"
              :key="item.boardName"
              class="rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-slate-100">
            <div class="mb-2 flex items-start justify-between gap-2">
              <span class="min-w-0 flex-1 truncate text-sm font-semibold text-white">{{ item.boardName }}</span>
              <span class="font-mono text-sm font-semibold text-red-300">{{ formatFundFlowAmount(item.netInflow100m) }}亿</span>
            </div>
            <div class="flex items-center gap-2">
              <button
                  @click="copyStockName(item)"
                  :title="`复制 ${item.selectedLeader || item.leader || '-'}`"
                  class="copy-stock-button rounded-md border border-amber-300/30 bg-amber-300/10 px-1.5 py-0.5 font-semibold text-amber-100">
                {{ copiedStockName === (item.selectedLeader || item.leader) ? '已复制' : (item.selectedLeader || item.leader || '-') }}
              </button>
              <span class="rounded-md border border-sky-300/25 bg-sky-300/10 px-1.5 py-0.5 font-mono font-semibold text-sky-100">{{ item.selectedTime || item.time }}</span>
            </div>
          </div>
          <div v-if="!filterResults.length"
               class="rounded-xl border border-slate-700 bg-white/5 px-3 py-3 text-center text-xs text-slate-500">
            暂无匹配
          </div>
        </div>
      </aside>

      <div ref="chartRef" class="min-w-0 flex-1 bg-[#0a0f1e] rounded-3xl chart-container"></div>
    </div>

    <!-- 错误弹框（保持不变） -->
    <div v-if="errorMessage"
         class="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div class="bg-[#1a2332] rounded-2xl p-8 max-w-md w-full mx-4 border border-red-500/50 shadow-2xl">
        <div class="flex items-center gap-4 mb-5">
          <div class="w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center flex-shrink-0">
            <span class="text-red-400 text-3xl">⚠️</span>
          </div>
          <div>
            <h3 class="text-2xl font-semibold text-white">后端服务未启动</h3>
            <p class="text-red-400 text-sm mt-1">连接失败</p>
          </div>
        </div>

        <p class="text-gray-300 leading-relaxed mb-6">{{ errorMessage }}</p>

        <div class="flex gap-3">
          <button @click="retryFetch"
                  class="flex-1 py-3.5 bg-white hover:bg-gray-200 active:bg-gray-300 text-black font-semibold rounded-xl transition-all flex items-center justify-center gap-2">
            <span>🔄</span>
            <span>重试连接</span>
          </button>
          <button @click="errorMessage = ''"
                  class="flex-1 py-3.5 bg-[#334155] hover:bg-[#475569] text-white font-medium rounded-xl transition-all">
            关闭
          </button>
        </div>
        <div class="mt-4 text-center text-xs text-gray-500">
          请确保后端服务已启动（端口 8527）
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { fetchFundFlowDates, fetchFundFlowHistory, openFundFlowStream } from '../modules/fund-flow/api.js'
import { formatFundFlowAmount } from '../modules/fund-flow/normalizers.js'

const chartRef = ref(null)
let chartInstance = null
let fundFlowStream = null
let streamRefreshTimer = null
let fetchController = null
let fetchRequestId = 0
const props = defineProps({
  title: {
    type: String,
    default: '板块资金流向'
  },
  flowType: {
    type: String,
    default: 'industry'
  },
  active: {
    type: Boolean,
    default: true
  }
})
const errorMessage = ref('')
const dateOptions = ref([])
const selectedDate = ref('')
const filterAmount = ref(3)
const filterResults = ref([])
const currentPlotData = ref([])
const notificationPermission = ref(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)
const lastNotificationKey = ref('')
const copiedStockName = ref('')
let copyFeedbackTimer = null

const getToday = () => {
  const date = new Date()
  return `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`
}

const formatDate = (date) => {
  if (!date || date.length !== 8) return date
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
}

const isTradingTime = () => {
  const now = new Date()
  const time = now.getHours() * 100 + now.getMinutes()
  return (time >= 930 && time <= 1130) || (time >= 1300 && time <= 1500)
}

const getColorByRank = (rank, total) => {
  if (total <= 1) return '#ff4757'
  const ratio = rank / (total - 1)
  const hue = Math.round(0 + 120 * ratio)
  return `hsl(${hue}, 94%, 56%)`
}

const parseFilterConditions = () => {
  const amount = Math.floor(Number(filterAmount.value) || 0)
  return { amount }
}

const isNotificationSupported = () => typeof Notification !== 'undefined'

const copyText = async (text) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

const copyStockName = async (item) => {
  const stockName = item.selectedLeader || item.leader
  if (!stockName) return

  try {
    await copyText(stockName)
    copiedStockName.value = stockName
    if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
    copyFeedbackTimer = setTimeout(() => {
      if (copiedStockName.value === stockName) {
        copiedStockName.value = ''
      }
    }, 1200)
  } catch (e) {
    console.error('复制股票名称失败:', e)
  }
}

const notificationButtonText = () => {
  if (notificationPermission.value === 'granted') return '通知已开'
  if (notificationPermission.value === 'denied') return '通知被拒'
  if (notificationPermission.value === 'unsupported') return '不支持通知'
  return '开启通知'
}

const notificationButtonTitle = () => {
  if (notificationPermission.value === 'denied') return '请在浏览器设置中允许此站点通知'
  if (notificationPermission.value === 'unsupported') return '当前浏览器不支持 Notification API'
  if (notificationPermission.value === 'granted') return '命中筛选条件时会触发浏览器通知'
  return '点击后允许浏览器通知'
}

const requestNotificationPermission = async () => {
  if (!isNotificationSupported()) {
    notificationPermission.value = 'unsupported'
    return
  }

  notificationPermission.value = await Notification.requestPermission()
  if (notificationPermission.value === 'granted') {
    notifyFilterResults(filterResults.value, true)
  }
}

const dedupeRowsByBoard = (rows) => {
  const bestByBoard = new Map()
  rows.forEach(row => {
    const existing = bestByBoard.get(row.boardName)
    if (!existing || Math.abs(row.netInflow100m) > Math.abs(existing.netInflow100m)) {
      bestByBoard.set(row.boardName, row)
    }
  })
  return [...bestByBoard.values()]
}

const updateFilterResults = () => {
  const { amount } = parseFilterConditions()
  const bestByBoard = new Map()

  currentPlotData.value.forEach(row => {
    if (row.netInflow100m <= amount) return

    const existing = bestByBoard.get(row.boardName)
    if (!existing) {
      bestByBoard.set(row.boardName, {
        ...row,
        selectedTime: row.time,
        selectedLeader: row.leader,
        selectedNetInflow100m: row.netInflow100m
      })
      return
    }

    const isEarlierEntry = row.time < existing.selectedTime
    const isSameTimeHigherEntry = row.time === existing.selectedTime && row.netInflow100m > existing.selectedNetInflow100m
    if (isEarlierEntry || isSameTimeHigherEntry) {
      existing.selectedTime = row.time
      existing.selectedLeader = row.leader
      existing.selectedNetInflow100m = row.netInflow100m
    }

    if (row.netInflow100m > existing.netInflow100m) {
      bestByBoard.set(row.boardName, {
        ...row,
        selectedTime: existing.selectedTime,
        selectedLeader: existing.selectedLeader,
        selectedNetInflow100m: existing.selectedNetInflow100m
      })
    }
  })

  filterResults.value = [...bestByBoard.values()]
      .sort((a, b) => {
        const timeSort = a.selectedTime.localeCompare(b.selectedTime)
        if (timeSort !== 0) return timeSort
        return b.selectedNetInflow100m - a.selectedNetInflow100m
      })
  notifyFilterResults(filterResults.value)
}

const updateFilterAmount = () => {
  filterAmount.value = Math.max(0, Math.floor(Number(filterAmount.value) || 0))
  updateFilterResults()
}

const notifyFilterResults = (results, force = false) => {
  if (!results.length || !isNotificationSupported()) return

  notificationPermission.value = Notification.permission
  if (notificationPermission.value !== 'granted') return

  const { amount } = parseFilterConditions()
  const latestResult = [...results].sort((a, b) => {
    const timeSort = (b.selectedTime || b.time).localeCompare(a.selectedTime || a.time)
    if (timeSort !== 0) return timeSort
    return (b.selectedNetInflow100m || b.netInflow100m) - (a.selectedNetInflow100m || a.netInflow100m)
  })[0]
  const latestTime = latestResult.selectedTime || latestResult.time
  const latestStock = latestResult.selectedLeader || latestResult.leader || '-'
  const notificationKey = `${props.flowType}|${selectedDate.value}|${amount}|${latestTime}|${latestResult.boardName}|${latestStock}`
  if (!force && notificationKey === lastNotificationKey.value) return
  lastNotificationKey.value = notificationKey

  new Notification(`${props.title}最新入选：${latestStock}`, {
    body: `${latestTime} ${latestResult.boardName} ${latestStock} ${formatFundFlowAmount(latestResult.netInflow100m)}亿`,
    tag: notificationKey,
    renotify: true,
  })
}

const fetchDates = async () => {
  const today = getToday()
  selectedDate.value = selectedDate.value || today
  dateOptions.value = [today]

  try {
    const dates = await fetchFundFlowDates(props.flowType)
    dateOptions.value = [...new Set([today, ...dates])].sort((a, b) => b.localeCompare(a))
  } catch (e) {
    console.error('获取日期失败:', e)
  }
}

const fetchData = async () => {
  const requestId = ++fetchRequestId
  if (fetchController) fetchController.abort()
  const controller = new AbortController()
  fetchController = controller
  errorMessage.value = ''
  try {
    const queryDate = selectedDate.value || getToday()
    const data = await fetchFundFlowHistory(props.flowType, queryDate, controller.signal)
    if (requestId !== fetchRequestId) return
    renderChart(data)
  } catch (e) {
    if (e?.name === 'AbortError' || requestId !== fetchRequestId) return
    console.error('获取数据失败:', e)
    if (e.message.includes('Failed to fetch') || e.name === 'TypeError') {
      errorMessage.value = '无法连接到后端服务，请检查后端服务是否已启动，并确认前端代理配置正常'
    } else {
      errorMessage.value = '获取数据失败，请稍后重试'
    }
  } finally {
    if (requestId === fetchRequestId) fetchController = null
  }
}

const retryFetch = async () => {
  errorMessage.value = ''
  await fetchDates()
  await fetchData()
}

const renderChart = (historyData) => {
  const chartDom = chartRef.value
  if (!chartDom) return
  if (!chartInstance) chartInstance = echarts.init(chartDom)
  else chartInstance.clear()

  const plotData = Array.isArray(historyData) ? historyData : []
  currentPlotData.value = plotData
  updateFilterResults()

  if (!plotData.length) {
    chartInstance.setOption({
      backgroundColor: '#0a0f1e',
      title: {
        text: `${formatDate(selectedDate.value)} 暂无资金流向数据`,
        left: 'center',
        top: 'center',
        textStyle: { color: '#94a3b8', fontSize: 16, fontWeight: 500 }
      }
    }, true)
    return
  }

  const timePoints = [...new Set(plotData.map(r => r.time))].sort()
  const latestTime = timePoints[timePoints.length - 1]
  const latestData = plotData.filter(r => r.time === latestTime)

  const selectedData = dedupeRowsByBoard(latestData)
      .sort((a, b) => b.netInflow100m - a.netInflow100m)

  const rowMap = new Map(
      plotData.map(row => [`${row.time}\u0000${row.boardName}`, row])
  )
  const series = selectedData.map((latestRow, i) => {
    const name = latestRow.boardName
    const color = getColorByRank(i, selectedData.length)

    return {
      id: `fund-flow-${i}`,
      name,
      type: 'line',
      color: color,
      // 某分钟未进入 Top 列表时没有原始点，连接前后有效点避免图表出现无意义断线。
      connectNulls: true,
      data: timePoints.map(time => {
        const row = rowMap.get(`${time}\u0000${name}`)
        // 未进入该分钟 Top 列表不代表资金净额为 0，保留为空值避免曲线错误跌至零轴。
        const amount = row ? row.netInflow100m : null
        return {
          value: amount,
          time,
          boardName: name,
          leader: row?.leader || '',
          netInflow100m: amount
        }
      }),
      showSymbol: false,
      smooth: false,
      lineStyle: { width: 3.8, color },
      endLabel: {
        show: true,
        formatter: params => {
          const data = params.data || {}
          return `${data.boardName}: ${formatFundFlowAmount(data.netInflow100m)}亿 ${data.leader || ''}`
        },
        color,
        fontSize: 11,
        fontWeight: 600
      },
      labelLayout: { moveOverlap: 'shiftY' }
    }
  })

  const allValues = plotData.map(r => r.netInflow100m)
  const dataMin = Math.min(...allValues)
  const dataMax = Math.max(...allValues)
  const axisPadding = dataMin === dataMax ? Math.max(Math.abs(dataMin) * 0.1, 0.01) : 0

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2332',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: params => {
        const sortedParams = [...params].sort((a, b) => {
          const va = Number(a.data?.netInflow100m ?? a.value ?? 0)
          const vb = Number(b.data?.netInflow100m ?? b.value ?? 0)
          return vb - va
        })
        let result = (params[0]?.axisValue || '') + '<br/>'
        sortedParams.forEach(item => {
          const data = item.data || {}
          const amount = Number(data.netInflow100m ?? item.value ?? 0)
          result += `<span style="color:${item.color}">${item.seriesName}: ${formatFundFlowAmount(amount)}亿  ${data.leader || ''}</span><br/>`
        })
        return result
      }
    },
    legend: { show: false },
    grid: { left: '0%', right: '9%', bottom: '0%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timePoints,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', rotate: 45 }
    },
    yAxis: {
      type: 'value',
      min: dataMin - axisPadding,
      max: dataMax + axisPadding,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', formatter: value => `${formatFundFlowAmount(value)}亿` },
      splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }
    },
    series
  }

  chartInstance.setOption(option, true)
}

const startFundFlowUpdateStream = () => {
  if (fundFlowStream || typeof EventSource === 'undefined') return
  fundFlowStream = openFundFlowStream(handleFundFlowUpdateEvent)
  fundFlowStream.onerror = () => {
    // EventSource 会自动重连，这里保留连接作为实时刷新通道。
  }
}

const stopFundFlowUpdateStream = () => {
  if (fundFlowStream) fundFlowStream.close()
  fundFlowStream = null
}

const handleFundFlowUpdateEvent = (payload) => {
  if (!payload || payload.type !== 'snapshot') return
  if (payload.flowType !== props.flowType) return

  clearTimeout(streamRefreshTimer)
  streamRefreshTimer = setTimeout(async () => {
    const snapshotDate = payload.tradeDate || getToday()
    if (!dateOptions.value.includes(snapshotDate)) {
      dateOptions.value = [...new Set([snapshotDate, ...dateOptions.value])]
          .sort((a, b) => b.localeCompare(a))
    }
    if (!selectedDate.value || selectedDate.value === payload.tradeDate) {
      selectedDate.value = snapshotDate
      await fetchData()
    }
  }, 80)
}

// 浏览器标签页恢复可见时补一次数据，日常更新由 SSE 事件驱动。
const handleVisibilityChange = () => {
  if (!props.active) return
  if (document.visibilityState === 'visible' && isTradingTime()) {
    fetchData()
  }
}

watch(() => props.active, async (isActive) => {
  if (isActive) {
    await nextTick()
    if (chartInstance) chartInstance.resize()
  }
})

onMounted(() => {
  selectedDate.value = getToday()
  fetchDates()
  fetchData()
  startFundFlowUpdateStream()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  if (chartInstance) chartInstance.dispose()
  stopFundFlowUpdateStream()
  if (streamRefreshTimer) clearTimeout(streamRefreshTimer)
  if (fetchController) fetchController.abort()
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.filter-control {
  display: flex;
  flex: none;
  align-items: center;
  height: 36px;
  overflow: hidden;
  border: 1px solid rgba(51, 65, 85, 0.95);
  border-radius: 8px;
  background: #0f172a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
}

.filter-control:hover {
  border-color: #64748b;
  background: #111827;
}

.filter-control:focus-within {
  border-color: #38bdf8;
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.filter-control-label {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 9px;
  border-right: 1px solid rgba(51, 65, 85, 0.8);
  background: rgba(30, 41, 59, 0.72);
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.filter-control-input {
  height: 100%;
  border: 0;
  background: transparent;
  color: #f8fafc;
  font-size: 13px;
  line-height: 1;
  outline: none;
}

.filter-amount-input {
  width: 54px;
  padding: 0 4px 0 10px;
  font-variant-numeric: tabular-nums;
}

.filter-control-unit {
  padding-right: 10px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.filter-amount-input::-webkit-inner-spin-button,
.filter-amount-input::-webkit-outer-spin-button {
  margin: 0;
  opacity: 0.35;
}

.filter-results-panel {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035), 0 25px 50px -24px rgba(0, 0, 0, 0.65);
}

.copy-stock-button {
  max-width: 118px;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: border-color 0.18s ease, background-color 0.18s ease, color 0.18s ease;
}

.copy-stock-button:hover {
  border-color: rgba(252, 211, 77, 0.55);
  background: rgba(252, 211, 77, 0.18);
  color: #fef3c7;
}

.copy-stock-button:active {
  background: rgba(252, 211, 77, 0.26);
}

.filter-results-list {
  scrollbar-width: thin;
  scrollbar-color: #334155 rgba(15, 23, 42, 0.45);
}

.filter-results-list::-webkit-scrollbar {
  width: 6px;
}

.filter-results-list::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.55);
  border-radius: 999px;
}

.filter-results-list::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 999px;
}

.filter-results-list::-webkit-scrollbar-thumb:hover {
  background: #475569;
}
</style>
