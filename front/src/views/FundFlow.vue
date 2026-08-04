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
              :key="item.板块名称"
              class="rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-slate-100">
            <div class="mb-2 flex items-start justify-between gap-2">
              <span class="min-w-0 flex-1 truncate text-sm font-semibold text-white">{{ item.板块名称 }}</span>
              <span class="font-mono text-sm font-semibold text-red-300">{{ item.资金净流入亿.toFixed(2) }}亿</span>
            </div>
            <div class="flex items-center gap-2">
              <button
                  @click="copyStockName(item)"
                  :title="`复制 ${item.入选龙头 || item.龙头 || '-'}`"
                  class="copy-stock-button rounded-md border border-amber-300/30 bg-amber-300/10 px-1.5 py-0.5 font-semibold text-amber-100">
                {{ copiedStockName === (item.入选龙头 || item.龙头) ? '已复制' : (item.入选龙头 || item.龙头 || '-') }}
              </button>
              <span class="rounded-md border border-sky-300/25 bg-sky-300/10 px-1.5 py-0.5 font-mono font-semibold text-sky-100">{{ item.入选时间 || item.时间 }}</span>
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
          请确保后端服务已启动（端口 8051）
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const FUND_FLOW_API_BASE = '/api/zijin'
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

const getFlow = (item) => {
  if (!item) return 0
  const yi = item['资金净流入(亿)'] ?? item.资金净流入亿 ?? 0
  return yi / 10000
}

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
  const stockName = item.入选龙头 || item.龙头
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

const flattenSparseMatrixHistoryData = (historyData) => {
  if (historyData?.format !== 'matrix-v2') return null

  const rows = []
  const times = Array.isArray(historyData.times) ? historyData.times : []
  const boards = Array.isArray(historyData.boards) ? historyData.boards : []
  boards.forEach(board => {
    const points = Array.isArray(board.points) ? board.points : []
    points.forEach(point => {
      const [timeIndex, rawFlow, leader = ''] = point
      const time = times[timeIndex]
      if (!time) return
      rows.push({
        时间: time,
        板块名称: board.name,
        龙头: leader || '',
        资金净流入亿: Number(rawFlow || 0) / 10000
      })
    })
  })
  return rows
}

const flattenMatrixHistoryData = (historyData) => {
  const sparseRows = flattenSparseMatrixHistoryData(historyData)
  if (sparseRows) return sparseRows
  if (historyData?.format !== 'matrix-v1') return null

  const rows = []
  const times = Array.isArray(historyData.times) ? historyData.times : []
  const boards = Array.isArray(historyData.boards) ? historyData.boards : []
  boards.forEach(board => {
    const values = Array.isArray(board.values) ? board.values : []
    const leaders = Array.isArray(board.leaders) ? board.leaders : []
    times.forEach((time, index) => {
      const rawFlow = values[index]
      if (rawFlow === null || rawFlow === undefined) return
      rows.push({
        时间: time,
        板块名称: board.name,
        龙头: leaders[index] || '',
        资金净流入亿: Number(rawFlow || 0) / 10000
      })
    })
  })
  return rows
}

const flattenHistoryData = (historyData) => {
  const matrixRows = flattenMatrixHistoryData(historyData)
  if (matrixRows) return matrixRows

  const rowMap = new Map()
  if (historyData?.length) {
    historyData.forEach(arr => {
      if (Array.isArray(arr)) {
        arr.forEach(item => {
          if (item?.板块名称 && item.时间) {
            const row = {
              时间: item.时间,
              板块名称: item.板块名称,
              龙头: item.龙头,
              资金净流入亿: getFlow(item)
            }
            rowMap.set(`${row.时间}|${row.板块名称}`, row)
          }
        })
      }
    })
  }
  return [...rowMap.values()]
}

const dedupeRowsByBoard = (rows) => {
  const bestByBoard = new Map()
  rows.forEach(row => {
    const existing = bestByBoard.get(row.板块名称)
    if (!existing || Math.abs(row.资金净流入亿) > Math.abs(existing.资金净流入亿)) {
      bestByBoard.set(row.板块名称, row)
    }
  })
  return [...bestByBoard.values()]
}

