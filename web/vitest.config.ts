import { defineConfig } from 'vitest/config';

// unit-тесты vitest не должны подхватывать Playwright-спеки из e2e/
export default defineConfig({
  test: {
    include: ['lib/**/*.test.ts', 'components/**/*.test.ts',
      'app/**/*.test.ts'],
    exclude: ['e2e/**', 'node_modules/**'],
  },
});
