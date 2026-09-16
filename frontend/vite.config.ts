import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  if (process.env.STORYBRIDGE_PUBLIC_BUILD === '1' &&
      (env.VITE_STORYBRIDGE_API_KEY || process.env.VITE_STORYBRIDGE_API_KEY)) {
    throw new Error('公开构建禁止 VITE_STORYBRIDGE_API_KEY。请移除前端共享密钥。')
  }
  return {
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  }
})
