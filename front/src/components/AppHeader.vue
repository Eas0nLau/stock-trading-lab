<template>
  <div class="bg-[#0a0f1e] border-b border-[#1e293b] px-8 py-4 flex items-center justify-between sticky top-0 z-50">
    <div class="flex items-center gap-8">
      <div class="flex items-center gap-3">
<!--        <div class="w-10 h-10 bg-[#6366f1]/10 rounded-2xl flex items-center justify-center">-->
<!--          <span class="text-[#6366f1] text-3xl">📈</span>-->
<!--        </div>-->
        <div>
          <div class="font-bold text-2xl tracking-tight text-white">我的</div>
<!--          <div class="text-[10px] text-[#64748b] -mt-1">同花顺远航版</div>-->
        </div>
      </div>

      <div class="flex items-center gap-1 text-sm pl-4 border-l border-[#1e293b]">
        <button @click="$emit('open-tab', '板块资金流向', 'FundFlow')"
                class="px-5 py-2.5 hover:bg-[#1e293b] rounded-2xl transition-all flex items-center gap-2 active:bg-[#334155]">
          <span>📊</span> 板块资金流向
        </button>
        <button @click="$emit('open-tab', '概念资金流向', 'ConceptFundFlow')"
                class="px-5 py-2.5 hover:bg-[#1e293b] rounded-2xl transition-all flex items-center gap-2 active:bg-[#334155]">
          <span>🧭</span> 概念资金流向
        </button>
        <button @click="$emit('open-tab', '策略选股监控', 'StrategyPickMonitor')"
                class="px-5 py-2.5 hover:bg-[#1e293b] rounded-2xl transition-all flex items-center gap-2 active:bg-[#334155]">
          <span>🎯</span> 策略选股监控
        </button>
        <button @click="$emit('open-tab', '指数周期', 'IndexCycle')"
                class="px-5 py-2.5 hover:bg-[#1e293b] rounded-2xl transition-all flex items-center gap-2 active:bg-[#334155]">
          <span>📉</span> 指数周期
        </button>
        <button @click="$emit('open-tab', '热门板块情绪', 'HotBoardEmotion')"
                class="px-5 py-2.5 hover:bg-[#1e293b] rounded-2xl transition-all flex items-center gap-2 active:bg-[#334155]">
          <span>🔥</span> 热门板块情绪
        </button>
        <button @click="$emit('open-tab', '龙虎榜溢价', 'DragonTigerPremium')"
                class="px-5 py-2.5 hover:bg-[#1e293b] rounded-2xl transition-all flex items-center gap-2 active:bg-[#334155]">
          <span>🏆</span> 龙虎榜溢价
        </button>
      </div>
    </div>
  </div>
</template>
