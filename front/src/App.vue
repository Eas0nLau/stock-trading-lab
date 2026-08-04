<template>
  <div class="min-h-screen flex flex-col ">
    <AppHeader @open-tab="handleOpenTab" />
    <TabBar />
    <div class="flex-1 overflow-hidden">
      <TabContent />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import TabBar from './components/TabBar.vue'
import TabContent from './components/TabContent.vue'
import { initDefaultTabs, openTab } from './composables/useTabs'
import FundFlow from './views/FundFlow.vue'
import Analysis from './views/Analysis.vue'
import StrategyPickMonitor from './views/StrategyPickMonitor.vue'
import IndexCycle from './views/IndexCycle.vue'
import HotBoardEmotion from './views/HotBoardEmotion.vue'

const STRATEGY_PICK_API_BASE = '/api/strategy-pick'
const notifiedStrategyEventIds = new Set()
let strategyNotificationStream = null

initDefaultTabs()

const handleOpenTab = (title, type) => {
  if (type === 'FundFlow') openTab(title, FundFlow)
  if (type === 'ConceptFundFlow') openTab(title, FundFlow, { title: '概念资金流向', flowType: 'concept' })
  if (type === 'Analysis') openTab(title, Analysis)
  if (type === 'StrategyPickMonitor') openTab(title, StrategyPickMonitor)
  if (type === 'IndexCycle') openTab(title, IndexCycle)
  if (type === 'HotBoardEmotion') openTab(title, HotBoardEmotion)
}

onMounted(() => {
  startStrategyNotificationStream()
})

onBeforeUnmount(() => {
  stopStrategyNotificationStream()
})

function startStrategyNotificationStream() {
  if (strategyNotificationStream || typeof EventSource === 'undefined') return

  strategyNotificationStream = new EventSource(`${STRATEGY_PICK_API_BASE}/stream`)
  strategyNotificationStream.onmessage = (event) => {
    try {
      handleStrategyNotificationPayload(JSON.parse(event.data))
    } catch (error) {
      console.warn('策略选股通知事件解析失败', error)
    }
  }
  strategyNotificationStream.onerror = () => {
    // EventSource 会自动重连，不在这里主动发起任何 fetch。
  }
}

function stopStrategyNotificationStream() {
  if (strategyNotificationStream) strategyNotificationStream.close()
  strategyNotificationStream = null
}

function handleStrategyNotificationPayload(payload) {
  if (!payload || payload.类型 !== 'snapshot') return

  const events = Array.isArray(payload.新增股票) ? payload.新增股票 : []
  const newEvents = events
    .filter((event) => !notifiedStrategyEventIds.has(getStrategyEventId(event)))
    .sort((a, b) => compareEventAsc(a, b))

  if (newEvents.length === 0) return

  newEvents.forEach((event) => notifiedStrategyEventIds.add(getStrategyEventId(event)))
  showStrategyBrowserNotification(newEvents)
}

function showStrategyBrowserNotification(events) {
  if (!isNotificationSupported() || Notification.permission !== 'granted') return

  const latest = events[events.length - 1]
  const displayEvents = events.slice(0, 5)
  const lines = displayEvents.map((event) => `${event.入选时间 || ''} ${event.策略名称 || ''} ${event.名称 || '-'} ${event.代码 || ''}`.trim())
  if (events.length > displayEvents.length) lines.push(`共 ${events.length} 只，已显示前 ${displayEvents.length} 只`)

  new Notification(`策略选股新入选：${latest?.名称 || '-'}`, {
    body: lines.join('\n'),
    tag: `strategy-pick-${getStrategyEventId(latest)}`,
    renotify: true,
  })
}

function isNotificationSupported() {
  return typeof Notification !== 'undefined'
}

function getStrategyEventId(event) {
  return event?.event_id || `${event?.入选日期 || ''}-${event?.入选时间 || ''}-${event?.策略ID || ''}-${event?.代码 || ''}`
}

function compareEventAsc(a, b) {
  const left = `${a?.入选时间 || `${a?.入选日期 || ''} ${a?.入选时分秒 || ''}`} ${a?.策略ID || ''} ${a?.代码 || ''}`
  const right = `${b?.入选时间 || `${b?.入选日期 || ''} ${b?.入选时分秒 || ''}`} ${b?.策略ID || ''} ${b?.代码 || ''}`
  return left.localeCompare(right)
}

</script>
