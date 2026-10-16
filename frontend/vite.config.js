import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server proxies /api to the Python backend so the React code can use
// relative URLs. Electron in dev loads this server; in prod it loads dist/.
export default defineConfig({
  plugins: [react()],
  // Relative asset paths: the packaged app loads dist/index.html over
  // file://, where absolute "/assets/..." URLs resolve to the drive root
  // and silently 404 (blank window). './' keeps dev and packaged identical.
  base: './',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
