import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const appPort = Number(env.LOG_PAINTER_PORT || 5173)
  const devHost = env.LOG_PAINTER_HOST || '0.0.0.0'
  const allowedHosts = (env.LOG_PAINTER_ALLOWED_HOSTS || '.velinithra.space')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean)
  const apiTarget = env.LOG_PAINTER_API_TARGET || 'https://worker.firehomework.top/dice/api'
  const exportTarget = env.LOG_PAINTER_EXPORT_TARGET || 'http://localhost:8000'

  return {
    plugins: [vue()],
    server: {
      host: devHost,
      port: appPort,
      strictPort: true,
      allowedHosts,
      proxy: {
      '/api': {
          changeOrigin: true,
          target: apiTarget,
          // target: 'http://8.130.140.128:8082',
          // target: 'http://localhost:8088',

          rewrite: (path) => path.replace(/^\/api/, ''),

      },
      '/export': {
        target: exportTarget, // FastAPI 后端地址
        changeOrigin: true,
      },
      }
    },
    preview: {
      host: devHost,
      port: appPort,
      strictPort: true,
      allowedHosts
    }
  }
})
