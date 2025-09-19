import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // allowedHosts: ['.atritrpg.chat'],
    proxy: {
      '/api': {
          changeOrigin: true,
          target: 'https://worker.firehomework.top/dice/api',
          // target: 'http://8.130.140.128:8082',
          // target: 'http://localhost:8088',

          rewrite: (path) => path.replace(/^\/api/, ''),

      },
      '/export': {
        target: 'http://localhost:8000', // FastAPI 后端地址
        changeOrigin: true,
      },
    }
  },
})