const updateFilterResults = () => {
  const { amount } = parseFilterConditions()
  const bestByBoard = new Map()

  currentPlotData.value.forEach(row => {
    if (row.资金净流入亿 <= amount) return

    const existing = bestByBoard.get(row.板块名称)
    if (!existing) {
      bestByBoard.set(row.板块名称, {
        ...row,
        入选时间: row.时间,
        入选龙头: row.龙头,
        入选资金净流入亿: row.资金净流入亿
      })
      return
    }

    const isEarlierEntry = row.时间 < existing.入选时间
    const isSameTimeHigherEntry = row.时间 === existing.入选时间 && row.资金净流入亿 > existing.入选资金净流入亿
    if (isEarlierEntry || isSameTimeHigherEntry) {
      existing.入选时间 = row.时间
      existing.入选龙头 = row.龙头
      existing.入选资金净流入亿 = row.资金净流入亿
    }

    if (row.资金净流入亿 > existing.资金净流入亿) {
      bestByBoard.set(row.板块名称, {
        ...row,
        入选时间: existing.入选时间,
        入选龙头: existing.入选龙头,
        入选资金净流入亿: existing.入选资金净流入亿
      })
    }
  })

  filterResults.value = [...bestByBoard.values()]
      .sort((a, b) => {
        const timeSort = a.入选时间.localeCompare(b.入选时间)
        if (timeSort !== 0) return timeSort
        return b.入选资金净流入亿 - a.入选资金净流入亿
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
    const timeSort = (b.入选时间 || b.时间).localeCompare(a.入选时间 || a.时间)
    if (timeSort !== 0) return timeSort
    return (b.入选资金净流入亿 || b.资金净流入亿) - (a.入选资金净流入亿 || a.资金净流入亿)
  })[0]
  const latestTime = latestResult.入选时间 || latestResult.时间
  const latestStock = latestResult.入选龙头 || latestResult.龙头 || '-'
  const notificationKey = `${props.flowType}|${selectedDate.value}|${amount}|${latestTime}|${latestResult.板块名称}|${latestStock}`
  if (!force && notificationKey === lastNotificationKey.value) return
  lastNotificationKey.value = notificationKey

  new Notification(`${props.title}最新入选：${latestStock}`, {
    body: `${latestTime} ${latestResult.板块名称} ${latestStock} ${latestResult.资金净流入亿.toFixed(2)}亿`,
    tag: notificationKey,
    renotify: true,
  })
}

const fetchDates = async () => {
  const today = getToday()
  selectedDate.value = selectedDate.value || today
  dateOptions.value = [today]

  try {
    const res = await fetch(`${FUND_FLOW_API_BASE}/${props.flowType}/dates`)
    if (!res.ok) throw new Error('获取日期失败')
    const dates = await res.json()
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
    const res = await fetch(
        `${FUND_FLOW_API_BASE}/${props.flowType}/history/${queryDate}`,
        { signal: controller.signal }
    )
    if (!res.ok) throw new Error('获取数据失败')
    const data = await res.json()
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

  const plotData = flattenHistoryData(historyData)
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

  const timePoints = [...new Set(plotData.map(r => r.时间))].sort()
  const latestTime = timePoints[timePoints.length - 1]
  const latestData = plotData.filter(r => r.时间 === latestTime)

  const selectedData = dedupeRowsByBoard(latestData)
      .sort((a, b) => b.资金净流入亿 - a.资金净流入亿)

  const rowMap = new Map(
      plotData.map(row => [`${row.时间}\u0000${row.板块名称}`, row])
  )
  const series = selectedData.map((latestRow, i) => {
    const name = latestRow.板块名称
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
        const amount = row ? row.资金净流入亿 : null
        return {
          value: amount,
          时间: time,
          板块名称: name,
          龙头: row?.龙头 || '',
          资金净流入亿: amount
        }
      }),
      showSymbol: false,
      smooth: false,
      lineStyle: { width: 3.8, color },
      endLabel: {
        show: true,
        formatter: params => {
          const data = params.data || {}
          return `${data.板块名称}: ${Number(data.资金净流入亿 || 0).toFixed(2)}亿 ${data.龙头 || ''}`
        },
        color,
        fontSize: 11,
        fontWeight: 600
      },
      labelLayout: { moveOverlap: 'shiftY' }
    }
  })

  const allValues = plotData.map(r => r.资金净流入亿)
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
          const va = Number(a.data?.资金净流入亿 ?? a.value ?? 0)
          const vb = Number(b.data?.资金净流入亿 ?? b.value ?? 0)
          return vb - va
        })
        let result = (params[0]?.axisValue || '') + '<br/>'
        sortedParams.forEach(item => {
          const data = item.data || {}
          const amount = Number(data.资金净流入亿 ?? item.value ?? 0)
          result += `<span style="color:${item.color}">${item.seriesName}: ${amount.toFixed(2)}亿  ${data.龙头 || ''}</span><br/>`
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
      axisLabel: { color: '#94a3b8', formatter: '{value}亿' },
      splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }
    },
    series
  }

  chartInstance.setOption(option, true)
}

const startFundFlowUpdateStream = () => {
  if (fundFlowStream || typeof EventSource === 'undefined') return
  fundFlowStream = new EventSource(`${FUND_FLOW_API_BASE}/stream`)
  fundFlowStream.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      handleFundFlowUpdateEvent(payload)
    } catch (error) {
      console.warn('资金流向更新事件解析失败', error)
    }
  }
  fundFlowStream.onerror = () => {
    // EventSource 会自动重连，这里保留连接作为实时刷新通道。
  }
}

const stopFundFlowUpdateStream = () => {
  if (fundFlowStream) fundFlowStream.close()
  fundFlowStream = null
}

const handleFundFlowUpdateEvent = (payload) => {
  if (!payload || payload.类型 !== 'snapshot') return
  if (payload.flowType !== props.flowType) return

  clearTimeout(streamRefreshTimer)
  streamRefreshTimer = setTimeout(async () => {
    const snapshotDate = payload.采集日期 || getToday()
    if (!dateOptions.value.includes(snapshotDate)) {
      dateOptions.value = [...new Set([snapshotDate, ...dateOptions.value])]
          .sort((a, b) => b.localeCompare(a))
    }
    if (!selectedDate.value || selectedDate.value === payload.采集日期) {
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
