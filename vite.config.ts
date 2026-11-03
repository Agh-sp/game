import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR کاملاً خاموش است: clientِ vite هرگز تلاش نمی‌کند به websocket متصل شود،
      // بنابراین در پروکسی‌های حافظه‌نويس (AI Studio / preview) ارور
      // «[vite] failed to connect to websocket (Error: WebSocket closed without opened.)»เกิดขึ้น نمی‌شود.
      hmr: false,
      // قطعِ config — server.ts در مود dev با middlewareMode و static serve انجام می‌شود.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
