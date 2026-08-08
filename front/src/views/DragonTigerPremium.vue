<template>
  <div class="min-h-full rounded-2xl border border-[#1e293b] bg-[#0f172a] p-6 text-slate-100">
    <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold">龙虎榜溢价分析</h2>
        <p class="mt-2 text-sm text-slate-400">刷新龙虎榜与营业部数据后，按历史样本筛选当前高溢价股票。</p>
      </div>
      <div class="flex flex-wrap items-end gap-3">
        <label class="text-xs text-slate-400">开始日期<input v-model="startDate" type="number" class="mt-1 block rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm" /></label>
        <label class="text-xs text-slate-400">最新日期<input v-model="latestDate" type="number" class="mt-1 block rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm" /></label>
        <button :disabled="busy" class="rounded-lg bg-cyan-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50" @click="startJob">{{ busy ? '处理中...' : '采集并分析' }}</button>
      </div>
    </div>
    <p v-if="errorMessage" class="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{{ errorMessage }}</p>
    <div class="mb-5 grid gap-4 sm:grid-cols-3">
      <div class="rounded-xl border border-slate-800 p-4"><div class="text-xs text-slate-500">任务阶段</div><div class="mt-2 font-semibold">{{ stageLabel }}</div></div>
      <div class="rounded-xl border border-slate-800 p-4"><div class="text-xs text-slate-500">选中股票</div><div class="mt-2 text-2xl font-bold">{{ result?.selectedCount ?? '-' }}</div></div>
      <div class="rounded-xl border border-slate-800 p-4"><div class="text-xs text-slate-500">分析区间</div><div class="mt-2 font-semibold">{{ result ? `${result.startDate} - ${result.latestDate}` : '-' }}</div></div>
    </div>
    <div v-if="result?.selectedCodes?.length" class="overflow-x-auto rounded-xl border border-slate-800">
      <table class="w-full text-left text-sm"><thead class="bg-slate-900 text-slate-400"><tr><th class="px-4 py-3">股票代码</th></tr></thead><tbody><tr v-for="code in result.selectedCodes" :key="code" class="border-t border-slate-800"><td class="px-4 py-3 font-mono">{{ code }}</td></tr></tbody></table>
    </div>
    <p v-else-if="result" class="rounded-xl border border-slate-800 p-6 text-center text-slate-400">当前区间没有满足条件的股票。</p>
    <p class="mt-6 text-xs text-slate-500">数据来源：dragon_tiger、broker_listing_history、daily_quotes。分析结果为本次计算结果，不构成交易建议。</p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { createDragonTigerCollectionJob, getDragonTigerCollectionJob } from '../modules/dragon-tiger/api.js'

const startDate = ref(20260404)
const latestDate = ref(Number(new Date().toISOString().slice(0, 10).replaceAll('-', '')))
const status = ref(null)
const result = ref(null)
const errorMessage = ref('')
let timer = null
let stopped = false

const busy = computed(() => ['queued', 'running'].includes(status.value?.status))
const stageLabel = computed(() => ({ queued: '排队中', listings: '采集龙虎榜', broker_directory: '更新营业部目录', broker_history: '更新营业部历史', analysis: '计算溢价', complete: '已完成', failed: '失败' }[status.value?.stage] || '尚未运行'))

async function startJob() {
  clearInterval(timer)
  stopped = false
  errorMessage.value = ''
  result.value = null
  try {
    const created = await createDragonTigerCollectionJob(startDate.value, latestDate.value)
    await poll(created.jobId)
  } catch (error) {
    errorMessage.value = error.message
  }
}

async function poll(jobId) {
  const update = async () => {
    if (stopped) return
    try {
      status.value = await getDragonTigerCollectionJob(jobId)
      if (stopped) return
      if (status.value.status === 'succeeded') {
        result.value = { ...status.value, startDate: startDate.value, latestDate: latestDate.value }
        clearInterval(timer)
      } else if (status.value.status === 'failed') {
        errorMessage.value = status.value.error || '采集任务失败'
        clearInterval(timer)
      }
    } catch (error) {
      errorMessage.value = error.message
      clearInterval(timer)
    }
  }
  await update()
  if (!stopped && busy.value) timer = setInterval(update, 1000)
}

onBeforeUnmount(() => { stopped = true; clearInterval(timer) })
</script>
