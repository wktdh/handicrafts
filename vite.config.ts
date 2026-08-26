import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Public category pages use paths such as /categories/ceramics. Absolute
  // asset URLs keep the JS and CSS available when a visitor opens one directly.
  base: '/',
  build: {
    rollupOptions: {
      output: {
        // Keep stable third-party chunks separate from application code. This
        // improves long-term caching and prevents optional editor tooling from
        // inflating the primary application chunk.
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("react-colorful")) return "color-picker";
          if (id.includes("lucide-react")) return "icons";
          if (
            id.includes("node_modules/react/") ||
            id.includes("node_modules/react-dom/") ||
            id.includes("node_modules/scheduler/")
          )
            return "react-vendor";
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8787',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
