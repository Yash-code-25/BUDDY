import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // `npm run dev` only: send API calls to Django on port 8000
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})