<template>
  <div class="h-full overflow-auto p-6">
    <template v-if="tabs.length">
      <template v-for="tab in tabs" :key="tab.id">
        <div
            v-if="activeTab?.id === tab.id || tab.visited"
            v-show="activeTab?.id === tab.id"
            class="h-full">
          <component
              :is="tab.component"
              v-bind="tab.props"
              :active="activeTab?.id === tab.id" />
        </div>
      </template>
    </template>
    <div v-else class="flex items-center justify-center h-full text-zinc-400 text-lg">
      请从上方菜单打开页面
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { tabs, activeTab } from '../composables/useTabs'

watch(activeTab, (tab) => {
  if (tab) tab.visited = true
}, { immediate: true })
</script>
