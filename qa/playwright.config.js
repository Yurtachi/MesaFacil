// @ts-check
const { defineConfig } = require('@playwright/test');
const path = require('path');

const PORT = 8791;
const TMP = path.join(__dirname, '.tmp');
const WIDTHS = [320, 360, 390, 768, 1024, 1440];
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: path.join(TMP, 'results.json') }]],
  globalSetup: require.resolve('./tests/global-setup.js'),
  use: { baseURL: `http://127.0.0.1:${PORT}`, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo', trace: 'off' },
  webServer: {
    command: `${python} app.py`,
    cwd: path.join(__dirname, '..'),
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      HOST: '127.0.0.1', PORT: String(PORT), PAYMENT_MODE: 'demo', ADMIN_PASSWORD: 'qa-senha-123',
      SINUCA_DB: path.join(TMP, 'qa.sqlite3'), SINUCA_KEYS: path.join(TMP, 'keys.json'),
      RATE_ORDERS_PER_MIN: '5000', ESTABELECIMENTO: 'Sinuca do Zé', PYTHONIOENCODING: 'utf-8',
      ORDER_TTL_S: '86400', COMMAND_TTL_S: '86400', DEVICE_ONLINE_S: '600',
    },
  },
  projects: WIDTHS.map(w => ({
    name: `w${w}`,
    use: { viewport: { width: w, height: w >= 1024 ? 900 : w >= 768 ? 1024 : 800 }, deviceScaleFactor: 1, hasTouch: w < 1024 },
  })),
});
