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
import StrategyPickMonitor from './views/StrategyPickMonitor.vue'
import IndexCycle from './views/IndexCycle.vue'
import HotBoardEmotion from './views/HotBoardEmotion.vue'
import { openStrategyPickStream } from './modules/strategy-pick/api.js'

const notifiedStrategyEventIds = new Set()
let strategyNotificationStream = null

initDefaultTabs()

const handleOpenTab = (title, type) => {
  if (type === 'FundFlow') openTab(title, FundFlow)
  if (type === 'ConceptFundFlow') openTab(title, FundFlow, { title: '概念资金流向', flowType: 'concept' })
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

  strategyNotificationStream = openStrategyPickStream(handleStrategyNotificationPayload)
}

function stopStrategyNotificationStream() {
  if (strategyNotificationStream) strategyNotificationStream.close()
  strategyNotificationStream = null
}

function handleStrategyNotificationPayload(payload) {
  if (!payload || payload.type !== 'snapshot') return

  const events = Array.isArray(payload.addedStocks) ? payload.addedStocks : []
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
  const lines = displayEvents.map((event) => `${event.selectedAt || ''} ${event.strategyName || ''} ${event.name || '-'} ${event.code || ''}`.trim())
  if (events.length > displayEvents.length) lines.push(`共 ${events.length} 只，已显示前 ${displayEvents.length} 只`)

  new Notification(`策略选股新入选：${latest?.name || '-'}`, {
    body: lines.join('\n'),
    tag: `strategy-pick-${getStrategyEventId(latest)}`,
    renotify: true,
  })
}

function isNotificationSupported() {
  return typeof Notification !== 'undefined'
}

function getStrategyEventId(event) {
  return event?.eventId || `${event?.selectedDate || ''}-${event?.selectedAt || ''}-${event?.strategyId || ''}-${event?.code || ''}`
}

function compareEventAsc(a, b) {
  const left = `${a?.selectedAt || `${a?.selectedDate || ''} ${a?.selectedClock || ''}`} ${a?.strategyId || ''} ${a?.code || ''}`
  const right = `${b?.selectedAt || `${b?.selectedDate || ''} ${b?.selectedClock || ''}`} ${b?.strategyId || ''} ${b?.code || ''}`
  return left.localeCompare(right)
}

</script>
