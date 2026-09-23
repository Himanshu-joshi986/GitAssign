import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        // Local npm run dev → localhost. Docker Compose frontend uses nginx, not Vite.
        target: process.env.VITE_API_PROXY || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    // Local/monorepo: emit into backend/static so FastAPI can serve the SPA.
    // Docker build overrides with: npx vite build --outDir dist
    outDir: '../backend/static',
    emptyOutDir: true,
  }
})
