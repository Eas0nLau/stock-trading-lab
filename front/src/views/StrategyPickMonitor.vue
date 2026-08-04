<template>
  <div class="h-full overflow-hidden bg-[#0f172a] text-slate-100">
    <div class="mx-auto flex h-full min-h-0 max-w-[1900px] flex-col gap-4 px-6 py-5">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h1 class="text-xl font-semibold text-white">策略选股监控</h1>
          <div class="mt-1 text-xs text-slate-400">{{ activeStrategy?.名称 || '未选择策略' }}</div>
        </div>

        <div class="flex flex-wrap items-center gap-3 text-sm">
          <label class="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
            <span class="text-slate-400">日期</span>
            <select v-model="selectedDate" class="bg-transparent text-slate-100 outline-none" @change="fetchDateData">
              <option v-for="date in availableDates" :key="date" :value="date" class="bg-slate-900">
                {{ formatDate(date) }}
              </option>
            </select>
          </label>

          <button
            class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="notificationPermission === 'granted' || notificationPermission === 'unsupported'"
            :title="notificationButtonTitle()"
            @click="requestNotificationPermission"
          >
            {{ notificationButtonText() }}
          </button>

          <div class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-300">
            最新采集：{{ latestCollectTime }}
          </div>

          <button
            class="rounded-lg bg-cyan-500 px-4 py-2 font-medium text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            :disabled="loading || !selectedStrategyId"
            @click="refreshNow"
          >
            {{ loading ? '刷新中' : '刷新当前策略' }}
          </button>
        </div>
      </div>

      <div v-if="errorMessage" class="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
        {{ errorMessage }}
      </div>

      <div class="strategy-layout-grid grid min-h-0 flex-1 overflow-hidden grid-cols-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside class="flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
          <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
            <h2 class="text-sm font-semibold text-white">策略管理</h2>
            <button class="rounded bg-slate-800 px-3 py-1.5 text-xs text-cyan-200 hover:bg-slate-700" @click="startCreateStrategy">
              新增
            </button>
          </div>

          <div class="strategy-scrollbar min-h-0 flex-1 overflow-auto px-3 py-3">
            <div v-if="strategies.length === 0" class="rounded-lg border border-dashed border-slate-700 py-8 text-center text-sm text-slate-500">
              暂无策略
            </div>
            <div v-else class="space-y-2">
              <div v-for="strategy in strategies" :key="strategy.id" class="space-y-2">
                <div
                  class="w-full cursor-pointer rounded-lg border px-3 py-3 text-left transition"
                  :class="strategy.id === selectedStrategyId ? 'border-cyan-400/50 bg-cyan-500/10' : 'border-slate-800 bg-slate-950 hover:border-slate-700'"
                  role="button"
                  tabindex="0"
                  @click="selectStrategy(strategy.id)"
                  @keydown.enter.prevent="selectStrategy(strategy.id)"
                  @keydown.space.prevent="selectStrategy(strategy.id)"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <div class="truncate text-sm font-semibold text-white">{{ strategy.名称 }}</div>
                      <div class="mt-1 truncate text-xs text-slate-500">{{ strategy.id }}</div>
                    </div>
                    <span class="shrink-0 rounded px-2 py-1 text-[11px]" :class="strategy.启用 ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-700 text-slate-300'">
                      {{ strategy.启用 ? '启用' : '停用' }}
                    </span>
                  </div>
                  <div class="mt-2 line-clamp-2 text-xs text-slate-400">{{ strategy.页面URL }}</div>
                  <div class="mt-2 flex flex-wrap gap-1.5 text-[11px] text-slate-300">
                    <span class="rounded border border-slate-700 px-2 py-1">{{ formatMonitorPeriods(strategy.监控时间段) }}</span>
                    <span class="rounded border border-slate-700 px-2 py-1">{{ formatInterval(strategy.监控频率秒) }}</span>
                  </div>
                  <div class="mt-3 flex gap-2">
                    <button
                      type="button"
                      class="rounded-md border border-cyan-400/50 bg-cyan-500/15 px-2.5 py-1.5 text-[11px] font-semibold text-cyan-100 shadow-sm shadow-cyan-950/40 transition hover:bg-cyan-500/25"
                      @click.stop="editStrategy(strategy)"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      class="rounded-md border px-2.5 py-1.5 text-[11px] font-semibold shadow-sm transition"
                      :class="strategy.启用 ? 'border-red-400/50 bg-red-500/15 text-red-100 shadow-red-950/40 hover:bg-red-500/25' : 'border-emerald-400/50 bg-emerald-500/15 text-emerald-100 shadow-emerald-950/40 hover:bg-emerald-500/25'"
                      @click.stop="toggleStrategy(strategy)"
                    >
                      {{ strategy.启用 ? '停用' : '启用' }}
                    </button>
                  </div>
                </div>

                <div v-if="editing && editingMode === 'edit' && editingStrategyId === strategy.id" class="strategy-scrollbar strategy-manage-form overflow-auto rounded-lg border border-cyan-400/40 bg-slate-950/95 p-4 shadow-lg shadow-cyan-950/25">
                  <div class="mb-3 text-sm font-semibold text-cyan-100">编辑策略</div>
                  <div class="space-y-3 text-sm">
                    <label class="block">
                      <span class="mb-1 block text-xs text-slate-400">名称</span>
                      <input v-model="strategyForm.名称" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
                    </label>
                    <label class="block">
                      <span class="mb-1 block text-xs text-slate-400">页面 URL</span>
                      <input v-model="strategyForm.页面URL" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
                    </label>
                    <label class="block">
                      <span class="mb-1 block text-xs text-slate-400">监听接口</span>
                      <textarea v-model="strategyForm.监听目标Text" rows="3" class="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
                    </label>
                    <label class="block">
                      <span class="mb-1 block text-xs text-slate-400">监控时间段</span>
                      <input v-model="strategyForm.监控时间段Text" placeholder="09:28~11:31, 13:00~15:01" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
                    </label>
                    <label class="block">
                      <span class="mb-1 block text-xs text-slate-400">监控频率（秒）</span>
                      <input v-model.number="strategyForm.监控频率秒" type="number" min="1" step="1" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
                    </label>
                    <label class="flex items-center gap-2 text-xs text-slate-300">
                      <input v-model="strategyForm.启用" type="checkbox" class="h-4 w-4 accent-cyan-400" />
                      启用监听
                    </label>
                    <div class="flex gap-2">
                      <button class="rounded-lg bg-cyan-500 px-3 py-2 text-xs font-medium text-slate-950 hover:bg-cyan-400" @click="saveStrategy">
                        保存
                      </button>
                      <button class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800" @click="cancelEdit">
                        取消
                      </button>
                      <button v-if="strategies.length > 1" class="ml-auto rounded-lg border border-red-500/40 px-3 py-2 text-xs text-red-300 hover:bg-red-500/10" @click="deleteStrategy">
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="editing && editingMode === 'create'" class="strategy-scrollbar strategy-manage-form shrink-0 overflow-auto border-t border-slate-800 p-4">
            <div class="mb-3 text-sm font-semibold text-white">新增策略</div>
            <div class="space-y-3 text-sm">
              <label class="block">
                <span class="mb-1 block text-xs text-slate-400">名称</span>
                <input v-model="strategyForm.名称" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-slate-400">页面 URL</span>
                <input v-model="strategyForm.页面URL" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-slate-400">监听接口</span>
                <textarea v-model="strategyForm.监听目标Text" rows="3" class="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-slate-400">监控时间段</span>
                <input v-model="strategyForm.监控时间段Text" placeholder="09:28~11:31, 13:00~15:01" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-slate-400">监控频率（秒）</span>
                <input v-model.number="strategyForm.监控频率秒" type="number" min="1" step="1" class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
              </label>
              <label class="flex items-center gap-2 text-xs text-slate-300">
                <input v-model="strategyForm.启用" type="checkbox" class="h-4 w-4 accent-cyan-400" />
                启用监听
              </label>
              <div class="flex gap-2">
                <button class="rounded-lg bg-cyan-500 px-3 py-2 text-xs font-medium text-slate-950 hover:bg-cyan-400" @click="saveStrategy">
                  保存
                </button>
                <button class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800" @click="cancelEdit">
                  取消
                </button>
              </div>
            </div>
          </div>
        </aside>

        <main class="flex min-h-0 flex-col gap-4 overflow-hidden">
          <div class="grid shrink-0 grid-cols-1 gap-3 md:grid-cols-4">
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div class="text-xs text-slate-400">当前入选</div>
              <div class="mt-2 text-2xl font-semibold text-white">{{ currentStockCount }}</div>
            </div>
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div class="text-xs text-slate-400">今日新增</div>
              <div class="mt-2 text-2xl font-semibold text-emerald-300">{{ eventCount }}</div>
            </div>
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div class="text-xs text-slate-400">最近入选</div>
              <div class="mt-2 text-lg font-semibold text-white">{{ latestEventTime }}</div>
            </div>
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div class="text-xs text-slate-400">采集状态</div>
              <div class="mt-2 text-lg font-semibold" :class="latestStatusClass">{{ latestStatusText }}</div>
            </div>
          </div>

          <div class="strategy-result-grid grid min-h-0 flex-1 overflow-hidden grid-cols-1 gap-4 2xl:grid-cols-[420px_minmax(0,1fr)]">
            <section class="strategy-result-panel flex min-h-0 w-full flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
              <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
                <h2 class="text-sm font-semibold text-white">入选事件</h2>
                <span class="text-xs text-slate-400">{{ sortedEvents.length }} 条</span>
              </div>
              <div class="strategy-scrollbar min-h-0 flex-1 overflow-auto px-3 py-3">
                <div v-if="sortedEvents.length === 0" class="rounded-lg border border-dashed border-slate-700 py-10 text-center text-sm text-slate-500">
                  暂无入选事件
                </div>
                <div v-else class="space-y-2">
                  <div v-for="event in sortedEvents" :key="event.event_id" class="rounded-lg border border-slate-800 bg-slate-950 px-3 py-3">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex flex-wrap items-center gap-2">
                        <button class="max-w-[170px] truncate text-left text-base font-semibold text-cyan-200 hover:text-cyan-100" :title="`点击复制 ${event.名称}`" @click="copyStockName(event.名称, event.event_id)">
                          {{ event.名称 || '-' }}
                        </button>
                        <span v-if="getShenwanIndustryValue(event.字段)" class="max-w-[190px] truncate rounded border border-red-400/40 bg-red-500/15 px-2 py-1 text-[11px] font-semibold text-red-200" :title="getShenwanIndustryValue(event.字段)">
                          {{ getShenwanIndustryValue(event.字段) }}
                        </span>
                      </div>
                      <span class="shrink-0 rounded border border-red-400/40 bg-red-500/15 px-2 py-1 text-xs font-semibold text-red-200">{{ formatEventClock(event) }}</span>
                    </div>
                    <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                      <span>{{ event.代码 }}</span>
                      <span>{{ event.市场 }}</span>
                      <span>{{ event.策略名称 }}</span>
                      <span v-if="copiedId === event.event_id" class="text-emerald-300">已复制</span>
                    </div>
                    <div v-if="formatEventFieldPairs(event.字段).length" class="mt-2 flex flex-wrap gap-1.5">
                      <span v-for="pair in formatEventFieldPairs(event.字段)" :key="pair.key" class="rounded border px-2 py-1 text-[11px]" :class="fieldPairClass(pair)" :title="formatFieldValue(pair)">
                        {{ pair.label }} {{ formatFieldValue(pair) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section class="strategy-result-panel flex min-h-0 w-full flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
              <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
                <h2 class="text-sm font-semibold text-white">当前策略入选股票</h2>
                <span class="text-xs text-slate-400">{{ currentStocks.length }} 只</span>
              </div>
              <div class="strategy-scrollbar min-h-0 flex-1 overflow-auto">
                <table class="w-full min-w-[1220px] text-left text-sm">
                  <thead class="sticky top-0 bg-slate-900 text-xs text-slate-400">
                    <tr class="border-b border-slate-800">
                      <th class="px-4 py-3 font-medium">股票名称</th>
                      <th class="px-4 py-3 font-medium">代码</th>
                      <th class="px-4 py-3 font-medium text-red-300">涨跌幅</th>
                      <th class="px-4 py-3 font-medium text-red-300">主力净额</th>
                      <th class="px-4 py-3 font-medium text-red-300">自由市值</th>
                      <th class="px-4 py-3 font-medium text-red-300">入选时间</th>
                      <th class="px-4 py-3 font-medium">最新采集</th>
                      <th class="px-4 py-3 font-medium">概念</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="currentStocks.length === 0">
                      <td colspan="8" class="px-4 py-12 text-center text-slate-500">暂无当前入选股票</td>
                    </tr>
                    <tr v-for="stock in currentStocks" :key="stock.代码" class="border-b border-slate-800/70 hover:bg-slate-800/40">
                      <td class="px-4 py-3">
                        <button class="max-w-[220px] truncate text-left text-base font-semibold text-white hover:text-cyan-200" :title="`点击复制 ${stock.名称}`" @click="copyStockName(stock.名称, stock.代码)">
                          {{ stock.名称 || '-' }}
                        </button>
                      </td>
                      <td class="px-4 py-3 font-mono text-slate-300">{{ stock.代码 }}</td>
                      <td class="px-4 py-3 font-semibold text-red-300">{{ getChangePercentValue(stock.字段) }}</td>
                      <td class="px-4 py-3 font-semibold text-red-300">{{ getMainNetAmountValue(stock.字段) }}</td>
                      <td class="px-4 py-3 font-semibold text-red-300">{{ getFreeMarketValue(stock.字段) }}</td>
                      <td class="px-4 py-3 font-semibold text-red-300">{{ formatStockSelectClock(stock) }}</td>
                      <td class="px-4 py-3 text-slate-300">{{ formatCollectClock(stock.最新采集时间 || latestCollectTime) }}</td>
                      <td class="px-4 py-3 text-slate-300">
                        <span class="block max-w-[320px] truncate" :title="getConceptValue(stock.字段)">{{ getConceptValue(stock.字段) }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <section class="shrink-0 rounded-lg border border-slate-800 bg-slate-900">
            <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
              <h2 class="text-sm font-semibold text-white">历史快照记录</h2>
              <span class="text-xs text-slate-400">{{ sortedHistory.length }} 次</span>
            </div>
            <div class="strategy-scrollbar max-h-60 overflow-auto">
              <table class="w-full min-w-[720px] text-left text-sm">
                <thead class="sticky top-0 bg-slate-900 text-xs text-slate-400">
                  <tr class="border-b border-slate-800">
                    <th class="px-4 py-3 font-medium">采集时间</th>
                    <th class="px-4 py-3 font-medium">名单数量</th>
                    <th class="px-4 py-3 font-medium">新增</th>
                    <th class="px-4 py-3 font-medium">移除</th>
                    <th class="px-4 py-3 font-medium">状态</th>
                    <th class="px-4 py-3 font-medium">错误信息</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="sortedHistory.length === 0">
                    <td colspan="6" class="px-4 py-8 text-center text-slate-500">暂无历史快照</td>
                  </tr>
                  <tr v-for="snapshot in sortedHistory" :key="`${snapshot.策略ID}-${snapshot.采集日期}-${snapshot.采集时间}-${snapshot.状态}`" class="border-b border-slate-800/70">
                    <td class="px-4 py-3 text-slate-300">{{ snapshot.采集时间 || '-' }}</td>
                    <td class="px-4 py-3 text-slate-300">{{ snapshot.股票列表?.length || 0 }}</td>
                    <td class="px-4 py-3 text-emerald-300">{{ snapshot.新增股票?.length || 0 }}</td>
                    <td class="px-4 py-3 text-amber-300">{{ snapshot.移除股票?.length || 0 }}</td>
                    <td class="px-4 py-3" :class="snapshot.状态 === 'success' ? 'text-emerald-300' : 'text-red-300'">{{ snapshot.状态 || '-' }}</td>
                    <td class="px-4 py-3 text-slate-400">{{ snapshot.错误信息 || '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  active: {
    type: Boolean,
    default: true,
  },
})

const API_BASE = '/api/strategy-pick'
const selectedDate = ref(getTodayKey())
const selectedStrategyId = ref('')
const strategies = ref([])
const dates = ref([])
const latestSnapshot = ref({})
const events = ref([])
const historySnapshots = ref([])
const loading = ref(false)
const errorMessage = ref('')
const copiedId = ref('')
const notificationPermission = ref(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)
const editing = ref(false)
const editingMode = ref('create')
const editingStrategyId = ref('')
const strategyForm = ref(createEmptyStrategyForm())
let copiedTimer = null
let strategyStream = null
let streamRefreshTimer = null

const activeStrategy = computed(() => strategies.value.find((item) => item.id === selectedStrategyId.value))

const availableDates = computed(() => {
  const set = new Set([selectedDate.value || getTodayKey(), ...dates.value])
  return [...set].filter(Boolean).sort((a, b) => b.localeCompare(a))
})

const currentStocks = computed(() => latestSnapshot.value?.股票列表 || [])
const currentStockCount = computed(() => currentStocks.value.length)
const eventCount = computed(() => events.value.length)

const sortedEvents = computed(() => [...events.value].sort((a, b) => compareDateTimeDesc(a.入选日期, a.入选时间, b.入选日期, b.入选时间)))
const sortedHistory = computed(() => [...historySnapshots.value].sort((a, b) => compareDateTimeDesc(a.采集日期, a.采集时间, b.采集日期, b.采集时间)))

const latestEventTime = computed(() => {
  const event = sortedEvents.value[0]
  return event ? formatEventClock(event) : '-'
})

const latestCollectTime = computed(() => {
  if (!latestSnapshot.value?.采集日期 || !latestSnapshot.value?.采集时间) return '-'
  return `${formatDate(latestSnapshot.value.采集日期)} ${latestSnapshot.value.采集时间}`
})

const latestStatusText = computed(() => latestSnapshot.value?.状态 || '-')
const latestStatusClass = computed(() => latestSnapshot.value?.状态 === 'success' ? 'text-emerald-300' : 'text-red-300')

onMounted(async () => {
  await fetchStrategies()
  startStrategyUpdateStream()
})

onBeforeUnmount(() => {
  stopStrategyUpdateStream()
  clearTimeout(copiedTimer)
  clearTimeout(streamRefreshTimer)
})


watch(selectedStrategyId, async () => {
  selectedDate.value = getTodayKey()
  latestSnapshot.value = {}
  events.value = []
  historySnapshots.value = []
  dates.value = []
  if (selectedStrategyId.value) await fetchAll()
})

async function fetchAll() {
  if (!selectedStrategyId.value) return
  await Promise.all([fetchDates(), fetchLatest(), fetchDateData()])
}

async function fetchStrategies() {
  try {
    const data = await requestJson(`${API_BASE}/strategies`)
    strategies.value = Array.isArray(data) ? data : []
    if (!selectedStrategyId.value && strategies.value.length) selectedStrategyId.value = strategies.value[0].id
    if (selectedStrategyId.value && !strategies.value.some((item) => item.id === selectedStrategyId.value)) {
      selectedStrategyId.value = strategies.value[0]?.id || ''
    }
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function fetchDates() {
  try {
    const data = await requestJson(`${API_BASE}/strategies/${selectedStrategyId.value}/dates`)
    dates.value = Array.isArray(data) ? data : []
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function fetchLatest() {
  try {
    latestSnapshot.value = await requestJson(`${API_BASE}/strategies/${selectedStrategyId.value}/latest`)
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function fetchDateData() {
  if (!selectedDate.value) selectedDate.value = getTodayKey()
  try {
    const [eventData, historyData] = await Promise.all([
      requestJson(`${API_BASE}/strategies/${selectedStrategyId.value}/events/${selectedDate.value}`),
      requestJson(`${API_BASE}/strategies/${selectedStrategyId.value}/history/${selectedDate.value}`),
    ])
    events.value = Array.isArray(eventData) ? eventData : []
    historySnapshots.value = Array.isArray(historyData) ? historyData : []
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function refreshNow() {
  loading.value = true
  errorMessage.value = ''
  try {
    latestSnapshot.value = await requestJson(`${API_BASE}/strategies/${selectedStrategyId.value}/refresh`, { method: 'POST' })
    selectedDate.value = latestSnapshot.value?.采集日期 || selectedDate.value || getTodayKey()
    await fetchAll()
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}


function startStrategyUpdateStream() {
  if (strategyStream || typeof EventSource === 'undefined') return
  strategyStream = new EventSource(`${API_BASE}/stream`)
  strategyStream.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      handleStrategyUpdateEvent(payload)
    } catch (error) {
      console.warn('策略选股更新事件解析失败', error)
    }
  }
  strategyStream.onerror = () => {
    // EventSource 会自动重连，这里不主动关闭。
  }
}

function stopStrategyUpdateStream() {
  if (strategyStream) strategyStream.close()
  strategyStream = null
}

function handleStrategyUpdateEvent(payload) {
  if (!payload || payload.类型 !== 'snapshot') return
  if (payload.策略ID && selectedStrategyId.value && payload.策略ID !== selectedStrategyId.value) return

  clearTimeout(streamRefreshTimer)
  streamRefreshTimer = setTimeout(async () => {
    if (!selectedStrategyId.value) return
    await Promise.all([fetchDates(), fetchLatest()])
    if (!selectedDate.value || selectedDate.value === payload.采集日期) {
      selectedDate.value = payload.采集日期 || selectedDate.value || getTodayKey()
      await fetchDateData()
    }
  }, 80)
}

function selectStrategy(strategyId) {
  selectedStrategyId.value = strategyId
}

function startCreateStrategy() {
  editing.value = true
  editingMode.value = 'create'
  editingStrategyId.value = ''
  strategyForm.value = createEmptyStrategyForm()
}

function editStrategy(strategy) {
  editing.value = true
  editingMode.value = 'edit'
  editingStrategyId.value = strategy.id
  strategyForm.value = {
    名称: strategy.名称 || '',
    页面URL: strategy.页面URL || '',
    监听目标Text: Array.isArray(strategy.监听目标) ? strategy.监听目标.join('\n') : String(strategy.监听目标 || ''),
    监控时间段Text: formatMonitorPeriods(strategy.监控时间段),
    监控频率秒: strategy.监控频率秒 || 60,
    启用: strategy.启用 !== false,
  }
}

function cancelEdit() {
  editing.value = false
  editingStrategyId.value = ''
  strategyForm.value = createEmptyStrategyForm()
}

async function saveStrategy() {
  const payload = buildStrategyPayload()
  try {
    let saved
    if (editingMode.value === 'edit') {
      saved = await requestJson(`${API_BASE}/strategies/${editingStrategyId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    } else {
      saved = await requestJson(`${API_BASE}/strategies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    }
    cancelEdit()
    await fetchStrategies()
    if (saved?.id) selectedStrategyId.value = saved.id
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function deleteStrategy() {
  if (!editingStrategyId.value) return
  try {
    await requestJson(`${API_BASE}/strategies/${editingStrategyId.value}`, { method: 'DELETE' })
    cancelEdit()
    await fetchStrategies()
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function toggleStrategy(strategy) {
  try {
    await requestJson(`${API_BASE}/strategies/${strategy.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...strategy, 启用: !strategy.启用 }),
    })
    await fetchStrategies()
  } catch (error) {
    errorMessage.value = error.message
  }
}

function buildStrategyPayload() {
  return {
    名称: strategyForm.value.名称.trim(),
    页面URL: strategyForm.value.页面URL.trim(),
    监听目标: strategyForm.value.监听目标Text.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean),
    监控时间段: parseMonitorPeriods(strategyForm.value.监控时间段Text),
    监控频率秒: Number(strategyForm.value.监控频率秒) || 60,
    启用: strategyForm.value.启用,
  }
}

function createEmptyStrategyForm() {
  return {
    名称: '',
    页面URL: '',
    监听目标Text: '/api/smart-tag/stock/v3/pw/search-code',
    监控时间段Text: '09:28~11:31, 13:00~15:01',
    监控频率秒: 60,
    启用: true,
  }
}

function isNotificationSupported() {
  return typeof Notification !== 'undefined'
}

function notificationButtonText() {
  if (notificationPermission.value === 'granted') return '通知已开'
  if (notificationPermission.value === 'denied') return '通知被拒'
  if (notificationPermission.value === 'unsupported') return '不支持通知'
  return '开启通知'
}

function notificationButtonTitle() {
  if (notificationPermission.value === 'denied') return '请在浏览器设置中允许此站点通知'
  if (notificationPermission.value === 'unsupported') return '当前浏览器不支持 Notification API'
  if (notificationPermission.value === 'granted') return '策略入选后会触发浏览器通知'
  return '点击后允许浏览器通知'
}

async function requestNotificationPermission() {
  if (!isNotificationSupported()) {
    notificationPermission.value = 'unsupported'
    return
  }
  notificationPermission.value = await Notification.requestPermission()
}

function formatMonitorPeriods(periods) {
  if (!Array.isArray(periods) || !periods.length) return '09:28~11:31, 13:00~15:01'
  return periods.map((item) => Array.isArray(item) ? `${item[0]}~${item[1]}` : String(item)).join(', ')
}

function parseMonitorPeriods(value) {
  return String(value || '')
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => item.split('~').map((part) => part.trim()))
    .filter((item) => item.length === 2 && item[0] && item[1])
}

function formatInterval(seconds) {
  const value = Number(seconds) || 60
  if (value % 60 === 0) return `${value / 60}分钟`
  return `${value}秒`
}

function formatEventTime(event) {
  if (!event) return '-'
  return formatFullDateTime(event.入选日期, event.入选时间, event.入选时分秒)
}

function formatEventClock(event) {
  return formatTimeOnly(formatEventTime(event))
}

function formatStockSelectTime(stock) {
  if (!stock) return '-'
  return formatFullDateTime(stock.入选日期, stock.入选时间, stock.入选时分秒)
}

function formatStockSelectClock(stock) {
  return formatTimeOnly(formatStockSelectTime(stock))
}

function formatCollectClock(value) {
  return formatTimeOnly(value)
}

function formatTimeOnly(value) {
  const text = String(value || '').trim()
  if (!text || text === '-') return '-'
  const match = text.match(/(\d{2}:\d{2}:\d{2})$/)
  return match ? match[1] : text
}

function formatFullDateTime(date, time, timeOfDay = '') {
  const value = String(time || timeOfDay || '').trim()
  if (!value) return '-'
  if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$/.test(value)) return value
  if (/^\d{8}\s+\d{2}:\d{2}:\d{2}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)} ${value.slice(9)}`
  }
  if (/^\d{2}:\d{2}:\d{2}$/.test(value)) {
    const dateText = formatDate(String(date || ''))
    return dateText && dateText !== '-' ? `${dateText} ${value}` : value
  }
  return value
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      message = body?.detail || message
    } catch (_) {}
    throw new Error(message)
  }
  return response.json()
}

function getTodayKey() {
  const now = new Date()
  const year = now.getFullYear()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${year}${month}${day}`
}

function formatDate(date) {
  if (!date || date.length !== 8) return date || '-'
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
}

function compareDateTimeDesc(dateA, timeA, dateB, timeB) {
  const left = normalizeDateTime(dateA, timeA)
  const right = normalizeDateTime(dateB, timeB)
  return right.localeCompare(left)
}

function normalizeDateTime(date, time) {
  if (!time) return `${date || ''}`
  if (/^\d{4}-\d{2}-\d{2}/.test(time)) return time
  return `${formatDate(date)} ${time}`
}

function formatEventFieldPairs(fields) {
  return pickCoreFieldPairs(fields)
}

function formatStockFieldPairs(fields) {
  return pickCoreFieldPairs(fields)
}

function pickCoreFieldPairs(fields) {
  return buildFieldPairs(fields)
    .filter((pair) => isCoreField(pair.key))
    .sort((a, b) => coreFieldOrder(a.key) - coreFieldOrder(b.key))
}

function isCoreField(key) {
  return isChangePercentField(key) || isMainNetAmountField(key) || isFreeMarketValueField(key) || isConceptField(key)
}

function coreFieldOrder(key) {
  if (isChangePercentField(key)) return 1
  if (isMainNetAmountField(key)) return 2
  if (isFreeMarketValueField(key)) return 3
  if (isConceptField(key)) return 4
  return 99
}
function buildFieldPairs(fields) {
  if (!fields || typeof fields !== 'object') return []
  return Object.entries(fields)
    .filter(([key, value]) => value !== null && value !== undefined && value !== '' && !['代码', '名称', '股票代码', '股票名称', '证券代码', '证券简称'].includes(String(key).trim()))
    .map(([key, value]) => ({ key, label: String(key).trim(), value }))
}

function formatFieldValue(pair) {
  if (!pair) return ''
  if (isChangePercentField(pair.key)) return formatPercentValue(pair.value)
  if (isConceptField(pair.key)) return formatConceptValue(pair.value)
  return pair.value
}

function formatPercentValue(value) {
  const text = String(value ?? '').trim()
  if (!text || text === '-') return '-'
  return text.includes('%') ? text : `${text}%`
}

function formatConceptValue(value) {
  const concepts = parseConceptValue(value)
  return concepts.length ? concepts.join('、') : '-'
}

function parseConceptValue(value) {
  const text = String(value || '').trim()
  if (!text) return []

  const bracketMatches = [...text.matchAll(/【([^】]+)】/g)].map((match) => match[1])
  const rawItems = bracketMatches.length
    ? bracketMatches
    : text.split(/[、,，;；\s]+/)

  return [...new Set(rawItems.map((item) => item.trim()).filter(Boolean))]
}

function prioritizeFieldPairs(pairs) {
  const highlighted = []
  const normal = []
  pairs.forEach((pair) => {
    if (isHighlightedField(pair.key)) highlighted.push(pair)
    else normal.push(pair)
  })
  return [...highlighted, ...normal]
}

function ensureAlwaysVisibleFields(pairs, limit) {
  const selected = pairs.slice(0, limit)
  const selectedKeys = new Set(selected.map((pair) => normalizeFieldKey(pair.key)))
  pairs.forEach((pair) => {
    const key = normalizeFieldKey(pair.key)
    if (isAlwaysVisibleField(pair.key) && !selectedKeys.has(key)) {
      selected.push(pair)
      selectedKeys.add(key)
    }
  })
  return selected
}

function getShenwanIndustryValue(fields) {
  const pair = buildFieldPairs(fields).find((item) => isShenwanIndustryField(item.key))
  return pair?.value || ''
}

function getMainNetAmountValue(fields) {
  return getMatchedFieldValue(fields, isMainNetAmountField)
}

function getFreeMarketValue(fields) {
  return getMatchedFieldValue(fields, isFreeMarketValueField)
}

function getChangePercentValue(fields) {
  return getMatchedFieldValue(fields, isChangePercentField)
}

function getConceptValue(fields) {
  return getMatchedFieldValue(fields, isConceptField)
}

function getMatchedFieldValue(fields, matcher) {
  const pair = buildFieldPairs(fields).find((item) => matcher(item.key))
  return pair ? formatFieldValue(pair) : '-'
}

function fieldPairClass(pair) {
  const base = isConceptField(pair?.key) ? 'inline-block max-w-[260px] truncate align-middle ' : ''
  if (isHighlightedField(pair?.key)) {
    return `${base}border-red-300/30 bg-red-400/10 font-semibold text-red-100 shadow-sm shadow-red-950/20`
  }
  return `${base}border-slate-600/70 bg-slate-800/60 text-slate-200`
}

function isAlwaysVisibleField(key) {
  return isShenwanIndustryField(key) || isConceptField(key)
}

function isShenwanIndustryField(key) {
  const text = normalizeFieldKey(key)
  return text.includes('申万行业分类') || (text.includes('申万') && text.includes('行业'))
}

function isConceptField(key) {
  const text = normalizeFieldKey(key)
  return text.includes('概念') || text.includes('CONCEPT')
}
function isChangePercentField(key) {
  return normalizeFieldKey(key).includes('涨跌幅')
}

function isLatestPriceField(key) {
  const text = normalizeFieldKey(key)
  return text.includes('最新价') || text.includes('现价') || text.includes('当前价') || text === 'PRICE' || text === 'LATESTPRICE'
}

function isHighlightedField(key) {
  const text = normalizeFieldKey(key)
  return isChangePercentField(text)
    || isMainNetAmountField(text)
    || isFreeMarketValueField(text)
}

function isMainNetAmountField(key) {
  const text = normalizeFieldKey(key)
  return text.includes('主力净额') || text.includes('主力净流入') || (text.includes('MAIN') && text.includes('NET'))
}

function isFreeMarketValueField(key) {
  const text = normalizeFieldKey(key)
  return text.includes('自由流通市值')
    || text.includes('自由市值')
    || (text.includes('FREE') && (text.includes('MV') || text.includes('MARKET') || text.includes('VALUE')))
}
function normalizeFieldKey(key) {
  return String(key || '').replace(/\s+/g, '').toUpperCase()
}

async function copyStockName(name, id) {
  if (!name) return
  try {
    await navigator.clipboard.writeText(name)
    copiedId.value = id
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      copiedId.value = ''
    }, 1600)
  } catch (error) {
    errorMessage.value = `复制失败：${error.message}`
  }
}
</script>
<style scoped>
.strategy-layout-grid {
  grid-template-rows: minmax(260px, 0.42fr) minmax(0, 1fr);
}

.strategy-result-grid {
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.strategy-result-panel {
  height: 100%;
  max-height: clamp(420px, calc(100vh - 320px), 860px);
}

.strategy-scrollbar {
  scrollbar-color: rgba(34, 211, 238, 0.55) rgba(15, 23, 42, 0.72);
  scrollbar-width: thin;
}

.strategy-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.strategy-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.72);
  border-radius: 999px;
}

.strategy-scrollbar::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(34, 211, 238, 0.68), rgba(20, 184, 166, 0.68));
  border: 2px solid rgba(15, 23, 42, 0.88);
  border-radius: 999px;
}

.strategy-scrollbar::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(103, 232, 249, 0.9), rgba(45, 212, 191, 0.9));
}

.strategy-scrollbar::-webkit-scrollbar-corner {
  background: transparent;
}

.strategy-manage-form {
  max-height: min(46vh, 430px);
}

@media (min-width: 1280px) {
  .strategy-layout-grid {
    grid-template-rows: minmax(0, 1fr);
  }
}

@media (min-width: 1536px) {
  .strategy-result-grid {
    grid-template-rows: minmax(0, 1fr);
  }
}
</style>
