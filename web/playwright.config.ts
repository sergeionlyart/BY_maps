import { defineConfig, devices } from '@playwright/test';

/**
 * E2E-тесты против production-сборки (статический экспорт out/, сервер
 * `serve` с clean URLs — как на Vercel). Порт параметризован (INF-13,
 * этап 0): изолированные рабочие копии INF-13/INF-15 запускают e2e на
 * своих портах (3113/3115), не занимая порт основной копии (3100).
 * Запуск: npm run build && npm run e2e   (E2E_PORT=3113 npm run e2e)
 */
const PORT = process.env.E2E_PORT ?? '3100';

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  retries: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npx serve out -l ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
    {
      name: 'reduced-motion',
      use: { ...devices['Desktop Chrome'], contextOptions: { reducedMotion: 'reduce' } },
    },
  ],
});
