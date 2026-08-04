<template>
  <div class="bg-zinc-900 border-b border-zinc-800 flex items-center px-2 overflow-x-auto h-11">
    <div v-for="tab in tabs" :key="tab.id"
         @click="switchTab(tab)"
         class="flex items-center gap-2 px-4 py-2 text-sm border-r border-zinc-800 cursor-pointer transition-all whitespace-nowrap"
         :class="{ 'bg-zinc-800 text-white': activeTab?.id === tab.id, 'text-zinc-400 hover:bg-zinc-800': activeTab?.id !== tab.id }">
      <span>{{ tab.title }}</span>
      <button @click.stop="closeTab(tab)" class="ml-1 w-4 h-4 flex items-center justify-center hover:bg-zinc-700 rounded text-xs">✕</button>
    </div>
  </div>
</template>

<script setup>
import { tabs, activeTab, switchTab, closeTab } from '../composables/useTabs'
</script>