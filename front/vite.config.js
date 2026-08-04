import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8990,
    host: true,                    // 允许外部访问（重要）
    allowedHosts: [
      '.ngrok-free.app'            // 允许所有 ngrok-free.app 的子域名（推荐）
      // 或者只允许当前这个：
      // '82fe-221-216-205-14.ngrok-free.app'
    ],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8051',
        changeOrigin: true
      }
    }
  }
})
