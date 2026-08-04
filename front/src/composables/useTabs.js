import { ref, shallowRef } from 'vue'
import FundFlow from '../views/FundFlow.vue'
import StrategyPickMonitor from '../views/StrategyPickMonitor.vue'

export const tabs = ref([])
export const activeTab = ref(null)
let nextTabId = 1

export function openTab(title, component, props = {}) {
    const existing = tabs.value.find(t => t.title === title)
    if (existing) {
        activeTab.value = existing
        return
    }
    const newTab = {
        id: nextTabId++,
        title,
        component: shallowRef(component),
        props
    }
    tabs.value.push(newTab)
    activeTab.value = newTab
}

export function closeTab(tab) {
    const index = tabs.value.indexOf(tab)
    if (index === -1) return
    tabs.value.splice(index, 1)
    if (activeTab.value === tab) {
        activeTab.value = tabs.value[index - 1] || tabs.value[0] || null
    }
}

export function switchTab(tab) {
    activeTab.value = tab
}

export function initDefaultTabs() {
    openTab('板块资金流向', FundFlow)
    const industryTab = activeTab.value
    openTab('概念资金流向', FundFlow, { title: '概念资金流向', flowType: 'concept' })
    openTab('策略选股监控', StrategyPickMonitor)
    activeTab.value = industryTab
}
